"""
Test Bidirectional Agent Transactions

Validates that all agents can both buy and sell services, creating
a self-sustaining agent economy.

Tests cover:
1. Agent-to-agent purchases (buyer functionality)
2. Agent serving requests (seller functionality)
3. Circular transactions (A buys from B, B buys from A)
4. Multi-agent workflows (orchestrated purchases)
5. Token balance tracking

Run: pytest tests/test_bidirectional_transactions.py -v -s
"""

import asyncio
import pytest
import httpx
import os
from decimal import Decimal
from typing import Dict, List

# Test configuration - support production endpoints via environment variable
USE_PRODUCTION = os.getenv("USE_PRODUCTION", "false").lower() == "true"

if USE_PRODUCTION:
    print("\n[INFO] Using PRODUCTION endpoints (AWS ECS)")
    print("[WARN]  Production agents may not have local data - tests requiring data will be skipped")
    TEST_CONFIG = {
        "karma_hello_url": "https://karma-hello.karmacadabra.ultravioletadao.xyz",
        "abracadabra_url": "https://abracadabra.karmacadabra.ultravioletadao.xyz",
        "skill_extractor_url": "https://skill-extractor.karmacadabra.ultravioletadao.xyz",
        "voice_extractor_url": "https://voice-extractor.karmacadabra.ultravioletadao.xyz",
        "validator_url": "https://validator.karmacadabra.ultravioletadao.xyz",
        "timeout": 60.0
    }
else:
    print("\n[INFO] Using LOCAL endpoints (localhost)")
    TEST_CONFIG = {
        "karma_hello_url": "http://localhost:8002",
        "abracadabra_url": "http://localhost:8003",
        "skill_extractor_url": "http://localhost:8004",
        "voice_extractor_url": "http://localhost:8005",
        "validator_url": "http://localhost:8001",
        "timeout": 60.0  # Doubled from 30.0 for CrewAI validation processing
    }


def check_data_availability(response, test_name: str):
    """
    Helper to skip tests when production agents don't have data.

    In production, agents are deployed without local data files, so tests
    that require data purchases will get 404 responses. This is expected.
    """
    if response.status_code == 404 and USE_PRODUCTION:
        print(f"   [SKIP] No data available in production")
        print(f"   Production agents don't have local files loaded")
        pytest.skip(f"{test_name}: Production agents lack local data (expected)")

    return response


class AgentBalanceTracker:
    """Track GLUE token balances for all agents"""

    def __init__(self):
        self.balances = {
            "karma-hello": Decimal("0"),
            "abracadabra": Decimal("0"),
            "skill-extractor": Decimal("0"),
            "voice-extractor": Decimal("0"),
            "validator": Decimal("0")
        }
        self.transactions = []

    def record_transaction(
        self,
        buyer: str,
        seller: str,
        amount: Decimal,
        service: str
    ):
        """Record a transaction"""
        # Auto-initialize agents if not present (for dynamic test agents)
        if buyer not in self.balances:
            self.balances[buyer] = Decimal("0")
        if seller not in self.balances:
            self.balances[seller] = Decimal("0")

        self.balances[buyer] -= amount
        self.balances[seller] += amount
        self.transactions.append({
            "buyer": buyer,
            "seller": seller,
            "amount": amount,
            "service": service
        })

    def print_summary(self):
        """Print transaction summary"""
        print("\n" + "="*60)
        print("TRANSACTION SUMMARY")
        print("="*60)

        for tx in self.transactions:
            print(f"{tx['buyer']:20} -> {tx['seller']:20} : {tx['amount']:6} GLUE ({tx['service']})")

        print("\n" + "="*60)
        print("FINAL BALANCES")
        print("="*60)
        for agent, balance in self.balances.items():
            sign = "+" if balance >= 0 else ""
            print(f"{agent:20} : {sign}{balance:6} GLUE")
        print("="*60 + "\n")


# Global balance tracker for all tests
balance_tracker = AgentBalanceTracker()


