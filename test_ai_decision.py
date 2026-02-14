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
    
    if "congestionRoad" in status and "recommendedDirection" in status:
        print("\nPASS: AI Status endpoint returns valid structure.")
    else:
        print("\nFAIL: Invalid AI Status structure.")

if __name__ == "__main__":
    run_test()
