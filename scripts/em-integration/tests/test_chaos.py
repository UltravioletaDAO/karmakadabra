"""
Karma Kadabra V2 -- Phase 6, Task 6.3: Chaos Test Scenarios

Deliberately breaks things to verify the API handles edge cases correctly.
Each scenario sends a malformed or out-of-order request and verifies the
server responds with the appropriate HTTP error code.

12 scenarios:
  1. Double-submit evidence
  2. Apply after deadline (expired task)
  3. Approve with wrong submission_id
  4. Cancel after assignment
  5. Rate with score > 100
  6. Rate with score < 0
  7. Self-application (agent applies to own task)
  8. Apply to non-existent task
  9. Submit without assignment
 10. Invalid payment token
 11. Invalid network
 12. Empty evidence

Usage:
  python scripts/kk/tests/test_chaos.py
  python scripts/kk/tests/test_chaos.py --dry-run
  python scripts/kk/tests/test_chaos.py --api-url https://api.execution.market
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env.local")
load_dotenv(_PROJECT_ROOT / "mcp_server" / ".env")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEFAULT_API_URL = "https://api.execution.market"

# A well-known test executor that exists in Supabase
FALLBACK_EXECUTOR_ID = "33333333-3333-3333-3333-333333333333"

# Tiny bounty -- safe for testing (Fase 1 = balance check only, no real cost)
TEST_BOUNTY = 0.10


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------
class ChaosResult:
    """Result of a single chaos scenario."""

    def __init__(
        self,
        name: str,
        expected: str,
        actual_status: int | None,
        passed: bool,
        details: str = "",
    ):
        self.name = name
        self.expected = expected
        self.actual_status = actual_status
        self.passed = passed
        self.details = details

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "expected": self.expected,
            "actual_status": self.actual_status,
            "passed": self.passed,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
async def api(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    json_data: dict | None = None,
    api_url: str = DEFAULT_API_URL,
    api_key: str = "",
) -> tuple[int, dict]:
    """Send an API request and return (status_code, body_dict)."""
    url = f"{api_url.rstrip('/')}/api/v1{path}"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    resp = await client.request(method, url, json=json_data, headers=headers)
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}
    return resp.status_code, body


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------------------
# Precondition helpers -- create tasks in specific states
# ---------------------------------------------------------------------------
async def _create_task(
    client: httpx.AsyncClient,
    api_url: str,
    api_key: str,
    title_suffix: str = "",
    deadline_hours: int = 1,
    payment_network: str = "base",
    payment_token: str = "USDC",
) -> tuple[int, dict]:
    """Create a fresh task. Returns (status_code, body)."""
    return await api(
        client,
        "POST",
        "/tasks",
        {
            "title": f"Chaos Test {title_suffix} {_ts()}"[:255],
            "instructions": "Automated chaos test -- this task is for integration testing purposes only.",
            "category": "simple_action",
            "bounty_usd": TEST_BOUNTY,
            "deadline_hours": deadline_hours,
            "evidence_required": ["text_response"],
            "payment_network": payment_network,
            "payment_token": payment_token,
        },
        api_url=api_url,
        api_key=api_key,
    )


async def _apply_to_task(
    client: httpx.AsyncClient,
    api_url: str,
    api_key: str,
    task_id: str,
    executor_id: str = FALLBACK_EXECUTOR_ID,
) -> tuple[int, dict]:
    return await api(
        client,
        "POST",
        f"/tasks/{task_id}/apply",
        {"executor_id": executor_id, "message": "Chaos test application"},
        api_url=api_url,
        api_key=api_key,
    )


async def _assign_worker(
    client: httpx.AsyncClient,
    api_url: str,
    api_key: str,
    task_id: str,
    executor_id: str = FALLBACK_EXECUTOR_ID,
) -> tuple[int, dict]:
    return await api(
        client,
        "POST",
        f"/tasks/{task_id}/assign",
        {"executor_id": executor_id, "notes": "Chaos test assignment"},
        api_url=api_url,
        api_key=api_key,
    )


async def _submit_evidence(
    client: httpx.AsyncClient,
    api_url: str,
    api_key: str,
    task_id: str,
    executor_id: str = FALLBACK_EXECUTOR_ID,
    evidence: dict | None = None,
) -> tuple[int, dict]:
    return await api(
        client,
        "POST",
        f"/tasks/{task_id}/submit",
        {
            "executor_id": executor_id,
            "evidence": evidence or {"text_response": "Chaos test evidence"},
            "notes": "Chaos test submission",
        },
        api_url=api_url,
        api_key=api_key,
    )


# ---------------------------------------------------------------------------
# Scenario implementations
# ---------------------------------------------------------------------------


async def chaos_double_submit(
    client: httpx.AsyncClient, api_url: str, api_key: str
) -> ChaosResult:
    """Scenario 1: Submit evidence to the same task twice."""
    name = "double_submit"
    expected = "409 or 400 on second submit"

    # Precondition: create -> apply -> assign -> submit (first time)
    status, body = await _create_task(client, api_url, api_key, "double-submit")
    if status != 201:
        return ChaosResult(
            name, expected, status, False, f"Setup: task creation failed ({status})"
        )
    task_id = body.get("id")

    status, _ = await _apply_to_task(client, api_url, api_key, task_id)
    if status not in (200, 201):
        return ChaosResult(
            name, expected, status, False, f"Setup: apply failed ({status})"
        )

    status, _ = await _assign_worker(client, api_url, api_key, task_id)
    if status not in (200, 201):
        return ChaosResult(
            name, expected, status, False, f"Setup: assign failed ({status})"
        )

    status, _ = await _submit_evidence(client, api_url, api_key, task_id)
    if status not in (200, 201):
        return ChaosResult(
            name, expected, status, False, f"Setup: first submit failed ({status})"
        )

    # Chaos: submit again
    status2, body2 = await _submit_evidence(client, api_url, api_key, task_id)
    passed = status2 in (400, 409)
    detail = body2.get("detail", str(body2)[:200])
    return ChaosResult(name, expected, status2, passed, detail)


async def chaos_apply_after_deadline(
    client: httpx.AsyncClient, api_url: str, api_key: str
) -> ChaosResult:
    """Scenario 2: Apply to an expired task.

    We cannot easily create a truly expired task via the API (min deadline is 1h),
    so we create a task and immediately cancel it, then try to apply. A cancelled
    task should reject applications the same way an expired one would.
    """
    name = "apply_after_deadline"
    expected = "400 or 409 (task not available)"

    status, body = await _create_task(client, api_url, api_key, "apply-expired")
    if status != 201:
        return ChaosResult(
            name, expected, status, False, f"Setup: task creation failed ({status})"
        )
    task_id = body.get("id")

    # Cancel the task so it's no longer available
    status_cancel, _ = await api(
        client, "POST", f"/tasks/{task_id}/cancel", api_url=api_url, api_key=api_key
    )
    if status_cancel != 200:
        return ChaosResult(
            name,
            expected,
            status_cancel,
            False,
            f"Setup: cancel failed ({status_cancel})",
        )

    # Chaos: try to apply to the cancelled/expired task
    status2, body2 = await _apply_to_task(client, api_url, api_key, task_id)
    passed = status2 in (400, 404, 409)
    detail = body2.get("detail", str(body2)[:200])
    return ChaosResult(name, expected, status2, passed, detail)


async def chaos_approve_wrong_submission(
    client: httpx.AsyncClient, api_url: str, api_key: str
) -> ChaosResult:
    """Scenario 3: Approve a submission that doesn't exist."""
    name = "approve_wrong_submission"
    expected = "404 or 400"

    fake_submission_id = str(uuid.uuid4())
    status, body = await api(
        client,
        "POST",
        f"/submissions/{fake_submission_id}/approve",
        {"notes": "Chaos test -- wrong submission", "rating_score": 80},
        api_url=api_url,
        api_key=api_key,
    )
    passed = status in (400, 403, 404)
    detail = body.get("detail", str(body)[:200])
    return ChaosResult(name, expected, status, passed, detail)