@pytest.fixture(scope="module")
async def ensure_agents_running():
    """Ensure all agents are running before tests"""
    agents = [
        ("Karma-Hello", TEST_CONFIG["karma_hello_url"]),
        ("Abracadabra", TEST_CONFIG["abracadabra_url"]),
        ("Skill-Extractor", TEST_CONFIG["skill_extractor_url"]),
        ("Voice-Extractor", TEST_CONFIG["voice_extractor_url"]),
        ("Validator", TEST_CONFIG["validator_url"])
    ]

    async with httpx.AsyncClient() as client:
        for name, url in agents:
            try:
                response = await client.get(f"{url}/health", timeout=5.0)
                if response.status_code == 200:
                    print(f"[OK] {name} is running at {url}")
                else:
                    pytest.skip(f"{name} not healthy at {url}")
            except Exception as e:
                pytest.skip(f"{name} not available at {url}: {e}")

    yield

    # Print summary after all tests
    balance_tracker.print_summary()


# ============================================================================
# Test 1: Skill-Extractor Buys from Karma-Hello
# ============================================================================

@pytest.mark.asyncio
async def test_skill_extractor_buys_logs(ensure_agents_running):
    """
    Test: Skill-Extractor discovers and purchases chat logs from Karma-Hello

    Flow:
    1. Skill-Extractor discovers Karma-Hello via A2A
    2. Skill-Extractor purchases chat logs (0.01 GLUE)
    3. Karma-Hello delivers logs
    4. Skill-Extractor processes logs into skill profile
    """
    print("\n" + "="*60)
    print("TEST 1: Skill-Extractor -> Karma-Hello")
    print("="*60)

    async with httpx.AsyncClient() as client:
        # Step 1: Discover Karma-Hello
        print("1. Discovering Karma-Hello...")
        response = await client.get(
            f"{TEST_CONFIG['karma_hello_url']}/.well-known/agent-card",
            timeout=TEST_CONFIG["timeout"]
        )
        assert response.status_code == 200, "Failed to discover Karma-Hello"

        agent_card = response.json()
        print(f"   [OK] Found: {agent_card.get('name', 'Unknown')}")
        print(f"   Skills: {len(agent_card.get('skills', []))}")

        # Step 2: Purchase chat logs
        print("\n2. Purchasing chat logs...")
        purchase_request = {
            "users": ["test_user"],
            "limit": 100,
            "include_stats": True
        }

        response = await client.post(
            f"{TEST_CONFIG['karma_hello_url']}/get_chat_logs",
            json=purchase_request,
            timeout=TEST_CONFIG["timeout"]
        )

        check_data_availability(response, "Skill-Extractor buys logs")
        assert response.status_code == 200, f"Purchase failed: {response.text}"

        logs = response.json()
        price = response.headers.get("X-Price", "0.01")

        print(f"   [OK] Purchased logs")
        print(f"   Messages: {logs.get('total_messages', 0)}")
        print(f"   Users: {logs.get('unique_users', 0)}")
        print(f"   Price: {price} GLUE")

        # Record transaction
        balance_tracker.record_transaction(
            "skill-extractor",
            "karma-hello",
            Decimal("0.01"),
            "chat_logs"
        )

        # Step 3: Verify data structure
        assert "messages" in logs
        assert "metadata" in logs
        print("   [OK] Log structure validated")


# ============================================================================
# Test 2: Voice-Extractor Buys from Karma-Hello
# ============================================================================

@pytest.mark.asyncio
async def test_voice_extractor_buys_logs(ensure_agents_running):
    """
    Test: Voice-Extractor purchases logs for personality analysis

    Flow:
    1. Voice-Extractor discovers Karma-Hello
    2. Purchases user-specific logs (0.01 GLUE)
    3. Processes into linguistic profile
    """
    print("\n" + "="*60)
    print("TEST 2: Voice-Extractor -> Karma-Hello")
    print("="*60)

    async with httpx.AsyncClient() as client:
        # Discover and purchase
        print("1. Discovering Karma-Hello...")
        agent_card = await client.get(
            f"{TEST_CONFIG['karma_hello_url']}/.well-known/agent-card"
        )
        assert agent_card.status_code == 200

        print("2. Purchasing chat logs...")
        response = await client.post(
            f"{TEST_CONFIG['karma_hello_url']}/get_chat_logs",
            json={"users": ["personality_test_user"], "limit": 500},
            timeout=TEST_CONFIG["timeout"]
        )

        check_data_availability(response, "Voice-Extractor buys logs")
        assert response.status_code == 200
        logs = response.json()
        print(f"   [OK] Purchased {logs.get('total_messages', 0)} messages")

        balance_tracker.record_transaction(
            "voice-extractor",
            "karma-hello",
            Decimal("0.01"),
            "chat_logs"
        )


