import sys
from pathlib import Path

# Add the parent directory to the path so we can import services
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.reputation_bridge import ReputationBridge

def test_live_em_api():
    print("Testing connection to live EM API (api.execution.market)...")
    bridge = ReputationBridge()
    # 0x52E05C8e45a32eeE169639F6d2cA40f8887b5A15 is the payment operator from TOOLS.md
    test_wallet = "0x52E05C8e45a32eeE169639F6d2cA40f8887b5A15"
    try:
        rep = bridge.fetch_agent_reputation(test_wallet)
        print(f"Success! Fetched reputation for {test_wallet}:")
        print(rep)
        return True
    except Exception as e:
        print(f"Error connecting to live EM API: {e}")
        return False

if __name__ == "__main__":
    test_live_em_api()
