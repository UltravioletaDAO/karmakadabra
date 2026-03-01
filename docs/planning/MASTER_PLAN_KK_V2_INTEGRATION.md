# MASTER PLAN: Karma Kadabra V2 — Full Integration

> 12 test scenarios + autonomous agent infrastructure for 24 agents on 8 chains
> Created: 2026-02-19 | Status: PENDING APPROVAL

---

## Executive Summary

This plan covers the implementation of **12 novel test scenarios** discovered during self-reflection of the KK V2 stack, plus the infrastructure needed for 24 autonomous agents to transact on Execution Market across 8 EVM chains with 5 stablecoins.

**Current State (Phases 1-14 DONE):**
- 24 HD wallets generated (6 system + 18 community)
- Multi-token allocation ($200 USDC, 5 stablecoins, 8 chains)
- 5 EM skills installed (publish, apply, approve, check-status, browse)
- EIP-8128 verifier fully implemented (verifier.py, auth.py, nonce_store.py)
- ERC-8004 reputation endpoints complete (rate_worker, rate_agent, prepare-feedback)
- Sweep/recovery script ready (sweep-funds.ts)
- Bridge script ready (bridge-from-source.ts)

**What's Missing:**
- 3 new skills (submit-evidence, rate-counterparty, register-identity)
- Self-application prevention (no validation exists)
- EIP-8128 signing library for agent-side (agents need to SIGN, not just verify)
- ERC-8004 bulk registration for 24 agents
- Cross-chain payment validation gaps
- Token mismatch handling
- Race condition protection on apply
- Rejection + resubmission flow untested
- Agent-to-agent bilateral economy test harness

---

## Phase 1: Missing Skills + Agent Auth (P0 — Foundation)

> Without these, agents cannot autonomously complete the full lifecycle.

### Task 1.1: Create `em-submit-evidence` skill
- **File**: `scripts/kk/skills/em-submit-evidence/SKILL.md` (NEW)
- **Issue**: Workers have no skill for submitting evidence after being assigned
- **Fix**: Create skill that calls `POST /api/v1/tasks/{task_id}/submissions` with evidence payload (text, photo URL, coordinates)
- **Validation**: Skill file exists and matches API contract in `mcp_server/api/routers/workers.py:68-130`

### Task 1.2: Create `em-rate-counterparty` skill
- **File**: `scripts/kk/skills/em-rate-counterparty/SKILL.md` (NEW)
- **Issue**: No skill for agents to rate each other after task completion
- **Fix**: Create skill covering both flows:
  - Agent rates worker: `POST /api/v1/reputation/rate-worker` (uses `rating_score` 0-100)
  - Worker rates agent: `POST /api/v1/reputation/rate-agent` (or prepare-feedback + confirm-feedback for on-chain)
- **Validation**: Skill matches API in `mcp_server/api/reputation.py:572-690` (rate_worker) and `:706-790` (rate_agent)

### Task 1.3: Create `em-register-identity` skill
- **File**: `scripts/kk/skills/em-register-identity/SKILL.md` (NEW)
- **Issue**: Agents need to register as workers AND get ERC-8004 identity before they can transact
- **Fix**: Create skill that calls:
  1. `POST /api/v1/workers/register` (creates executor profile)
  2. `POST /api/v1/reputation/register` (gets on-chain ERC-8004 identity via Facilitator, gasless)
- **Validation**: Skill matches API in `mcp_server/api/routers/workers.py` and `mcp_server/api/reputation.py:414-520`

### Task 1.4: Create EIP-8128 signing library for KK agents
- **File**: `scripts/kk/lib/eip8128-signer.ts` (NEW)
- **Issue**: Server can VERIFY ERC-8128 signatures (`mcp_server/integrations/erc8128/verifier.py`) but agents need a client-side library to SIGN requests
- **Fix**: Implement TypeScript library that:
  1. Takes a viem `WalletClient` (from HD wallet private key)
  2. Constructs RFC 9421 signature base from HTTP request
  3. Signs with EIP-191 personal_sign
  4. Adds `Signature` + `Signature-Input` headers
  5. Includes nonce from `GET /api/v1/auth/nonce` endpoint
