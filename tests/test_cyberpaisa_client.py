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
from shared.agent_config import load_agent_config
from dotenv import load_dotenv
import os

# Don't load .env - use AWS Secrets Manager directly via load_agent_config()
# (client-agent credentials are in AWS, no local .env needed)


async def test_cyberpaisa_purchases():
    """Test cyberpaisa purchasing from multiple agents"""

    print("=" * 80)
    print("TESTING CYBERPAISA USER AGENT AS CLIENT")
    print("=" * 80)

    # Initialize cyberpaisa agent
    print("\n[INFO] Step 1: Initialize cyberpaisa agent")
    print("-" * 80)

    try:
        # Load config using AWS Secrets Manager (fetches PRIVATE_KEY automatically)
        # Using client-agent as cyberpaisa (generic user agent)
        config = load_agent_config("client-agent")

        print(f"[OK] Config loaded from AWS Secrets Manager (using client-agent)")
        print(f"   Agent: {config.agent_name}")
        print(f"   Domain: {config.agent_domain}")

        agent = ERC8004BaseAgent(
            agent_name=config.agent_name,
            agent_domain=config.agent_domain,
            rpc_url=config.rpc_url,
            chain_id=config.chain_id,
            identity_registry_address=config.identity_registry,
            reputation_registry_address=config.reputation_registry,
            validation_registry_address=config.validation_registry,
            private_key=config.private_key
        )
    except Exception as e:
        print(f"[ERROR] Failed to load config or initialize agent: {e}")
        print(f"   Make sure client-agent exists in AWS Secrets Manager")
        print(f"   Available agents: validator-agent, karma-hello-agent, client-agent, etc.")
        import traceback
        traceback.print_exc()
        return

    try:

        print(f"[OK] Agent initialized: {agent.agent_name}")
        print(f"   Wallet: {agent.address}")

        initial_balance = agent.get_balance()
        print(f"   [GLUE] Initial GLUE Balance: {initial_balance}")

        if initial_balance < Decimal("1.0"):
            print(f"[WARN]  WARNING: Low GLUE balance. Recommended: 1000+ GLUE")
            print(f"   Run: python erc-20/distribute-token.py")

    except Exception as e:
        print(f"[ERROR] Failed to initialize agent: {e}")
        return

    # Test 1: Discover and buy from karma-hello
    print("\n[DISCOVER] Step 2: Discover karma-hello agent")
    print("-" * 80)

    karma_hello_url = "https://karma-hello.karmacadabra.ultravioletadao.xyz"

    try:
        agent_card = await agent.discover_agent(karma_hello_url)

        if agent_card:
            print(f"[OK] Discovered karma-hello agent!")
            print(f"   Agent ID: {agent_card.get('agentId', 'N/A')}")
            print(f"   Skills: {len(agent_card.get('skills', []))}")

            # Show available skills
            for skill in agent_card.get('skills', [])[:3]:  # Show first 3
                print(f"      - {skill.get('skillId')}: {skill.get('price', {}).get('amount')} GLUE")
        else:
            print("[ERROR] Could not discover karma-hello agent")
            return

    except Exception as e:
        print(f"[ERROR] Discovery failed: {e}")
        return

    # Test 2: Purchase chat logs
    print("\n[PURCHASE] Step 3: Purchase chat logs from karma-hello")
    print("-" * 80)

    try:
        result = await agent.buy_from_agent(
            agent_url=karma_hello_url,
            endpoint="/get_chat_logs",
            request_data={
                "date": "20241021",
                "format": "json"
            },
            expected_price_glue="0.01"
        )

        if result and result.get("success"):
            print("[OK] Purchase successful!")
            data = result.get('data', {})
            print(f"   [DATA] Data received: {len(str(data))} bytes")

            if isinstance(data, dict):
                print(f"   [STATS] Keys in response: {list(data.keys())[:5]}")

            tx_hash = result.get('tx_hash')
            if tx_hash:
                print(f"   [TX] Transaction: {tx_hash}")
                print(f"   [LINK] View on Snowtrace: https://testnet.snowtrace.io/tx/{tx_hash}")
        elif result:
            print(f"[ERROR] Purchase failed: {result.get('error', 'Unknown error')}")
        else:
            print(f"[WARN]  Purchase returned no result (agent may not have data available)")

    except Exception as e:
        print(f"[ERROR] Purchase failed with exception: {e}")

    # Test 3: Discover and buy from abracadabra
    print("\n[DISCOVER] Step 4: Discover abracadabra agent")
    print("-" * 80)

    abracadabra_url = "https://abracadabra.karmacadabra.ultravioletadao.xyz"

    try:
        agent_card = await agent.discover_agent(abracadabra_url)

        if agent_card:
            print(f"[OK] Discovered abracadabra agent!")
            print(f"   Agent ID: {agent_card.get('agentId', 'N/A')}")
            print(f"   Skills: {len(agent_card.get('skills', []))}")
        else:
            print("[WARN]  Could not discover abracadabra agent (may be offline)")

    except Exception as e:
        print(f"[WARN]  Discovery failed: {e}")

    # Test 4: Purchase transcript (optional - costs more)
    print("\n[PURCHASE] Step 5: Purchase transcript from abracadabra (optional)")
    print("-" * 80)
    print("[SKIP]  Skipped (costs 0.02 GLUE) - uncomment to test")

    # Uncomment to test:
    # try:
    #     result = await agent.buy_from_agent(
    #         agent_url=abracadabra_url,
    #         endpoint="/get_transcription",
    #         request_data={"stream_id": "20241021"},
    #         expected_price_glue="0.02"
    #     )
    #     if result.get("success"):
    #         print("[OK] Transcript purchase successful!")
    #     else:
    #         print(f"[ERROR] Purchase failed: {result.get('error')}")
    # except Exception as e:
    #     print(f"[WARN]  Purchase failed: {e}")

    # Final balance
    print("\n[STATS] Step 6: Final Summary")
    print("-" * 80)

    final_balance = agent.get_balance()
    spent = initial_balance - final_balance

    print(f"[GLUE] Initial Balance: {initial_balance} GLUE")
    print(f"[GLUE] Final Balance:   {final_balance} GLUE")
    print(f"[PURCHASE] Total Spent:     {spent} GLUE")

    print("\n" + "=" * 80)
    print("[OK] TEST COMPLETE!")
    print("=" * 80)

    print("\n[NEXT] Next steps:")
    print("   1. View transactions on Snowtrace:")
    print(f"      https://testnet.snowtrace.io/address/{agent.address}")
    print("   2. Test other agents (skill-extractor, voice-extractor)")
    print("   3. Register cyberpaisa on-chain: python scripts/register_missing_agents.py")
    print("   4. Run full marketplace test: python tests/test_marketplace_bootstrap.py")


if __name__ == "__main__":
    asyncio.run(test_cyberpaisa_purchases())