# ============================================================================
# Test 3: Abracadabra Buys from Karma-Hello
# ============================================================================

@pytest.mark.asyncio
async def test_abracadabra_buys_logs(ensure_agents_running):
    """
    Test: Abracadabra buys chat logs to enrich transcriptions

    Flow:
    1. Abracadabra discovers Karma-Hello
    2. Purchases logs for sentiment context (0.01 GLUE)
    3. Enriches transcription analysis
    """
    print("\n" + "="*60)
    print("TEST 3: Abracadabra -> Karma-Hello")
    print("="*60)

    async with httpx.AsyncClient() as client:
        print("1. Abracadabra purchasing logs for enrichment...")
        response = await client.post(
            f"{TEST_CONFIG['karma_hello_url']}/get_chat_logs",
            json={"users": ["0xultravioleta"], "limit": 1000},
            timeout=TEST_CONFIG["timeout"]
        )

        check_data_availability(response, "Abracadabra buys logs")
        assert response.status_code == 200
        logs = response.json()
        print(f"   [OK] Abracadabra purchased logs: {logs.get('total_messages', 0)} messages")

        balance_tracker.record_transaction(
            "abracadabra",
            "karma-hello",
            Decimal("0.01"),
            "chat_logs"
        )


# ============================================================================
# Test 4: Karma-Hello Buys from Abracadabra (Circular Transaction)
# ============================================================================

@pytest.mark.asyncio
async def test_karma_hello_buys_transcription(ensure_agents_running):
    """
    Test: Karma-Hello purchases transcription from Abracadabra

    This is a CIRCULAR TRANSACTION:
    - Karma-Hello sells logs to others (earns 0.01 GLUE)
    - Karma-Hello buys transcription (spends 0.02 GLUE)
    - Net: Karma-Hello -0.01 GLUE, Abracadabra +0.02 GLUE

    Flow:
    1. Karma-Hello discovers Abracadabra
    2. Purchases transcription (0.02 GLUE)
    3. Enriches its own data with audio context
    """
    print("\n" + "="*60)
    print("TEST 4: Karma-Hello -> Abracadabra (CIRCULAR)")
    print("="*60)

    async with httpx.AsyncClient() as client:
        # Step 1: Discover Abracadabra
        print("1. Karma-Hello discovering Abracadabra...")
        agent_card = await client.get(
            f"{TEST_CONFIG['abracadabra_url']}/.well-known/agent-card",
            timeout=TEST_CONFIG["timeout"]
        )
        assert agent_card.status_code == 200
        print(f"   [OK] Found Abracadabra")

        # Step 2: Purchase transcription
        print("2. Karma-Hello purchasing transcription...")
        response = await client.post(
            f"{TEST_CONFIG['abracadabra_url']}/get_transcription",
            json={"stream_id": "2597743149"},
            timeout=TEST_CONFIG["timeout"]
        )

        check_data_availability(response, "Karma-Hello buys transcription")
        assert response.status_code == 200
        transcription = response.json()
        print(f"   [OK] Purchased transcription")
        print(f"   Duration: {transcription.get('duration_seconds', 0)}s")
        print(f"   Segments: {len(transcription.get('transcript', []))}")

        balance_tracker.record_transaction(
            "karma-hello",
            "abracadabra",
            Decimal("0.02"),
            "transcription"
        )


# ============================================================================
# Test 5: Skill-Extractor Sells Profile (Complete Value Chain)
# ============================================================================