- **Validation**: Unit test signs a request and Python verifier accepts it
- **Reference**: `mcp_server/integrations/erc8128/verifier.py:86-258` for expected format

### Task 1.5: Create EIP-8128 signing library for KK agents (Python)
- **File**: `scripts/kk/lib/eip8128_signer.py` (NEW)
- **Issue**: Python agents (swarm_runner.py, em_client.py) also need to sign ERC-8128 requests
- **Fix**: Python port of Task 1.4 using `eth_account` for signing
- **Validation**: Round-trip test: Python signer → Python verifier

### Task 1.6: Update `em_client.py` to use EIP-8128 auth
- **File**: `scripts/kk/services/em_client.py` (MODIFY)
- **Issue**: Current EM client uses `X-Agent-Wallet` header (plain wallet address, no crypto proof)
- **Fix**: Replace `X-Agent-Wallet` with EIP-8128 signed headers using Task 1.5's library. Accept `private_key` parameter in constructor.
- **Validation**: Client can create tasks on production API with EIP-8128 auth

### Task 1.7: Migrate API routes to `verify_agent_auth()`
- **File**: `mcp_server/api/routers/tasks.py:18-22`, `submissions.py`, `workers.py`, `misc.py` (MODIFY)
- **Issue**: Routes still use old `verify_api_key_if_required()` / `verify_api_key_optional()`. The unified `verify_agent_auth()` function exists at `auth.py:492-570` but is NOT wired into any route. EIP-8128 signed requests will authenticate but route dependencies won't use the result.
- **Fix**: In each router file:
  1. Replace `from ..auth import verify_api_key_if_required, APIKeyData` with `from ..auth import verify_agent_auth, AgentAuth`
  2. Change `Depends(verify_api_key_if_required)` → `Depends(verify_agent_auth)`
  3. Update function signatures: `api_key_data: APIKeyData` → `auth: AgentAuth`
  4. Access `auth.agent_id`, `auth.wallet_address`, `auth.auth_method`
- **Validation**: `test_erc8128_auth_on_task_creation` — EIP-8128 signed POST to `/api/v1/tasks` returns 200

### Task 1.8: Add nonce endpoint for EIP-8128
- **File**: `mcp_server/api/routers/misc.py` (MODIFY)
- **Issue**: No `GET /api/v1/auth/erc8128/nonce` endpoint. Agents need fresh nonces for replay protection. Function `generate_auth_nonce()` exists at `auth.py:578-589` but has no route.
- **Fix**: Add route:
  ```python
  @router.get("/api/v1/auth/erc8128/nonce")
  async def get_erc8128_nonce():
      return await generate_auth_nonce()
  ```
- **Validation**: `GET /api/v1/auth/erc8128/nonce` returns `{"nonce": "...", "ttl_seconds": 300}`

### Task 1.9: Deploy DynamoDB nonce table (Terraform)
- **File**: `infrastructure/terraform/dynamodb.tf` (NEW)
- **Issue**: `nonce_store.py` references DynamoDB table `em-production-nonce-store` but table doesn't exist in AWS. Currently falls back to in-memory store.
- **Fix**: Terraform resource for DynamoDB table with TTL on `expires_at`, PAY_PER_REQUEST billing. Add IAM policy to ECS task role.
- **Validation**: `aws dynamodb describe-table --table-name em-production-nonce-store` returns table info

---

## Phase 2: Self-Protection + Race Conditions (P0 — Security)

> Critical bugs that 24 agents will hit immediately.

