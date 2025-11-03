#!/usr/bin/env python3
"""
x402-Compliant Test Seller (SVM/Solana) - Official Protocol Implementation

Sells "Hello World" messages for 0.01 USDC on Solana mainnet.
Implements the official x402 protocol specification for Solana Virtual Machine.

Key compliance features:
- Returns proper x402PaymentRequiredResponse on GET (402)
- Includes extra.feePayer in PaymentRequirements (CRITICAL for Solana)
- Accepts X-PAYMENT header with partially-signed transaction
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
    """Official x402 PaymentRequirements structure for Solana"""
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
    extra: Optional[dict] = None  # MUST include {"feePayer": "facilitator-pubkey"} for Solana

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


class SolanaPaymentPayload(BaseModel):
    """Solana exact scheme payload - contains base64-encoded partially-signed transaction"""
    transaction: str  # Base64-encoded serialized VersionedTransaction


class PaymentPayload(BaseModel):
    """Official x402 PaymentPayload structure for Solana"""
    x402_version: int = Field(alias="x402Version")
    scheme: str
    network: str
    payload: SolanaPaymentPayload

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
    transaction: Optional[str] = None  # Base58-encoded transaction signature
    network: Optional[str] = None
    payer: Optional[str] = None  # Buyer's public key

    model_config = ConfigDict(populate_by_name=True)


# === Configuration ===

def load_config():
    """Load configuration from AWS Secrets Manager or environment variables"""
    try:
        import boto3
        secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
        response = secrets_client.get_secret_value(SecretId='karmacadabra-test-seller-solana')
        config = json.loads(response['SecretString'])
        logger.info("Loaded config from AWS Secrets Manager")
        return {
            'seller_pubkey': config.get('pubkey'),
        }
    except Exception as e:
        logger.warning(f"Could not load from AWS: {e}. Using environment variables")
        return {
            'seller_pubkey': os.getenv("SELLER_PUBKEY"),
        }


config = load_config()
SELLER_PUBKEY = config['seller_pubkey']
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC on Solana mainnet
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://facilitator.ultravioletadao.xyz")
FACILITATOR_PUBKEY = os.getenv("FACILITATOR_PUBKEY", "EwWqGE4ZFKLofuestmU4LDdK7XM1N4ALgdZccwYugwGd")
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
    logger.info("x402-Compliant Test Seller (Solana) Starting")
    logger.info("=" * 60)
    logger.info(f"Seller Pubkey: {SELLER_PUBKEY}")
    logger.info(f"Price: ${float(PRICE_USDC)/1000000:.2f} USDC")
    logger.info(f"Network: Solana mainnet")
    logger.info(f"Asset: {USDC_MINT}")
    logger.info(f"Facilitator: {FACILITATOR_URL}")
    logger.info(f"Facilitator Pubkey: {FACILITATOR_PUBKEY}")
    logger.info("=" * 60)
    yield
    logger.info(f"Shutting down - Paid: {stats['paid_requests']} - Revenue: ${stats['total_revenue']/1000000:.2f}")


app = FastAPI(
    title="x402-Compliant Test Seller (Solana)",
    description="Official x402 protocol implementation for Solana Virtual Machine",
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
        "service": "test-seller-solana-x402",
        "network": "solana",
        "price_usdc": PRICE_USDC,
        "seller_pubkey": SELLER_PUBKEY,
        "facilitator": FACILITATOR_URL,
        "facilitator_pubkey": FACILITATOR_PUBKEY,
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

    Per official x402 spec for Solana, returns x402PaymentRequiredResponse with:
    - Standard PaymentRequirements fields
    - extra.feePayer = facilitator's public key (CRITICAL for Solana)
    """
    stats["total_requests"] += 1
    stats["unpaid_requests"] += 1

    logger.info(f"[402] Payment required from {request.client.host}")

    # Build PaymentRequirements per official Solana spec
    # CRITICAL: extra.feePayer tells client who will sign as fee payer
    requirements = PaymentRequirements(
        scheme="exact",
        network="solana",
        max_amount_required=PRICE_USDC,
        resource=str(request.url),
        description="Hello World message",
        mime_type="application/json",
        pay_to=SELLER_PUBKEY,
        max_timeout_seconds=60,
        asset=USDC_MINT,
        extra={
            "feePayer": FACILITATOR_PUBKEY  # ⚠️ CRITICAL: Facilitator will sign as fee payer
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

    Per official x402 spec for Solana:
    1. Extract X-PAYMENT header (base64 encoded PaymentPayload)
    2. PaymentPayload contains partially-signed Solana transaction
    3. Call facilitator /verify
    4. If valid, process resource
    5. Call facilitator /settle (facilitator adds signature and submits to Solana)
    6. Return resource with X-PAYMENT-RESPONSE header
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

    # Validate payment is for Solana
    if payment.network != "solana":
        stats["unpaid_requests"] += 1
        raise HTTPException(status_code=400, detail=f"Invalid network: {payment.network} (expected solana)")

    if payment.scheme != "exact":
        stats["unpaid_requests"] += 1
        raise HTTPException(status_code=400, detail=f"Unsupported scheme: {payment.scheme}")

    # Build expected requirements
    requirements = PaymentRequirements(
        scheme="exact",
        network="solana",
        max_amount_required=PRICE_USDC,
        resource=str(request.url).replace("http://", "https://"),  # Normalize
        description="Hello World message",
        mime_type="application/json",
        pay_to=SELLER_PUBKEY,
        max_timeout_seconds=60,
        asset=USDC_MINT,
        extra={"feePayer": FACILITATOR_PUBKEY}
    )

    logger.info(f"[VERIFY] Verifying Solana payment...")

    # Step 2: Verify payment
    try:
        verify_response = await verify_payment(payment, requirements)

        if not verify_response.is_valid:
            stats["unpaid_requests"] += 1
            reason = verify_response.invalid_reason or "Unknown"
            logger.error(f"[INVALID] Payment verification failed: {reason}")
            raise HTTPException(status_code=402, detail=f"Payment invalid: {reason}")

        payer = verify_response.payer or "unknown"
        logger.info(f"[VALID] Payment verified from {payer[:10] if payer != 'unknown' else 'unknown'}...")

    except HTTPException:
        raise
    except Exception as e:
        stats["unpaid_requests"] += 1
        logger.error(f"[ERROR] Verify failed: {e}")
        raise HTTPException(status_code=502, detail=f"Verification error: {e}")

    # Step 3: Process resource (generate response)
    resource_response = {
        "message": "Hello World! 🌎",
        "status": "paid",
        "price": f"${float(PRICE_USDC)/1000000:.2f} USDC",
        "payer": payer,
        "seller": SELLER_PUBKEY,
        "network": "solana",
    }

    # Step 4: Settle payment (only after successful resource generation)
    try:
        settle_response = await settle_payment(payment, requirements)

        if not settle_response.success:
            error_reason = settle_response.error_reason or "Unknown"
            logger.error(f"[SETTLE FAILED] {error_reason}")
            raise HTTPException(status_code=502, detail=f"Settlement failed: {error_reason}")

        tx_signature = settle_response.transaction
        logger.info(f"[SUCCESS] Payment settled on Solana - TX: {tx_signature} - Payer: {payer[:10] if payer != 'unknown' else 'unknown'}...")

        # Update stats
        stats["paid_requests"] += 1
        stats["total_revenue"] += int(PRICE_USDC)

        # Add transaction to response
        resource_response["tx_hash"] = tx_signature
        resource_response["tx_signature"] = tx_signature
        resource_response["explorer_url"] = f"https://solscan.io/tx/{tx_signature}"

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
        "service": "x402-Compliant Test Seller (Solana)",
        "version": "1.0.0",
        "protocol": "x402-v1",
        "description": "Official x402 protocol implementation for Solana Virtual Machine",
        "network": "solana",
        "price": f"${float(PRICE_USDC)/1000000:.2f} USDC",
        "seller_pubkey": SELLER_PUBKEY,
        "facilitator_pubkey": FACILITATOR_PUBKEY,
        "compliance": {
            "x402_payment_required_response": True,
            "x_payment_header": True,
            "extra_fee_payer_field": True,  # ⚠️ CRITICAL for Solana
            "verify_then_settle_flow": True,
            "x_payment_response_header": True,
            "camelCase_fields": True,
        },
        "endpoints": {
            "GET /hello": "Returns 402 with PaymentRequirements (includes extra.feePayer)",
            "POST /hello": "Processes paid request with X-PAYMENT header",
            "GET /health": "Health check",
            "GET /stats": "Service statistics",
        },
        "stats": stats,
    }


if __name__ == "__main__":
    if not SELLER_PUBKEY:
        logger.warning("WARNING: SELLER_PUBKEY not set! Service will not process payments.")
        logger.warning("Set SELLER_PUBKEY environment variable to your Solana public key")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        log_level="info",
        access_log=True,
    )
