"""
Test Seller Service - Hello World for $0.01 USDC

A simple x402-enabled service that sells "Hello World" messages for $0.01 USDC on Base.
Perfect for load testing the x402 facilitator with real payments.

Endpoint: test-seller.karmacadabra.ultravioletadao.xyz
Price: $0.01 USDC (10000 micro-units with 6 decimals)
Network: Base mainnet
"""

import os
import logging
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load configuration from AWS Secrets Manager or environment
def load_config():
    """Load configuration from AWS Secrets Manager or fall back to environment variables"""
    try:
        import boto3
        import json

        secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
        response = secrets_client.get_secret_value(SecretId='karmacadabra-test-seller')
        config = json.loads(response['SecretString'])

        return {
            'seller_address': config.get('address'),
            'private_key': config.get('private_key'),
        }
    except Exception as e:
        logger.warning(f"Could not load from AWS Secrets Manager: {e}")
        logger.info("Falling back to environment variables")
        return {
            'seller_address': os.getenv("SELLER_ADDRESS"),
            'private_key': os.getenv("PRIVATE_KEY"),
        }

# Load config
config = load_config()
SELLER_ADDRESS = config['seller_address']
USDC_BASE_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://facilitator.ultravioletadao.xyz")
PRICE_USDC = "10000"  # $0.01 USDC (6 decimals)
PORT = int(os.getenv("PORT", "8080"))