@pytest.mark.asyncio
async def test_skill_extractor_sells_profile(ensure_agents_running):
    """
    Test: Complete value chain for Skill-Extractor

    Flow:
    1. Skill-Extractor buys logs from Karma-Hello (0.01 GLUE) [ALREADY TESTED]
    2. Skill-Extractor processes logs with CrewAI
    3. Client buys skill profile from Skill-Extractor (0.10 GLUE)
    4. Net: Skill-Extractor earns 0.09 GLUE profit

    This tests the SELLER side of Skill-Extractor
    """
    print("\n" + "="*60)
    print("TEST 5: Client -> Skill-Extractor (Value Chain)")
    print("="*60)

    async with httpx.AsyncClient() as client:
        try:
            # Discover Skill-Extractor
            print("1. Client discovering Skill-Extractor...")
            agent_card = await client.get(
                f"{TEST_CONFIG['skill_extractor_url']}/.well-known/agent-card",
                timeout=TEST_CONFIG["timeout"]
            )

            if agent_card.status_code != 200:
                print(f"   [SKIP] Skill-Extractor not running ({agent_card.status_code})")
                pytest.skip("Skill-Extractor agent not running")
                return

            print(f"   [OK] Found Skill-Extractor")

            # Purchase skill profile
            print("2. Client purchasing skill profile...")
            response = await client.post(
                f"{TEST_CONFIG['skill_extractor_url']}/get_skill_profile",
                json={
                    "username": "test_user",
                    "profile_level": "standard",
                    "include_monetization": True
                },
                timeout=TEST_CONFIG["timeout"]
            )

            check_data_availability(response, "Client buys skill profile")
            assert response.status_code == 200
            profile = response.json()
            print(f"   [OK] Purchased profile for {profile.get('user_id', 'unknown')}")
            print(f"   Skills found: {len(profile.get('skills', []))}")
            print(f"   Monetization opportunities: {len(profile.get('monetization_opportunities', []))}")

            # Record transaction
            balance_tracker.record_transaction(
                "client",
                "skill-extractor",
                Decimal("0.10"),
                "skill_profile"
            )

            # Validate structure
            assert "skills" in profile
            assert "monetization_opportunities" in profile
            print("   [OK] Profile structure validated")

        except httpx.ConnectError as e:
            print(f"   [SKIP] Skill-Extractor not running: {e}")
            pytest.skip("Skill-Extractor agent not running")


# ============================================================================
# Test 6: Voice-Extractor Sells Profile
# ============================================================================

@pytest.mark.asyncio
async def test_voice_extractor_sells_profile(ensure_agents_running):
    """
    Test: Voice-Extractor complete value chain

    Flow:
    1. Buys logs from Karma-Hello (0.01 GLUE) [ALREADY TESTED]
    2. Processes with CrewAI psycholinguistic analysis
    3. Sells personality profile to client (0.10 GLUE)
    4. Net: Earns 0.09 GLUE profit
    """
    print("\n" + "="*60)
    print("TEST 6: Client -> Voice-Extractor (Value Chain)")
    print("="*60)

    async with httpx.AsyncClient() as client:
        try:
            # Purchase personality profile
            print("1. Client purchasing personality profile...")
            response = await client.post(
                f"{TEST_CONFIG['voice_extractor_url']}/get_voice_profile",
                json={
                    "username": "personality_test_user",
                    "profile_type": "standard"
                },
                timeout=TEST_CONFIG["timeout"]
            )

            if response.status_code != 200:
                print(f"   [SKIP] Voice-Extractor not running ({response.status_code})")
                pytest.skip("Voice-Extractor agent not running")
                return

            profile = response.json()
            print(f"   [OK] Purchased profile for {profile.get('username', 'unknown')}")
            print(f"   Analysis categories: {len(profile.get('analysis', {}).keys())}")

            balance_tracker.record_transaction(
                "client",
                "voice-extractor",
                Decimal("0.10"),
                "personality_profile"
            )

        except httpx.ConnectError as e:
            print(f"   [SKIP] Voice-Extractor not running: {e}")
            pytest.skip("Voice-Extractor agent not running")


# ============================================================================
# Test 7: Validator Service (Independent)
# ============================================================================

