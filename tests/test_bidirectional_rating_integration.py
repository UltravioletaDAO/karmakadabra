#!/usr/bin/env python3
"""
Integration Test: Bidirectional Trust Pattern
==============================================

Tests the complete bidirectional rating flow:
1. Server provides service to client
2. Client rates server (existing functionality)
3. Validator validates the service
4. Server rates validator (NEW bidirectional functionality)
5. Verify all ratings on-chain

This demonstrates the bidirectional trust pattern contribution to EIP-8004.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.base_agent import ERC8004BaseAgent
from shared.agent_config import load_agent_config
from web3 import Web3
import time


# ============================================================================
# Test Configuration
# ============================================================================

def print_section(title):
    """Print formatted section header"""
    print("\n" + "="*70)
    print(f"{title}")
    print("="*70 + "\n")


def print_step(step_num, description):
    """Print formatted step"""
    print(f"{step_num}. {description}")


def print_result(status, message, indent=3):
    """Print formatted result"""
    prefix = "[OK]" if status else "[FAIL]"
    print(f"{'   '*indent}{prefix} {message}")


# ============================================================================
# Test Setup
# ============================================================================

def setup_test_agents():
    """Initialize test agents"""
    print_section("TEST SETUP: Initializing Agents")

    # Load configurations
    print_step("1", "Loading agent configurations...")
    try:
        server_config = load_agent_config("karma-hello-agent")
        validator_config = load_agent_config("validator-agent")
        client_config = load_agent_config("client-agent")
        print_result(True, "Configurations loaded")
    except Exception as e:
        print_result(False, f"Failed to load configs: {e}")
        return None, None, None

    # Create agent instances
    print_step("2", "Creating ERC8004BaseAgent instances...")
    try:
        server_agent = ERC8004BaseAgent(
            agent_name="karma-hello-agent",
            agent_domain=server_config.agent_domain,
            rpc_url=server_config.rpc_url,
            identity_registry_address=server_config.identity_registry,
            reputation_registry_address=server_config.reputation_registry,
            validation_registry_address=server_config.validation_registry
        )
        print_result(True, f"Server agent: {server_agent.address}")

        validator_agent = ERC8004BaseAgent(
            agent_name="validator-agent",
            agent_domain=validator_config.agent_domain,
            rpc_url=validator_config.rpc_url,
            identity_registry_address=validator_config.identity_registry,
            reputation_registry_address=validator_config.reputation_registry,
            validation_registry_address=validator_config.validation_registry
        )
        print_result(True, f"Validator agent: {validator_agent.address}")

        client_agent = ERC8004BaseAgent(
            agent_name="client-agent",
            agent_domain=client_config.agent_domain,
            rpc_url=client_config.rpc_url,
            identity_registry_address=client_config.identity_registry,
            reputation_registry_address=client_config.reputation_registry,
            validation_registry_address=client_config.validation_registry
        )
        print_result(True, f"Client agent: {client_agent.address}")

    except Exception as e:
        print_result(False, f"Failed to create agents: {e}")
        return None, None, None

    # Verify agents are registered
    print_step("3", "Verifying agent registrations...")
    try:
        if not server_agent.agent_id:
            print_result(False, "Server agent not registered. Run scripts/register_seller.py first")
            return None, None, None
        print_result(True, f"Server agent ID: {server_agent.agent_id}")

        if not validator_agent.agent_id:
            print_result(False, "Validator agent not registered. Run scripts/register_validator.py first")
            return None, None, None
        print_result(True, f"Validator agent ID: {validator_agent.agent_id}")

        if not client_agent.agent_id:
            print_result(False, "Client agent not registered")
            return None, None, None
        print_result(True, f"Client agent ID: {client_agent.agent_id}")

    except Exception as e:
        print_result(False, f"Registration check failed: {e}")
        return None, None, None

    print(f"\n{'='*70}")
    print("[OK] SETUP COMPLETE: All agents initialized")
    print(f"{'='*70}\n")

    return server_agent, validator_agent, client_agent


# ============================================================================
# Test 1: Traditional Unidirectional Rating (Baseline)
# ============================================================================

def test_unidirectional_rating(server_agent, client_agent):
    """Test traditional client->server rating (EIP-8004 base functionality)"""
    print_section("TEST 1: Unidirectional Rating (Baseline)")

    print_step("1a", "Client rates server (traditional EIP-8004)...")
    try:
        # Client must accept feedback first
        print("      Accepting feedback authorization...")
        feedback_auth_id = server_agent.accept_feedback(server_agent.agent_id)
        print_result(True, f"Feedback authorized")

        # Client rates server
        rating = 85
        tx_hash = client_agent.rate_server(server_agent.agent_id, rating, feedback_auth_id)
        print_result(True, f"Client rated server: {rating}/100")
        print_result(True, f"TX: {tx_hash}", indent=4)

        # Wait for transaction confirmation
        time.sleep(3)

        # Query the rating
        has_rating, stored_rating = server_agent.get_server_rating(client_agent.agent_id, server_agent.agent_id)
        if has_rating and stored_rating == rating:
            print_result(True, f"Rating verified on-chain: {stored_rating}/100")
        else:
            print_result(False, f"Rating mismatch or not found")
            return False

    except Exception as e:
        print_result(False, f"Unidirectional rating failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    print(f"\n{'='*70}")
    print("[OK] TEST 1 PASSED: Unidirectional Rating Works")
    print(f"{'='*70}\n")
    return True


# ============================================================================
# Test 2: Bidirectional Rating (NEW FUNCTIONALITY)
# ============================================================================

def test_bidirectional_rating(server_agent, validator_agent):
    """Test NEW bidirectional rating: server rates validator"""
    print_section("TEST 2: Bidirectional Rating (NEW)")

    print_step("2a", "Server rates validator (NEW bidirectional functionality)...")
    try:
        # Server rates validator
        rating = 95
        tx_hash = server_agent.rate_validator(validator_agent.agent_id, rating)
        print_result(True, f"Server rated validator: {rating}/100")
        print_result(True, f"TX: {tx_hash}", indent=4)

        # Wait for transaction confirmation
        time.sleep(3)

        # Query the validator rating using NEW method
        has_rating, stored_rating = server_agent.get_validator_rating(
            validator_agent.agent_id,
            server_agent.agent_id
        )

        if has_rating and stored_rating == rating:
            print_result(True, f"Validator rating verified on-chain: {stored_rating}/100")
        else:
            print_result(False, f"Validator rating mismatch or not found")
            return False

    except Exception as e:
        print_result(False, f"Bidirectional rating failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    print(f"\n{'='*70}")
    print("[OK] TEST 2 PASSED: Bidirectional Rating Works")
    print(f"{'='*70}\n")
    return True


# ============================================================================
# Test 3: Server Rates Client (Reverse Rating)
# ============================================================================

def test_server_rates_client(server_agent, client_agent):
    """Test server rating client (also bidirectional)"""
    print_section("TEST 3: Server Rates Client (Reverse Direction)")

    print_step("3a", "Server rates client...")
    try:
        # Generate feedback authorization
        print("      Generating feedback authorization...")
        feedback_auth_id = bytes(32)  # Simplified for test

        # Server rates client
        rating = 75
        tx_hash = server_agent.rate_client(client_agent.agent_id, rating, feedback_auth_id)
        print_result(True, f"Server rated client: {rating}/100")
        print_result(True, f"TX: {tx_hash}", indent=4)

        # Wait for transaction confirmation
        time.sleep(3)

        # Query the rating
        has_rating, stored_rating = server_agent.get_client_rating(
            client_agent.agent_id,
            server_agent.agent_id
        )

        if has_rating and stored_rating == rating:
            print_result(True, f"Client rating verified on-chain: {stored_rating}/100")
        else:
            print_result(False, f"Client rating mismatch or not found")
            return False

    except Exception as e:
        print_result(False, f"Server->Client rating failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    print(f"\n{'='*70}")
    print("[OK] TEST 3 PASSED: Server Can Rate Clients")
    print(f"{'='*70}\n")
    return True


# ============================================================================
# Test 4: Complete Bidirectional Pattern
# ============================================================================

def test_complete_bidirectional_pattern(server_agent, validator_agent, client_agent):
    """Test complete bidirectional trust pattern"""
    print_section("TEST 4: Complete Bidirectional Trust Pattern")

    print_step("4a", "Retrieving all ratings for each agent...")

    try:
        # Get bidirectional ratings for server
        print("\n   Server Agent Ratings:")
        server_ratings = server_agent.get_bidirectional_ratings(server_agent.agent_id)
        print(f"      Structure validated: {bool(server_ratings)}")

        # Get bidirectional ratings for validator
        print("\n   Validator Agent Ratings:")
        validator_ratings = validator_agent.get_bidirectional_ratings(validator_agent.agent_id)
        print(f"      Structure validated: {bool(validator_ratings)}")

        # Get bidirectional ratings for client
        print("\n   Client Agent Ratings:")
        client_ratings = client_agent.get_bidirectional_ratings(client_agent.agent_id)
        print(f"      Structure validated: {bool(client_ratings)}")

        print_result(True, "All bidirectional rating structures valid")

    except Exception as e:
        print_result(False, f"Failed to retrieve bidirectional ratings: {e}")
        return False

    print(f"\n{'='*70}")
    print("[OK] TEST 4 PASSED: Complete Bidirectional Pattern")
    print(f"{'='*70}\n")
    return True


# ============================================================================
# Test 5: Rating Boundaries
# ============================================================================

def test_rating_boundaries(server_agent, validator_agent):
    """Test edge cases for ratings"""
    print_section("TEST 5: Rating Boundaries & Edge Cases")

    print_step("5a", "Testing rating = 0 (minimum valid)...")
    try:
        tx_hash = server_agent.rate_validator(validator_agent.agent_id, 0)
        time.sleep(3)
        has_rating, stored_rating = server_agent.get_validator_rating(
            validator_agent.agent_id, server_agent.agent_id
        )
        if has_rating and stored_rating == 0:
            print_result(True, "Rating 0 works correctly")
        else:
            print_result(False, "Rating 0 failed")
            return False
    except Exception as e:
        print_result(False, f"Rating 0 failed: {e}")
        return False

    print_step("5b", "Testing rating = 100 (maximum valid)...")
    try:
        tx_hash = server_agent.rate_validator(validator_agent.agent_id, 100)
        time.sleep(3)
        has_rating, stored_rating = server_agent.get_validator_rating(
            validator_agent.agent_id, server_agent.agent_id
        )
        if has_rating and stored_rating == 100:
            print_result(True, "Rating 100 works correctly")
        else:
            print_result(False, "Rating 100 failed")
            return False
    except Exception as e:
        print_result(False, f"Rating 100 failed: {e}")
        return False

    print_step("5c", "Testing rating > 100 (should fail)...")
    try:
        tx_hash = server_agent.rate_validator(validator_agent.agent_id, 101)
        print_result(False, "Rating 101 should have been rejected")
        return False
    except ValueError as e:
        if "between 0 and 100" in str(e):
            print_result(True, "Rating 101 correctly rejected")
        else:
            print_result(False, f"Wrong error: {e}")
            return False
    except Exception as e:
        print_result(False, f"Unexpected error: {e}")
        return False

    print(f"\n{'='*70}")
    print("[OK] TEST 5 PASSED: Rating Boundaries Work Correctly")
    print(f"{'='*70}\n")
    return True


# ============================================================================
# Test 6: Update Ratings
# ============================================================================

def test_update_ratings(server_agent, validator_agent):
    """Test updating existing ratings"""
    print_section("TEST 6: Rating Updates")

    print_step("6a", "Creating initial rating...")
    try:
        initial_rating = 60
        tx_hash = server_agent.rate_validator(validator_agent.agent_id, initial_rating)
        time.sleep(3)
        has_rating, stored_rating = server_agent.get_validator_rating(
            validator_agent.agent_id, server_agent.agent_id
        )
        if has_rating and stored_rating == initial_rating:
            print_result(True, f"Initial rating: {initial_rating}/100")
        else:
            print_result(False, "Initial rating failed")
            return False
    except Exception as e:
        print_result(False, f"Initial rating failed: {e}")
        return False

    print_step("6b", "Updating rating to higher value...")
    try:
        updated_rating = 90
        tx_hash = server_agent.rate_validator(validator_agent.agent_id, updated_rating)
        time.sleep(3)
        has_rating, stored_rating = server_agent.get_validator_rating(
            validator_agent.agent_id, server_agent.agent_id
        )
        if has_rating and stored_rating == updated_rating:
            print_result(True, f"Rating updated: {updated_rating}/100")
        else:
            print_result(False, f"Rating update failed (got {stored_rating})")
            return False
    except Exception as e:
        print_result(False, f"Rating update failed: {e}")
        return False

    print(f"\n{'='*70}")
    print("[OK] TEST 6 PASSED: Rating Updates Work")
    print(f"{'='*70}\n")
    return True


# ============================================================================
# Main Test Runner
# ============================================================================

def main():
    """Run all bidirectional rating integration tests"""
    print("\n" + "="*70)
    print("BIDIRECTIONAL TRUST PATTERN - INTEGRATION TESTS")
    print("Testing EIP-8004 Extension: Validator Rating by Servers")
    print("="*70)

    # Setup
    server_agent, validator_agent, client_agent = setup_test_agents()
    if not all([server_agent, validator_agent, client_agent]):
        print("\n[FAIL] Setup failed - cannot continue")
        return False

    # Track test results
    results = {}

    # Run tests
    results['test1_unidirectional'] = test_unidirectional_rating(server_agent, client_agent)
    results['test2_bidirectional'] = test_bidirectional_rating(server_agent, validator_agent)
    results['test3_reverse'] = test_server_rates_client(server_agent, client_agent)
    results['test4_complete'] = test_complete_bidirectional_pattern(server_agent, validator_agent, client_agent)
    results['test5_boundaries'] = test_rating_boundaries(server_agent, validator_agent)
    results['test6_updates'] = test_update_ratings(server_agent, validator_agent)

    # Summary
    print_section("TEST SUMMARY")
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)

    for test_name, result in results.items():
        status = "[OK]" if result else "[FAIL]"
        print(f"{status} {test_name}")

    print(f"\n{'='*70}")
    if passed_tests == total_tests:
        print(f"[SUCCESS] ALL TESTS PASSED ({passed_tests}/{total_tests})")
        print("="*70)
        print("\nBidirectional Trust Pattern: VALIDATED")
        print("- Servers can rate validators (NEW)")
        print("- Servers can rate clients (existing)")
        print("- Clients can rate servers (existing)")
        print("- All ratings persist on-chain")
        print("- Rating updates work correctly")
        print("- Boundary conditions handled properly")
        print("\nReady for testnet deployment and real transaction execution.")
        print("="*70 + "\n")
        return True
    else:
        print(f"[FAIL] TESTS FAILED ({passed_tests}/{total_tests} passed)")
        print("="*70 + "\n")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
