# KarmaCadabra Test Report — Feb 23, 2026

## Summary

| Suite | Tests | Status |
|-------|-------|--------|
| **tests/v2/** | 988 | ✅ ALL PASSING |
| **tests/** (legacy v1) | ~35 | ❌ Import errors (crewai dependency) |
| **tests/x402/** | ~50 | ⚠️ Not run (missing deps) |
| **Total v2** | **988** | **100% pass rate** |

## V2 Test Suite (988 tests)

All 988 tests pass with Python 3.14. Run time: ~56 seconds.

### Coverage by module:
- `test_working_state.py` — Parse/write roundtrip, state mutations
- `test_coordinator_enhanced.py` — 5-factor matching, legacy fallback
- `test_performance_tracker.py` — Enhanced matching, ranking, persistence
- `test_observability.py` — Agent health, swarm metrics, trends
- `test_memory_bridge.py` — Local-first + Acontext write-through
- `test_eip8128_signer.py` — EIP-191 crypto round-trips (68 tests)
- `test_irc_client.py` — Protocol edge cases, nick collisions (70 tests)
- `test_acontext_client.py` — Graceful degradation (42 tests)
- `test_balance_monitor.py` — Balance alerts (32 tests)
- `test_health_check.py` — System health (18 tests)
- `test_em_client.py` — EM API client (33 tests)
- `test_reputation_bridge.py` — 3-layer reputation bridge
- `test_swarm_dashboard.py` — Terminal/markdown/JSON renderers
- `test_soul_fusion.py` — Personality generation
- `test_chaos.py` — Chaos/resilience tests
- ...and more

## Known Issues

1. **Python 3.9 incompatible** — Code uses `X | None` syntax (requires 3.10+). System Python is 3.9, but Homebrew Python 3.14 works fine.
2. **Legacy v1 tests** — Depend on `crewai` (v1 orchestration framework, replaced by v2). These are effectively deprecated.
3. **x402 tests** — Need `websockets` and facilitator server running. Integration tests, not unit tests.

## Recommendations

1. Add `python_requires='>=3.10'` to setup.py/pyproject.toml
2. Archive or delete legacy v1 tests (tests/test_bidirectional_*, tests/test_cyberpaisa_*)
3. Consider CI pipeline with Python 3.13+ for automated test runs
