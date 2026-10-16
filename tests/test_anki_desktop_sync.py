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


def test_anki_wal_mode_active_uncheckpointed_reviews_replayed(tmp_path):
    """
    Simulates real-world Anki Desktop running in WAL mode on Windows.
    Verifies that open_anki_db_readonly replays uncheckpointed reviews from .anki2-wal
    instead of bypassing them with immutable=1.
    """
    import sqlite3
    from datetime import datetime, date
    from app.services.anki_desktop_sync import read_live_anki_desktop_state
    from app.db.anki_db import open_anki_db_readonly

    db_file = tmp_path / "collection.anki2"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode = WAL;")

    cur.execute("CREATE TABLE col (id integer primary key, crt integer)")
    cur.execute("CREATE TABLE decks (id integer primary key, name text)")
    cur.execute("CREATE TABLE cards (id integer primary key, nid integer, did integer, ord integer, mod integer, usn integer, type integer, queue integer, due integer, ivl integer, factor integer, reps integer, lapses integer, left integer, odue integer, odid integer, flags integer, data text)")
    cur.execute("CREATE TABLE notes (id integer primary key, guid text, mid integer, mod integer, usn integer, tags text, flds text, sfld text, csum integer, flags integer, data text)")
    cur.execute("CREATE TABLE revlog (id integer primary key, cid integer, usn integer, ease integer, ivl integer, lastIvl integer, factor integer, time integer, type integer)")

    cur.execute("INSERT INTO col VALUES (1, 1700000000)")
    cur.execute("INSERT INTO decks VALUES (1, 'TB Herz')")
    cur.execute("INSERT INTO notes VALUES (10, 'g1', 1, 0, 0, '', 'Card front', 'Card front', 0, 0, '')")
    cur.execute("INSERT INTO cards VALUES (101, 10, 1, 0, 0, 0, 2, 2, 100, 15, 2500, 5, 0, 0, 0, 0, 0, '')")

    # Insert review into WAL
    now_ms = int(datetime.now().timestamp() * 1000)
    cur.execute("INSERT INTO revlog VALUES (?, 101, -1, 3, 15, 7, 2500, 5000, 1)", (now_ms,))
    conn.commit()

    # Ensure WAL file exists on disk with content
    wal_file = tmp_path / "collection.anki2-wal"
    assert wal_file.exists() and wal_file.stat().st_size > 0

    # With open_anki_db_readonly, WAL is cleanly replayed:
    with open_anki_db_readonly(db_file) as reader_conn:
        rev_cnt = reader_conn.cursor().execute("SELECT count(*) FROM revlog").fetchone()[0]
        assert rev_cnt == 1

    # End-to-end sync state must see the review:
    result = read_live_anki_desktop_state(col_path=str(db_file), target_date_str=date.today().isoformat())
    assert result["connected"] is True
    assert result["total_reviews_count"] == 1
    assert result["repetition_cards_count"] == 1

    conn.close()


def test_real_anki_collection_live_sync_telemetry():
    """
    If running locally on Constantin's Windows PC with real Anki collection,
    verify that live Anki state captures all real reviews and does not report false zeros.
    """
    import os
    from app.services.anki_desktop_sync import read_live_anki_desktop_state, find_local_anki_collection

    col = find_local_anki_collection()
    if not col or not col.exists() or os.environ.get("APPDATA") is None:
        return  # Skip in headless CI environments

    state = read_live_anki_desktop_state(col_path=str(col))
    assert state["connected"] is True
    # If today's collection has reviews, they must not be 0:
    if state["total_reviews_count"] > 0:
        assert state["repetition_cards_count"] > 0 or state["new_cards_count"] > 0
        assert state["effective_study_minutes"] > 0.0


