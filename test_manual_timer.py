import requests
import time

BASE_URL = "http://localhost:8001"
INTERSECTION_ID = "I-101"

print("--- Testing Manual Mode Timer ---")

# 1. Set to MANUAL
print("Setting I-101 to MANUAL...")
payload = {"mode": "MANUAL", "nsGreenTime": 5.0, "ewGreenTime": 5.0} # fast cycle
requests.post(f"{BASE_URL}/api/signals/{INTERSECTION_ID}/update", json=payload)

# 2. Monitor Timer
print("Monitoring timer...")
timers = []
for i in range(5):
    r = requests.get(f"{BASE_URL}/api/signals/{INTERSECTION_ID}")
    data = r.json()
    timer = data["timer"]
    signal = data["nsSignal"]
    print(f"Time {i}: Timer={timer}, Signal={signal}")
    timers.append(timer)
    time.sleep(1.0)

# Check if timer changed
if len(set(timers)) > 1:
     print("SUCCESS: Timer is changing in MANUAL mode.")
else:
     print("FAILURE: Timer is invalid or static.")
