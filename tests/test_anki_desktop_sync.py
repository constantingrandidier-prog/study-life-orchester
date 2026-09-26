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
        'target_date': '2099-01-01',
        'today_reviewed_count': 25,
        'new_cards_count': 25,
        'new_cards_opened_count': 35,
        'new_cards_in_learning_count': 10,
        'today_time_minutes': 15.0,
        'due_tomorrow_count': 10,
        'due_tomorrow_topics': [{'deck': 'TB Blut', 'count': 10}],
    }
    resp = client.post('/api/v1/schedule/anki/desktop-sync', json=payload)
    assert resp.status_code == 200
    assert resp.json()['status'] == 'ok'

    from app.services.anki_desktop_sync import get_cached_desktop_sync_state
    cached = get_cached_desktop_sync_state('2099-01-01')
    assert cached is not None
    assert cached.get('new_cards_count') == 25
    assert cached.get('new_cards_opened_count') == 35
    assert cached.get('new_cards_in_learning_count') == 10

def test_anki_graduation_logic_in_sqlite(tmp_path):
    import sqlite3
    from datetime import datetime, date
    from app.services.anki_desktop_sync import read_live_anki_desktop_state

    db_file = tmp_path / "collection.anki2"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    
    # Minimal Anki schema
    cur.execute("CREATE TABLE col (id integer primary key, crt integer)")
    cur.execute("CREATE TABLE decks (id integer primary key, name text)")
    cur.execute("CREATE TABLE cards (id integer primary key, nid integer, did integer, ord integer, mod integer, usn integer, type integer, queue integer, due integer, ivl integer, factor integer, reps integer, lapses integer, left integer, odue integer, odid integer, flags integer, data text)")
    cur.execute("CREATE TABLE notes (id integer primary key, guid text, mid integer, mod integer, usn integer, tags text, flds text, sfld text, csum integer, flags integer, data text)")
    cur.execute("CREATE TABLE revlog (id integer primary key, cid integer, usn integer, ease integer, ivl integer, lastIvl integer, factor integer, time integer, type integer)")

    # crt: creation timestamp (e.g. 1700000000)
    cur.execute("INSERT INTO col VALUES (1, 1700000000)")
    cur.execute("INSERT INTO decks VALUES (1, 'TestDeck')")
    cur.execute("INSERT INTO notes VALUES (10, 'g1', 1, 0, 0, '', 'Note 1', 'Note 1 front', 0, 0, '')")
    cur.execute("INSERT INTO notes VALUES (20, 'g2', 1, 0, 0, '', 'Note 2', 'Note 2 front', 0, 0, '')")
    cur.execute("INSERT INTO notes VALUES (30, 'g3', 1, 0, 0, '', 'Note 3', 'Note 3 front', 0, 0, '')")

    cur.execute("INSERT INTO cards VALUES (101, 10, 1, 0, 0, 0, 0, 2, 100, 1, 2500, 2, 0, 0, 0, 0, 0, '')")
    cur.execute("INSERT INTO cards VALUES (102, 20, 1, 0, 0, 0, 0, 1, 100, -600, 2500, 1, 0, 0, 0, 0, 0, '')")
    cur.execute("INSERT INTO cards VALUES (103, 30, 1, 0, 0, 0, 2, 2, 100, 15, 2500, 5, 0, 0, 0, 0, 0, '')")

    # Reviews today (after 04:00 AM)
    today_dt = datetime.now()
    now_ms = int(today_dt.timestamp() * 1000)

    # Card 101: graduated new card (first touch -600s, second touch ivl=1 day)
    cur.execute("INSERT INTO revlog VALUES (?, 101, -1, 3, -600, 0, 0, 10000, 0)", (now_ms - 20000,))
    cur.execute("INSERT INTO revlog VALUES (?, 101, -1, 3, 1, -600, 0, 8000, 0)", (now_ms - 10000,))

    # Card 102: new card still in intra-day learning (last touch ivl=-600)
    cur.execute("INSERT INTO revlog VALUES (?, 102, -1, 3, -600, 0, 0, 9000, 0)", (now_ms - 5000,))

    # Card 103: repetition card (type=1, ivl=15)
    cur.execute("INSERT INTO revlog VALUES (?, 103, -1, 3, 15, 7, 2500, 7000, 1)", (now_ms - 1000,))

    conn.commit()
    conn.close()

    result = read_live_anki_desktop_state(col_path=str(db_file), target_date_str=date.today().isoformat())
    assert result['connected'] is True
    # Card 101 graduated, Card 102 still learning:
    assert result['new_cards_count'] == 1
    assert result['new_cards_opened_count'] == 2
    assert result['new_cards_in_learning_count'] == 1
    assert result['repetition_cards_count'] == 1
    assert result['today_reviewed_count'] == 1

