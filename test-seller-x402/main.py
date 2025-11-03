#!/usr/bin/env python3
"""
x402-Compliant Test Seller (EVM) - Official Protocol Implementation

Sells "Hello World" messages for $0.01 USDC on Base mainnet.
Implements the official x402 protocol specification exactly.

Key compliance features:
- Returns proper x402PaymentRequiredResponse on GET (402)
- Accepts X-PAYMENT header (base64 encoded PaymentPayload)
- Calls facilitator /verify then /settle
- Returns X-PAYMENT-RESPONSE header on success
- Uses camelCase field naming per spec
"""
import os
import json
import base64
import logging
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from pydantic import BaseModel, Field, ConfigDict
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# === Pydantic Models (matching official x402 types) ===

class PaymentRequirements(BaseModel):
    """Official x402 PaymentRequirements structure"""
    scheme: str
    network: str
    max_amount_required: str = Field(alias="maxAmountRequired")
    resource: str
    description: str
    mime_type: str = Field(alias="mimeType")
    output_schema: Optional[dict] = Field(None, alias="outputSchema")
    pay_to: str = Field(alias="payTo")
    max_timeout_seconds: int = Field(alias="maxTimeoutSeconds")
    asset: str
    extra: Optional[dict] = None

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda x: ''.join(word.capitalize() if i > 0 else word for i, word in enumerate(x.split('_')))
    )


class X402PaymentRequiredResponse(BaseModel):
    """Official 402 response structure"""
    x402_version: int = Field(alias="x402Version")
    accepts: list[PaymentRequirements]
    error: str

    model_config = ConfigDict(populate_by_name=True)


class EIP3009Authorization(BaseModel):
    """EIP-3009 transferWithAuthorization parameters"""
    from_: str = Field(alias="from")
    to: str
    value: str
    valid_after: str = Field(alias="validAfter")
    valid_before: str = Field(alias="validBefore")
    nonce: str

    model_config = ConfigDict(populate_by_name=True)


class ExactPaymentPayload(BaseModel):
    """EVM exact scheme payload"""
    signature: str
    authorization: EIP3009Authorization


class PaymentPayload(BaseModel):
    """Official x402 PaymentPayload structure"""
    x402_version: int = Field(alias="x402Version")
    scheme: str
    network: str
    payload: ExactPaymentPayload

    model_config = ConfigDict(populate_by_name=True)


class VerifyResponse(BaseModel):
    """Facilitator /verify response"""
    is_valid: bool = Field(alias="isValid")
    invalid_reason: Optional[str] = Field(None, alias="invalidReason")
    payer: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class SettleResponse(BaseModel):
    """Facilitator /settle response"""
    success: bool
    error_reason: Optional[str] = Field(None, alias="errorReason")
    transaction: Optional[str] = None
    network: Optional[str] = None
    payer: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


# === Configuration ===

def load_config():
    """Load configuration from AWS Secrets Manager or environment variables"""
    try:
        import boto3
        secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
        response = secrets_client.get_secret_value(SecretId='karmacadabra-test-seller')
        config = json.loads(response['SecretString'])
        logger.info("Loaded config from AWS Secrets Manager")
        return {
            'seller_address': config.get('address'),
            'private_key': config.get('private_key'),
        }
    except Exception as e:
        logger.warning(f"Could not load from AWS: {e}. Using environment variables")
        return {
            'seller_address': os.getenv("SELLER_ADDRESS"),
            'private_key': os.getenv("PRIVATE_KEY"),
        }


config = load_config()
SELLER_ADDRESS = config['seller_address']
USDC_BASE_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"  # USDC on Base mainnet
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://facilitator.ultravioletadao.xyz")
PRICE_USDC = "10000"  # $0.01 USDC (6 decimals)
PORT = int(os.getenv("PORT", "8080"))

# Stats
stats = {
    "total_requests": 0,
    "paid_requests": 0,
    "unpaid_requests": 0,
    "total_revenue": 0,
}


# === FastAPI Application ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan"""
    logger.info("=" * 60)
    logger.info("x402-Compliant Test Seller (EVM) Starting")
    logger.info("=" * 60)
    logger.info(f"Seller Address: {SELLER_ADDRESS}")
    logger.info(f"Price: ${float(PRICE_USDC)/1000000:.2f} USDC")
    logger.info(f"Network: Base mainnet")
    logger.info(f"Asset: {USDC_BASE_ADDRESS}")
    logger.info(f"Facilitator: {FACILITATOR_URL}")
    logger.info("=" * 60)
    yield
    logger.info(f"Shutting down - Paid: {stats['paid_requests']} - Revenue: ${stats['total_revenue']/1000000:.2f}")


