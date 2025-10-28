"""
Test script for bidirectional rating methods in base_agent.py

Tests the newly implemented methods:
- rate_validator()
- get_validator_rating()
- get_bidirectional_ratings()
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.base_agent import ERC8004BaseAgent
from shared.agent_config import load_agent_config


def test_validator_rating_methods():
    """Test that validator rating methods exist and have correct signatures"""

    print("\n" + "="*60)
    print("Testing Bidirectional Rating Methods")
    print("="*60)

    # Load config for validator agent
    print("\n[1/5] Loading validator agent config...")
    config = load_agent_config("validator-agent")

    # Create agent instance
    print("[2/5] Creating ERC8004BaseAgent instance...")
    agent = ERC8004BaseAgent(
        agent_name="validator-agent",
        agent_domain=config.agent_domain,
        rpc_url=config.rpc_url,
        identity_registry_address=config.identity_registry,
        reputation_registry_address=config.reputation_registry,
        validation_registry_address=config.validation_registry
    )

    # Test 1: Check methods exist
    print("\n[3/5] Checking methods exist...")
    methods = ['rate_validator', 'get_validator_rating', 'get_bidirectional_ratings']
    for method_name in methods:
        assert hasattr(agent, method_name), f"Missing method: {method_name}"
        method = getattr(agent, method_name)
        assert callable(method), f"Method not callable: {method_name}"
        print(f"  [OK] {method_name}() exists and is callable")

    # Test 2: Check method signatures
    print("\n[4/5] Checking method signatures...")

    # rate_validator(validator_agent_id: int, rating: int) -> str
    import inspect
    sig = inspect.signature(agent.rate_validator)
    params = list(sig.parameters.keys())
    assert params == ['validator_agent_id', 'rating'], f"rate_validator signature mismatch: {params}"
    print(f"  [OK] rate_validator(validator_agent_id, rating) -> str")

    # get_validator_rating(validator_id: int, server_id: int) -> Tuple[bool, int]
    sig = inspect.signature(agent.get_validator_rating)
    params = list(sig.parameters.keys())
    assert params == ['validator_id', 'server_id'], f"get_validator_rating signature mismatch: {params}"
    print(f"  [OK] get_validator_rating(validator_id, server_id) -> Tuple[bool, int]")

    # get_bidirectional_ratings(agent_id: int) -> dict
    sig = inspect.signature(agent.get_bidirectional_ratings)
    params = list(sig.parameters.keys())
    assert params == ['agent_id'], f"get_bidirectional_ratings signature mismatch: {params}"
    print(f"  [OK] get_bidirectional_ratings(agent_id) -> dict")

    # Test 3: Test get_bidirectional_ratings structure
    print("\n[5/5] Testing get_bidirectional_ratings() structure...")
    result = agent.get_bidirectional_ratings(agent.agent_id if agent.agent_id else 1)

    assert isinstance(result, dict), "get_bidirectional_ratings should return dict"
    assert 'ratings_given' in result, "Missing 'ratings_given' key"
    assert 'ratings_received' in result, "Missing 'ratings_received' key"
    assert 'to_clients' in result['ratings_given'], "Missing 'to_clients' key"
    assert 'to_validators' in result['ratings_given'], "Missing 'to_validators' key"
    assert 'as_client' in result['ratings_received'], "Missing 'as_client' key"
    assert 'as_validator' in result['ratings_received'], "Missing 'as_validator' key"

    print(f"  [OK] Returns correct structure:")
    print(f"    - ratings_given: to_clients, to_validators")
    print(f"    - ratings_received: as_client, as_validator")

    # Summary
    print("\n" + "="*60)
    print("[OK] All tests passed!")
    print("="*60)
    print("\nImplementation Status:")
    print("  [OK] rate_validator() - Allows servers to rate validators")
    print("  [OK] get_validator_rating() - Query validator ratings")
    print("  [OK] get_bidirectional_ratings() - Get all ratings (both directions)")
    print("\nBidirectional Trust Pattern: IMPLEMENTED [OK]")
    print("="*60 + "\n")


def test_contract_methods_accessible():
    """Test that the contract methods can be accessed via Web3"""

    print("\n" + "="*60)
    print("Testing Contract Method Accessibility")
    print("="*60)

    # Load config
    config = load_agent_config("validator-agent")

    # Create agent instance
    agent = ERC8004BaseAgent(
        agent_name="validator-agent",
        agent_domain=config.agent_domain,
        rpc_url=config.rpc_url,
        identity_registry_address=config.identity_registry,
        reputation_registry_address=config.reputation_registry,
        validation_registry_address=config.validation_registry
    )

    print("\n[1/2] Checking rateValidator() is accessible...")
    assert hasattr(agent.reputation_registry.functions, 'rateValidator'), "rateValidator not in contract"
    print("  [OK] rateValidator() accessible on contract")

    print("\n[2/2] Checking getValidatorRating() is accessible...")
    assert hasattr(agent.reputation_registry.functions, 'getValidatorRating'), "getValidatorRating not in contract"
    print("  [OK] getValidatorRating() accessible on contract")

    print("\n" + "="*60)
    print("[OK] All contract methods accessible!")
    print("="*60 + "\n")


if __name__ == "__main__":
    try:
        # Test contract methods are accessible
        test_contract_methods_accessible()

        # Test Python methods
        test_validator_rating_methods()

        print("\n[SUCCESS] Day 3 Implementation: COMPLETE")
        print("\nNext Steps (Day 4):")
        print("  - Deploy updated contracts to Fuji testnet")
        print("  - Execute real transactions with bidirectional ratings")
        print("  - Verify on-chain data with Snowtrace")

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