async def chaos_cancel_after_assignment(
    client: httpx.AsyncClient, api_url: str, api_key: str
) -> ChaosResult:
    """Scenario 4: Cancel a task after a worker has been assigned.

    In platform_release mode, only 'published' tasks can be cancelled.
    In direct_release mode, 'published' and 'accepted' can be cancelled.
    Either way, after assignment the task should be in 'accepted' or 'in_progress'
    and may be non-cancellable depending on config.
    """
    name = "cancel_after_assignment"
    expected = "409 (task not cancellable in accepted/in_progress status)"

    status, body = await _create_task(client, api_url, api_key, "cancel-assigned")
    if status != 201:
        return ChaosResult(
            name, expected, status, False, f"Setup: task creation failed ({status})"
        )
    task_id = body.get("id")

    status, _ = await _apply_to_task(client, api_url, api_key, task_id)
    if status not in (200, 201):
        return ChaosResult(
            name, expected, status, False, f"Setup: apply failed ({status})"
        )

    status, _ = await _assign_worker(client, api_url, api_key, task_id)
    if status not in (200, 201):
        return ChaosResult(
            name, expected, status, False, f"Setup: assign failed ({status})"
        )

    # Chaos: try to cancel
    status2, body2 = await api(
        client, "POST", f"/tasks/{task_id}/cancel", api_url=api_url, api_key=api_key
    )
    # Strict: only 409 means the guard is active. HTTP 200 means no guard
    # triggered (possible in direct_release mode where accepted tasks are
    # cancellable — but that should still be tested separately, not here).
    passed = status2 == 409
    detail = body2.get("detail", body2.get("message", str(body2)[:200]))
    extra = ""
    if status2 == 200:
        extra = (
            " (NOTE: direct_release mode may allow accepted cancels — verify config)"
        )
    return ChaosResult(name, expected, status2, passed, f"{detail}{extra}")


