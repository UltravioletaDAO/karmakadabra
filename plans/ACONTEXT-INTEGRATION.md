# Acontext Integration Strategy (KK V2 Swarm)

*Pre-Dawn Synthesis: March 4, 2026*

## Current Status
- `lib/acontext_client.py` is written and ready.
- Acontext SDK wrappers for the swarm are prepped.
- Integration tests are written but skipped/blocked pending local Acontext Docker stack.

## Next Steps for Unblocking
1. **Bring up Acontext Server:** Once the Docker blocker is resolved, run `acontext server up`.
2. **API Key Provisioning:** Grab the root key from Acontext and inject it into `karmakadabra/.env` as `ACONTEXT_API_KEY`.
3. **Run Full Tests:** Execute `pytest tests/v2/test_acontext_client.py -v`.
4. **Agent Hookup:** In `swarm_orchestrator.py`, uncomment the Acontext session initialization block so every agent spawn automatically gets a tracked Acontext workspace.

## Why this matters for the Swarm
Acontext gives every agent a verifiable, compressed context window. Instead of paying LLM token costs for the entire agent's lifetime of memories, Acontext summarizes and injects only what's necessary, bridging nicely with the ERC-8004 reputation system.