### Task 2.1: Add self-application prevention (agent_id level)
- **File**: `mcp_server/supabase_client.py:417-505` + `mcp_server/api/routers/workers.py:43-58` (MODIFY)
- **Issue**: `apply_to_task()` at `supabase_client.py:456-465` checks `executor_id` against existing applications but does NOT compare `executor_id != task.agent_id`. An agent can apply to its own task because the check only prevents duplicate applications, not self-applications. With 24 agents sharing the same API, this WILL happen.
- **Fix**: Add guard at `supabase_client.py:430` (after task fetch):
  ```python
  # Block self-application: agent cannot execute own task
  if str(executor_id).lower() == str(task.get("agent_id", "")).lower():
      raise Exception("Cannot apply to your own task")
  ```
  Also add HTTP-level guard in `workers.py:apply_to_task()` to return clean 403 before hitting DB.
- **Validation**: `test_self_application_rejected` — agent creates task, tries to apply with same wallet, gets 403

### Task 2.2: Add self-application prevention in MCP tool
- **File**: `mcp_server/server.py` (MODIFY, find `em_apply_task` tool)
- **Issue**: MCP tool `em_apply_task` also needs self-application guard
- **Fix**: Same wallet comparison as Task 2.1 in the MCP tool handler
- **Validation**: `test_mcp_self_application_rejected`

### Task 2.3: Race condition protection on task application
- **File**: `supabase/migrations/` (NEW migration) + `mcp_server/supabase_client.py:460-478` (MODIFY)
- **Issue**: `apply_to_task()` reads existing applications at line 460 then inserts at line 478 — NO transaction isolation, NO `SELECT FOR UPDATE`, NO unique constraint. Between check and insert, another agent can insert. All 5 succeed. PostgreSQL RLS is enabled but doesn't prevent this race.
- **Fix**:
  1. Add unique constraint migration:
     ```sql
     ALTER TABLE task_applications
     ADD CONSTRAINT unique_task_executor UNIQUE(task_id, executor_id);
     ```
  2. Catch constraint violation in `supabase_client.py:493` and return HTTP 409 "Already applied"
- **Validation**: `test_concurrent_applications` — 5 parallel applies, exactly 5 unique applications created, no duplicates

### Task 2.4: Add `payment_token` field to task creation
- **File**: `mcp_server/api/routers/_models.py:75` (MODIFY `CreateTaskRequest`)
- **Issue**: Tasks specify `payment_network` but not which stablecoin. With 5 tokens per chain, this is ambiguous. Currently defaults to USDC.
- **Fix**: Add optional `payment_token: str = Field(default="USDC", max_length=10)` to CreateTaskRequest. Validate against `NETWORK_CONFIG[network]["tokens"]`.
- **Validation**: `test_create_task_with_eurc` — create task with `payment_token="EURC"` on Base

### Task 2.5: Validate payment_token exists on target network
- **File**: `mcp_server/api/routers/tasks.py:370-380` (MODIFY)
- **Issue**: No validation that the requested token actually exists on the payment network
- **Fix**: After `validate_payment_network()`, add `validate_payment_token(network, token)` that checks `NETWORK_CONFIG[network]["tokens"][token]` exists
- **Validation**: `test_invalid_token_for_network` — PYUSD on Base returns 400 (PYUSD only on Ethereum)

---

## Phase 3: ERC-8004 Bulk Registration + Reputation (P0 — Identity)

> All 24 agents need on-chain identity before they can rate each other.

### Task 3.1: Bulk ERC-8004 registration script
- **File**: `scripts/kk/register-agents-erc8004.ts` (MODIFY — file exists but may need updates)
- **Issue**: All 24 agents need ERC-8004 identity on Base (minimum). Script exists but needs to handle bulk registration via Facilitator gasless endpoint.
- **Fix**: Update to:
  1. Load wallets from `config/wallets.json`
  2. For each wallet, call `POST /api/v1/reputation/register` with wallet address
  3. Store returned `agent_id` in a new `config/identities.json`
  4. Handle rate limiting (sleep 2s between calls)
  5. Report: N registered, M already registered, K failed
- **Validation**: Run script → all 24 agents have ERC-8004 agent IDs

