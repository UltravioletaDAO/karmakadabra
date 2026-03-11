"""
Acontext Bridge for KK V2 Swarm

Provides methods to index and retrieve deep context from the Acontext server.
Uses synchronous HTTP for compatibility with the coordinator service.

Methods:
  - ingest_task_result: Store completed task results + evidence for embedding
  - retrieve_worker_context: Get past interactions with a specific worker
  - retrieve_similar_tasks: Semantic search for similar historical tasks
"""

import logging
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger("kk.context")


class AcontextBridge:
    """Bridge to the Acontext context server for deep semantic retrieval.

    Supports both live mode (real Acontext server) and stub mode
    (returns empty/placeholder responses when server is unavailable).
    """

    def __init__(
        self,
        acontext_url: str = "http://localhost:8000",
        api_key: str = "",
        timeout: float = 5.0,
    ):
        self.url = acontext_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    def check_health(self) -> bool:
        """Check if Acontext server is alive."""
        try:
            resp = requests.get(
                f"{self.url}/health",
                headers=self.headers,
                timeout=2.0,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.warning("Acontext health check failed: %s", e)
            return False

    def ingest_task_result(
        self,
        task_id: str,
        worker_wallet: str,
        result_data: Dict[str, Any],
        agent_notes: str,
    ) -> Optional[Dict[str, Any]]:
        """Send completed task result to Acontext for embedding/storage.

        Returns the response JSON on success (200/201), None on failure.
        """
        payload = {
            "type": "task_result",
            "task_id": task_id,
            "worker_wallet": worker_wallet,
            "result": result_data,
            "notes": agent_notes,
        }
        try:
            resp = requests.post(
                f"{self.url}/api/v1/context",
                json=payload,
                headers=self.headers,
                timeout=self.timeout,
            )
            if resp.status_code in (200, 201):
                return resp.json()
            logger.warning(
                "Acontext ingest failed: status=%d task=%s",
                resp.status_code,
                task_id,
            )
            return None
        except requests.exceptions.ConnectionError as e:
            logger.warning("Acontext connection error (ingest): %s", e)
            return None
        except requests.exceptions.Timeout as e:
            logger.warning("Acontext timeout (ingest): %s", e)
            return None
        except Exception as e:
            logger.warning("Acontext ingest error: %s", e)
            return None

    def retrieve_worker_context(
        self, worker_wallet: str
    ) -> List[Dict[str, Any]]:
        """Query Acontext for past interactions with a specific worker.

        Returns a list of context records, or empty list on failure.
        """
        try:
            resp = requests.get(
                f"{self.url}/api/v1/context/worker/{worker_wallet}",
                headers=self.headers,
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("results", [])
            logger.warning(
                "Acontext worker context failed: status=%d wallet=%s",
                resp.status_code,
                worker_wallet,
            )
            return []
        except requests.exceptions.ConnectionError as e:
            logger.warning("Acontext connection error (worker): %s", e)
            return []
        except Exception as e:
            logger.warning("Acontext worker context error: %s", e)
            return []

    def retrieve_similar_tasks(
        self, task_description: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Semantic search for similar historical tasks.

        Returns a list of matched tasks with similarity scores, or
        empty list on failure.
        """
        payload = {
            "query": task_description,
            "type": "task_result",
            "limit": limit,
        }
        try:
            resp = requests.post(
                f"{self.url}/api/v1/context/search",
                json=payload,
                headers=self.headers,
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("matches", [])
            logger.warning(
                "Acontext similar tasks failed: status=%d",
                resp.status_code,
            )
            return []
        except requests.exceptions.ConnectionError as e:
            logger.warning("Acontext connection error (search): %s", e)
            return []
        except Exception as e:
            logger.warning("Acontext similar tasks error: %s", e)
            return []
