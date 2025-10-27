#!/usr/bin/env python3
"""
Example usage of ERC8004BaseAgent

Demonstrates:
1. Agent initialization
2. Registration in Identity Registry
3. Querying agent information
4. Rating other agents
5. Accepting and managing feedback
"""

from base_agent import ERC8004BaseAgent


def main():
    print("=" * 70)
    print("ERC8004BaseAgent Example")
    print("=" * 70)
    print()

    # Example 1: Initialize an agent (uses AWS Secrets Manager)
    print("[1] Initializing agent...")
    agent = ERC8004BaseAgent(
        agent_name="validator-agent",
        agent_domain="validator.ultravioletadao.xyz"
    )
    print(f"    Agent: {agent}")
    print(f"    Balance: {agent.get_balance()} AVAX")
    print()

    # Example 2: Register agent (if not already registered)
    print("[2] Registering agent...")
    try:
        agent_id = agent.register_agent()
        print(f"    ✅ Registered with ID: {agent_id}")
    except Exception as e:
        print(f"    ℹ️  Registration failed (may already be registered): {e}")
        # If already registered, we can query by address
        agent.agent_id = 0  # Set manually or query from contract
    print()

    # Example 3: Query agent information
    print("[3] Querying agent count...")
    agent_count = agent.get_agent_count()
    print(f"    Total agents: {agent_count}")
    print()

    if agent_count > 0:
        print("[4] Querying first agent...")
        agent_info = agent.get_agent_info(0)
        print(f"    Agent ID: {agent_info['agent_id']}")
        print(f"    Domain: {agent_info['agent_domain']}")
        print(f"    Address: {agent_info['agent_address']}")
        print()

    # Example 4: Rate a server (if we have at least 2 agents)
    if agent_count >= 2 and agent.agent_id is not None:
        print("[5] Rating server agent...")
        try:
            # Rate agent ID 1 with score 85
            tx_hash = agent.rate_server(server_agent_id=1, rating=85)
            print(f"    ✅ Rating submitted: {tx_hash}")
        except Exception as e:
            print(f"    ℹ️  Rating failed: {e}")
        print()

        # Query the rating we just gave
        print("[6] Querying server rating...")
        has_rating, rating = agent.get_server_rating(
            client_id=agent.agent_id,
            server_id=1
        )
        if has_rating:
            print(f"    ✅ Rating exists: {rating}/100")
        else:
            print(f"    ℹ️  No rating found")
        print()

    # Example 5: Accept feedback (as a client)
    if agent_count >= 2 and agent.agent_id is not None:
        print("[7] Accepting feedback from server...")
        try:
            tx_hash = agent.accept_feedback(server_agent_id=1)
            print(f"    ✅ Feedback accepted: {tx_hash}")

            # Get the feedback auth ID
            feedback_auth_id = agent.get_feedback_auth_id(
                client_id=agent.agent_id,
                server_id=1
            )
            print(f"    Feedback Auth ID: {feedback_auth_id.hex()}")
        except Exception as e:
            print(f"    ℹ️  Accept feedback failed: {e}")
        print()

    print("=" * 70)
    print("Example complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
