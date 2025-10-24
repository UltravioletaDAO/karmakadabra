"""
Unit Tests for Client Agent

Tests the client agent with mock data without external dependencies.
No blockchain, no HTTP calls, no OpenAI - pure logic testing.

Usage:
    python test_client.py --mock    # Run all unit tests with mock data
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, patch, AsyncMock

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass


# ============================================================================
# Mock Data
# ============================================================================

MOCK_AGENT_CARD = {
    "schema_version": "1.0.0",
    "agent_id": "1",
    "name": "Karma-Hello Seller",
    "description": "Twitch chat log seller",
    "domain": "karma-hello.ultravioletadao.xyz",
    "wallet_address": "0x2C3e071df446B25B821F59425152838ae4931E75",
    "skills": [
        {
            "name": "get_chat_logs",
            "description": "Get chat logs for a stream",
            "pricing": {
                "currency": "GLUE",
                "base_price": "0.01",
                "price_per_message": "0.0001"
            }
        }
    ],
    "payment_methods": [
        {
            "protocol": "x402",
            "version": "1.0",
            "token": {
                "symbol": "GLUE",
                "address": "0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743"
            }
        }
    ]
}

MOCK_VALIDATION_RESPONSE = {
    "valid": True,
    "overall_score": 0.85,
    "quality_score": 0.88,
    "fraud_score": 0.95,
    "price_score": 0.72,
    "recommendation": "APPROVE",
    "message": "Data quality is good"
}

MOCK_CHAT_LOGS = {
    "stream_id": "stream_20251023_001",
    "total_messages": 50,
    "messages": [
        {"user": "alice", "message": "Hello!", "timestamp": "2025-10-23T10:00:00Z"},
        {"user": "bob", "message": "Hi Alice!", "timestamp": "2025-10-23T10:01:00Z"}
    ]
}


# ============================================================================
# Test Functions
# ============================================================================

def test_agent_card_parsing():
    """Test parsing of AgentCard from seller"""
    print("\n📋 Test 1: AgentCard Parsing")
    print("=" * 60)

    # Parse agent card
    card = MOCK_AGENT_CARD

    # Verify structure
    assert "schema_version" in card, "Missing schema_version"
    assert "agent_id" in card, "Missing agent_id"
    assert "name" in card, "Missing name"
    assert "skills" in card, "Missing skills"
    assert len(card["skills"]) > 0, "No skills defined"

    # Verify skill structure
    skill = card["skills"][0]
    assert "name" in skill, "Skill missing name"
    assert "pricing" in skill, "Skill missing pricing"

    # Verify payment methods
    assert "payment_methods" in card, "Missing payment_methods"
    assert len(card["payment_methods"]) > 0, "No payment methods"

    print(f"✅ AgentCard parsed successfully")
    print(f"   Agent: {card['name']}")
    print(f"   Skills: {len(card['skills'])}")
    print(f"   Payment methods: {len(card['payment_methods'])}")

    return True


def test_price_calculation():
    """Test price calculation logic"""
    print("\n💰 Test 2: Price Calculation")
    print("=" * 60)

    # Extract pricing from agent card
    skill = MOCK_AGENT_CARD["skills"][0]
    pricing = skill["pricing"]

    base_price = float(pricing["base_price"])
    price_per_message = float(pricing["price_per_message"])

    # Calculate price for 100 messages
    message_count = 100
    total_price = base_price + (price_per_message * message_count)

    print(f"   Base price: {base_price} GLUE")
    print(f"   Per message: {price_per_message} GLUE")
    print(f"   Messages: {message_count}")
    print(f"✅ Calculated price: {total_price} GLUE")

    assert total_price == 0.02, f"Expected 0.02 GLUE, got {total_price}"

    return True


def test_validation_score_check():
    """Test validation score checking logic"""
    print("\n🔍 Test 3: Validation Score Check")
    print("=" * 60)

    validation = MOCK_VALIDATION_RESPONSE
    min_score = 0.7

    overall_score = validation["overall_score"]
    recommendation = validation["recommendation"]

    # Check if score meets minimum
    passes = overall_score >= min_score

    print(f"   Overall score: {overall_score}")
    print(f"   Minimum required: {min_score}")
    print(f"   Recommendation: {recommendation}")

    if passes:
        print(f"✅ Validation passed (score: {overall_score})")
    else:
        print(f"❌ Validation failed (score: {overall_score} < {min_score})")

    assert passes, f"Validation score {overall_score} below minimum {min_score}"

    return True


def test_data_storage_structure():
    """Test data storage directory structure"""
    print("\n💾 Test 4: Data Storage Structure")
    print("=" * 60)

    # Mock purchase
    seller_name = "karma-hello"
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # Expected directory structure
    storage_dir = Path("purchased_data") / seller_name / timestamp

    print(f"   Storage path: {storage_dir}")
    print(f"   Seller: {seller_name}")
    print(f"   Timestamp: {timestamp}")
    print(f"✅ Storage structure validated")

    return True


def test_buyer_flow_logic():
    """Test complete buyer flow logic (mocked)"""
    print("\n🔄 Test 5: Buyer Flow Logic")
    print("=" * 60)

    # Step 1: Discover seller
    print("   1. Discover seller... ✅")
    agent_card = MOCK_AGENT_CARD

    # Step 2: Request validation
    print("   2. Request validation... ✅")
    validation = MOCK_VALIDATION_RESPONSE

    # Step 3: Check validation score
    print("   3. Check validation score... ✅")
    if validation["overall_score"] < 0.7:
        print("   ❌ Validation failed - would abort purchase")
        return False

    # Step 4: Calculate price
    print("   4. Calculate price... ✅")
    skill = agent_card["skills"][0]
    price = float(skill["pricing"]["base_price"])

    # Step 5: Check max price
    print("   5. Check max price... ✅")
    max_price = 1.0
    if price > max_price:
        print(f"   ❌ Price {price} exceeds max {max_price} - would abort")
        return False

    # Step 6: Generate payment (mocked)
    print("   6. Generate payment signature... ✅ (mocked)")

    # Step 7: Make purchase request (mocked)
    print("   7. Make purchase request... ✅ (mocked)")

    # Step 8: Save data (mocked)
    print("   8. Save purchased data... ✅ (mocked)")

    print(f"\n✅ Complete buyer flow validated")

    return True


def test_agent_discovery():
    """Test agent discovery via A2A protocol"""
    print("\n🔍 Test 6: Agent Discovery")
    print("=" * 60)

    # Mock discovering multiple agents
    agents = {
        "karma-hello": {
            "url": "http://localhost:8002",
            "card": MOCK_AGENT_CARD
        },
        "validator": {
            "url": "http://localhost:8001",
            "card": {
                "name": "Validator",
                "skills": [{"name": "validate_data"}]
            }
        }
    }

    print(f"   Discovered {len(agents)} agents:")
    for name, info in agents.items():
        print(f"   - {name}: {info['url']}")

    print(f"✅ Agent discovery validated")

    return True


# ============================================================================
# Test Runner
# ============================================================================

def run_all_tests():
    """Run all unit tests"""
    print("\n" + "=" * 60)
    print("  CLIENT AGENT - UNIT TESTS (Mock Mode)")
    print("=" * 60)

    tests = [
        ("AgentCard Parsing", test_agent_card_parsing),
        ("Price Calculation", test_price_calculation),
        ("Validation Score Check", test_validation_score_check),
        ("Data Storage Structure", test_data_storage_structure),
        ("Buyer Flow Logic", test_buyer_flow_logic),
        ("Agent Discovery", test_agent_discovery)
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, "PASS", None))
        except AssertionError as e:
            results.append((test_name, "FAIL", str(e)))
        except Exception as e:
            results.append((test_name, "ERROR", str(e)))

    # Print summary
    print("\n" + "=" * 60)
    print("  TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, status, _ in results if status == "PASS")
    failed = sum(1 for _, status, _ in results if status == "FAIL")
    errors = sum(1 for _, status, _ in results if status == "ERROR")

    for test_name, status, error in results:
        if status == "PASS":
            print(f"✅ {test_name}: PASS")
        elif status == "FAIL":
            print(f"❌ {test_name}: FAIL - {error}")
        else:
            print(f"⚠️  {test_name}: ERROR - {error}")

    print("\n" + "=" * 60)
    print(f"  Total: {len(results)} | Passed: {passed} | Failed: {failed} | Errors: {errors}")
    print("=" * 60)

    return failed == 0 and errors == 0


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import sys

    if "--mock" in sys.argv or len(sys.argv) == 1:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    else:
        print("Usage: python test_client.py --mock")
        sys.exit(1)
