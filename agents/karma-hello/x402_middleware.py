"""
x402 Payment Middleware for FastAPI

Enforces payment before allowing access to endpoints.
Verifies EIP-3009 signatures and forwards to facilitator.
"""

import re
import time
import json
import requests
from typing import Optional, Callable, Dict, Any
from functools import wraps

from fastapi import Request, HTTPException, Response
from fastapi.responses import JSONResponse
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct

# Configuration
FACILITATOR_URL = "https://facilitator.ultravioletadao.xyz"
GLUE_TOKEN = "0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743"
GLUE_DECIMALS = 6
RPC_URL = "https://avalanche-fuji-c-chain-rpc.publicnode.com"


class X402PaymentRequired(HTTPException):
    """Exception raised when payment is required"""
    def __init__(self, price: float, currency: str = "GLUE"):
        super().__init__(
            status_code=402,
            detail={
                "error": "Payment Required",
                "price": price,
                "currency": currency,
                "payment_protocol": "x402-v1",
                "instructions": "Include Authorization header with x402-v1 payment"
            }
        )


def parse_x402_header(auth_header: str) -> Optional[Dict[str, Any]]:
    """
    Parse x402-v1 authorization header

    Format: x402-v1 token=<addr> from=<addr> to=<addr> value=<int>
            validAfter=<int> validBefore=<int> nonce=<hex> v=<int> r=<hex> s=<hex>
    """
    if not auth_header or not auth_header.startswith("x402-v1 "):
        return None

    try:
        params_str = auth_header[8:]  # Remove "x402-v1 " prefix

        # Parse key-value pairs
        params = {}
        pattern = r'(\w+)=([^\s]+)'
        matches = re.findall(pattern, params_str)

        for key, value in matches:
            params[key] = value

        # Validate required fields
        required = ['token', 'from', 'to', 'value', 'validAfter', 'validBefore', 'nonce', 'v', 'r', 's']
        if not all(k in params for k in required):
            return None

        # Convert types
        return {
            'token': params['token'],
            'from': params['from'],
            'to': params['to'],
            'value': int(params['value']),
            'validAfter': int(params['validAfter']),
            'validBefore': int(params['validBefore']),
            'nonce': params['nonce'],
            'v': int(params['v']),
            'r': params['r'],
            's': params['s']
        }
    except Exception as e:
        print(f"Error parsing x402 header: {e}")
        return None


