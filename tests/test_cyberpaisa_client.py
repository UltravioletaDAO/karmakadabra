"""
Test cyberpaisa user agent as a client

This script tests the cyberpaisa agent buying services from system agents:
- Discovers agents via A2A protocol
- Makes purchases using x402 payments
- Verifies transactions on-chain
"""

import asyncio
import sys
from pathlib import Path
from decimal import Decimal

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.base_agent import ERC8004BaseAgent
from dotenv import load_dotenv
import os

# Load cyberpaisa config
load_dotenv("client-agents/cyberpaisa/.env")


async def test_cyberpaisa_purchases():
    """Test cyberpaisa purchasing from multiple agents"""

    print("=" * 80)
    print("🧪 TESTING CYBERPAISA USER AGENT AS CLIENT")
    print("=" * 80)

    # Initialize cyberpaisa agent
    print("\n📋 Step 1: Initialize cyberpaisa agent")
    print("-" * 80)

    config = {
        "agent_name": os.getenv("AGENT_NAME"),
        "agent_domain": os.getenv("AGENT_DOMAIN"),
        "rpc_url_fuji": os.getenv("RPC_URL_FUJI"),
        "chain_id": int(os.getenv("CHAIN_ID")),
        "identity_registry": os.getenv("IDENTITY_REGISTRY"),
        "reputation_registry": os.getenv("REPUTATION_REGISTRY"),
        "validation_registry": os.getenv("VALIDATION_REGISTRY"),
        "private_key": os.getenv("PRIVATE_KEY")
    }

    if not config["private_key"]:
        print("❌ ERROR: No PRIVATE_KEY found in client-agents/cyberpaisa/.env")
        print("   Please follow Step 1-2 in docs/guides/TEST_USER_AGENT_CYBERPAISA.md")
        return

    try:
        agent = ERC8004BaseAgent(
            agent_name=config["agent_name"],
            agent_domain=config["agent_domain"],
            rpc_url=config["rpc_url_fuji"],
            chain_id=config["chain_id"],
            identity_registry_address=config["identity_registry"],
            reputation_registry_address=config["reputation_registry"],
            validation_registry_address=config["validation_registry"],
            private_key=config["private_key"]
        )

        print(f"✅ Agent initialized: {agent.agent_name}")
        print(f"   Wallet: {agent.wallet_address}")

        initial_balance = agent.get_balance()
        print(f"   💎 Initial GLUE Balance: {initial_balance}")

        if initial_balance < Decimal("1.0"):
            print(f"⚠️  WARNING: Low GLUE balance. Recommended: 1000+ GLUE")
            print(f"   Run: python erc-20/distribute-token.py")

    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        return

    # Test 1: Discover and buy from karma-hello
    print("\n🔍 Step 2: Discover karma-hello agent")
    print("-" * 80)

    karma_hello_url = "https://karma-hello.karmacadabra.ultravioletadao.xyz"

    try:
        agent_card = await agent.discover_agent(karma_hello_url)

        if agent_card:
            print(f"✅ Discovered karma-hello agent!")
            print(f"   Agent ID: {agent_card.get('agentId', 'N/A')}")
            print(f"   Skills: {len(agent_card.get('skills', []))}")

            # Show available skills
            for skill in agent_card.get('skills', [])[:3]:  # Show first 3
                print(f"      - {skill.get('skillId')}: {skill.get('price', {}).get('amount')} GLUE")
        else:
            print("❌ Could not discover karma-hello agent")
            return

    except Exception as e:
        print(f"❌ Discovery failed: {e}")
        return

    # Test 2: Purchase chat logs
    print("\n💸 Step 3: Purchase chat logs from karma-hello")
    print("-" * 80)

    try:
        result = await agent.buy_from_agent(
            seller_url=karma_hello_url,
            skill_id="get_logs",
            price_glue="0.01",
            params={
                "date": "20241021",
                "format": "json"
            }
        )

        if result.get("success"):
            print("✅ Purchase successful!")
            data = result.get('data', {})
            print(f"   📦 Data received: {len(str(data))} bytes")

            if isinstance(data, dict):
                print(f"   📊 Keys in response: {list(data.keys())[:5]}")

            tx_hash = result.get('tx_hash')
            if tx_hash:
                print(f"   🔗 Transaction: {tx_hash}")
                print(f"   🌐 View on Snowtrace: https://testnet.snowtrace.io/tx/{tx_hash}")
        else:
            print(f"❌ Purchase failed: {result.get('error', 'Unknown error')}")

    except Exception as e:
        print(f"❌ Purchase failed with exception: {e}")

    # Test 3: Discover and buy from abracadabra
    print("\n🔍 Step 4: Discover abracadabra agent")
    print("-" * 80)

    abracadabra_url = "https://abracadabra.karmacadabra.ultravioletadao.xyz"

    try:
        agent_card = await agent.discover_agent(abracadabra_url)

        if agent_card:
            print(f"✅ Discovered abracadabra agent!")
            print(f"   Agent ID: {agent_card.get('agentId', 'N/A')}")
            print(f"   Skills: {len(agent_card.get('skills', []))}")
        else:
            print("⚠️  Could not discover abracadabra agent (may be offline)")

    except Exception as e:
        print(f"⚠️  Discovery failed: {e}")

    # Test 4: Purchase transcript (optional - costs more)
    print("\n💸 Step 5: Purchase transcript from abracadabra (optional)")
    print("-" * 80)
    print("⏭️  Skipped (costs 0.02 GLUE) - uncomment to test")

    # Uncomment to test:
    # try:
    #     result = await agent.buy_from_agent(
    #         seller_url=abracadabra_url,
    #         skill_id="get_transcript",
    #         price_glue="0.02",
    #         params={"stream_id": "20241021"}
    #     )
    #     if result.get("success"):
    #         print("✅ Transcript purchase successful!")
    #     else:
    #         print(f"❌ Purchase failed: {result.get('error')}")
    # except Exception as e:
    #     print(f"⚠️  Purchase failed: {e}")

    # Final balance
    print("\n📊 Step 6: Final Summary")
    print("-" * 80)

    final_balance = agent.get_balance()
    spent = initial_balance - final_balance

    print(f"💎 Initial Balance: {initial_balance} GLUE")
    print(f"💎 Final Balance:   {final_balance} GLUE")
    print(f"💸 Total Spent:     {spent} GLUE")

    print("\n" + "=" * 80)
    print("✅ TEST COMPLETE!")
    print("=" * 80)

    print("\n📝 Next steps:")
    print("   1. View transactions on Snowtrace:")
    print(f"      https://testnet.snowtrace.io/address/{agent.wallet_address}")
    print("   2. Test other agents (skill-extractor, voice-extractor)")
    print("   3. Register cyberpaisa on-chain: python scripts/register_missing_agents.py")
    print("   4. Run full marketplace test: python tests/test_marketplace_bootstrap.py")


if __name__ == "__main__":
    asyncio.run(test_cyberpaisa_purchases())
