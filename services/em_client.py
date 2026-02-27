"""
Karma Kadabra V2 — Execution Market API Client

Shared HTTP client used by all KK agent services to interact
with the Execution Market REST API.

All agent operations go through this client:
  - Publish tasks (bounties for data/services)
  - Browse available tasks
  - Apply to tasks
  - Submit evidence
  - Approve/reject submissions
  - Rate workers/agents
"""

import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# Add lib/ to path so we can import the EIP-8128 signer
_lib_dir = str(Path(__file__).parent.parent / "lib")
if _lib_dir not in sys.path:
    sys.path.insert(0, _lib_dir)

_project_root = Path(__file__).parent.parent.parent.parent
load_dotenv(_project_root / ".env.local")

logger = logging.getLogger("kk.em_client")

API_BASE = os.environ.get("EM_API_URL", "https://api.execution.market").rstrip("/")
API_V1 = f"{API_BASE}/api/v1"


@dataclass
class AgentContext:
    """Identity and state for one KK agent interacting with EM."""

    name: str
    wallet_address: str
    workspace_dir: Path
    api_key: str = ""
    private_key: str = ""
    chain_id: int = 8453
    erc8004_agent_id: int | None = None
    executor_id: str | None = None

    # Runtime state
    daily_spent_usd: float = 0.0
    daily_budget_usd: float = 2.0
    per_task_budget_usd: float = 0.50
    active_tasks: list[str] = field(default_factory=list)

    def can_spend(self, amount: float) -> bool:
        return (self.daily_spent_usd + amount) <= self.daily_budget_usd

    def record_spend(self, amount: float) -> None:
        self.daily_spent_usd += amount

    def reset_daily_budget(self) -> None:
        self.daily_spent_usd = 0.0