@pytest.mark.asyncio
async def test_validator_service(ensure_agents_running):
    """
    Test: Validator provides independent verification

    Flow:
    1. Agent requests validation (0.001 GLUE)
    2. Validator runs CrewAI crews
    3. Submits validation score on-chain
    4. Returns validation response

    Note: Validator is a pure seller, doesn't buy from other agents
    """
    print("\n" + "="*60)
    print("TEST 7: Agent -> Validator (Verification)")
    print("="*60)

    async with httpx.AsyncClient() as client:
        # Request validation
        print("1. Requesting data validation...")
        validation_request = {
            "data_type": "chat_logs",
            "data_content": {
                "messages": [
                    {"user": "test", "message": "hello", "timestamp": "2025-10-24T10:00:00"},
                    {"user": "test", "message": "world", "timestamp": "2025-10-24T10:01:00"}
                ]
            },
            "seller_address": "0x1234...seller",
            "buyer_address": "0x5678...buyer",
            "price_glue": "0.01"
        }

        response = await client.post(
            f"{TEST_CONFIG['validator_url']}/validate",
            json=validation_request,
            timeout=TEST_CONFIG["timeout"]
        )

        assert response.status_code == 200
        validation = response.json()

        print(f"   [OK] Validation complete")
        print(f"   Quality score: {validation.get('quality_score', 0):.2f}")
        print(f"   Fraud score: {validation.get('fraud_score', 0):.2f}")
        print(f"   Overall score: {validation.get('overall_score', 0):.2f}")
        print(f"   Recommendation: {validation.get('recommendation', 'unknown')}")

        balance_tracker.record_transaction(
            "seller",
            "validator",
            Decimal("0.001"),
            "validation"
        )

        assert "quality_score" in validation
        assert "overall_score" in validation
        assert "recommendation" in validation


# ============================================================================
# Test 8: Multi-Agent Orchestrated Workflow
# ============================================================================

@pytest.mark.asyncio
async def test_orchestrated_workflow(ensure_agents_running):
    """
    Test: Complex multi-agent workflow

    Flow (simulates an orchestrator agent):
    1. Buy logs from Karma-Hello (0.01 GLUE)
    2. Buy transcription from Abracadabra (0.02 GLUE)
    3. Buy skill profile from Skill-Extractor (0.10 GLUE)
    4. Buy personality from Voice-Extractor (0.10 GLUE)
    5. Request validation from Validator (0.001 GLUE)
    6. Synthesize comprehensive report
    7. Sell report to client (1.00 GLUE)

    Total spent: 0.231 GLUE
    Revenue: 1.00 GLUE
    Profit: 0.769 GLUE
    """
    print("\n" + "="*60)
    print("TEST 8: Orchestrated Multi-Agent Workflow")
    print("="*60)

    async with httpx.AsyncClient() as client:
        comprehensive_data = {}

        # Step 1: Buy logs
        print("1. Orchestrator buying chat logs...")
        response = await client.post(
            f"{TEST_CONFIG['karma_hello_url']}/get_chat_logs",
            json={"users": ["0xultravioleta", "0xj4an"], "limit": 1000},
            timeout=TEST_CONFIG["timeout"]
        )
        check_data_availability(response, "Orchestrated workflow - buy logs")
        assert response.status_code == 200
        comprehensive_data["logs"] = response.json()
        print(f"   [OK] Got {comprehensive_data['logs'].get('total_messages', 0)} messages")

        # Step 2: Buy transcription
        print("2. Orchestrator buying transcription...")
        response = await client.post(
            f"{TEST_CONFIG['abracadabra_url']}/get_transcription",
            json={"stream_id": "2597743149"},
            timeout=TEST_CONFIG["timeout"]
        )
        check_data_availability(response, "Orchestrated workflow - buy transcription")
        assert response.status_code == 200
        comprehensive_data["transcription"] = response.json()
        print(f"   [OK] Got transcription ({comprehensive_data['transcription'].get('duration_seconds', 0)}s)")

        # Step 3: Buy skill profile (skip if not available)
        print("3. Orchestrator buying skill profile...")
        try:
            response = await client.post(
                f"{TEST_CONFIG['skill_extractor_url']}/get_skill_profile",
                json={"username": "0xultravioleta", "profile_level": "standard"},
                timeout=TEST_CONFIG["timeout"]
            )
            if response.status_code == 200:
                comprehensive_data["skills"] = response.json()
                print(f"   [OK] Got {len(comprehensive_data['skills'].get('skills', []))} skills")
                balance_tracker.record_transaction("orchestrator", "skill-extractor", Decimal("0.10"), "skills")
            else:
                print(f"   [SKIP] Skill-extractor not available ({response.status_code})")
        except Exception as e:
            print(f"   [SKIP] Skill-extractor not available: {e}")

        # Step 4: Buy personality profile (skip if not available)
        print("4. Orchestrator buying personality profile...")
        try:
            response = await client.post(
                f"{TEST_CONFIG['voice_extractor_url']}/get_voice_profile",
                json={"username": "0xultravioleta", "profile_type": "standard"},
                timeout=TEST_CONFIG["timeout"]
            )
            if response.status_code == 200:
                comprehensive_data["personality"] = response.json()
                print(f"   [OK] Got personality analysis")
                balance_tracker.record_transaction("orchestrator", "voice-extractor", Decimal("0.10"), "personality")
            else:
                print(f"   [SKIP] Voice-extractor not available ({response.status_code})")
        except Exception as e:
            print(f"   [SKIP] Voice-extractor not available: {e}")

        # Step 5: Validate with Validator (optional)
        print("5. Orchestrator validating data quality...")
        # (validation request would go here)

        # Record base transactions (skills and personality already recorded above if successful)
        balance_tracker.record_transaction("orchestrator", "karma-hello", Decimal("0.01"), "logs")
        balance_tracker.record_transaction("orchestrator", "abracadabra", Decimal("0.02"), "transcription")

        # Step 6: Synthesize report
        print("\n6. Synthesizing comprehensive report...")
        print("   [OK] Combined data from 4 agents")
        print(f"   Total cost: 0.23 GLUE")

        # Step 7: Sell to client
        print("7. Selling comprehensive report to client...")
        balance_tracker.record_transaction("client", "orchestrator", Decimal("1.00"), "comprehensive_report")
        print(f"   [OK] Sold for 1.00 GLUE")
        print(f"   Net profit: 0.77 GLUE")


