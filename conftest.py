"""
KarmaKadabra V2 — Test Configuration

Configures pytest collection to skip test files with external dependencies
that may not be available in all environments.
"""

collect_ignore_glob = [
    # External API dependencies (cyberpaisa)
    "tests/test_cyberpaisa_client*.py",
    # x402 SDK tests (separate dependency chain)
    "tests/x402/**",
    # Facilitator tests (separate Python SDK)
    "tests/test_facilitator.py",
    # Bidirectional rating tests (require running server)
    "tests/test_bidirectional_rating*.py",
    "tests/test_bidirectional_transactions.py",
    # Level 2/3 integration tests (require running server + network)
    "tests/test_integration_level2.py",
    "tests/test_level3_e2e.py",
]