app = FastAPI(
    title="x402-Compliant Test Seller (EVM)",
    description="Official x402 protocol implementation for EVM chains",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Helper Functions ===

def decode_x_payment_header(header_value: str) -> PaymentPayload:
    """Decode base64-encoded X-PAYMENT header to PaymentPayload"""
    try:
        decoded_json = base64.b64decode(header_value).decode('utf-8')
        payment_dict = json.loads(decoded_json)
        return PaymentPayload(**payment_dict)
    except Exception as e:
        raise ValueError(f"Invalid X-PAYMENT header: {e}")


def encode_x_payment_response(settle_response: SettleResponse) -> str:
    """Encode SettleResponse to base64 for X-PAYMENT-RESPONSE header"""
    response_json = settle_response.model_dump_json(by_alias=True)
    return base64.b64encode(response_json.encode('utf-8')).decode('utf-8')


async def verify_payment(payment: PaymentPayload, requirements: PaymentRequirements) -> VerifyResponse:
    """Call facilitator /verify endpoint"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{FACILITATOR_URL}/verify",
            json={
                "x402Version": 1,
                "paymentPayload": payment.model_dump(by_alias=True),
                "paymentRequirements": requirements.model_dump(by_alias=True, exclude_none=True),
            },
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Facilitator verify failed: {response.text}")

        return VerifyResponse(**response.json())


async def settle_payment(payment: PaymentPayload, requirements: PaymentRequirements) -> SettleResponse:
    """Call facilitator /settle endpoint"""
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            f"{FACILITATOR_URL}/settle",
            json={
                "x402Version": 1,
                "paymentPayload": payment.model_dump(by_alias=True),
                "paymentRequirements": requirements.model_dump(by_alias=True, exclude_none=True),
            },
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Facilitator settle failed: {response.text}")

        return SettleResponse(**response.json())


# === Endpoints ===

@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "service": "test-seller-x402",
        "network": "base",
        "price_usdc": PRICE_USDC,
        "seller_address": SELLER_ADDRESS,
        "facilitator": FACILITATOR_URL,
        "protocol": "x402-v1-compliant",
    }


@app.get("/stats")
async def get_stats():
    """Service statistics"""
    return {
        "total_requests": stats["total_requests"],
        "paid_requests": stats["paid_requests"],
        "unpaid_requests": stats["unpaid_requests"],
        "total_revenue_usdc": f"${stats['total_revenue']/1000000:.2f}",
        "price_per_request": f"${float(PRICE_USDC)/1000000:.2f}",
    }


@app.get("/hello")
async def get_hello_402(request: Request):
    """
    GET /hello - Returns 402 Payment Required

    Per official x402 spec, returns x402PaymentRequiredResponse with PaymentRequirements
    """
    stats["total_requests"] += 1
    stats["unpaid_requests"] += 1

    logger.info(f"[402] Payment required from {request.client.host}")

    # Build PaymentRequirements per official spec
    requirements = PaymentRequirements(
        scheme="exact",
        network="base",
        max_amount_required=PRICE_USDC,
        resource=str(request.url),
        description="Hello World message",
        mime_type="application/json",
        pay_to=SELLER_ADDRESS,
        max_timeout_seconds=60,
        asset=USDC_BASE_ADDRESS,
        extra={
            "name": "USD Coin",  # EIP712Domain for EIP-3009
            "version": "2"
        }
    )

    response_body = X402PaymentRequiredResponse(
        x402_version=1,
        accepts=[requirements],
        error="Payment required to access this resource"
    )

    return JSONResponse(
        status_code=402,
        content=response_body.model_dump(by_alias=True)
    )


@app.post("/hello")
async def post_hello_paid(request: Request):
    """
    POST /hello - Process paid request

    Per official x402 spec:
    1. Extract X-PAYMENT header (base64 encoded PaymentPayload)
    2. Call facilitator /verify
    3. If valid, process resource
    4. Call facilitator /settle
    5. Return resource with X-PAYMENT-RESPONSE header
    """
    stats["total_requests"] += 1

    # Step 1: Extract and decode X-PAYMENT header
    x_payment_header = request.headers.get("X-PAYMENT")
    if not x_payment_header:
        stats["unpaid_requests"] += 1
        logger.warning(f"[REJECTED] Missing X-PAYMENT header from {request.client.host}")
        raise HTTPException(status_code=402, detail="Missing X-PAYMENT header")

    try:
        payment = decode_x_payment_header(x_payment_header)
    except ValueError as e:
        stats["unpaid_requests"] += 1
        logger.error(f"[REJECTED] Invalid X-PAYMENT header: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    # Build expected requirements
    requirements = PaymentRequirements(
        scheme="exact",
        network="base",
        max_amount_required=PRICE_USDC,
        resource=str(request.url).replace("http://", "https://"),  # Normalize
        description="Hello World message",
        mime_type="application/json",
        pay_to=SELLER_ADDRESS,
        max_timeout_seconds=60,
        asset=USDC_BASE_ADDRESS,
        extra={"name": "USD Coin", "version": "2"}
    )

    # Extract payer
    payer = payment.payload.authorization.from_
    logger.info(f"[VERIFY] Verifying payment from {payer[:10]}...")

    # Step 2: Verify payment
    try:
        verify_response = await verify_payment(payment, requirements)

        if not verify_response.is_valid:
            stats["unpaid_requests"] += 1
            reason = verify_response.invalid_reason or "Unknown"
            logger.error(f"[INVALID] Payment verification failed: {reason}")
            raise HTTPException(status_code=402, detail=f"Payment invalid: {reason}")

        logger.info(f"[VALID] Payment verified from {payer[:10]}...")

    except HTTPException:
        raise
    except Exception as e:
        stats["unpaid_requests"] += 1
        logger.error(f"[ERROR] Verify failed: {e}")
        raise HTTPException(status_code=502, detail=f"Verification error: {e}")

    # Step 3: Process resource (generate response)
    resource_response = {
        "message": "Hello World! 🌍",
        "status": "paid",
        "price": f"${float(PRICE_USDC)/1000000:.2f} USDC",
        "payer": payer,
        "seller": SELLER_ADDRESS,
        "network": "base",
    }

    # Step 4: Settle payment (only after successful resource generation)
    try:
        settle_response = await settle_payment(payment, requirements)

        if not settle_response.success:
            error_reason = settle_response.error_reason or "Unknown"
            logger.error(f"[SETTLE FAILED] {error_reason}")
            raise HTTPException(status_code=502, detail=f"Settlement failed: {error_reason}")

        tx_hash = settle_response.transaction
        logger.info(f"[SUCCESS] Payment settled - TX: {tx_hash} - Payer: {payer[:10]}...")

        # Update stats
        stats["paid_requests"] += 1
        stats["total_revenue"] += int(PRICE_USDC)

        # Add transaction to response
        resource_response["tx_hash"] = tx_hash
        resource_response["transaction_hash"] = tx_hash

        # Step 5: Return with X-PAYMENT-RESPONSE header
        x_payment_response = encode_x_payment_response(settle_response)

        return JSONResponse(
            status_code=200,
            content=resource_response,
            headers={"X-PAYMENT-RESPONSE": x_payment_response}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Settle failed: {e}")
        raise HTTPException(status_code=502, detail=f"Settlement error: {e}")


@app.get("/")
async def root():
    """Service information"""
    return {
        "service": "x402-Compliant Test Seller (EVM)",
        "version": "1.0.0",
        "protocol": "x402-v1",
        "description": "Official x402 protocol implementation for EVM chains",
        "network": "base",
        "price": f"${float(PRICE_USDC)/1000000:.2f} USDC",
        "seller_address": SELLER_ADDRESS,
        "compliance": {
            "x402_payment_required_response": True,
            "x_payment_header": True,
            "verify_then_settle_flow": True,
            "x_payment_response_header": True,
            "camelCase_fields": True,
        },
        "endpoints": {
            "GET /hello": "Returns 402 with PaymentRequirements",
            "POST /hello": "Processes paid request with X-PAYMENT header",
            "GET /health": "Health check",
            "GET /stats": "Service statistics",
        },
        "stats": stats,
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        log_level="info",
        access_log=True,
    )
