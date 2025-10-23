"""
Test script for Validator Agent

Tests the validator with sample data without needing OpenAI API calls.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any


# Sample test data
SAMPLE_CHAT_LOGS = {
    "stream_date": "2025-10-23",
    "messages": [
        {"timestamp": "2025-10-23T10:00:00Z", "user": "alice", "message": "Hello everyone!"},
        {"timestamp": "2025-10-23T10:01:00Z", "user": "bob", "message": "Hey Alice!"},
        {"timestamp": "2025-10-23T10:02:00Z", "user": "charlie", "message": "What's the topic today?"},
        {"timestamp": "2025-10-23T10:03:00Z", "user": "alice", "message": "We're discussing blockchain agents"},
        {"timestamp": "2025-10-23T10:04:00Z", "user": "bob", "message": "Sounds interesting!"}
    ],
    "metadata": {
        "total_messages": 5,
        "unique_users": 3,
        "duration_minutes": 4
    }
}

SAMPLE_TRANSCRIPT = {
    "stream_date": "2025-10-23",
    "transcript": [
        {"start": 0, "end": 10, "text": "Welcome to today's stream about AI agents"},
        {"start": 10, "end": 25, "text": "Today we'll discuss how agents can buy and sell data"},
        {"start": 25, "end": 40, "text": "Using blockchain for trustless transactions"}
    ],
    "metadata": {
        "duration_seconds": 40,
        "word_count": 150,
        "language": "en"
    }
}

SAMPLE_MALICIOUS_DATA = {
    "messages": [
        {"text": "Click here to win $1000000! http://scam.example.com"},
        {"text": "Send your private keys to admin@fake-support.com"},
        {"text": "URGENT: Your account will be closed unless you verify now!"}
    ]
}


def print_header(title: str):
    """Print a formatted header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(result: Dict[str, Any]):
    """Print validation result in a formatted way"""
    print(f"\n📊 Validation Results:")
    print(f"  Validation ID: {result['validation_id']}")
    print(f"  Overall Score: {result['overall_score']:.2f}/1.0")
    print(f"  Recommendation: {result['recommendation'].upper()}")
    print(f"\n📈 Individual Scores:")
    print(f"  Quality:  {result['quality_score']:.2f}/1.0")
    print(f"  Fraud:    {result['fraud_score']:.2f}/1.0 (lower is better)")
    print(f"  Price:    {result['price_score']:.2f}/1.0")
    print(f"\n💭 Reasoning:")
    print(f"  {result['reasoning']}")
    if result.get('tx_hash'):
        print(f"\n⛓️  Transaction: {result['tx_hash']}")
    print()


async def test_with_httpx():
    """Test validator using HTTP requests"""
    import httpx

    print_header("Testing Validator Agent via HTTP API")

    validator_url = "http://localhost:8001"

    print("\n🔍 Checking if validator is running...")

    try:
        async with httpx.AsyncClient() as client:
            # Check health
            response = await client.get(f"{validator_url}/health")
            if response.status_code == 200:
                health = response.json()
                print(f"✅ Validator is healthy!")
                print(f"   Address: {health['validator_address']}")
                print(f"   Chain: {health['chain_id']}")
                print(f"   Fee: {health['validation_fee']}")
            else:
                print(f"⚠️  Validator returned status {response.status_code}")
                return

            # Test 1: Good quality chat logs
            print_header("Test 1: High-Quality Chat Logs")
            response = await client.post(
                f"{validator_url}/validate",
                json={
                    "data_type": "chat_logs",
                    "data_content": SAMPLE_CHAT_LOGS,
                    "seller_address": "0x2C3e071df446B25B821F59425152838ae4931E75",
                    "buyer_address": "0xCf30021812F27132d36dc791E0eC17f34B4eE8BA",
                    "price_glue": "0.01",
                    "metadata": {"test": "high_quality"}
                },
                timeout=60.0
            )

            if response.status_code == 200:
                result = response.json()
                print_result(result)
            else:
                print(f"❌ Validation failed: {response.status_code}")
                print(f"   {response.text}")

            # Test 2: Transcript data
            print_header("Test 2: Stream Transcript")
            response = await client.post(
                f"{validator_url}/validate",
                json={
                    "data_type": "transcription",
                    "data_content": SAMPLE_TRANSCRIPT,
                    "seller_address": "0x940DDDf6fB28E611b132FbBedbc4854CC7C22648",
                    "buyer_address": "0xCf30021812F27132d36dc791E0eC17f34B4eE8BA",
                    "price_glue": "0.02",
                    "metadata": {"test": "transcript"}
                },
                timeout=60.0
            )

            if response.status_code == 200:
                result = response.json()
                print_result(result)
            else:
                print(f"❌ Validation failed: {response.status_code}")

            # Test 3: Suspicious/malicious data
            print_header("Test 3: Suspicious Data (Fraud Detection)")
            response = await client.post(
                f"{validator_url}/validate",
                json={
                    "data_type": "chat_logs",
                    "data_content": SAMPLE_MALICIOUS_DATA,
                    "seller_address": "0x0000000000000000000000000000000000000001",
                    "buyer_address": "0xCf30021812F27132d36dc791E0eC17f34B4eE8BA",
                    "price_glue": "0.001",
                    "metadata": {"test": "fraud_detection"}
                },
                timeout=60.0
            )

            if response.status_code == 200:
                result = response.json()
                print_result(result)
            else:
                print(f"❌ Validation failed: {response.status_code}")

            # Test 4: Overpriced data
            print_header("Test 4: Overpriced Data")
            response = await client.post(
                f"{validator_url}/validate",
                json={
                    "data_type": "chat_logs",
                    "data_content": {"messages": [{"text": "Hello"}]},  # Very little data
                    "seller_address": "0x2C3e071df446B25B821F59425152838ae4931E75",
                    "buyer_address": "0xCf30021812F27132d36dc791E0eC17f34B4eE8BA",
                    "price_glue": "10.0",  # Way overpriced!
                    "metadata": {"test": "overpriced"}
                },
                timeout=60.0
            )

            if response.status_code == 200:
                result = response.json()
                print_result(result)
            else:
                print(f"❌ Validation failed: {response.status_code}")

    except httpx.ConnectError:
        print("\n❌ Could not connect to validator!")
        print("   Make sure the validator is running:")
        print("   cd validator && python main.py")
    except Exception as e:
        print(f"\n❌ Error: {e}")