async def chaos_rate_score_above_100(
    client: httpx.AsyncClient, api_url: str, api_key: str
) -> ChaosResult:
    """Scenario 5: Rate with score > 100 (max is 100)."""
    name = "rate_score_above_100"
    expected = "400 or 422 (validation error)"

    fake_task_id = str(uuid.uuid4())
    status, body = await api(
        client,
        "POST",
        "/reputation/agents/rate",
        {
            "agent_id": 2106,
            "task_id": fake_task_id,
            "score": 150,
            "comment": "Chaos test -- score too high",
        },
        api_url=api_url,
        api_key=api_key,
    )
    passed = status in (400, 422)
    detail = str(body.get("detail", body))[:200]
    return ChaosResult(name, expected, status, passed, detail)


async def chaos_rate_score_below_0(
    client: httpx.AsyncClient, api_url: str, api_key: str
) -> ChaosResult:
    """Scenario 6: Rate with score < 0 (min is 0)."""
    name = "rate_score_below_0"
    expected = "400 or 422 (validation error)"

    fake_task_id = str(uuid.uuid4())
    status, body = await api(
        client,
        "POST",
        "/reputation/agents/rate",
        {
            "agent_id": 2106,
            "task_id": fake_task_id,
            "score": -10,
            "comment": "Chaos test -- negative score",
        },
        api_url=api_url,
        api_key=api_key,
    )
    passed = status in (400, 422)
    detail = str(body.get("detail", body))[:200]
    return ChaosResult(name, expected, status, passed, detail)


async def chaos_self_application(
    client: httpx.AsyncClient, api_url: str, api_key: str
) -> ChaosResult:
    """Scenario 7: Agent tries to apply to their own task.

    Self-application prevention may not exist yet (noted in MEMORY.md).
    We accept 403 as the ideal response, but also treat 200/201 as an
    informational result (documents the gap).
    """
    name = "self_application"
    expected = "403 (self-apply blocked)"

    status, body = await _create_task(client, api_url, api_key, "self-apply")
    if status != 201:
        return ChaosResult(
            name, expected, status, False, f"Setup: task creation failed ({status})"
        )
    task_id = body.get("id")

    # The agent_id used for this task is the API key's identity.
    # We try to apply with the same identity. This requires an executor_id
    # linked to the agent wallet -- use a dummy that the server may or may
    # not recognize as the agent.
    status2, body2 = await _apply_to_task(client, api_url, api_key, task_id)
    if status2 == 403:
        passed = True
        detail = body2.get("detail", "Self-application correctly blocked")
    elif status2 in (200, 201):
        # Self-application prevention does not exist yet -- document this
        passed = False
        detail = (
            "KNOWN GAP: self-application prevention not implemented (see MEMORY.md)"
        )
    else:
        passed = status2 in (400, 409)
        detail = body2.get("detail", str(body2)[:200])
    return ChaosResult(name, expected, status2, passed, detail)


