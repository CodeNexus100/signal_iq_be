import requests
import time
import sys

BASE_URL = "http://127.0.0.1:8001/api"

def run_test():
    print("--- Testing AI Decision Engine ---")

    # 1. Enable AI Mode
    print("\nEnabling AI Mode...")
    try:
        requests.post(f"{BASE_URL}/signals/ai", json={"enabled": True})
        print("AI Mode Enabled.")
    except Exception as e:
        print(f"Error connecting to server: {e}")
        return

    # 2. Wait for AI Engine to run (it runs every tick, updates status every 2s)
    print("Waiting for AI Engine to initialize...")
    time.sleep(3)
    
    # 3. Check Status (Should be Balanced initially as grid is random but roughly equal)
    try:
        resp = requests.get(f"{BASE_URL}/ai/status")
        status = resp.json()
        print("\nInitial AI Status:")
        print(status)
    except Exception as e:
        print(f"Error getting status: {e}")

    # 4. Simulate Congestion? 
    # Hard to simulate specific congestion via API without spawning tons of vehicles specificly.
    # But we can check if the status is valid structure.
    
    # 4. Check status structure
    if "congestionLevel" in status and "recommendation" in status:
        print("\nPASS: AI Status endpoint returns valid structure.")
        print(f"Congestion Level: {status.get('congestionLevel')}")
        print(f"Recommendation: {status.get('recommendation')}")
    else:
        print("\nFAIL: Invalid AI Status structure.")
        print(f"Received keys: {list(status.keys())}")

if __name__ == "__main__":
    run_test()