# Stats tracking
stats = {
    "total_requests": 0,
    "paid_requests": 0,
    "unpaid_requests": 0,
    "total_revenue": 0,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("🚀 Test Seller Service starting up")
    logger.info(f"   Seller Address: {SELLER_ADDRESS}")
    logger.info(f"   Price: ${float(PRICE_USDC)/1000000:.2f} USDC")
    logger.info(f"   Network: Base mainnet")
    logger.info(f"   Facilitator: {FACILITATOR_URL}")
    yield
    logger.info("👋 Test Seller Service shutting down")
    logger.info(f"   Total Requests: {stats['total_requests']}")
    logger.info(f"   Paid Requests: {stats['paid_requests']}")
    logger.info(f"   Total Revenue: ${stats['total_revenue']/1000000:.2f} USDC")


app = FastAPI(
    title="Test Seller - Hello World",
    description="x402-enabled test endpoint selling Hello World for $0.01 USDC",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "test-seller",
        "network": "base",
        "price_usdc": PRICE_USDC,
        "seller_address": SELLER_ADDRESS,
        "facilitator": FACILITATOR_URL,
    }


@app.get("/stats")
async def get_stats():
    """Get service statistics"""
    return {
        "total_requests": stats["total_requests"],
        "paid_requests": stats["paid_requests"],
        "unpaid_requests": stats["unpaid_requests"],
        "total_revenue_usdc": f"${stats['total_revenue']/1000000:.2f}",
        "price_per_request": f"${float(PRICE_USDC)/1000000:.2f}",
    }


@app.get("/hello")
async def get_hello_unpaid(request: Request):
    """
    GET /hello - Returns payment requirements (402 Payment Required)

    This endpoint requires payment via x402 protocol.
    """
    stats["total_requests"] += 1
    stats["unpaid_requests"] += 1

    logger.info(f"[402] Unpaid request from {request.client.host}")

    # Return 402 Payment Required with x402 payment requirements
    return JSONResponse(
        status_code=402,
        content={
            "error": "payment_required",
            "message": "Payment required to access this resource",
            "x402": {
                "version": 1,
                "accepts": [
                    {
                        "scheme": "exact",
                        "network": "base",
                        "maxAmountRequired": PRICE_USDC,
                        "resource": str(request.url),
                        "description": "Hello World message",
                        "mimeType": "application/json",
                        "payTo": SELLER_ADDRESS,
                        "maxTimeoutSeconds": 60,
                        "asset": USDC_BASE_ADDRESS,
                        "extra": {
                            "name": "USD Coin",
                            "version": "2"
                        }
                    }
                ]
            }
        }
    )


@app.post("/hello")
async def post_hello_paid(request: Request):
    """
    POST /hello - Process paid request with x402 payment

    Expects payment metadata in request body:
    {
        "x402Payment": {
            "paymentPayload": { ... },
            "paymentRequirements": { ... }
        }
    }
    """
    stats["total_requests"] += 1

    try:
        body = await request.json()
        payment = body.get("x402Payment")

        if not payment:
            stats["unpaid_requests"] += 1
            raise HTTPException(
                status_code=400,
                detail="Missing x402Payment in request body"
            )

        # Extract payer address from payment payload
        payer = payment.get("paymentPayload", {}).get("payload", {}).get("authorization", {}).get("from", "unknown")

        # Verify and settle payment with facilitator
        logger.info(f"[VERIFY] Calling facilitator to verify payment from {payer[:10]}...")
        logger.info(f"[DEBUG] Payment structure keys: {list(payment.keys())}")
        logger.info(f"[DEBUG] Payment x402Version: {payment.get('x402Version', 'MISSING')}")
        logger.info(f"[DEBUG] paymentPayload keys: {list(payment.get('paymentPayload', {}).keys())}")
        logger.info(f"[DEBUG] payload keys: {list(payment.get('paymentPayload', {}).get('payload', {}).keys())}")

        try:
            import json
            logger.info(f"[DEBUG] Full payment JSON: {json.dumps(payment, indent=2)[:500]}")

            response = requests.post(
                f"{FACILITATOR_URL}/settle",
                json=payment,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )

            if response.status_code != 200:
                stats["unpaid_requests"] += 1
                logger.error(f"[FAILED] Facilitator returned {response.status_code}: {response.text[:200]}")
                raise HTTPException(
                    status_code=402,
                    detail=f"Payment verification failed: {response.text[:100]}"
                )

            facilitator_data = response.json()
            is_valid = facilitator_data.get('isValid', False)

            if not is_valid:
                stats["unpaid_requests"] += 1
                invalid_reason = facilitator_data.get('invalidReason', 'Unknown')
                logger.error(f"[INVALID] Payment invalid: {invalid_reason}")
                raise HTTPException(
                    status_code=402,
                    detail=f"Payment invalid: {invalid_reason}"
                )

            # Extract transaction hash
            tx_hash = (facilitator_data.get('transaction_hash') or
                      facilitator_data.get('tx_hash') or
                      facilitator_data.get('transactionHash'))

            stats["paid_requests"] += 1
            stats["total_revenue"] += int(PRICE_USDC)

            logger.info(f"[SUCCESS] Payment settled - TX: {tx_hash} - Payer: {payer[:10]}...")

            return {
                "message": "Hello World! 🌍",
                "status": "paid",
                "price": f"${float(PRICE_USDC)/1000000:.2f} USDC",
                "payer": payer,
                "seller": SELLER_ADDRESS,
                "network": "base",
                "timestamp": request.headers.get("date"),
                "tx_hash": tx_hash,
                "transaction_hash": tx_hash,  # Also include both common field names
            }

        except requests.RequestException as e:
            stats["unpaid_requests"] += 1
            logger.error(f"[ERROR] Failed to contact facilitator: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to verify payment with facilitator: {str(e)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing paid request: {e}")
        stats["unpaid_requests"] += 1
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Test Seller - Hello World",
        "version": "1.0.0",
        "description": "x402-enabled test endpoint selling Hello World for $0.01 USDC",
        "network": "base",
        "price": f"${float(PRICE_USDC)/1000000:.2f} USDC",
        "seller_address": SELLER_ADDRESS,
        "endpoints": {
            "GET /hello": "Returns 402 Payment Required with payment details",
            "POST /hello": "Processes paid request (requires x402Payment in body)",
            "GET /health": "Health check",
            "GET /stats": "Service statistics",
        },
        "stats": {
            "total_requests": stats["total_requests"],
            "paid_requests": stats["paid_requests"],
            "total_revenue": f"${stats['total_revenue']/1000000:.2f} USDC",
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        log_level="info",
        access_log=True,
    )