def verify_payment_with_facilitator(payment: Dict[str, Any], seller_address: str) -> Optional[str]:
    """
    Forward payment to facilitator for execution via /settle endpoint

    Returns:
        Transaction hash if successful, None otherwise
    """
    try:
        # Call facilitator's /settle endpoint (executes payment on-chain)
        facilitator_endpoint = f"{FACILITATOR_URL}/settle"

        # Format the settle request according to x402-rs spec
        # The facilitator expects exact structure matching Rust types with camelCase

        # Combine r, s, v into 65-byte signature (r=32 bytes, s=32 bytes, v=1 byte)
        # Remove '0x' prefix from r and s if present
        r_bytes = bytes.fromhex(payment['r'][2:] if payment['r'].startswith('0x') else payment['r'])
        s_bytes = bytes.fromhex(payment['s'][2:] if payment['s'].startswith('0x') else payment['s'])
        v_byte = bytes([payment['v']])
        signature_hex = '0x' + (r_bytes + s_bytes + v_byte).hex()

        payload = {
            "x402Version": 1,
            "paymentPayload": {
                "x402Version": 1,
                "scheme": "exact",
                "network": "avalanche-fuji",
                "payload": {
                    "signature": signature_hex,
                    "authorization": {
                        "from": payment['from'],
                        "to": payment['to'],
                        "value": str(payment['value']),
                        "validAfter": str(payment['validAfter']),
                        "validBefore": str(payment['validBefore']),
                        "nonce": payment['nonce']
                    }
                }
            },
            "paymentRequirements": {
                "scheme": "exact",
                "network": "avalanche-fuji",
                "maxAmountRequired": str(payment['value']),
                "resource": "https://karma-hello.karmacadabra.ultravioletadao.xyz/get_chat_logs",
                "description": "Karma-Hello chat logs",
                "mimeType": "application/json",
                "payTo": seller_address,
                "maxTimeoutSeconds": 300,
                "asset": GLUE_TOKEN,
                "extra": {
                    "name": "Gasless Ultravioleta DAO Extended Token",
                    "version": "2"
                }
            }
        }

        print(f"Calling facilitator /settle with: from={payment['from'][:10]}... to={payment['to'][:10]}... value={payment['value']}")
        print(f"DEBUG: Payload being sent to facilitator:")
        print(json.dumps(payload, indent=2))

        response = requests.post(
            facilitator_endpoint,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            # Extract transaction hash from response
            tx_hash = data.get('transaction_hash') or data.get('tx_hash') or data.get('transactionHash')
            if tx_hash:
                print(f"✅ Payment settled: {tx_hash}")
                return tx_hash
            else:
                print(f"⚠️  Settlement succeeded but no tx hash: {data}")
                return "settled"  # Payment was accepted
        else:
            print(f"Facilitator error: {response.status_code} - {response.text[:500]}")
            return None

    except Exception as e:
        print(f"Error calling facilitator: {e}")
        import traceback
        traceback.print_exc()
        return None


def x402_required(price: float, currency: str = "GLUE"):
    """
    Decorator to require x402 payment before accessing endpoint

    Usage:
        @app.post("/get_data")
        @x402_required(price=0.01)
        async def get_data():
            return {"data": "protected content"}
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Check for Authorization header
            auth_header = request.headers.get("Authorization")

            if not auth_header:
                raise X402PaymentRequired(price, currency)

            # Parse x402 header
            payment = parse_x402_header(auth_header)

            if not payment:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid x402 authorization header format"
                )

            # Verify payment amount (convert to smallest units)
            expected_amount = int(price * (10 ** GLUE_DECIMALS))
            if payment['value'] < expected_amount:
                raise HTTPException(
                    status_code=402,
                    detail=f"Insufficient payment: {payment['value']} < {expected_amount}"
                )

            # Verify payment is not expired
            current_time = int(time.time())
            if current_time < payment['validAfter'] or current_time > payment['validBefore']:
                raise HTTPException(
                    status_code=402,
                    detail="Payment authorization expired"
                )

            # Forward to facilitator for execution
            print(f"Processing payment: {payment['from'][:10]}... -> {payment['to'][:10]}... ({payment['value']} smallest units)")

            seller_address = payment['to']
            tx_hash = verify_payment_with_facilitator(payment, seller_address)

            if not tx_hash:
                raise HTTPException(
                    status_code=402,
                    detail="Payment verification failed - transaction not executed"
                )

            print(f"✅ Payment successful: {tx_hash}")

            # Execute the original endpoint function
            result = await func(request, *args, **kwargs)

            # Add payment info to response if it's a JSONResponse
            if isinstance(result, JSONResponse):
                # Add transaction hash to response
                result.headers['X-Payment-Tx'] = tx_hash
                result.headers['X-Payment-Amount'] = str(payment['value'])
                result.headers['X-Payment-Token'] = currency

            return result

        return wrapper
    return decorator


def create_payment_required_response(price: float, currency: str = "GLUE") -> JSONResponse:
    """
    Create a 402 Payment Required response with payment instructions
    """
    return JSONResponse(
        status_code=402,
        content={
            "error": "Payment Required",
            "price": price,
            "currency": currency,
            "payment_protocol": "x402-v1",
            "instructions": {
                "step1": "Create EIP-3009 transferWithAuthorization signature",
                "step2": "Include Authorization header: x402-v1 token=... from=... to=... value=... ...",
                "step3": "Retry request with payment authorization"
            },
            "facilitator": FACILITATOR_URL,
            "token_contract": GLUE_TOKEN
        },
        headers={
            "X-Accept-Payment": "x402-v1",
            "X-Price": str(price),
            "X-Currency": currency
        }
    )
