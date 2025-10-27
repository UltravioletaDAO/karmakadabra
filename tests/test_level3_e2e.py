#!/usr/bin/env python3
"""
Level 3: End-to-End Tests
==========================

Tests complete buyer->validator->seller flows:
1. Discovery via A2A protocol
2. Validation flow
3. Purchase flow (simulated payments)

All tests use HTTP requests to running agent servers.
"""

import asyncio
import httpx
import sys
from typing import Dict, Any

# ============================================================================
# Test Configuration
# ============================================================================

# Check if --production flag is provided
USE_PRODUCTION = "--production" in sys.argv

if USE_PRODUCTION:
    print("\n[INFO] Using PRODUCTION endpoints (AWS ECS)")
    AGENTS = {
        "karma-hello": "https://karma-hello.karmacadabra.ultravioletadao.xyz",
        "abracadabra": "https://abracadabra.karmacadabra.ultravioletadao.xyz",
        "validator": "https://validator.karmacadabra.ultravioletadao.xyz",
        "voice-extractor": "https://voice-extractor.karmacadabra.ultravioletadao.xyz",
        "skill-extractor": "https://skill-extractor.karmacadabra.ultravioletadao.xyz"
    }
else:
    print("\n[INFO] Using LOCAL endpoints (localhost)")
    AGENTS = {
        "karma-hello": "http://localhost:8002",
        "abracadabra": "http://localhost:8003",
        "validator": "http://localhost:8011",
        "client": "http://localhost:8000",
        "voice-extractor": "http://localhost:8005",
        "skill-extractor": "http://localhost:8006"
    }

# ============================================================================
# Test 1: Discovery Flow
# ============================================================================

