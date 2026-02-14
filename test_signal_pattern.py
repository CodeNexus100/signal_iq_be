import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8001/api"

def run_test():
    print("--- Testing Signal Pattern Override ---")

    try:
        # 1. Apply Pattern
        pattern = "rush_hour"
        print(f"Applying pattern: {pattern}")
        payload = {"pattern": pattern}
        
        response = requests.post(f"{BASE_URL}/signals/pattern", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            print("PASS: Endpoint reachable.")
            print(json.dumps(data, indent=2))
            
            if data["patternApplied"] == pattern and data["intersectionsUpdated"] > 0:
                print("PASS: Response valid.")
            else:
                 print(f"FAIL: Unexpected response. {data}")
                 
            # 2. Verify effect on an intersection
            # Get list to find an ID
            list_res = requests.get(f"{BASE_URL}/intersections")
            if list_res.status_code == 200:
                ids = [i['id'] for i in list_res.json()]
                if not ids:
                    print("WARN: No intersections to check.")
                    return
                    
                test_id = ids[0]
                detail_res = requests.get(f"{BASE_URL}/signals/{test_id}")
                if detail_res.status_code == 200:
                    details = detail_res.json()
                    print(f"Verification on {test_id}:")
                    print(f"NS Green: {details['nsGreenTime']} (Expected 40)")
                    print(f"EW Green: {details['ewGreenTime']} (Expected 20)")
                    
                    if details['nsGreenTime'] == 40 and details['ewGreenTime'] == 20:
                        print("PASS: Timing updated correctly.")
                    else:
                        print("FAIL: Timings did not update.")
            
        else:
            print(f"FAIL: Status Code {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"FAIL: Exception {e}")

if __name__ == "__main__":
    run_test()
