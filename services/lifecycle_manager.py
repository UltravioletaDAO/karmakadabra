import json
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class AgentLifecycleManager:
    """
    Manages the birth, work cycle, and death/sleep states of KK V2 Swarm agents.
    Tracks state transitions: INIT -> IDLE -> SEEKING_WORK -> WORKING -> VERIFYING -> IDLE
    """
    def __init__(self, state_dir="data/lifecycle_state"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
    def _get_agent_file(self, agent_id):
        return self.state_dir / f"{agent_id}.json"

    def transition(self, agent_id, new_state, context=None):
        logger.info(f"Agent {agent_id} transitioning to {new_state}")
        
        file_path = self._get_agent_file(agent_id)
        current_state = {}
        if file_path.exists():
            try:
                with open(file_path, "r") as f:
                    current_state = json.load(f)
            except Exception:
                pass
                
        now = int(time.time())
        updated_state = {
            "agent_id": agent_id,
            "state": new_state,
            "last_transition": now,
            "last_heartbeat": now,
            "history": current_state.get("history", [])[-9:], # keep last 9
            "context": context or {}
        }
        
        if "state" in current_state:
            updated_state["history"].append({
                "from": current_state["state"],
                "to": new_state,
                "timestamp": now
            })
            
        with open(file_path, "w") as f:
            json.dump(updated_state, f, indent=2)
            
        return updated_state
        
    def heartbeat(self, agent_id):
        """Register that an agent is still alive and processing."""
        file_path = self._get_agent_file(agent_id)
        if not file_path.exists():
            return False
            
        try:
            with open(file_path, "r") as f:
                state = json.load(f)
            
            state["last_heartbeat"] = int(time.time())
            with open(file_path, "w") as f:
                json.dump(state, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Heartbeat failed for {agent_id}: {e}")
            return False

    def get_stale_agents(self, timeout_seconds=300):
        """Returns a list of agents that haven't heartbeated recently."""
        stale = []
        now = int(time.time())
        for file_path in self.state_dir.glob("*.json"):
            try:
                with open(file_path, "r") as f:
                    state = json.load(f)
                if now - state.get("last_heartbeat", 0) > timeout_seconds:
                    stale.append(state["agent_id"])
            except Exception:
                continue
        return stale