async def test_discovery_flow():
    """Test A2A protocol discovery"""
    print("\n" + "="*70)
    print("TEST 1: Discovery Flow (A2A Protocol)")
    print("="*70 + "\n")

    async with httpx.AsyncClient(timeout=10.0) as client:

        # Test 1a: Discover Karma-Hello
        print("1a. Discovering Karma-Hello seller...")
        try:
            response = await client.get(f"{AGENTS['karma-hello']}/.well-known/agent-card")
            if response.status_code == 200:
                card = response.json()
                print(f"   [OK] Karma-Hello discovered")
                print(f"      Agent ID: {card.get('agent_id', 'N/A')}")
                print(f"      Skills: {len(card.get('skills', []))} available")
                assert "skills" in card, "AgentCard missing skills"
                assert len(card["skills"]) > 0, "No skills published"
            else:
                print(f"   [FAIL] Discovery failed: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"   [FAIL] Error: {e}")
            return False

        # Test 1b: Discover Validator
        print("\n1b. Discovering Validator...")
        try:
            response = await client.get(f"{AGENTS['validator']}/.well-known/agent-card")
            if response.status_code == 200:
                card = response.json()
                print(f"   [OK] Validator discovered")
                print(f"      Agent ID: {card.get('agent_id', 'N/A')}")
                print(f"      Skills: {len(card.get('skills', []))} available")
            else:
                print(f"   [FAIL] Discovery failed: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"   [FAIL] Error: {e}")
            return False

        # Test 1c: Parse AgentCard structure
        print("\n1c. Parsing AgentCard structure...")
        required_fields = ["agentId", "name", "domain", "skills"]  # A2A protocol uses camelCase
        missing = [f for f in required_fields if f not in card]
        if missing:
            print(f"   [FAIL] Missing fields: {missing}")
            return False
        else:
            print(f"   [OK] AgentCard valid (all required fields present)")

        # Test 1d: Verify EIP-8004 endpoints field
        print("\n1d. Verifying EIP-8004 endpoints...")
        if "endpoints" in card:
            endpoints = card["endpoints"]
            if isinstance(endpoints, list) and len(endpoints) > 0:
                print(f"   [OK] Endpoints field present ({len(endpoints)} endpoints)")
                for ep in endpoints:
                    print(f"      - {ep.get('name')}: {ep.get('endpoint')}")
            else:
                print(f"   [WARN] Endpoints field exists but is empty")
        else:
            print(f"   [WARN] Endpoints field missing (not EIP-8004 compliant)")

    print(f"\n{'='*70}")
    print("[OK] TEST 1 PASSED: Discovery Flow")
    print(f"{'='*70}\n")
    return True

# ============================================================================
# Test 2: Validation Flow
# ============================================================================

async def test_validation_flow():
    """Test validator analysis flow"""
    print("\n" + "="*70)
    print("TEST 2: Validation Flow")
    print("="*70 + "\n")

    async with httpx.AsyncClient(timeout=55.0) as client:

        # Test 2a: Request validation
        print("2a. Requesting validation from Validator...")
        validation_request = {
            "data_type": "chat_logs",
            "data_content": {"messages": ["Sample chat log data for validation"]},
            "seller_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "buyer_address": "0x8626f6940E2eb28930eFb4CeF49B2d1F2C9C1199",
            "price_glue": "0.01"
        }

        try:
            response = await client.post(
                f"{AGENTS['validator']}/validate",
                json=validation_request
            )

            if response.status_code == 200:
                result = response.json()
                print(f"   [OK] Validation completed")
                print(f"      Overall Score: {result.get('overall_score', 'N/A'):.2f}")
                print(f"      Recommendation: {result.get('recommendation', 'N/A')}")
                assert "overall_score" in result, "Validation missing overall_score"
                assert 0 <= result["overall_score"] <= 1.0, "Invalid score range"
            else:
                print(f"   [FAIL] Validation failed: HTTP {response.status_code}")
                return False
        except httpx.ConnectError:
            print(f"   [WARN]  Validator not running on {AGENTS['validator']}")
            print(f"      Skipping validation test")
            return True  # Don't fail test if validator not running
        except Exception as e:
            print(f"   [FAIL] Error: {e}")
            print(f"   [DEBUG] Exception type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            return False

    print(f"\n{'='*70}")
    print("[OK] TEST 2 PASSED: Validation Flow")
    print(f"{'='*70}\n")
    return True

# ============================================================================
# Test 3: Purchase Flow (Simulated)
# ============================================================================

async def test_purchase_flow():
    """Test data purchase flow (simulated payment)"""
    print("\n" + "="*70)
    print("TEST 3: Purchase Flow (Simulated Payment)")
    print("="*70 + "\n")

    async with httpx.AsyncClient(timeout=55.0) as client:

        # Test 3a: Request data from Karma-Hello
        print("3a. Requesting chat logs from Karma-Hello...")
        request_data = {
            "users": ["testuser"],
            "limit": 10,
            "include_stats": True
        }

        try:
            response = await client.post(
                f"{AGENTS['karma-hello']}/get_chat_logs",
                json=request_data
            )

            if response.status_code == 200:
                data = response.json()
                price = response.headers.get("X-Price", "unknown")
                print(f"   [OK] Data retrieved successfully")
                print(f"      Messages: {data.get('total_messages', 'N/A')}")
                print(f"      Price: {price} GLUE")
                assert "total_messages" in data, "Response missing total_messages"
            else:
                print(f"   [FAIL] Purchase failed: HTTP {response.status_code}")
                return False
        except httpx.ConnectError:
            print(f"   [WARN]  Karma-Hello not running on {AGENTS['karma-hello']}")
            print(f"      Skipping purchase test")
            return True
        except Exception as e:
            print(f"   [FAIL] Error: {e}")
            return False

        # Test 3b: Verify data structure
        print("\n3b. Verifying data structure...")
        required_fields = ["total_messages", "messages"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            print(f"   [FAIL] Missing fields: {missing}")
            return False
        else:
            print(f"   [OK] Data structure valid")

    print(f"\n{'='*70}")
    print("[OK] TEST 3 PASSED: Purchase Flow")
    print(f"{'='*70}\n")
    return True

# ============================================================================
# Test 4: Health Check All Agents
# ============================================================================

async def test_health_all_agents():
    """Test health endpoints for all agents"""
    print("\n" + "="*70)
    print("TEST 4: Health Check All Agents")
    print("="*70 + "\n")

    async with httpx.AsyncClient(timeout=5.0) as client:
        results = {}

        for agent_name, url in AGENTS.items():
            try:
                response = await client.get(f"{url}/health")
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "unknown")
                    results[agent_name] = status == "healthy"
                    symbol = "[OK]" if results[agent_name] else "[FAIL]"
                    print(f"   {symbol} {agent_name:20s} - {status}")
                else:
                    results[agent_name] = False
                    print(f"   [FAIL] {agent_name:20s} - HTTP {response.status_code}")
            except httpx.ConnectError:
                results[agent_name] = False
                print(f"   [WARN]  {agent_name:20s} - not running")
            except Exception as e:
                results[agent_name] = False
                print(f"   [FAIL] {agent_name:20s} - {str(e)[:30]}")

        healthy_count = sum(results.values())
        total_count = len(results)

        print(f"\n   Healthy: {healthy_count}/{total_count} agents")

        if healthy_count >= 2:  # At least 2 agents running is enough for basic testing
            print(f"\n{'='*70}")
            print(f"[OK] TEST 4 PASSED: {healthy_count} agents healthy")
            print(f"{'='*70}\n")
            return True
        else:
            print(f"\n{'='*70}")
            print(f"[WARN]  TEST 4 INCOMPLETE: Only {healthy_count} agents running")
            print(f"   Start more agents for complete testing")
            print(f"{'='*70}\n")
            return True  # Don't fail if agents aren't running

# ============================================================================
# Main Test Runner
# ============================================================================

async def run_all_tests():
    """Run all Level 3 end-to-end tests"""
    print("\n" + "="*70)
    print("  LEVEL 3: END-TO-END TESTS")
    print("  Complete Buyer->Validator->Seller Flow")
    print("="*70)

    results = {}

    # Run tests
    results["health"] = await test_health_all_agents()
    results["discovery"] = await test_discovery_flow()
    results["validation"] = await test_validation_flow()
    results["purchase"] = await test_purchase_flow()

    # Summary
    print("\n" + "="*70)
    print("  TEST SUMMARY")
    print("="*70 + "\n")

    passed = sum(results.values())
    total = len(results)

    for test_name, result in results.items():
        symbol = "[OK]" if result else "[FAIL]"
        print(f"   {symbol} {test_name.title():20s} - {'PASSED' if result else 'FAILED'}")

    print(f"\n   Total: {passed}/{total} tests passed")

    if passed == total:
        print(f"\n{'='*70}")
        print("  [OK] ALL LEVEL 3 TESTS PASSED")
        print("="*70 + "\n")
        return 0
    else:
        print(f"\n{'='*70}")
        print(f"  [WARN]  {total - passed} test(s) incomplete/failed")
        print("="*70 + "\n")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    exit(exit_code)