async def chaos_apply_nonexistent_task(
    client: httpx.AsyncClient, api_url: str, api_key: str
) -> ChaosResult:
    """Scenario 8: Apply to a task that doesn't exist."""
    name = "apply_nonexistent_task"
    expected = "404"

    fake_task_id = str(uuid.uuid4())
    status, body = await _apply_to_task(client, api_url, api_key, fake_task_id)
    passed = status == 404
    detail = body.get("detail", str(body)[:200])
    return ChaosResult(name, expected, status, passed, detail)


async def chaos_submit_without_assignment(
    client: httpx.AsyncClient, api_url: str, api_key: str
) -> ChaosResult:
    """Scenario 9: Submit evidence to a task you're not assigned to."""
    name = "submit_without_assignment"
    expected = "403 or 400 or 409"

    # Create task but do NOT assign anyone
    status, body = await _create_task(client, api_url, api_key, "submit-unassigned")
    if status != 201:
        return ChaosResult(
            name, expected, status, False, f"Setup: task creation failed ({status})"
        )
    task_id = body.get("id")

    # Chaos: submit evidence without being assigned
    status2, body2 = await _submit_evidence(client, api_url, api_key, task_id)
    passed = status2 in (400, 403, 409)
    detail = body2.get("detail", str(body2)[:200])
    return ChaosResult(name, expected, status2, passed, detail)


async def chaos_invalid_payment_token(
    client: httpx.AsyncClient, api_url: str, api_key: str
) -> ChaosResult:
    """Scenario 10: Create task with payment_token='FAKE'."""
    name = "invalid_payment_token"
    expected = "400 (invalid token)"

    status, body = await _create_task(
        client, api_url, api_key, "invalid-token", payment_token="FAKE"
    )
    passed = status == 400
    detail = body.get("detail", str(body)[:200])
    return ChaosResult(name, expected, status, passed, detail)


async def chaos_invalid_network(
    client: httpx.AsyncClient, api_url: str, api_key: str
) -> ChaosResult:
    """Scenario 11: Create task with payment_network='imaginary'."""
    name = "invalid_network"
    expected = "400 (invalid network)"

    status, body = await _create_task(
        client, api_url, api_key, "invalid-network", payment_network="imaginary"
    )
    passed = status == 400
    detail = body.get("detail", str(body)[:200])
    return ChaosResult(name, expected, status, passed, detail)


async def chaos_empty_evidence(
    client: httpx.AsyncClient, api_url: str, api_key: str
) -> ChaosResult:
    """Scenario 12: Submit empty evidence object."""
    name = "empty_evidence"
    expected = "400 or 422"

    # Need an assigned task first
    status, body = await _create_task(client, api_url, api_key, "empty-evidence")
    if status != 201:
        return ChaosResult(
            name, expected, status, False, f"Setup: task creation failed ({status})"
        )
    task_id = body.get("id")

    status, _ = await _apply_to_task(client, api_url, api_key, task_id)
    if status not in (200, 201):
        return ChaosResult(
            name, expected, status, False, f"Setup: apply failed ({status})"
        )

    status, _ = await _assign_worker(client, api_url, api_key, task_id)
    if status not in (200, 201):
        return ChaosResult(
            name, expected, status, False, f"Setup: assign failed ({status})"
        )

    # Chaos: submit with empty evidence
    status2, body2 = await _submit_evidence(
        client, api_url, api_key, task_id, evidence={}
    )
    passed = status2 in (400, 422)
    # Also treat 200 as "known gap" -- server may accept empty evidence
    if status2 in (200, 201):
        passed = False
        detail = "Server accepted empty evidence (may be expected in some modes)"
    else:
        detail = body2.get("detail", str(body2)[:200])
    return ChaosResult(name, expected, status2, passed, detail)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
ALL_SCENARIOS = [
    ("1. Double-submit", chaos_double_submit),
    ("2. Apply after deadline", chaos_apply_after_deadline),
    ("3. Approve wrong submission", chaos_approve_wrong_submission),
    ("4. Cancel after assignment", chaos_cancel_after_assignment),
    ("5. Rate score > 100", chaos_rate_score_above_100),
    ("6. Rate score < 0", chaos_rate_score_below_0),
    ("7. Self-application", chaos_self_application),
    ("8. Apply non-existent task", chaos_apply_nonexistent_task),
    ("9. Submit without assignment", chaos_submit_without_assignment),
    ("10. Invalid payment token", chaos_invalid_payment_token),
    ("11. Invalid network", chaos_invalid_network),
    ("12. Empty evidence", chaos_empty_evidence),
]


