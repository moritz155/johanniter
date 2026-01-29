def test_api_init_empty(client):
    rv = client.get('/api/init')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'squads' in data
    assert 'missions' in data
    assert data['config'] is None

def test_config_start(client):
    payload = {
        "location": "Test Event",
        "squads": [{"name": "S1"}]
    }
    rv = client.post('/api/config', json=payload)
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['location'] == "Test Event"
    assert data['session_id'] is not None

    # Check init again
    rv = client.get('/api/init')
    data = rv.get_json()
    assert data['config']['location'] == "Test Event"
    assert len(data['squads']) == 1
    assert data['squads'][0]['name'] == "S1"
