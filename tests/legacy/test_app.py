import requests
import time

BASE_URL = "http://127.0.0.1:5000"

def test_app():
    print("Starting tests for Mission Control...")
    
    # 1. Config Shift (Init)
    print("Testing Shift Config...")
    try:
        # Optional fields: Address provided, Start time empty (should default to now)
        payload = {
            "location": "Test Event 2024",
            "address": "Musterstraße 1",
            "squads": [
                {"name": "Trupp 1", "qualification": "San"},
                {"name": "Trupp 2", "qualification": "RS"},
                {"name": "NEF", "qualification": "NA"}
            ],
            "options": {
                "location": ["Zelt 1", "Bühne"],
                "reason": ["Intern", "Chirurg"]
            }
        }
        resp = requests.post(f"{BASE_URL}/api/config", json=payload)
        if resp.status_code == 200:
            print("SUCCESS: Shift configured.")
            data = resp.json()
            if data.get('address') == "Musterstraße 1":
                print("SUCCESS: Address saved correctly.")
            else:
                print(f"FAILURE: Address mismatch: {data.get('address')}")
        else:
            print(f"FAILURE: Config failed. {resp.text}")
            return
            
        # 1.5 Update Config
        print("Testing Update Config...")
        update_payload = {"address": "Neue Straße 2"}
        resp = requests.put(f"{BASE_URL}/api/config", json=update_payload)
        if resp.status_code == 200:
             if resp.json()['address'] == "Neue Straße 2":
                 print("SUCCESS: Config updated.")
             else:
                 print("FAILURE: Config update return wrong value.")
        else:
            print(f"FAILURE: Update Config failed. {resp.text}")
            
    except Exception as e:
        print(f"FAILURE: Connection error. {e}")
        return

    # 2. Get Init Data
    time.sleep(1)
    print("Testing Init Data...")
    resp = requests.get(f"{BASE_URL}/api/init")
    data = resp.json()
    squads = data['squads']
    print(f"SUCCESS: Loaded {len(squads)} squads.")
    
    if len(squads) < 1:
        print("FAILURE: No squads found.")
        return

    # 3. Create Mission
    print("Testing Create Mission...")
    squad_ids = [squads[0]['id'], squads[1]['id']] # Assign 2 squads
    payload = {
        "mission_number": "101",
        "location": "Bühne",
        "reason": "Chirurg",
        "description": "Pat. gestürzt",
        "squad_ids": squad_ids,
        "alarming_entity": "Securitas"
    }
    resp = requests.post(f"{BASE_URL}/api/missions", json=payload)
    if resp.status_code == 201:
        mission_id = resp.json()['id']
        print(f"SUCCESS: Mission created with ID {mission_id}.")
    else:
        print(f"FAILURE: Could not create mission. {resp.text}")
        return

    # 4. Update Squad Status
    print("Testing Squad Status Update...")
    squad_id = squads[0]['id']
    # Update to '3' (zBO)
    resp = requests.post(f"{BASE_URL}/api/squads/{squad_id}/status", json={"status": "3"})
    if resp.status_code == 200:
        print("SUCCESS: Squad status updated to 3.")
    else:
        print(f"FAILURE: Could not update squad status. {resp.text}")

    # 4.5 Edit Squad
    print("Testing Edit Squad...")
    resp = requests.put(f"{BASE_URL}/api/squads/{squad_id}", json={"name": "Trupp 1 Revised", "qualification": "NFS"})
    if resp.status_code == 200:
        if resp.json()['name'] == "Trupp 1 Revised":
             print("SUCCESS: Squad edited.")
        else:
             print("FAILURE: Squad name mismatch.")
    else:
        print(f"FAILURE: Squad edit failed. {resp.text}")

    # 4.6 Delete Squad (Create a dummy one to delete)
    print("Testing Delete Squad...")
    # Create
    r_tmp = requests.post(f"{BASE_URL}/api/squads", json={"name": "Temp Squad"})
    tmp_id = r_tmp.json()['id']
    # Delete
    resp = requests.delete(f"{BASE_URL}/api/squads/{tmp_id}")
    if resp.status_code == 200:
        print("SUCCESS: Squad deleted.")
    else:
        print(f"FAILURE: Squad delete failed. {resp.text}")

    # 5. Mission Update (Finish)
    print("Testing Mission Update...")
    resp = requests.put(f"{BASE_URL}/api/missions/{mission_id}", json={"status": "Abgeschlossen", "notes": "Transportiert"})
    if resp.status_code == 200:
        print("SUCCESS: Mission finished.")
    else:
        print(f"FAILURE: Mission update failed.")

    # 6. Check Logs
    print("Testing Logs...")
    resp = requests.get(f"{BASE_URL}/api/changes")
    logs = resp.json()
    print(f"SUCCESS: {len(logs)} log entries found.")

    # 7. Export
    print("Testing Export...")
    resp = requests.get(f"{BASE_URL}/api/export")
    if resp.status_code == 200:
        print("SUCCESS: Export downloaded.")
    else:
        print(f"FAILURE: Export failed. {resp.status_code}")

    # 8. End Shift
    print("Testing End Shift...")
    resp = requests.post(f"{BASE_URL}/api/config/end")
    if resp.status_code == 200:
        print("SUCCESS: Shift ended.")
    else:
        print(f"FAILURE: End shift failed.")
    
    # Verify no active config
    resp = requests.get(f"{BASE_URL}/api/init")
    if resp.json()['config'] is None:
        print("SUCCESS: Config is now None (Overlay should show).")
    else:
        print("FAILURE: Config still active.")

if __name__ == "__main__":
    test_app()
