#!/usr/bin/env python3
"""
Test Seller for Solana - SPEC-COMPLIANT Implementation
Based on facilitator golden source analysis (SOLANA_SPEC.md)

Correctly handles facilitator response types:
- Validation errors: {"isValid": false, "invalidReason": "..."}
- Settlement errors: {"success": false, "error_reason": "..."}
- Settlement success: {"success": true, "payer": "...", "transaction": "..."}
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import requests
import os
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_seller_config():
    """Load seller configuration from AWS Secrets Manager"""
    try:
        import boto3
        secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
        response = secrets_client.get_secret_value(SecretId='karmacadabra-test-seller-solana')
        config = json.loads(response['SecretString'])
        seller_pubkey = config.get('pubkey')
        logger.info(f"Loaded seller config from AWS: {seller_pubkey}")
        return {'seller_pubkey': seller_pubkey}
    except Exception as e:
        logger.warning(f"Could not load from AWS: {e}")
        return {'seller_pubkey': os.getenv("SELLER_PUBKEY")}


app = FastAPI(title="Test Seller Solana (Spec-Compliant)", version="4.0.0")

# Configuration
config = load_seller_config()
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://facilitator.ultravioletadao.xyz")
SELLER_PUBKEY = config['seller_pubkey']
PRICE_USDC = "10000"  # 0.01 USDC (6 decimals) - STRING per spec
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # Solana mainnet


class X402PaymentSolana(BaseModel):
    x402Version: int
    paymentPayload: Dict[str, Any]
    paymentRequirements: Dict[str, Any]


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "test-seller-solana",
        "version": "4.0.0-spec-compliant",
        "seller_pubkey": SELLER_PUBKEY,
        "facilitator": FACILITATOR_URL,
        "network": "solana",
        "spec_version": "2025-11-02",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/")
async def root():
    """Service information"""
    return {
        "service": "Test Seller Solana (Spec-Compliant)",
        "version": "4.0.0",
        "description": "Sells 'Hello World' messages for 0.01 USDC on Solana mainnet",
        "price": "0.01 USDC",
        "spec": "Based on facilitator golden source analysis",
        "endpoints": {
            "health": "/health",
            "purchase": "/hello (POST with x402 payment)",
        },
        "payment": {
            "protocol": "x402",
            "network": "solana",
            "asset": USDC_MINT,
            "facilitator": FACILITATOR_URL,
        }
    }


@app.post("/hello")
async def hello_world(payment: X402PaymentSolana):
    """
    Sell a Hello World message for 0.01 USDC on Solana

    Per SOLANA_SPEC.md, facilitator returns:
    1. Validation failure: {"isValid": false, "invalidReason": "..."}
    2. Settlement success: {"success": true, "payer": "...", "transaction": "..."}
    3. Settlement failure: {"success": false, "error_reason": "..."}
    """
    try:
        timestamp = datetime.utcnow().isoformat()
        logger.info(f"[{timestamp}] Received payment request")

        # Validate seller configuration
        if not SELLER_PUBKEY:
            logger.error("Seller not configured (missing SELLER_PUBKEY)")
            raise HTTPException(500, "Seller not configured")

        # Validate x402 version
        if payment.x402Version != 1:
            raise HTTPException(400, f"Unsupported x402Version: {payment.x402Version}")

        payload = payment.paymentPayload
        requirements = payment.paymentRequirements

        # Validate network
        if payload.get("network") != "solana":
            raise HTTPException(400, f"Invalid network: {payload.get('network')} (expected solana)")

        # Validate scheme
        if payload.get("scheme") != "exact":
            raise HTTPException(400, f"Unsupported scheme: {payload.get('scheme')}")

        # Validate transaction payload exists
        solana_payload = payload.get("payload", {})
        if "transaction" not in solana_payload:
            raise HTTPException(400, "Missing 'transaction' field in payment payload")

        # Validate payment requirements
        if requirements.get("maxAmountRequired") != PRICE_USDC:
            raise HTTPException(
                402,
                f"Incorrect amount: {requirements.get('maxAmountRequired')} (expected {PRICE_USDC})"
            )

        if requirements.get("payTo") != SELLER_PUBKEY:
            raise HTTPException(
                402,
                f"Incorrect recipient: {requirements.get('payTo')} (expected {SELLER_PUBKEY})"
            )

        if requirements.get("asset") != USDC_MINT:
            raise HTTPException(
                402,
                f"Incorrect asset: {requirements.get('asset')} (expected {USDC_MINT})"
            )

        # Forward payment to facilitator for settlement
        logger.info(f"[{timestamp}] Forwarding to facilitator: {FACILITATOR_URL}/settle")

        try:
            facilitator_response = requests.post(
                f"{FACILITATOR_URL}/settle",
                json=payment.dict(),
                headers={'Content-Type': 'application/json'},
                timeout=90  # Per spec: Solana confirmation can take 60-90s
            )

            timestamp = datetime.utcnow().isoformat()
            logger.info(f"[{timestamp}] Facilitator status: {facilitator_response.status_code}")

            if facilitator_response.status_code != 200:
                error_detail = facilitator_response.text
                logger.error(f"[{timestamp}] Facilitator non-200: {error_detail}")
                raise HTTPException(402, f"Facilitator error: {error_detail}")

            facilitator_data = facilitator_response.json()
            logger.info(f"[{timestamp}] Facilitator response: {facilitator_data}")

            # Per SPEC: Check if it's a validation response (isValid field)
            if "isValid" in facilitator_data:
                if not facilitator_data["isValid"]:
                    invalid_reason = facilitator_data.get("invalidReason", "Unknown validation error")
                    logger.error(f"[{timestamp}] Validation failed: {invalid_reason}")
                    raise HTTPException(402, f"Payment validation failed: {invalid_reason}")

            # Per SPEC: Check settlement success (success field)
            if not facilitator_data.get("success"):
                error_reason = facilitator_data.get("error_reason", "Unknown settlement error")
                logger.error(f"[{timestamp}] Settlement failed: {error_reason}")
                raise HTTPException(402, f"Payment settlement failed: {error_reason}")

        except requests.exceptions.Timeout:
            logger.error(f"[{timestamp}] Facilitator timeout after 90s")
            raise HTTPException(402, "Payment timeout - facilitator did not respond in time")
        except requests.exceptions.RequestException as e:
            logger.error(f"[{timestamp}] Request exception: {str(e)}")
            raise HTTPException(402, f"Failed to contact facilitator: {str(e)}")

        # Success! Extract transaction details
        tx_hash = facilitator_data.get("transaction")
        payer = facilitator_data.get("payer")  # Per spec: This is the buyer (authority), not fee payer

        logger.info(f"[{timestamp}] Payment successful!")
        logger.info(f"  Payer (authority): {payer}")
        logger.info(f"  Transaction: {tx_hash}")

        # Return the purchased content
        return {
            "message": "Hello World! 🌎",
            "price": "0.01 USDC",
            "payer": payer,
            "tx_hash": tx_hash,
            "network": "solana",
            "explorer": f"https://solscan.io/tx/{tx_hash}" if tx_hash else None,
            "timestamp": datetime.utcnow().isoformat(),
            "spec_version": "4.0.0-compliant"
        }

    except HTTPException:
        raise
    except Exception as e:
        timestamp = datetime.utcnow().isoformat()
        logger.error(f"[{timestamp}] Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(500, f"Internal server error: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    # Check configuration
    if not SELLER_PUBKEY:
        logger.warning("SELLER_PUBKEY not set! Service will not process payments.")

    logger.info("=" * 60)
    logger.info("Test Seller Solana - Spec-Compliant v4.0.0")
    logger.info("=" * 60)
    logger.info(f"Facilitator: {FACILITATOR_URL}")
    logger.info(f"Seller Pubkey: {SELLER_PUBKEY or 'NOT SET'}")
    logger.info(f"Price: 0.01 USDC")
    logger.info(f"Network: Solana mainnet")
    logger.info(f"Asset: {USDC_MINT}")
    logger.info(f"Spec: SOLANA_SPEC.md (facilitator golden source)")
    logger.info("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8080)
