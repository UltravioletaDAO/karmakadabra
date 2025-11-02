#!/usr/bin/env python3
"""
Test Seller for Solana - x402 Payment System
Accepts SPL Token payments via x402-rs facilitator on Solana mainnet
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import requests
import os
import uvicorn
from datetime import datetime

app = FastAPI(title="Test Seller Solana", version="1.0.0")

# Configuration
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://facilitator.ultravioletadao.xyz")
SELLER_PUBKEY = os.getenv("SELLER_PUBKEY")  # Solana public key of seller
PRICE_USDC = "10000"  # 0.01 USDC (6 decimals)
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC on Solana mainnet

# Payment request model
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
        "seller_pubkey": SELLER_PUBKEY,
        "facilitator": FACILITATOR_URL,
        "network": "solana",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/")
async def root():
    """Service information"""
    return {
        "service": "Test Seller Solana",
        "version": "1.0.0",
        "description": "Sells 'Hello World' messages for 0.01 USDC on Solana mainnet",
        "price": f"{int(PRICE_USDC) / 1_000_000} USDC",
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

    Requires x402 payment via facilitator
    """
    try:
        # Validate seller configuration
        if not SELLER_PUBKEY:
            raise HTTPException(
                status_code=500,
                detail="Seller not configured (missing SELLER_PUBKEY)"
            )

        # Verify payment structure
        if payment.x402Version != 1:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported x402Version: {payment.x402Version}"
            )

        payload = payment.paymentPayload
        requirements = payment.paymentRequirements

        # Validate network
        if payload.get("network") != "solana":
            raise HTTPException(
                status_code=400,
                detail=f"Invalid network: {payload.get('network')} (expected solana)"
            )

        # Validate scheme
        if payload.get("scheme") != "exact":
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported scheme: {payload.get('scheme')}"
            )

        # Validate transaction payload exists
        solana_payload = payload.get("payload", {})
        if "transaction" not in solana_payload:
            raise HTTPException(
                status_code=400,
                detail="Missing 'transaction' field in payment payload"
            )

        # Validate payment requirements
        if requirements.get("maxAmountRequired") != PRICE_USDC:
            raise HTTPException(
                status_code=402,
                detail=f"Incorrect amount: {requirements.get('maxAmountRequired')} (expected {PRICE_USDC})"
            )

        if requirements.get("payTo") != SELLER_PUBKEY:
            raise HTTPException(
                status_code=402,
                detail=f"Incorrect recipient: {requirements.get('payTo')} (expected {SELLER_PUBKEY})"
            )

        if requirements.get("asset") != USDC_MINT:
            raise HTTPException(
                status_code=402,
                detail=f"Incorrect asset: {requirements.get('asset')} (expected {USDC_MINT})"
            )

        # Forward payment to facilitator for settlement
        print(f"[{datetime.utcnow().isoformat()}] Forwarding payment to facilitator: {FACILITATOR_URL}/settle")

        facilitator_response = requests.post(
            f"{FACILITATOR_URL}/settle",
            json=payment.dict(),
            headers={'Content-Type': 'application/json'},
            timeout=90  # 90s timeout for Solana confirmation
        )

        if facilitator_response.status_code != 200:
            error_detail = facilitator_response.text
            print(f"[{datetime.utcnow().isoformat()}] Facilitator error: {error_detail}")
            raise HTTPException(
                status_code=402,
                detail=f"Payment verification failed: {error_detail}"
            )

        facilitator_data = facilitator_response.json()

        # Check if payment was successful
        if not facilitator_data.get("success"):
            error_reason = facilitator_data.get("error_reason", "Unknown error")
            print(f"[{datetime.utcnow().isoformat()}] Payment failed: {error_reason}")
            raise HTTPException(
                status_code=402,
                detail=f"Payment failed: {error_reason}"
            )

        tx_hash = facilitator_data.get("transaction")
        payer = facilitator_data.get("payer")

        print(f"[{datetime.utcnow().isoformat()}] Payment successful!")
        print(f"  Payer: {payer}")
        print(f"  Transaction: {tx_hash}")

        # Return the purchased content
        return {
            "message": "Hello World! 🌎",
            "price": f"{int(PRICE_USDC) / 1_000_000} USDC",
            "payer": payer,
            "tx_hash": tx_hash,
            "network": "solana",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[{datetime.utcnow().isoformat()}] Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom exception handler for better error responses"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


if __name__ == "__main__":
    # Check configuration
    if not SELLER_PUBKEY:
        print("WARNING: SELLER_PUBKEY not set! Service will not process payments.")
        print("Set SELLER_PUBKEY environment variable to your Solana public key")

    print("=" * 60)
    print("Test Seller Solana - x402 Payment System")
    print("=" * 60)
    print(f"Facilitator: {FACILITATOR_URL}")
    print(f"Seller Pubkey: {SELLER_PUBKEY or 'NOT SET'}")
    print(f"Price: {int(PRICE_USDC) / 1_000_000} USDC")
    print(f"Network: Solana mainnet")
    print(f"Asset: {USDC_MINT}")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8080)