class EMClient:
    """Async HTTP client for the Execution Market API.

    Authentication priority:
      1. EIP-8128 wallet signatures (if ``agent.private_key`` is set)
      2. API key header (if ``agent.api_key`` is set)
      3. Plain ``X-Agent-Wallet`` header (fallback)
    """

    def __init__(self, agent: AgentContext, timeout: float = 30.0):
        self.agent = agent
        self._signer = None

        # Try to set up EIP-8128 signer if private key is available
        if agent.private_key:
            try:
                from eip8128_signer import EIP8128Signer

                self._signer = EIP8128Signer(
                    private_key=agent.private_key,
                    chain_id=agent.chain_id,
                    api_base=API_BASE,
                )
                logger.info(
                    "EIP-8128 auth enabled for %s (%s)",
                    agent.name,
                    self._signer.address_lower,
                )
            except ImportError:
                logger.warning(
                    "eip8128_signer not available — falling back to header auth"
                )

        headers: dict[str, str] = {"Content-Type": "application/json"}
        # Always send X-Agent-Wallet — some EM endpoints require it
        # even when EIP-8128 signature is present
        headers["X-Agent-Wallet"] = agent.wallet_address
        if agent.api_key:
            headers["X-API-Key"] = agent.api_key

        self._client = httpx.AsyncClient(
            base_url=API_V1,
            headers=headers,
            timeout=timeout,
        )

    def _sign_headers(
        self, method: str, url: str, body: str = ""
    ) -> dict[str, str]:
        """Compute EIP-8128 signature headers for a request.

        Returns an empty dict when the signer is not configured, so
        callers can always do ``headers.update(self._sign_headers(...))``.
        """
        if self._signer is None:
            return {}
        return self._signer.sign_request(method, url, body)

    async def close(self) -> None:
        await self._client.aclose()

    # -- Tasks -----------------------------------------------------------------

    async def publish_task(
        self,
        title: str,
        instructions: str,
        category: str,
        bounty_usd: float,
        deadline_hours: int = 1,
        evidence_required: list[str] | None = None,
        payment_network: str = "base",
    ) -> dict[str, Any]:
        """Publish a new task (bounty) on Execution Market.

        Args:
            title: Brief task title.
            instructions: Detailed description (API field: ``instructions``).
            category: One of physical_presence, knowledge_access, human_authority,
                      simple_action, digital_physical.
            bounty_usd: Bounty in USD (float, e.g. 0.10).
            deadline_hours: Hours until deadline (1-720).
            evidence_required: List of evidence type strings. Valid values:
                photo, photo_geo, video, document, receipt, signature,
                notarized, timestamp_proof, text_response, measurement,
                screenshot, json_response, api_response, code_output,
                file_artifact, url_reference, structured_data, text_report.
                Defaults to ["json_response"].
            payment_network: Chain name (default "base").
        """
        payload: dict[str, Any] = {
            "title": title,
            "instructions": instructions,
            "category": category,
            "bounty_usd": bounty_usd,
            "deadline_hours": deadline_hours,
            "payment_network": payment_network,
            "evidence_required": evidence_required or ["json_response"],
        }

        body_str = json.dumps(payload)
        url = f"{API_V1}/tasks"
        sig_headers = self._sign_headers("POST", url, body_str)
        resp = await self._client.post(
            "/tasks", content=body_str, headers=sig_headers
        )
        resp.raise_for_status()
        return resp.json()

    async def get_task(self, task_id: str) -> dict[str, Any]:
        """Get details of a specific task."""
        url = f"{API_V1}/tasks/{task_id}"
        sig_headers = self._sign_headers("GET", url)
        resp = await self._client.get(f"/tasks/{task_id}", headers=sig_headers)
        resp.raise_for_status()
        return resp.json()

    async def browse_tasks(
        self,
        status: str = "published",
        category: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Browse available tasks on EM."""
        params: dict[str, Any] = {"status": status, "limit": limit}
        if category:
            params["category"] = category
        url = f"{API_V1}/tasks/available"
        sig_headers = self._sign_headers("GET", url)
        resp = await self._client.get(
            "/tasks/available", params=params, headers=sig_headers
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        return data.get("tasks", [])

    async def list_tasks(
        self,
        agent_wallet: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List tasks belonging to the authenticated agent.

        NOTE: The /tasks endpoint auto-filters by the agent identity
        from the ERC-8128 signature. The ``agent_wallet`` parameter is
        accepted for backward-compat but ignored (EM API does not use it).
        """
        params: dict[str, Any] = {"limit": limit}
        # agent_wallet is NOT a valid query param on /tasks —
        # the server auto-filters by the authenticated wallet
        if status:
            params["status"] = status
        url = f"{API_V1}/tasks"
        sig_headers = self._sign_headers("GET", url)
        resp = await self._client.get("/tasks", params=params, headers=sig_headers)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        return data.get("tasks", [])

    async def cancel_task(self, task_id: str) -> dict[str, Any]:
        """Cancel a published task."""
        url = f"{API_V1}/tasks/{task_id}/cancel"
        sig_headers = self._sign_headers("POST", url)
        resp = await self._client.post(
            f"/tasks/{task_id}/cancel", headers=sig_headers
        )
        resp.raise_for_status()
        return resp.json()

    # -- Worker actions --------------------------------------------------------

    async def apply_to_task(
        self,
        task_id: str,
        executor_id: str,
        message: str = "",
    ) -> dict[str, Any]:
        """Apply (as worker) to a task."""
        payload: dict[str, Any] = {
            "executor_id": executor_id,
        }
        if message:
            payload["message"] = message
        body_str = json.dumps(payload)
        url = f"{API_V1}/tasks/{task_id}/apply"
        sig_headers = self._sign_headers("POST", url, body_str)
        resp = await self._client.post(
            f"/tasks/{task_id}/apply", content=body_str, headers=sig_headers
        )
        resp.raise_for_status()
        return resp.json()

    async def submit_evidence(
        self,
        task_id: str,
        executor_id: str,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Submit evidence for a task.

        Args:
            task_id: The task UUID.
            executor_id: The executor UUID (not wallet address).
            evidence: Evidence dict, e.g. {"url": "...", "type": "text", "notes": "..."}.
        """
        payload: dict[str, Any] = {
            "executor_id": executor_id,
            "evidence": evidence or {},
        }
        body_str = json.dumps(payload)
        url = f"{API_V1}/tasks/{task_id}/submit"
        sig_headers = self._sign_headers("POST", url, body_str)
        resp = await self._client.post(
            f"/tasks/{task_id}/submit", content=body_str, headers=sig_headers
        )
        resp.raise_for_status()
        return resp.json()

    # -- Agent review actions --------------------------------------------------

    async def assign_task(self, task_id: str, executor_id: str) -> dict[str, Any]:
        """Assign an applicant to a task."""
        payload = {"executor_id": executor_id}
        body_str = json.dumps(payload)
        url = f"{API_V1}/tasks/{task_id}/assign"
        sig_headers = self._sign_headers("POST", url, body_str)
        resp = await self._client.post(
            f"/tasks/{task_id}/assign", content=body_str, headers=sig_headers
        )
        resp.raise_for_status()
        return resp.json()

    async def approve_submission(
        self,
        submission_id: str,
        rating_score: int = 80,
        notes: str = "",
    ) -> dict[str, Any]:
        """Approve a submission.

        Args:
            submission_id: Submission UUID.
            rating_score: 0-100 rating (not 1-5 stars).
            notes: Optional approval notes.
        """
        payload: dict[str, Any] = {}
        if rating_score is not None:
            payload["rating_score"] = rating_score
        if notes:
            payload["notes"] = notes
        body_str = json.dumps(payload)
        url = f"{API_V1}/submissions/{submission_id}/approve"
        sig_headers = self._sign_headers("POST", url, body_str)
        resp = await self._client.post(
            f"/submissions/{submission_id}/approve",
            content=body_str,
            headers=sig_headers,
        )
        resp.raise_for_status()
        return resp.json()

    async def reject_submission(
        self,
        submission_id: str,
        notes: str = "Does not meet requirements.",
        severity: str = "minor",
    ) -> dict[str, Any]:
        """Reject a submission.

        Args:
            submission_id: Submission UUID.
            notes: Rejection reason (min 10 characters).
            severity: "minor" or "major".
        """
        payload = {"notes": notes, "severity": severity}
        body_str = json.dumps(payload)
        url = f"{API_V1}/submissions/{submission_id}/reject"
        sig_headers = self._sign_headers("POST", url, body_str)
        resp = await self._client.post(
            f"/submissions/{submission_id}/reject",
            content=body_str,
            headers=sig_headers,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_submissions(self, task_id: str) -> list[dict[str, Any]]:
        """Get submissions for a task."""
        url = f"{API_V1}/tasks/{task_id}/submissions"
        sig_headers = self._sign_headers("GET", url)
        resp = await self._client.get(
            f"/tasks/{task_id}/submissions", headers=sig_headers
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        return data.get("submissions", [])

    # -- Health ----------------------------------------------------------------

    async def health(self) -> dict[str, Any]:
        """Check API health."""
        url = f"{API_V1}/health"
        sig_headers = self._sign_headers("GET", url)
        resp = await self._client.get("/health", headers=sig_headers)
        resp.raise_for_status()
        return resp.json()


def load_agent_context(workspace_dir: Path) -> AgentContext:
    """Load agent context from a workspace directory."""
    wallet_file = workspace_dir / "data" / "wallet.json"
    profile_file = workspace_dir / "data" / "profile.json"

    wallet_data = json.loads(wallet_file.read_text(encoding="utf-8")) if wallet_file.exists() else {}
    profile_data = json.loads(profile_file.read_text(encoding="utf-8")) if profile_file.exists() else {}

    name = workspace_dir.name.removeprefix("kk-") if workspace_dir.name.startswith("kk-") else workspace_dir.name

    return AgentContext(
        name=name,
        wallet_address=wallet_data.get("address", ""),
        workspace_dir=workspace_dir,
        api_key=os.environ.get("EM_API_KEY", ""),
        private_key=wallet_data.get("private_key", ""),
        chain_id=int(wallet_data.get("chain_id", 8453)),
        executor_id=wallet_data.get("executor_id"),
    )
