import logging
import asyncio
from reputation_bridge import ReputationBridge

logging.basicConfig(level=logging.INFO)

async def test_live_em_api():
    print("Testing ReputationBridge against live Execution Market API...")
    bridge = ReputationBridge()
    
    test_wallet = "0x52E05C8e45a32eeE169639F6d2cA40f8887b5A15"
    
    print(f"Fetching reputation for {test_wallet}...")
    rep = bridge.fetch_agent_reputation(test_wallet)
    print(f"Reputation Result: {rep}")
    
    print(f"\nTesting Coordinator EM Client against live Execution Market API...")
    try:
        import requests
        res = requests.get("https://api.execution.market/api/v1/tasks/available?status=published&limit=5", timeout=5)
        if res.status_code == 200:
            resp_json = res.json()
            tasks = resp_json.get("tasks", resp_json) if isinstance(resp_json, dict) else resp_json
            print(f"Successfully fetched {len(tasks)} available tasks from Live EM API.")
            if tasks and len(tasks) > 0:
                print(f"Sample task: {tasks[0].get('id')} - {tasks[0].get('title')}")
        else:
            print(f"Failed to fetch tasks: {res.status_code}")
    except Exception as e:
        print(f"Error connecting to Live EM API: {e}")

if __name__ == "__main__":
    asyncio.run(test_live_em_api())