def print_summary(results: list[ChaosResult]) -> None:
    """Print a formatted summary table."""
    print()
    print("=" * 78)
    print("CHAOS TEST SUMMARY")
    print("=" * 78)
    print(f"{'#':<4} {'Scenario':<35} {'Expected':<18} {'Actual':<8} {'Result':<6}")
    print("-" * 78)

    for i, r in enumerate(results, 1):
        actual_str = str(r.actual_status) if r.actual_status is not None else "N/A"
        result_str = "PASS" if r.passed else "FAIL"
        print(f"{i:<4} {r.name:<35} {r.expected:<18} {actual_str:<8} {result_str:<6}")
        if r.details and not r.passed:
            # Show details for failures
            detail_truncated = r.details[:70]
            print(f"     -> {detail_truncated}")

    print("-" * 78)
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    print(f"Total: {len(results)} | Passed: {passed} | Failed: {failed}")
    print("=" * 78)


async def run_chaos(api_url: str, api_key: str, dry_run: bool = False) -> int:
    """Run all chaos scenarios. Returns 0 if all pass, 1 if any fail."""

    print("=" * 78)
    print("KARMA KADABRA V2 -- CHAOS TEST SCENARIOS")
    print(f"API:     {api_url}")
    print(f"Key:     {'***' + api_key[-4:] if len(api_key) > 4 else '(not set)'}")
    print(f"Time:    {_ts()}")
    print(f"Dry-run: {dry_run}")
    print("=" * 78)

    if dry_run:
        print("\n[DRY-RUN] Configuration OK. Would run 12 chaos scenarios.")
        print(f"  API URL: {api_url}")
        print(f"  API Key set: {bool(api_key)}")
        print(f"  Executor ID: {FALLBACK_EXECUTOR_ID}")
        print(f"  Test bounty: ${TEST_BOUNTY}")
        return 0

    # Verify connectivity first
    timeout = httpx.Timeout(60.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            health_url = f"{api_url.rstrip('/')}/health/"
            resp = await client.get(health_url)
            if resp.status_code != 200:
                print(f"\n[ERROR] Health check failed: HTTP {resp.status_code}")
                print(f"  URL: {health_url}")
                print("  Is the API running?")
                return 1
            print(f"\n[OK] API health check passed (HTTP {resp.status_code})")
        except httpx.ConnectError as e:
            print(f"\n[ERROR] Cannot connect to API: {e}")
            print(f"  URL: {api_url}")
            return 1
        except httpx.TimeoutException:
            print(f"\n[ERROR] Connection timed out: {api_url}")
            return 1

        results: list[ChaosResult] = []

        for label, scenario_fn in ALL_SCENARIOS:
            print(f"\n--- {label} ---")
            try:
                result = await scenario_fn(client, api_url, api_key)
                results.append(result)
                tag = "PASS" if result.passed else "FAIL"
                print(f"  [{tag}] HTTP {result.actual_status} -- {result.details[:80]}")
            except httpx.ConnectError as e:
                results.append(
                    ChaosResult(label, "N/A", None, False, f"Connection error: {e}")
                )
                print(f"  [FAIL] Connection error: {e}")
            except httpx.TimeoutException:
                results.append(
                    ChaosResult(label, "N/A", None, False, "Request timed out")
                )
                print("  [FAIL] Request timed out")
            except Exception as e:
                results.append(
                    ChaosResult(label, "N/A", None, False, f"Unexpected: {e}")
                )
                print(f"  [FAIL] Unexpected error: {e}")

            # Small delay between scenarios to avoid rate limiting
            await asyncio.sleep(1)

        print_summary(results)

        failed = sum(1 for r in results if not r.passed)
        return 0 if failed == 0 else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Karma Kadabra V2 -- Chaos test scenarios for Execution Market API"
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("EM_API_URL", DEFAULT_API_URL),
        help=f"API base URL (default: {DEFAULT_API_URL})",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("EM_API_KEY", ""),
        help="API key for authenticated endpoints (default: from EM_API_KEY env)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only check config, don't run scenarios",
    )
    args = parser.parse_args()

    return asyncio.run(run_chaos(args.api_url, args.api_key, args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
