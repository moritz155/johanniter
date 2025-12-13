import requests
import json

url = 'http://127.0.0.1:5001/api/missions'
payload = {
    'mission_number': 'TEST-001',
    'location': 'Test Location',
    'reason': 'Test Reason',
    'description': 'Test Description',
    'notes': 'Test Note',
    'squad_ids': []
}

try:
    headers = {'Content-Type': 'application/json'}
    # Session cookie? get_session_id uses session['user_id'].
    # Flask session is client-side signed cookie 'session'.
    # If I don't send a cookie, Flask creates a new session.
    # That should work fine.
    
    response = requests.post(url, json=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 201:
        print("Success: Mission created.")
    else:
        print("Failure: Mission not created.")

except Exception as e:
    print(f"Error: {e}")
