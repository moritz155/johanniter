import requests
import json

BASE_URL = "http://localhost:5001"

def test_qr_login_flow():
    # 1. Start Shift (Config)
    print("1. Starting Shift...")
    config_payload = {
        "location": "TestQR",
        "password": "test",
        "squads": [] 
    }
    # Initial config might return 200 or 201
    try:
        res = requests.post(f"{BASE_URL}/api/config", json=config_payload)
        # res.raise_for_status() 
        # If config exists, it might update.
    except Exception as e:
        print(f"Config failed or server down: {e}")
        return

    # 2. Create Squad
    print("2. Creating Squad...")
    squad_payload = {
        "name": "TestSquadQR",
        "qualification": "RS"
    }
    res = requests.post(f"{BASE_URL}/api/squads", json=squad_payload)
    if res.status_code not in [200, 201]:
        print(f"Failed to create squad: {res.text}")
        return
    
    squad_data = res.json()
    squad_id = squad_data['id']
    token = squad_data.get('access_token')
    
    if not token:
        print("FAIL: No access_token returned in create_squad response!")
        return
    else:
        print(f"PASS: Squad created with token: {token}")

    # 3. Access Mobile View
    print("3. Accessing Mobile View...")
    mobile_url = f"{BASE_URL}/squad/mobile-view?token={token}"
    res = requests.get(mobile_url)
    
    if res.status_code == 200 and "TestSquadQR" in res.text:
        print("PASS: Mobile View loaded successfully with correct squad name.")
    else:
        print(f"FAIL: Mobile View failed. Code: {res.status_code}")
        # print(res.text)

    # 4. End Shift
    print("4. Ending Shift...")
    res = requests.post(f"{BASE_URL}/api/config/end")
    if res.status_code == 200:
        print("PASS: Shift ended.")
    else:
        print("FAIL: End Shift failed.")

    # 5. Check Token Cleanup
    # We can't easily check DB directly via API (unless we leak access_token in list).
    # But we can try to access the Mobile View again!
    print("5. Verifying Token Cleanup...")
    res = requests.get(mobile_url)
    if res.status_code == 403:
        print("PASS: Mobile View correctly denied after shift end.")
    else:
        print(f"FAIL: Mobile View still accessible! Code: {res.status_code}")

if __name__ == "__main__":
    test_qr_login_flow()
