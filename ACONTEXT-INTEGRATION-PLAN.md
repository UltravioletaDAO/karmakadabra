# Acontext ↔ KK V2 Memory System Integration Plan

## The Goal
Acontext is our agent-native context server. The KK V2 Swarm needs a way to store, index, and retrieve deep historical context about tasks, workers, and previous interactions. Currently, Acontext is blocked on Docker deployment issues, but we can prepare the bridge architecture so it drops right in once the container is running.

## Architecture

### 1. The Context Bridge (`lib/context_bridge.py`)
This will be a new component in the KK V2 Swarm alongside `reputation_bridge.py`.

```python
class AcontextBridge:
    def __init__(self, acontext_url="http://localhost:8000"):
        self.url = acontext_url

    def ingest_task_result(self, task_id, worker_wallet, result_data, agent_notes):
        # Sends structured context to Acontext for embedding/storage
        pass

    def retrieve_worker_context(self, worker_wallet):
        # Queries Acontext for past interactions with this specific worker
        pass

    def retrieve_similar_tasks(self, task_description):
        # Semantic search against Acontext for similar historical tasks
        pass
```

### 2. Integration Points in Swarm Orchestrator
- **Pre-Assignment:** Before the Coordinator assigns a task to a worker, it queries `retrieve_worker_context` to see if the swarm has any historical warnings or positive notes about this worker that aren't captured purely by the ERC-8004 score.
- **Post-Completion:** After the Evidence Processor grades a task, the lifecycle manager calls `ingest_task_result` to log the detailed qualitative feedback into Acontext.

### 3. Execution Market Synergy
While Execution Market stores the *proof* (the hash and the reputation score), Acontext will store the *narrative* (the actual conversation, the nuances of the worker's delivery, the agent's internal monologue about the grading). 
- **EM = Trust** (On-chain, verifiable, boolean/numeric)
- **Acontext = Nuance** (Off-chain, semantic, qualitative)

## Next Steps (Once Docker is Unblocked)
1. Stand up the Acontext container locally.
2. Implement the `AcontextBridge` class using standard HTTP requests.
3. Write an integration test similar to `test_live_em_api.py` but for the local Acontext instance.
4. Hook the bridge into `services/lifecycle_manager.py`.

