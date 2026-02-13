import requests
import time
import traceback

BASE_URL = "http://127.0.0.1:8001"
INTERSECTION_ID = "I-101"

def inject_traffic():
    print("Injecting heavy traffic on Vertical Lane V0...")
    try:
        # Spawn 10 vehicles on V0 close to intersection
        for i in range(10):
            payload = {
                "lane_id": "V0",
                "position": i * 5.0, # Close cluster
                "direction": "north"
            }
            requests.post(f"{BASE_URL}/api/debug/spawn", params=payload)
    except Exception as e:
        print(f"Error injecting traffic: {e}")

def monitor_ai_behavior():
    print(f"--- Monitoring AI Optimization for {INTERSECTION_ID} ---")
    
    # 1. Enable AI Mode
    print("Enabling AI Mode...")
    try:
        r = requests.post(f"{BASE_URL}/api/signals/ai", json={"enabled": True})
        print(f"AI Toggle Response: {r.status_code} {r.text}")
    except Exception as e:
        print(f"Error toggling AI: {e}")
        return

    
    # 2. Inject Traffic
    inject_traffic()

    # 3. Monitor Green Times
    print("\nMonitoring Signal Timings (Press Ctrl+C to stop)...")
    initial_ns = 0
    initial_ew = 0
    
    try:
        for i in range(10): # Monitor for 10 checks
            r = requests.get(f"{BASE_URL}/api/signals/{INTERSECTION_ID}")
            if r.status_code == 200:
                data = r.json()
                ns_green = data.get("nsGreenTime")
                ew_green = data.get("ewGreenTime")
                mode = data.get("mode")
                
                if i == 0:
                    initial_ns = ns_green
                    initial_ew = ew_green
                
                print(f"Check {i+1}: NS={ns_green}s, EW={ew_green}s, Mode={mode}")
            else:
                 print(f"Error fetching signal: {r.status_code}")
            
            time.sleep(2) # Wait a bit to let simulation run
            
        print("\n--- Summary ---")
        print(f"Initial: NS={initial_ns}, EW={initial_ew}")
        print(f"Final:   NS={ns_green}, EW={ew_green}")
        
        if ns_green != initial_ns or ew_green != initial_ew:
            print("SUCCESS: Signal timings changed under AI control.")
        else:
            print("WARNING: Signal timings did not change. Traffic density might be low or balanced.")

    except Exception as e:
        print(f"Monitoring error: {e}")

if __name__ == "__main__":
    monitor_ai_behavior()
