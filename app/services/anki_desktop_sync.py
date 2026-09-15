import os
import json
import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.db.repository import save_daily_progress, get_db_connection

def find_local_anki_collection():
    appdata = os.environ.get('APPDATA')
    if appdata:
        p = Path(appdata) / 'Anki2' / 'Benutzer 1' / 'collection.anki2'
        if p.exists():
            return p
        base = Path(appdata) / 'Anki2'
        if base.exists():
            for folder in base.iterdir():
                if folder.is_dir() and (folder / 'collection.anki2').exists() and not folder.name.startswith('.'):
                    return folder / 'collection.anki2'

    bundled = Path(__file__).resolve().parent.parent / 'data' / 'anki' / 'Benutzer 1' / 'collection.anki2'
    if bundled.exists():
        return bundled
    bundled_alt = Path(__file__).resolve().parent.parent / 'data' / 'collection.anki2'
    if bundled_alt.exists():
        return bundled_alt
    return None

def clean_deck_name(dname):
    clean = dname.replace(chr(31), ' :: ')
    clean = clean.replace('1year :: 1. Semester :: ', '').replace('1year :: 2.Semester :: ', '').replace('1year :: ', '')
    return clean

def read_live_anki_desktop_state(col_path=None, target_date_str=None):
    target_path = Path(col_path) if col_path else find_local_anki_collection()
    now = datetime.now()

    if target_date_str:
        try:
            query_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        except ValueError:
            query_date = date.today()
    else:
        query_date = date.today()

    is_today = (query_date == date.today())

    if not target_path or not target_path.exists():
        last_state = get_cached_desktop_sync_state()
        if last_state:
            return last_state
        return {
            'connected': False,
            'source': 'None',
            'collection_path': None,
            'target_date': query_date.isoformat(),
            'today_reviewed_count': 0,
            'today_time_minutes': 0.0,
            'today_lapses_count': 0,
            'today_new_count': 0,
            'today_review_count': 0,
            'today_relearn_count': 0,
            'today_deck_breakdown': {},
            'due_today_count': 85,
            'due_tomorrow_count': 0,
            'due_tomorrow_deck_breakdown': {},
            'due_tomorrow_topics': [],
            'recent_reviews_sample': [],
            'due_tomorrow_sample': [],
            'last_sync_timestamp': now.isoformat(),
            'message': 'Keine Anki-Desktop Sammlung gefunden.',
        }

    uri = f'file:///{target_path.as_posix()}?mode=ro&immutable=1'
    conn = sqlite3.connect(uri, uri=True)
    cur = conn.cursor()

    crt = cur.execute('SELECT crt FROM col').fetchone()[0]
    current_day = int((now.timestamp() - crt) // 86400)

    decks = {}
    for did, dname in cur.execute('SELECT id, name FROM decks').fetchall():
        decks[did] = clean_deck_name(dname)

    day_start_dt = datetime(query_date.year, query_date.month, query_date.day, 4, 0, 0)
    day_start_ms = int(day_start_dt.timestamp() * 1000)
    day_end_ms = day_start_ms + (86400 * 1000)

    rev_sql = 'SELECT r.id, r.cid, c.did, r.ease, r.ivl, r.lastIvl, r.time, r.type, n.sfld FROM revlog r JOIN cards c ON r.cid = c.id JOIN notes n ON c.nid = n.id WHERE r.id >= ? AND r.id < ? ORDER BY r.id DESC'
    revs_rows = cur.execute(rev_sql, (day_start_ms, day_end_ms)).fetchall()

    today_count = len(revs_rows)
    today_time_mins = round(sum(r[6] for r in revs_rows) / 1000 / 60, 1)
    today_lapses = sum(1 for r in revs_rows if r[3] == 1)
    today_new = sum(1 for r in revs_rows if r[7] == 0)
    today_review = sum(1 for r in revs_rows if r[7] == 1)
    today_relearn = sum(1 for r in revs_rows if r[7] == 2)

    today_breakdown = {}
    recent_sample = []
    for idx, r in enumerate(revs_rows):
        dname = decks.get(r[2], 'Unbekanntes Deck')
        today_breakdown[dname] = today_breakdown.get(dname, 0) + 1
        if idx < 10:
            rev_time_str = datetime.fromtimestamp(r[0] / 1000).strftime('%H:%M:%S')
            recent_sample.append({
                'time': rev_time_str,
                'deck': dname,
                'ease': r[3],
                'ease_label': {1: 'Nochmal', 2: 'Schwer', 3: 'Gut', 4: 'Einfach'}.get(r[3], 'Gut'),
                'front': r[8][:90] if r[8] else 'Karte',
            })

    due_today_cnt = cur.execute('SELECT count(*) FROM cards WHERE queue=2 AND due <= ?', (current_day,)).fetchone()[0]

    tom_sql = 'SELECT c.id, c.did, n.sfld FROM cards c JOIN notes n ON c.nid = n.id WHERE c.queue = 2 AND c.due = ?'
    due_tomorrow_rows = cur.execute(tom_sql, (current_day + 1,)).fetchall()

    tomorrow_breakdown = {}
    tomorrow_sample = []
    for idx, r in enumerate(due_tomorrow_rows):
        dname = decks.get(r[1], 'Unbekanntes Deck')
        tomorrow_breakdown[dname] = tomorrow_breakdown.get(dname, 0) + 1
        if idx < 15:
            tomorrow_sample.append({
                'card_id': r[0],
                'deck': dname,
                'front': r[2][:90] if r[2] else 'Karte',
            })

    tomorrow_count = len(due_tomorrow_rows)
    tomorrow_topics = [
        {'deck': k, 'count': v}
        for k, v in sorted(tomorrow_breakdown.items(), key=lambda x: x[1], reverse=True)
    ]

    conn.close()

    result = {
        'connected': True,
        'source': 'Anki Desktop (Benutzer 1)',
        'target_date': query_date.isoformat(),
        'is_today': is_today,
        'collection_path': str(target_path),
        'today_reviewed_count': today_count,
        'today_time_minutes': today_time_mins,
        'today_lapses_count': today_lapses,
        'today_new_count': today_new,
        'today_review_count': today_review,
        'today_relearn_count': today_relearn,
        'today_deck_breakdown': today_breakdown,
        'due_today_count': due_today_cnt,
        'due_tomorrow_count': tomorrow_count,
        'due_tomorrow_deck_breakdown': tomorrow_breakdown,
        'due_tomorrow_topics': tomorrow_topics,
        'recent_reviews_sample': recent_sample,
        'due_tomorrow_sample': tomorrow_sample,
        'last_sync_timestamp': now.isoformat(),
        'current_day_index': current_day,
    }

    if today_count > 0:
        try:
            save_daily_progress(
                target_date=query_date,
                cards_completed=today_count,
                minutes_spent=int(today_time_mins),
                source='anki_desktop_auto',
                notes=f'Auto-Sync Anki Desktop ({today_count} Karten, {today_time_mins}m)',
                user_id='student',
            )
        except Exception:
            pass

    cache_desktop_sync_state(result)
    return result

def cache_desktop_sync_state(state):
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute('CREATE TABLE IF NOT EXISTS anki_desktop_sync_cache (id INTEGER PRIMARY KEY CHECK (id = 1), state_json TEXT NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);')
            cur.execute('INSERT INTO anki_desktop_sync_cache (id, state_json, updated_at) VALUES (1, ?, CURRENT_TIMESTAMP) ON CONFLICT(id) DO UPDATE SET state_json = excluded.state_json, updated_at = CURRENT_TIMESTAMP;', (json.dumps(state),))
    except Exception:
        pass

def get_cached_desktop_sync_state():
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute('CREATE TABLE IF NOT EXISTS anki_desktop_sync_cache (id INTEGER PRIMARY KEY CHECK (id = 1), state_json TEXT NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);')
            row = cur.execute('SELECT state_json FROM anki_desktop_sync_cache WHERE id = 1').fetchone()
            if row:
                return json.loads(row[0])
    except Exception:
        pass
    return None
