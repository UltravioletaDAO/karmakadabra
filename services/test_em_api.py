import logging
from reputation_bridge import ReputationBridge

logging.basicConfig(level=logging.INFO)

def test_live_em_api():
    print("Testing ReputationBridge against live Execution Market API...")
    bridge = ReputationBridge()
    
    # Test wallet (Saul's worker test wallet or a dummy)
    test_wallet = "0x52E05C8e45a32eeE169639F6d2cA40f8887b5A15"
    
    print(f"Fetching reputation for {test_wallet}...")
    rep = bridge.fetch_agent_reputation(test_wallet)
    print(f"Reputation Result: {rep}")
    
    print(f"Checking worker confidence for 'photo_geo'...")
    conf = bridge.get_worker_confidence(test_wallet, "photo_geo")
    print(f"Confidence Score: {conf}")

if __name__ == "__main__":
    test_live_em_api()
