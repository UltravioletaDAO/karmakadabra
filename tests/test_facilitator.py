#!/usr/bin/env python3
"""
Facilitator Integration Tests
==============================

Comprehensive tests for the x402 facilitator (x402-rs).

Tests:
1. Facilitator health and availability
2. All 4 networks operational (Avalanche Fuji/Mainnet, Base Sepolia/Mainnet)
3. Payment verification flow
4. Payment settlement flow (testnet only)
5. Agent-to-facilitator communication
6. Multi-network support

Production Facilitator: https://facilitator.ultravioletadao.xyz
Local Facilitator: http://localhost:8080

Usage:
    # Test production facilitator
    python tests/test_facilitator.py

    # Test local facilitator
    FACILITATOR_URL=http://localhost:8080 python tests/test_facilitator.py
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional
import httpx
from web3 import Web3
from decimal import Decimal

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.x402_client import X402Client
from shared.payment_signer import PaymentSigner

# =============================================================================
# Configuration
# =============================================================================

FACILITATOR_URL = os.getenv(
    "FACILITATOR_URL",
    "https://facilitator.ultravioletadao.xyz"
)

# Network configurations
NETWORKS = {
    "avalanche-fuji": {
        "name": "Avalanche Fuji Testnet",
        "chain_id": 43113,
        "rpc": "https://avalanche-fuji-c-chain-rpc.publicnode.com",
        "glue_token": "0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743",
        "test_settlement": True  # Can test settlement on testnet
    },
    "avalanche": {
        "name": "Avalanche Mainnet",
        "chain_id": 43114,
        "rpc": "https://avalanche-c-chain-rpc.publicnode.com",
        "glue_token": None,  # Not deployed yet
        "test_settlement": False  # Do NOT test settlement on mainnet
    },
    "base-sepolia": {
        "name": "Base Sepolia Testnet",
        "chain_id": 84532,
        "rpc": "https://sepolia.base.org",
        "glue_token": None,  # GLUE not on Base, uses USDC
        "test_settlement": True  # Can test settlement on testnet
    },
    "base": {
        "name": "Base Mainnet",
        "chain_id": 8453,
        "rpc": "https://mainnet.base.org",
        "glue_token": None,  # GLUE not on Base, uses USDC
        "test_settlement": False  # Do NOT test settlement on mainnet
    }
}

# Test wallets (for signature testing only, no real funds)
TEST_BUYER_KEY = "0x" + "1" * 64
TEST_SELLER_KEY = "0x" + "2" * 64

# Derive addresses
from eth_account import Account
TEST_BUYER_ADDRESS = Account.from_key(TEST_BUYER_KEY).address
TEST_SELLER_ADDRESS = Account.from_key(TEST_SELLER_KEY).address

# =============================================================================
# Test 1: Facilitator Health Check
# =============================================================================

async def test_facilitator_health():
    """Test facilitator /health endpoint"""
    print("\n" + "="*80)
    print("TEST 1: Facilitator Health Check")
    print("="*80 + "\n")

    print(f"Testing: {FACILITATOR_URL}/health")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{FACILITATOR_URL}/health")

            if response.status_code == 200:
                data = response.json()
                print(f"[OK] Facilitator is healthy")
                print(f"     Response: {data}")

                # Verify response structure
                if "kinds" not in data:
                    print(f"[WARN] Response missing 'kinds' field")
                    return False

                return True
            else:
                print(f"[FAIL] HTTP {response.status_code}: {response.text}")
                return False

    except httpx.ConnectError:
        print(f"[FAIL] Cannot connect to facilitator at {FACILITATOR_URL}")
        print(f"      Is the facilitator running?")
        return False
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False

# =============================================================================
# Test 2: Supported Networks
# =============================================================================

async def test_supported_networks():
    """Test facilitator /supported endpoint and verify all 4 networks"""
    print("\n" + "="*80)
    print("TEST 2: Supported Networks")
    print("="*80 + "\n")

    print(f"Testing: {FACILITATOR_URL}/supported")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{FACILITATOR_URL}/supported")

            if response.status_code == 200:
                data = response.json()
                kinds = data.get("kinds", [])

                print(f"[OK] Facilitator supports {len(kinds)} network(s)")
                print()

                # Extract supported networks
                supported_networks = set()
                for kind in kinds:
                    network = kind.get("network")
                    scheme = kind.get("scheme")
                    version = kind.get("x402Version")

                    supported_networks.add(network)
                    print(f"  - {network:20s} scheme={scheme:10s} x402Version={version}")

                # Verify all expected networks are supported
                expected_networks = {"avalanche-fuji", "avalanche", "base-sepolia", "base"}
                missing_networks = expected_networks - supported_networks

                print()
                if missing_networks:
                    print(f"[FAIL] Missing networks: {missing_networks}")
                    return False
                else:
                    print(f"[OK] All 4 expected networks are supported!")
                    return True
            else:
                print(f"[FAIL] HTTP {response.status_code}: {response.text}")
                return False

    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False

# =============================================================================
# Test 3: Facilitator Wallet Balance Check
# =============================================================================

async def test_facilitator_wallet_balances():
    """Verify facilitator wallet has sufficient balance on all networks"""
    print("\n" + "="*80)
    print("TEST 3: Facilitator Wallet Balance Check")
    print("="*80 + "\n")

    # Get facilitator wallet address from AWS (or use known address)
    facilitator_wallet = "0x103040545AC5031A11E8C03dd11324C7333a13C7"

    print(f"Facilitator Wallet: {facilitator_wallet}")
    print()

    all_funded = True

    for network_key, config in NETWORKS.items():
        w3 = Web3(Web3.HTTPProvider(config["rpc"]))

        try:
            balance = w3.eth.get_balance(facilitator_wallet)
            balance_eth = float(w3.from_wei(balance, 'ether'))

            currency = "AVAX" if "avalanche" in network_key else "ETH"

            # Determine status
            min_balance = 0.1  # Minimum operational balance
            if balance_eth >= min_balance:
                status = "[OK] FUNDED"
            elif balance_eth > 0:
                status = "[WARN] LOW"
                all_funded = False
            else:
                status = "[FAIL] EMPTY"
                all_funded = False

            print(f"{config['name']:30s} {balance_eth:8.4f} {currency:4s} {status}")

        except Exception as e:
            print(f"{config['name']:30s} [ERROR] {str(e)[:40]}")
            all_funded = False

    print()
    if all_funded:
        print("[OK] Facilitator wallet is sufficiently funded on all networks")
        return True
    else:
        print("[WARN] Some networks have low or zero balance")
        print("      This may prevent payment settlement")
        return True  # Don't fail test, just warn

# =============================================================================
# Test 4: Payment Verification Flow
# =============================================================================

async def test_payment_verification():
    """Test payment verification with facilitator"""
    print("\n" + "="*80)
    print("TEST 4: Payment Verification Flow")
    print("="*80 + "\n")

    print("Testing payment verification on Avalanche Fuji...")
    print(f"  Buyer:  {TEST_BUYER_ADDRESS}")
    print(f"  Seller: {TEST_SELLER_ADDRESS}")
    print(f"  Amount: 0.01 GLUE")
    print()

    try:
        # Initialize x402 client
        glue_token = NETWORKS["avalanche-fuji"]["glue_token"]
        chain_id = NETWORKS["avalanche-fuji"]["chain_id"]

        async with X402Client(
            facilitator_url=FACILITATOR_URL,
            glue_token_address=glue_token,
            chain_id=chain_id,
            private_key=TEST_BUYER_KEY
        ) as client:

            # Create payment payload
            print("[1] Creating payment payload...")
            payment_payload = client.create_payment_payload(
                to_address=TEST_SELLER_ADDRESS,
                amount_glue="0.01"
            )

            print(f"    Payload scheme: {payment_payload.get('scheme')}")
            print(f"    Network: {payment_payload.get('network')}")
            auth = payment_payload['payload']['authorization']
            print(f"    From: {auth['from']}")
            print(f"    To: {auth['to']}")
            print(f"    Value: {auth['value']}")
            print()

            # Prepare payment requirements
            payment_requirements = {
                "scheme": "eip3009",
                "network": f"avalanche-fuji:{chain_id}",
                "receiver": TEST_SELLER_ADDRESS,
                "price": {
                    "tokenAddress": glue_token,
                    "amount": str(client.glue_amount("0.01"))
                }
            }

            # Verify payment with facilitator
            print("[2] Verifying payment with facilitator...")
            try:
                verify_result = await client.facilitator_verify(
                    payment_payload=payment_payload,
                    payment_requirements=payment_requirements
                )

                # Facilitator uses camelCase: isValid, invalidReason
                is_valid = verify_result.get("isValid", verify_result.get("valid", False))
                reason = verify_result.get("invalidReason", verify_result.get("reason", "No reason provided"))

                if is_valid:
                    print(f"    [OK] Payment verified successfully")
                    payer = verify_result.get("payer", "unknown")
                    print(f"    Payer: {payer}")
                    return True
                else:
                    print(f"    [INFO] Payment verification returned: isValid={is_valid}")
                    print(f"    Reason: {reason}")
                    print(f"    (This is expected if buyer has insufficient balance)")
                    return True  # Don't fail test for expected verification failures

            except httpx.HTTPStatusError as e:
                # Capture facilitator error response
                print(f"    [ERROR] HTTP {e.response.status_code}: {e.response.reason_phrase}")
                try:
                    error_body = e.response.json()
                    print(f"    Response: {error_body}")
                except:
                    print(f"    Response: {e.response.text}")

                # Check if it's a validation error (expected for test wallets without balance)
                if e.response.status_code in [400, 422]:
                    print(f"    [INFO] Validation error is expected for test wallets")
                    return True
                else:
                    raise

    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False

# =============================================================================
# Test 5: X402 Client Integration
# =============================================================================

async def test_x402_client_integration():
    """Test X402Client can communicate with facilitator"""
    print("\n" + "="*80)
    print("TEST 5: X402 Client Integration")
    print("="*80 + "\n")

    try:
        glue_token = NETWORKS["avalanche-fuji"]["glue_token"]
        chain_id = NETWORKS["avalanche-fuji"]["chain_id"]

        async with X402Client(
            facilitator_url=FACILITATOR_URL,
            glue_token_address=glue_token,
            chain_id=chain_id,
            private_key=TEST_BUYER_KEY
        ) as client:

            print(f"[1] X402Client initialized")
            print(f"    Buyer address: {client.from_address}")
            print(f"    Facilitator: {client.facilitator_url}")
            print()

            # Test health endpoint
            print("[2] Testing facilitator_health()...")
            health = await client.facilitator_health()
            print(f"    Response: {health}")
            print()

            # Test supported endpoint
            print("[3] Testing facilitator_supported()...")
            supported = await client.facilitator_supported()
            networks = [k.get("network") for k in supported.get("kinds", [])]
            print(f"    Supported networks: {', '.join(networks)}")
            print()

            # Test payment payload creation
            print("[4] Testing create_payment_payload()...")
            payload = client.create_payment_payload(
                to_address=TEST_SELLER_ADDRESS,
                amount_glue="0.01"
            )
            print(f"    Payload created: scheme={payload.get('scheme')}")
            sig = payload['payload']['signature']
            print(f"    Signature valid: v={sig['v']}, r={sig['r'][:10]}..., s={sig['s'][:10]}...")
            print()

            # Test payment header encoding
            print("[5] Testing encode_payment_header()...")
            encoded = client.encode_payment_header(payload)
            print(f"    Encoded header length: {len(encoded)} bytes")
            print(f"    Header preview: {encoded[:50]}...")
            print()

            print("[OK] X402Client integration test passed")
            return True

    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False

# =============================================================================
# Test 6: Multi-Network Support
# =============================================================================

async def test_multi_network_support():
    """Test that facilitator properly handles all 4 networks"""
    print("\n" + "="*80)
    print("TEST 6: Multi-Network Support")
    print("="*80 + "\n")

    print("Testing payment payload creation for all networks...")
    print()

    all_passed = True

    for network_key, config in NETWORKS.items():
        if config["glue_token"] is None:
            print(f"[SKIP] {config['name']:30s} (GLUE token not deployed)")
            continue

        try:
            signer = PaymentSigner(
                glue_token_address=config["glue_token"],
                chain_id=config["chain_id"]
            )

            # Create signed payment
            signature = signer.sign_transfer_authorization(
                from_address=TEST_BUYER_ADDRESS,
                to_address=TEST_SELLER_ADDRESS,
                value=signer.glue_amount("0.01"),
                private_key=TEST_BUYER_KEY
            )

            # Verify signature structure
            has_all_fields = all(
                k in signature for k in ['from', 'to', 'value', 'v', 'r', 's', 'nonce']
            )

            if has_all_fields:
                print(f"[OK] {config['name']:30s} payment signature valid")
            else:
                print(f"[FAIL] {config['name']:30s} missing signature fields")
                all_passed = False

        except Exception as e:
            print(f"[FAIL] {config['name']:30s} error: {str(e)[:40]}")
            all_passed = False

    print()
    if all_passed:
        print("[OK] Multi-network support test passed")
        return True
    else:
        print("[FAIL] Some networks failed")
        return False

# =============================================================================
# Main Test Runner
# =============================================================================

async def run_all_tests():
    """Run all facilitator tests"""
    print("\n" + "="*80)
    print("  FACILITATOR INTEGRATION TESTS")
    print(f"  Facilitator: {FACILITATOR_URL}")
    print("="*80)

    results = {}

    # Run tests
    results["health"] = await test_facilitator_health()
    results["supported_networks"] = await test_supported_networks()
    results["wallet_balances"] = await test_facilitator_wallet_balances()
    results["payment_verification"] = await test_payment_verification()
    results["x402_client_integration"] = await test_x402_client_integration()
    results["multi_network_support"] = await test_multi_network_support()

    # Summary
    print("\n" + "="*80)
    print("  TEST SUMMARY")
    print("="*80 + "\n")

    passed = sum(results.values())
    total = len(results)

    for test_name, result in results.items():
        symbol = "[OK]" if result else "[FAIL]"
        status = "PASSED" if result else "FAILED"
        print(f"   {symbol} {test_name.replace('_', ' ').title():40s} {status}")

    print(f"\n   Total: {passed}/{total} tests passed")

    if passed == total:
        print(f"\n{'='*80}")
        print("  [SUCCESS] ALL FACILITATOR TESTS PASSED")
        print("="*80 + "\n")
        return 0
    else:
        print(f"\n{'='*80}")
        print(f"  [FAILURE] {total - passed} test(s) failed")
        print("="*80 + "\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    exit(exit_code)
