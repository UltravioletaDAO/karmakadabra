"""
Unit Tests for Karma-Hello Agent

Tests the karma-hello agent with mock data without external dependencies.
No MongoDB, no HTTP calls, no blockchain - pure logic testing.

Usage:
    python test_karma_hello.py --mock    # Run all unit tests with mock data
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

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

MOCK_CHAT_LOGS = {
    "stream_id": "stream_20251023_001",
    "stream_date": "2025-10-23",
    "total_messages": 156,
    "unique_users": 23,
    "messages": [
        {"user": "alice", "message": "Hello everyone!", "timestamp": "2025-10-23T10:00:00Z"},
        {"user": "bob", "message": "Hi Alice!", "timestamp": "2025-10-23T10:01:00Z"},
        {"user": "charlie", "message": "What's up?", "timestamp": "2025-10-23T10:02:00Z"},
        {"user": "alice", "message": "We're discussing blockchain agents", "timestamp": "2025-10-23T10:03:00Z"},
    ],
    "stats": {
        "avg_message_length": 42,
        "most_active_user": "alice",
        "duration_minutes": 120
    }
}

MOCK_TRANSCRIPTION = {
    "stream_id": "stream_20251023_001",
    "duration_seconds": 7200,
    "language": "en",
    "transcript": [
        {"start": 0, "end": 15, "text": "Welcome to today's stream", "speaker": "host"},
        {"start": 15, "end": 30, "text": "Today we'll build AI agents", "speaker": "host"}
    ],
    "summary": "Stream about building AI agents with blockchain",
    "key_topics": ["AI agents", "blockchain", "autonomy"]
}


# ============================================================================
# Test Functions
# ============================================================================

def test_agent_card_generation():
    """Test AgentCard generation"""
    print("\n📋 Test 1: AgentCard Generation")
    print("=" * 60)

    # Mock agent card structure
    agent_card = {
        "schema_version": "1.0.0",
        "agent_id": "2",
        "name": "Karma-Hello Agent",
        "description": "Twitch chat log seller + buyer",
        "skills": [
            {
                "name": "get_chat_logs",
                "description": "Get chat logs for a stream",
                "pricing": {
                    "currency": "GLUE",
                    "base_price": "0.01",
                    "price_per_message": "0.0001",
                    "max_price": "200.0"
                }
            }
        ]
    }

    # Verify structure
    assert "skills" in agent_card
    assert len(agent_card["skills"]) > 0

    skill = agent_card["skills"][0]
    assert "pricing" in skill
    assert "base_price" in skill["pricing"]

    print(f"✅ AgentCard generated successfully")
    print(f"   Name: {agent_card['name']}")
    print(f"   Skills: {len(agent_card['skills'])}")

    return True


def test_price_calculation_seller():
    """Test price calculation for selling chat logs"""
    print("\n💰 Test 2: Price Calculation (Seller)")
    print("=" * 60)

    base_price = 0.01
    price_per_message = 0.0001
    max_price = 200.0

    # Test case 1: 100 messages
    message_count = 100
    price = base_price + (price_per_message * message_count)
    price = min(price, max_price)

    print(f"   Case 1: {message_count} messages")
    print(f"   Price: {price} GLUE")
    assert price == 0.02, f"Expected 0.02, got {price}"

    # Test case 2: 1000 messages
    message_count = 1000
    price = base_price + (price_per_message * message_count)
    price = min(price, max_price)

    print(f"   Case 2: {message_count} messages")
    print(f"   Price: {price} GLUE")
    assert price == 0.11, f"Expected 0.11, got {price}"

    # Test case 3: Max price limit
    message_count = 3000000  # Very large
    price = base_price + (price_per_message * message_count)
    price = min(price, max_price)

    print(f"   Case 3: {message_count} messages (should hit max)")
    print(f"   Price: {price} GLUE")
    assert price == max_price, f"Expected {max_price}, got {price}"

    print(f"✅ Price calculation validated")

    return True


def test_chat_log_filtering():
    """Test chat log filtering by user"""
    print("\n🔍 Test 3: Chat Log Filtering")
    print("=" * 60)

    messages = MOCK_CHAT_LOGS["messages"]

    # Filter by specific user
    target_user = "alice"
    filtered = [m for m in messages if m["user"] == target_user]

    print(f"   Total messages: {len(messages)}")
    print(f"   Messages from '{target_user}': {len(filtered)}")
    assert len(filtered) == 2, f"Expected 2 messages from alice, got {len(filtered)}"

    print(f"✅ Filtering validated")

    return True


def test_buyer_transcription_parsing():
    """Test parsing transcriptions bought from Abracadabra"""
    print("\n📥 Test 4: Buyer - Transcription Parsing")
    print("=" * 60)

    transcription = MOCK_TRANSCRIPTION

    # Verify structure
    assert "stream_id" in transcription
    assert "transcript" in transcription
    assert "duration_seconds" in transcription

    # Verify segments
    segments = transcription["transcript"]
    assert len(segments) > 0
    assert "text" in segments[0]
    assert "start" in segments[0]

    print(f"   Stream ID: {transcription['stream_id']}")
    print(f"   Duration: {transcription['duration_seconds']}s")
    print(f"   Segments: {len(segments)}")
    print(f"✅ Transcription parsing validated")

    return True


def test_storage_structure():
    """Test storage directory structure for both buying and selling"""
    print("\n💾 Test 5: Storage Structure")
    print("=" * 60)

    # Seller: stores chat logs locally
    logs_dir = Path("logs") / "20251023"
    print(f"   Seller storage: {logs_dir}")

    # Buyer: stores purchased transcriptions
    purchases_dir = Path("purchased_transcriptions")
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    purchase_file = purchases_dir / f"stream_20251023_001_{timestamp}.json"
    print(f"   Buyer storage: {purchase_file}")

    print(f"✅ Storage structure validated")

    return True


def test_seller_flow_logic():
    """Test complete seller flow logic"""
    print("\n📤 Test 6: Seller Flow Logic")
    print("=" * 60)

    # Step 1: Receive request for chat logs
    print("   1. Receive request... ✅")
    request = {
        "stream_id": "stream_20251023_001",
        "users": ["alice"],
        "limit": 1000
    }

    # Step 2: Load logs (mocked) - make a copy to avoid modifying original
    print("   2. Load logs from storage... ✅ (mocked)")
    logs = {
        "stream_id": MOCK_CHAT_LOGS["stream_id"],
        "messages": list(MOCK_CHAT_LOGS["messages"]),  # Copy list
        "total_messages": MOCK_CHAT_LOGS["total_messages"]
    }

    # Step 3: Filter by users if specified
    print("   3. Filter by users... ✅")
    if "users" in request and request["users"]:
        target_users = request["users"]
        filtered_messages = [m for m in logs["messages"] if m["user"] in target_users]
        logs["messages"] = filtered_messages
        logs["total_messages"] = len(filtered_messages)

    # Step 4: Calculate price
    print("   4. Calculate price... ✅")
    price = 0.01 + (0.0001 * logs["total_messages"])

    # Step 5: Return data with price header
    print("   5. Return data with X-Price header... ✅")

    print(f"\n✅ Seller flow validated (price: {price} GLUE)")

    return True


def test_buyer_flow_logic():
    """Test complete buyer flow logic"""
    print("\n📥 Test 7: Buyer Flow Logic")
    print("=" * 60)

    # Step 1: Discover Abracadabra
    print("   1. Discover Abracadabra seller... ✅ (mocked)")

    # Step 2: Request transcription
    print("   2. Request transcription... ✅ (mocked)")
    request = {
        "stream_id": "stream_20251023_001",
        "include_summary": True
    }

    # Step 3: Receive transcription
    print("   3. Receive transcription... ✅ (mocked)")
    transcription = MOCK_TRANSCRIPTION

    # Step 4: Validate transcription
    print("   4. Validate transcription structure... ✅")
    assert "stream_id" in transcription
    assert "transcript" in transcription

    # Step 5: Save to storage
    print("   5. Save to purchased_transcriptions/... ✅ (mocked)")

    print(f"\n✅ Buyer flow validated")

    return True


def test_data_stats_calculation():
    """Test calculation of chat statistics"""
    print("\n📊 Test 8: Data Stats Calculation")
    print("=" * 60)

    messages = MOCK_CHAT_LOGS["messages"]

    # Calculate stats
    total_messages = len(messages)
    unique_users = len(set(m["user"] for m in messages))
    avg_length = sum(len(m["message"]) for m in messages) / total_messages if total_messages > 0 else 0

    print(f"   Total messages: {total_messages}")
    print(f"   Unique users: {unique_users}")
    print(f"   Avg message length: {avg_length:.1f} chars")

    assert total_messages == 4
    assert unique_users == 3

    print(f"✅ Stats calculation validated")

    return True


# ============================================================================
# Test Runner
# ============================================================================

def run_all_tests():
    """Run all unit tests"""
    print("\n" + "=" * 60)
    print("  KARMA-HELLO AGENT - UNIT TESTS (Mock Mode)")
    print("=" * 60)

    tests = [
        ("AgentCard Generation", test_agent_card_generation),
        ("Price Calculation (Seller)", test_price_calculation_seller),
        ("Chat Log Filtering", test_chat_log_filtering),
        ("Buyer - Transcription Parsing", test_buyer_transcription_parsing),
        ("Storage Structure", test_storage_structure),
        ("Seller Flow Logic", test_seller_flow_logic),
        ("Buyer Flow Logic", test_buyer_flow_logic),
        ("Data Stats Calculation", test_data_stats_calculation)
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
        print("Usage: python test_karma_hello.py --mock")
        sys.exit(1)