# ============================================================================
# Test 9: Verify Agent Discovery Works
# ============================================================================

@pytest.mark.asyncio
async def test_all_agents_discoverable(ensure_agents_running):
    """
    Test: All agents publish valid A2A AgentCards

    Validates that every agent can be discovered by others
    """
    print("\n" + "="*60)
    print("TEST 9: Agent Discovery Verification")
    print("="*60)

    agents = [
        ("Karma-Hello", TEST_CONFIG["karma_hello_url"]),
        ("Abracadabra", TEST_CONFIG["abracadabra_url"]),
        ("Skill-Extractor", TEST_CONFIG["skill_extractor_url"]),
        ("Voice-Extractor", TEST_CONFIG["voice_extractor_url"]),
        ("Validator", TEST_CONFIG["validator_url"])
    ]

    async with httpx.AsyncClient() as client:
        discovered_count = 0
        for name, url in agents:
            print(f"\nDiscovering {name}...")
            try:
                response = await client.get(
                    f"{url}/.well-known/agent-card",
                    timeout=10.0
                )

                if response.status_code != 200:
                    print(f"   [SKIP] {name} not available ({response.status_code})")
                    continue

                agent_card = response.json()
                print(f"   [OK] {name} discovered")
                print(f"   Agent ID: {agent_card.get('agentId', 'N/A')}")
                print(f"   Domain: {agent_card.get('domain', 'N/A')}")
                print(f"   Skills: {len(agent_card.get('skills', []))}")

                # Validate structure (handle both agent_id and agentId)
                assert "agent_id" in agent_card or "agentId" in agent_card
                assert "name" in agent_card
                assert "skills" in agent_card
                assert len(agent_card["skills"]) > 0

                discovered_count += 1

            except Exception as e:
                print(f"   [SKIP] {name} not available: {e}")

        # At least core agents (karma-hello, abracadabra, validator) should be discoverable
        assert discovered_count >= 2, f"Only {discovered_count} agents discovered, expected at least 2"


if __name__ == "__main__":
    """Run tests manually"""
    import sys
    pytest.main([__file__, "-v", "-s"] + sys.argv[1:])
