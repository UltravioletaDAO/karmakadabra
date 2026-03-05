import json
import os
import requests
import logging

logger = logging.getLogger(__name__)

class ReputationBridge:
    """
    Bridges Execution Market's ERC-8004 on-chain reputation with KarmaCadabra Swarm State.
    Ensures agent interactions and human-worker hires are governed by verified DNA.
    """
    def __init__(self, rpc_url="https://mainnet.base.org"):
        self.rpc_url = rpc_url
        self.em_api_base = "https://api.execution.market/api/v1"
        self.autojob_reputation_url = "http://localhost:8080/api/reputation"
        
    def fetch_agent_reputation(self, wallet_address):
        """Fetches ERC-8004 reputation for a given agent/worker wallet."""
        try:
            # Fallback to local AutoJob API if available
            try:
                res = requests.get(f"{self.autojob_reputation_url}/{wallet_address}", timeout=2)
                if res.status_code == 200:
                    return res.json()
            except requests.exceptions.RequestException:
                pass # Local AutoJob API not available, proceed to direct EM API
                
            # Direct EM API fallback
            try:
                res = requests.get(f"{self.em_api_base}/reputation/wallet/{wallet_address}", timeout=5)
                if res.status_code == 200:
                    return res.json()
                elif res.status_code == 404:
                     return {"wallet": wallet_address, "score": 0, "attestations": 0, "status": "not_found"}
            except requests.exceptions.RequestException as em_e:
                logger.error(f"Failed to reach live EM API for {wallet_address}: {em_e}")
                
            return {"wallet": wallet_address, "score": 0, "attestations": 0}
        except Exception as e:
            logger.error(f"Failed to fetch reputation for {wallet_address}: {e}")
            return {"wallet": wallet_address, "score": 0, "attestations": 0, "error": str(e)}

    def attest_task_completion(self, agent_wallet, worker_wallet, task_id, grade, signature):
        """
        Submits an ERC-8004 attestation via EM API for a completed task.
        grade: integer 1-100
        """
        payload = {
            "attestor": agent_wallet,
            "subject": worker_wallet,
            "task_id": task_id,
            "grade": grade,
            "signature": signature
        }
        try:
            res = requests.post(f"{self.em_api_base}/reputation/attest", json=payload)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            logger.error(f"Attestation failed: {e}")
            raise
