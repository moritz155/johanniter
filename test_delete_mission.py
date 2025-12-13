import requests

# Create a dummy mission first to delete
create_url = 'http://127.0.0.1:5001/api/missions'
payload = {
    'mission_number': 'DEL-TEST',
    'location': 'Delete Me',
    'reason': 'To be deleted',
    'squad_ids': []
}
try:
    # We need a session cookie for session_id binding
    s = requests.Session()
    
    # Init config/session
    s.get('http://127.0.0.1:5001/api/init')
    
    resp = s.post(create_url, json=payload)
    if resp.status_code == 201:
        data = resp.json()
        mid = data['id']
        print(f"Created mission {mid}")
        
        # Now delete it
        del_url = f'http://127.0.0.1:5001/api/missions/{mid}'
        del_payload = {'reason': 'Test Deletion Script'}
        
        del_resp = s.delete(del_url, json=del_payload)
        print(f"Delete Status: {del_resp.status_code}")
        print(f"Delete Response: {del_resp.text}")
        
        if del_resp.status_code == 200:
            print("Backend Delete seems successful.")
        else:
            print("Backend Delete failed.")
    else:
        print(f"Failed to create dummy mission: {resp.text}")

except Exception as e:
    print(f"Error: {e}")
