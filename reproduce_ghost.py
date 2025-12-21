
import requests

BASE_URL = "http://127.0.0.1:5001/api"

def run():
    s = requests.Session()
    
    # 1. Start Shift (to ensure session)
    print("Starting shift...")
    s.post(f"{BASE_URL}/config", json={"location": "Test"})

    # 2. Create Squad A
    print("Creating Squad A...")
    # r = s.get(f"{BASE_URL}/init").json()['squads'] # Not needed really
    
    r = s.post(f"{BASE_URL}/squads", json={"name": "GhostSquad"})
    if r.status_code != 201:
        print("Failed to create squad:", r.text)
        return
    squad_a = r.json()
    sid = squad_a['id']
    print(f"Squad A created. ID: {sid}")

    # 3. Create Mission linking Squad A
    print("Creating Mission...")
    r = s.post(f"{BASE_URL}/missions", json={
        "location": "Nowhere",
        "reason": "Test",
        "squad_ids": [sid]
    })
    if r.status_code != 201:
        print("Failed to create mission:", r.text)
        return
    mission = r.json()
    print(f"Mission created. ID: {mission['id']}")

    # 4. Delete Squad A
    print(f"Deleting Squad A (ID: {sid})...")
    r = s.delete(f"{BASE_URL}/squads/{sid}")
    print("Delete status:", r.status_code)
    if r.status_code != 200:
        print("Delete failed:", r.text)
        return

    # 5. Create Squad B
    print("Creating Squad B...")
    r = s.post(f"{BASE_URL}/squads", json={"name": "NewSquad"})
    squad_b = r.json()
    print(f"Squad B created. ID: {squad_b['id']}")

    if squad_b['id'] == sid:
        print("ID REUSED! Checking for ghost mission...")
    else:
        print(f"ID not reused (Got {squad_b['id']}). Verification might be skipping the ghost condition if ID reuse is key.")

    # Check active mission
    if squad_b.get('active_mission'):
        print(f"FAIL: New Squad B has active mission: {squad_b['active_mission']}")
    else:
        print("SUCCESS: New Squad B has NO active mission.")

if __name__ == "__main__":
    run()
