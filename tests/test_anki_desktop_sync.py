from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_anki_desktop_status():
    resp = client.get('/api/v1/schedule/anki/desktop-status')
    assert resp.status_code == 200
    data = resp.json()
    assert 'connected' in data
    assert 'today_reviewed_count' in data
    assert 'due_tomorrow_count' in data
    assert 'due_tomorrow_topics' in data

def test_post_anki_desktop_sync():
    payload = {
        'today_reviewed_count': 25,
        'today_time_minutes': 15.0,
        'due_tomorrow_count': 10,
        'due_tomorrow_topics': [{'deck': 'TB Blut', 'count': 10}],
    }
    resp = client.post('/api/v1/schedule/anki/desktop-sync', json=payload)
    assert resp.status_code == 200
    assert resp.json()['status'] == 'ok'