### Task 3.2: Multi-chain ERC-8004 registration
- **File**: `scripts/kk/register-agents-erc8004.ts` (MODIFY)
- **Issue**: Agents operate on 8 chains. ERC-8004 identity should be registered on all chains where the agent will transact.
- **Fix**: Add `--networks` flag that registers each agent on multiple networks via Facilitator
- **Validation**: Agent has identity on Base, Polygon, Arbitrum (minimum 3)

### Task 3.3: Add reputation skill to agent SOUL templates
- **File**: `scripts/kk/generate-soul.py` (MODIFY)
- **Issue**: Agent SOULs don't mention reputation system. Agents need to know they MUST rate every counterparty.
- **Fix**: Add to SOUL template:
  - "After every completed task, ALWAYS rate the counterparty (0-100 score)"
  - "Your reputation score affects which tasks you can get assigned"
  - Link to `em-rate-counterparty` skill
- **Validation**: Generated SOUL.md files contain reputation instructions

### Task 3.4: Generate relay wallets for autonomous agent-to-agent reputation
- **File**: `scripts/kk/generate-wallets.ts` (MODIFY)
- **Issue**: Current `rate_agent()` returns `pending_signature` — worker must manually sign TX. With 24 autonomous agents, this blocks the entire reputation flow. Each agent needs a **relay wallet** that can sign `giveFeedback()` directly without triggering the ERC-8004 self-feedback revert.
- **Fix**: For each agent wallet, derive a second "relay" wallet at index `agent_index + 100` (e.g., agent 0 → relay at m/44'/60'/0'/0/100). Store in `config/wallets.json` as `relay_address` + `relay_index` per agent.
- **Validation**: Each agent has 2 addresses in wallets.json: `address` (main) + `relay_address` (reputation)
- **Reference**: `mcp_server/integrations/erc8004/direct_reputation.py:83-210` (give_feedback_direct accepts private_key override)

### Task 3.5: Modify `rate_agent()` for autonomous direct signing
- **File**: `mcp_server/integrations/erc8004/facilitator_client.py:866-934` (MODIFY)
- **Issue**: `rate_agent()` always returns `pending_signature`. For autonomous agents, it should accept an optional `relay_private_key` and call `give_feedback_direct()` when provided.
- **Fix**: Add `relay_private_key: Optional[str] = None` parameter. If provided, call `give_feedback_direct(agent_id, ..., private_key=relay_private_key)` and return `success=True, transaction_hash=tx_hash`.
- **Validation**: `test_rate_agent_with_relay_wallet` — relay wallet signs directly, TX hash returned

### Task 3.6: Update MCP tool `em_rate_agent` for autonomous flow
- **File**: `mcp_server/tools/reputation_tools.py:216-316` (MODIFY)
- **Issue**: MCP tool returns pending_signature. Autonomous agents calling via MCP need full on-chain completion.
- **Fix**: In `em_rate_agent()`, check if calling agent has relay key in env/config. If yes, pass to `rate_agent(relay_private_key=key)`. Return TX hash.
- **Validation**: MCP tool returns TX hash, not pending_signature

### Task 3.7: Create reputation leaderboard query
- **File**: `scripts/kk/lib/reputation-query.ts` (NEW)
- **Issue**: No way to see reputation standings across all 24 agents
- **Fix**: Script that queries `GET /api/v1/reputation/score/{wallet}` for each agent wallet and outputs a sorted leaderboard
- **Validation**: Outputs table with all 24 agents, scores, and tier

---

## Phase 4: Test Scenarios 1-6 (P1 — Core Scenarios)

> The first 6 of 12 novel scenarios. Each gets a dedicated test.

### Task 4.1: Test — Cross-chain task lifecycle
- **File**: `mcp_server/tests/test_kk_scenarios.py` (NEW)
- **Scenario**: Agent A publishes task on Polygon (`payment_network=polygon`), Agent B on Base applies and completes it. Payment settles on Polygon.
- **Test**: `test_cross_chain_task_lifecycle`
- **What to verify**: Task creation with non-default network, escrow lock on correct chain, payment release on correct chain
- **Reference**: `mcp_server/api/routers/tasks.py:370-490` (task creation with payment_network)

### Task 4.2: Test — Self-application prevention
- **File**: `mcp_server/tests/test_kk_scenarios.py` (ADD)
- **Scenario**: Agent A publishes task, Agent A tries to apply to own task
- **Test**: `test_self_application_rejected`
- **What to verify**: 403 returned, application not created
- **Depends**: Task 2.1

### Task 4.3: Test — Concurrent applications race condition
- **File**: `mcp_server/tests/test_kk_scenarios.py` (ADD)
- **Scenario**: 5 agents apply simultaneously to the same task
- **Test**: `test_concurrent_applications`
- **What to verify**: All 5 applications created, no duplicates, assignment is atomic
- **Depends**: Task 2.3

### Task 4.4: Test — Token mismatch on approval
- **File**: `mcp_server/tests/test_kk_scenarios.py` (ADD)
- **Scenario**: Task created with `payment_token=EURC`, but approval tries to settle with USDC
- **Test**: `test_token_mismatch_on_approval`
- **What to verify**: PaymentDispatcher uses task's token, not a default. `payment_dispatcher.py:486-509` (`_authorize_fase1`) does balance check but doesn't verify token type. Line 549 reads `request.payment_token or "USDC"` without cross-referencing task's token.
- **Reference**: `mcp_server/integrations/x402/payment_dispatcher.py:450-550`
- **Fix needed**: Pass `task.payment_token` to `release_payment()` and validate in settlement flow

### Task 4.5: Test — Rejection + resubmission flow
- **File**: `mcp_server/tests/test_kk_scenarios.py` (ADD)
- **Scenario**: Worker submits, agent rejects with feedback, worker resubmits improved evidence
- **Test**: `test_rejection_resubmission_flow`
- **What to verify**: Task goes submitted→rejected→submitted→completed. Worker can resubmit after rejection. Rating still works after resubmission.
- **Gap found**: `supabase_client.py:543-544` validates evidence but has NO deadline re-check on resubmission. Worker can resubmit 3 days after deadline.
- **Reference**: `mcp_server/api/routers/submissions.py` (reject_submission), `supabase_client.py:507-575` (submit_work)

### Task 4.6: Test — Task expiry with escrow locked
- **File**: `mcp_server/tests/test_kk_scenarios.py` (ADD)
- **Scenario**: Task created with escrow lock, deadline passes, task expires
- **Test**: `test_expiry_with_escrow_refund`
- **What to verify**: Escrow refund triggered on expiry. Agent gets funds back. Task status = expired.
- **Gap found**: NO automatic expiry background job exists. `expire_tasks()` RPC exists in Supabase but nothing calls it. Tasks stay PUBLISHED forever if no one cancels. Refund is async/best-effort only.
- **Reference**: `mcp_server/api/routers/_helpers.py:1189` (escrow handling), `payment_dispatcher.py:135-220` (REFUNDABLE_ESCROW_STATUSES)

---

## Phase 5: Test Scenarios 7-12 (P1 — Advanced Scenarios)

> The remaining 6 novel scenarios. More complex interactions.

### Task 5.1: Test — Reputation without transaction
- **File**: `mcp_server/tests/test_kk_scenarios.py` (ADD)
- **Scenario**: Agent tries to rate another agent without having completed a task together
- **Test**: `test_rate_without_transaction`
- **What to verify**: Rating endpoint should reject if no completed submission exists for the task. Currently `POST /api/v1/reputation/rate-worker` accepts ANY task_id without verifying `submission.agent_verdict == "accepted"`. No transaction hash check either.
- **Gap found**: No proof-of-work requirement. Agent can rate worker who never did work → ERC-8004 reputation inflation.
- **Reference**: `mcp_server/api/reputation.py:572-630`, needs `submission_id` validation

### Task 5.2: Test — Bilateral task economy
- **File**: `mcp_server/tests/test_kk_scenarios.py` (ADD)
- **Scenario**: Agent A creates task for B, Agent B creates task for A. Both complete. Circular economy.
- **Test**: `test_bilateral_task_economy`
- **What to verify**: Both tasks complete independently. Both agents rate each other. Reputation updates for both.

### Task 5.3: Test — EIP-8128 auth without ERC-8004 identity
- **File**: `mcp_server/tests/test_kk_scenarios.py` (ADD)
- **Scenario**: Agent signs request with EIP-8128 but has no ERC-8004 registration
- **Test**: `test_eip8128_auth_without_erc8004`
- **What to verify**: Auth succeeds (wallet verified), but `erc8004_registered=False` in AgentAuth. Agent can still create tasks but reputation operations may fail.
- **Reference**: `mcp_server/api/auth.py:519-534` (cross-reference with ERC-8004)

### Task 5.4: Test — Insufficient funds during escrow release
- **File**: `mcp_server/tests/test_kk_scenarios.py` (ADD)
- **Scenario**: Agent creates task, escrow locked. Before approval, agent's balance drops (spent on another task).
- **Test**: `test_insufficient_funds_during_release`
- **What to verify**: Fase 2 (escrow): release succeeds (funds already locked). Fase 1 (direct): settlement fails with clear error.
- **Gap found**: `payment_dispatcher.py:486-509` does balance check at CREATION but NOT at approval. `_settle_submission_payment()` at line 550 calls `_compute_treasury_remainder()` without verifying agent still has funds. Task gets marked COMPLETED but payment never settles.
- **Fix needed**: Add balance re-check in `_settle_submission_payment()` before settlement. If insufficient, mark task FAILED_PAYMENT.

### Task 5.5: Test — Cross-chain approval
- **File**: `mcp_server/tests/test_kk_scenarios.py` (ADD)
- **Scenario**: Task published on Base, but the approval request comes with payment context from Polygon
- **Test**: `test_cross_chain_approval_mismatch`
- **What to verify**: System uses task's `payment_network` for settlement, not the approval request's context.
- **Gap found**: `submissions.py:150-250` reads `task.get("payment_network")` but NEVER verifies the EIP-3009 settlement signature is for that chain. Chain-specific signatures fail silently. Reputation feedback at line 462 hardcodes `network=task.get("payment_network", "base")` without validating settlement happened on that network.
- **Fix needed**: Add `X-Settlement-Chain` header validation or derive chain from EIP-8128 auth `chain_id`.

### Task 5.6: Test — Token denomination mismatch
- **File**: `mcp_server/tests/test_kk_scenarios.py` (ADD)
- **Scenario**: Task bounty in EURC ($0.10), worker only has USDC. Can the worker receive payment in EURC?
- **Test**: `test_token_denomination_mismatch`
- **What to verify**: Worker receives EURC (task's token), not USDC.
- **Gap found**: `payment_dispatcher.py:450-509` doesn't validate token parameter matches task. Settlement defaults to USDC. No token parameter passed to `release_payment()`. Worker could receive wrong stablecoin.
- **Fix needed**: Pass `task.payment_token` through entire settlement pipeline. Validate token exists on network in SDK call.

---

## Phase 6: Integration Harness + Golden Flow (P1 — E2E)

> Bring it all together. Full swarm test.

### Task 6.1: Create KK V2 integration test harness
- **File**: `scripts/kk/tests/test_integration.py` (NEW)
- **Issue**: No automated test that runs the full agent-to-agent flow
- **Fix**: Python script that:
  1. Creates 3 test agents (from first 3 wallets)
  2. Registers all 3 as workers + ERC-8004
  3. Agent A publishes task on Base
  4. Agent B applies + gets assigned
  5. Agent B submits evidence
  6. Agent A approves + payment settles
  7. Agent A rates Agent B
  8. Agent B rates Agent A
  9. Verify: reputation updated for both
- **Validation**: Script passes end-to-end on production API

### Task 6.2: Create multi-chain integration test
- **File**: `scripts/kk/tests/test_multichain_integration.py` (NEW)
- **Issue**: Need to test the same flow across multiple chains
- **Fix**: Parameterized version of Task 6.1 that runs on Base, Polygon, Arbitrum, Avalanche (the 4 chains with passing Golden Flow)
- **Validation**: All 4 chains pass

### Task 6.3: Create chaos test scenarios
- **File**: `scripts/kk/tests/test_chaos.py` (NEW)
- **Issue**: Agents need to intentionally break things
- **Fix**: Script with deliberate failure scenarios:
  - Double-submit (submit evidence twice)
  - Apply after deadline
  - Approve with wrong submission_id
  - Cancel after assignment
  - Rate with score > 100
- **Validation**: All chaos scenarios return appropriate error codes

### Task 6.4: Update Golden Flow for multi-token support
- **File**: `scripts/e2e_golden_flow.py` (MODIFY)
- **Issue**: Golden Flow only tests USDC. Needs to test EURC, AUSD, USDT too.
- **Fix**: Add `--token` flag. When `--token=EURC`, create task with `payment_token=EURC` and verify EURC settlement.
- **Validation**: `python scripts/e2e_golden_flow.py --token EURC --network base` passes

### Task 6.5: Create swarm coordinator test
- **File**: `scripts/kk/tests/test_swarm_coordinator.py` (NEW)
- **Issue**: Need to test that the coordinator agent can orchestrate 24 agents
- **Fix**: Simulated swarm test that:
  1. Creates 6 tasks (one per system agent)
  2. 18 community agents compete to apply
  3. 6 get assigned, 12 don't
  4. Verify: all 6 complete, all rate each other
  5. Verify: reputation leaderboard changes
- **Validation**: Coordinator reports all tasks completed

---

## Dependency Graph

```
Phase 1 (Foundation) ──┬──> Phase 2 (Security) ──┬──> Phase 4 (Scenarios 1-6)
                       │                          │
                       └──> Phase 3 (Identity) ───┘──> Phase 5 (Scenarios 7-12)
                                                            │
                                                            v
                                                   Phase 6 (Integration)
```

## Summary

| Phase | Tasks | Priority | Depends On |
|-------|-------|----------|------------|
| 1. Missing Skills + Agent Auth + Route Migration | 9 | P0 | None |
| 2. Self-Protection + Race Conditions | 5 | P0 | None |
| 3. ERC-8004 Bulk Registration + Relay Wallets | 7 | P0 | Phase 1 (skills) |
| 4. Test Scenarios 1-6 | 6 | P1 | Phase 2 (guards) |
| 5. Test Scenarios 7-12 | 6 | P1 | Phase 1, 2, 3 |
| 6. Integration Harness | 5 | P1 | Phase 4, 5 |
| **TOTAL** | **38** | | |

## Notes

- **EIP-8128 verifier is FULLY IMPLEMENTED** server-side (721 lines, 80 tests). BUT: routes NOT migrated to `verify_agent_auth()`, nonce endpoint missing, DynamoDB table not deployed. Tasks 1.7-1.9 cover these gaps.
- **ERC-8004 reputation is FULLY IMPLEMENTED** server-side (rate_worker, rate_agent, prepare-feedback, confirm-feedback). Agents need skills + registration.
- **Self-application prevention does NOT exist** — will be hit immediately with 24 agents.
- **`payment_token` field does NOT exist** on tasks — all tasks default to USDC. Must add for multi-token testing.
- **Concurrent application protection** relies on Supabase RPC `apply_to_task` — needs verification of atomicity guarantees.
- **Autonomous agent-to-agent reputation BLOCKED**: `rate_agent()` returns `pending_signature` requiring manual wallet signing. Fix: relay wallets that sign `giveFeedback()` directly (Tasks 3.4-3.6).
- **Relay wallet architecture**: Each agent gets a second wallet at BIP-44 index+100. The relay wallet doesn't own any agent NFT, so it can call `giveFeedback()` without self-feedback revert. Reference: `direct_reputation.py:83-210`.