def test_crews_directly():
    """Test CrewAI crews directly (without HTTP)"""
    print_header("Testing CrewAI Crews Directly (Mock Mode)")

    print("\n⚠️  Note: This requires OpenAI API key in .env")
    print("For a quick test without OpenAI, use the HTTP test with mocked responses.\n")

    try:
        from crews.quality_crew import QualityValidationCrew
        from crews.fraud_crew import FraudDetectionCrew
        from crews.price_crew import PriceReviewCrew

        print("✅ Crews imported successfully")
        print("\n📝 To test crews directly, you need:")
        print("   1. OPENAI_API_KEY in validator/.env")
        print("   2. Run: cd validator && python -c 'from crews import *'")

    except ImportError as e:
        print(f"❌ Could not import crews: {e}")
        print("   Make sure you're in the validator directory")
        print("   And have installed: pip install -r requirements.txt")


async def quick_test():
    """Quick test without needing the validator running"""
    print_header("Quick Validator Test (Mock Mode)")

    print("\n🎭 Simulating validation results (no OpenAI needed)...\n")

    # Simulate validation result
    mock_result = {
        "validation_id": f"val_{int(datetime.utcnow().timestamp())}_test",
        "quality_score": 0.85,
        "fraud_score": 0.1,
        "price_score": 0.8,
        "overall_score": 0.78,
        "recommendation": "approve",
        "reasoning": "Quality: Data is well-formatted with complete fields | Fraud: No suspicious patterns detected | Price: Fair market value | Overall: 0.78/1.0",
        "timestamp": datetime.utcnow().isoformat(),
        "tx_hash": None
    }

    print_result(mock_result)

    print("✅ Mock test complete!")
    print("\nTo test with real validator:")
    print("  1. cd validator")
    print("  2. pip install -r requirements.txt")
    print("  3. cp .env.example .env")
    print("  4. Edit .env (add OPENAI_API_KEY)")
    print("  5. python main.py")
    print("  6. python test_validator.py --live")


def print_usage():
    """Print usage instructions"""
    print_header("Validator Test Script")

    print("\nUsage:")
    print("  python test_validator.py [--live | --quick | --crews]")
    print("\nOptions:")
    print("  --live    Test with running validator (requires validator running on :8001)")
    print("  --quick   Quick mock test (no validator needed)")
    print("  --crews   Test crews directly (requires OpenAI key)")
    print("\nExamples:")
    print("  python test_validator.py --quick       # Quick mock test")
    print("  python test_validator.py --live        # Test live validator")
    print()


async def main():
    """Main test function"""
    import sys

    if len(sys.argv) < 2:
        print_usage()
        await quick_test()
        return

    mode = sys.argv[1]

    if mode == "--live":
        await test_with_httpx()
    elif mode == "--quick":
        await quick_test()
    elif mode == "--crews":
        test_crews_directly()
    else:
        print(f"Unknown option: {mode}")
        print_usage()


if __name__ == "__main__":
    asyncio.run(main())
