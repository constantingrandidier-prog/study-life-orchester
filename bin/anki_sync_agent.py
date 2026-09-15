import sys
import os
import time
import json
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.services.anki_desktop_sync import read_live_anki_desktop_state, find_local_anki_collection
from app.services.anki_backlog_triage import calculate_backlog_triage

TARGET_SYNC_URLS = [
    'https://study-life-orchester.onrender.com/api/v1/schedule/anki/desktop-sync',
    'https://study-life-orchester-8gci.onrender.com/api/v1/schedule/anki/desktop-sync',
    'http://127.0.0.1:8000/api/v1/schedule/anki/desktop-sync'
]

TARGET_TRIAGE_URLS = [
    'https://study-life-orchester.onrender.com/api/v1/schedule/anki/triage-sync',
    'https://study-life-orchester-8gci.onrender.com/api/v1/schedule/anki/triage-sync',
    'http://127.0.0.1:8000/api/v1/schedule/anki/triage-sync'
]

def sync_now():
    from datetime import date, timedelta
    # 1. Sync yesterday's state (ensures roadmap quota calculation has exact count)
    try:
        yesterday_str = (date.today() - timedelta(days=1)).isoformat()
        y_state = read_live_anki_desktop_state(target_date_str=yesterday_str)
        y_data = json.dumps(y_state).encode('utf-8')
        for url in TARGET_SYNC_URLS:
            try:
                req = urllib.request.Request(url, data=y_data, headers={'Content-Type': 'application/json'}, method='POST')
                urllib.request.urlopen(req, timeout=10)
            except Exception:
                pass
    except Exception:
        pass

    # 2. Sync today's state
    state = read_live_anki_desktop_state()
    data = json.dumps(state).encode('utf-8')
    for url in TARGET_SYNC_URLS:
        try:
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass

    # 3. Also sync triage
    try:
        triage = calculate_backlog_triage()
        tdata = json.dumps(triage).encode('utf-8')
        for url in TARGET_TRIAGE_URLS:
            try:
                treq = urllib.request.Request(url, data=tdata, headers={'Content-Type': 'application/json'}, method='POST')
                urllib.request.urlopen(treq, timeout=10)
            except Exception:
                pass
    except Exception:
        pass

    revs = state.get('today_reviewed_count', 0)
    reps = state.get('repetition_cards_count', 0)
    done = state.get('due_tomorrow_count', 0)
    print(f'Synced: {revs} new cards, {reps} repetitions, {done} due tomorrow (Triage updated).')

if __name__ == '__main__':
    if '--once' in sys.argv:
        sync_now()
    else:
        col = find_local_anki_collection()
        last_mtime = 0
        print('Anki Live Sync Agent running in background (monitoring collection.anki2)...')
        while True:
            try:
                if col and col.exists():
                    m = col.stat().st_mtime
                    if m != last_mtime:
                        sync_now()
                        last_mtime = m
            except Exception:
                pass
            time.sleep(15)
