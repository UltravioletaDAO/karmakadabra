import json
import logging
import requests

logger = logging.getLogger(__name__)

class AcontextBridge:
    """
    Bridge to the Acontext context server.
    Provides semantic, qualitative memory for the KK V2 Swarm, complementing the on-chain trust of EM.
    """
    def __init__(self, acontext_url="http://localhost:8000"):
        self.url = acontext_url
        self.headers = {"Content-Type": "application/json"}

    def ingest_task_result(self, task_id, worker_wallet, result_data, agent_notes):
        """
        Sends structured context to Acontext for embedding/storage.
        """
        payload = {
            "type": "task_result",
            "task_id": task_id,
            "worker_wallet": worker_wallet,
            "result_data": result_data,
            "agent_notes": agent_notes
        }
        try:
            res = requests.post(f"{self.url}/api/v1/context/ingest", json=payload, headers=self.headers, timeout=5)
            if res.status_code in [200, 201]:
                return res.json()
            else:
                logger.warning(f"Acontext ingest returned {res.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to ingest to Acontext: {e}")
            return None

    def retrieve_worker_context(self, worker_wallet):
        """
        Queries Acontext for past interactions with this specific worker.
        """
        try:
            res = requests.get(f"{self.url}/api/v1/context/query", params={"wallet": worker_wallet}, timeout=5)
            if res.status_code == 200:
                return res.json().get("results", [])
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to retrieve worker context from Acontext: {e}")
            return []

    def retrieve_similar_tasks(self, task_description):
        """
        Semantic search against Acontext for similar historical tasks.
        """
        try:
            payload = {"query": task_description, "type": "task_result"}
            res = requests.post(f"{self.url}/api/v1/context/search", json=payload, headers=self.headers, timeout=5)
            if res.status_code == 200:
                return res.json().get("matches", [])
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to search similar tasks in Acontext: {e}")
            return []
