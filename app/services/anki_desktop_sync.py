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
    clean = clean.replace('2. SJ - 1 :: ', '').replace('2. SJ - 1 TB ', 'TB ')
    clean = clean.replace('Einf\ufffdhrung', 'Einführung').replace('Einfhrung', 'Einführung')
    return clean.strip()

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
    is_cloud = (os.environ.get('APPDATA') is None)

    # In cloud (Render) or when laptop pushed a live sync payload:
    cached = get_cached_desktop_sync_state(target_date_str=query_date.isoformat())
    if is_cloud and cached:
        if cached.get('target_date') == query_date.isoformat():
            return cached

    if not target_path or not target_path.exists():
        if cached and cached.get('target_date') == query_date.isoformat():
            return cached
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
    target_day = int((datetime(query_date.year, query_date.month, query_date.day, 12, 0, 0).timestamp() - crt) // 86400)
    next_day = target_day + 1

    decks = {}
    for did, dname in cur.execute('SELECT id, name FROM decks').fetchall():
        decks[did] = clean_deck_name(dname)

    day_start_dt = datetime(query_date.year, query_date.month, query_date.day, 4, 0, 0)
    day_start_ms = int(day_start_dt.timestamp() * 1000)
    day_end_ms = day_start_ms + (86400 * 1000)

    rev_sql = 'SELECT r.id, r.cid, c.did, r.ease, r.ivl, r.lastIvl, r.time, r.type, n.sfld FROM revlog r JOIN cards c ON r.cid = c.id JOIN notes n ON c.nid = n.id WHERE r.id >= ? AND r.id < ? ORDER BY r.id DESC'
    revs_rows = cur.execute(rev_sql, (day_start_ms, day_end_ms)).fetchall()

    total_reviews_count = len(revs_rows)
    today_time_mins = round(sum(r[6] for r in revs_rows) / 1000 / 60, 1)
    today_lapses = sum(1 for r in revs_rows if r[3] == 1)

    # Real-life study session wall-clock time calculation:
    # Reviews within 10-minute pauses (600s) are grouped into contiguous study blocks
    sorted_revs = sorted(revs_rows, key=lambda x: x[0])
    sessions = []
    curr_sess = []
    for r in sorted_revs:
        ts = r[0] / 1000.0  # seconds
        card_dur = max(5.0, min(180.0, r[6] / 1000.0))
        if not curr_sess:
            curr_sess = [ts, ts + card_dur]
        else:
            if ts - curr_sess[1] <= 600:
                curr_sess[1] = max(curr_sess[1], ts + card_dur)
            else:
                sessions.append(curr_sess)
                curr_sess = [ts, ts + card_dur]
    if curr_sess:
        sessions.append(curr_sess)

    total_sess_sec = sum(s[1] - s[0] for s in sessions)
    today_session_time_mins = round(total_sess_sec / 60, 1)
    effective_study_mins = max(today_time_mins, today_session_time_mins)

    # Unique cards breakdown:
    # type = 0: new card (first learn) -> THIS counts towards the new cards pacing goal!
    # type in (1, 2): repetition / review / relearn
    unique_new_cids = set(r[1] for r in revs_rows if r[7] == 0)
    unique_rep_cids = set(r[1] for r in revs_rows if r[7] in (1, 2))

    new_cards_count = len(unique_new_cids)
    repetition_cards_count = len(unique_rep_cids)

    # Breakdown by deck for new cards
    new_by_deck = {}
    seen_new = set()
    for r in revs_rows:
        if r[7] == 0 and r[1] not in seen_new:
            seen_new.add(r[1])
            dname = decks.get(r[2], 'Unbekanntes Deck')
            new_by_deck[dname] = new_by_deck.get(dname, 0) + 1

    # Breakdown by deck for repetition cards
    rep_by_deck = {}
    seen_rep = set()
    for r in revs_rows:
        if r[7] in (1, 2) and r[1] not in seen_rep:
            seen_rep.add(r[1])
            dname = decks.get(r[2], 'Unbekanntes Deck')
            rep_by_deck[dname] = rep_by_deck.get(dname, 0) + 1

    today_breakdown = {}
    recent_sample = []
    for idx, r in enumerate(revs_rows):
        dname = decks.get(r[2], 'Unbekanntes Deck')
        today_breakdown[dname] = today_breakdown.get(dname, 0) + 1
        if idx < 10:
            rev_time_str = datetime.fromtimestamp(r[0] / 1000).strftime('%H:%M:%S')
            type_label = 'Neu' if r[7] == 0 else ('Wiederholung' if r[7] == 1 else 'Wiederlernen')
            recent_sample.append({
                'time': rev_time_str,
                'deck': dname,
                'ease': r[3],
                'ease_label': {1: 'Nochmal', 2: 'Schwer', 3: 'Gut', 4: 'Einfach'}.get(r[3], 'Gut'),
                'type_label': type_label,
                'front': r[8][:90] if r[8] else 'Karte',
            })

    due_today_cnt = cur.execute('SELECT count(*) FROM cards WHERE queue=2 AND due <= ?', (current_day,)).fetchone()[0]

    # Dynamically select cards due tomorrow relative to target query date!
    tom_sql = 'SELECT c.id, c.did, n.sfld FROM cards c JOIN notes n ON c.nid = n.id WHERE c.queue = 2 AND c.due = ?'
    due_tomorrow_rows = cur.execute(tom_sql, (next_day,)).fetchall()

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

    # Calculate yesterday's stats relative to today 04:00 AM
    today_4am_dt = datetime.now().replace(hour=4, minute=0, second=0, microsecond=0)
    today_4am_ms = int(today_4am_dt.timestamp() * 1000)
    yesterday_4am_ms = today_4am_ms - (86400 * 1000)

    y_new_rows = cur.execute('SELECT DISTINCT cid FROM revlog WHERE id >= ? AND id < ? AND type = 0', (yesterday_4am_ms, today_4am_ms)).fetchall()
    yesterday_new_cards = len(y_new_rows)
    y_rep_rows = cur.execute('SELECT DISTINCT cid FROM revlog WHERE id >= ? AND id < ? AND type IN (1, 2)', (yesterday_4am_ms, today_4am_ms)).fetchall()
    yesterday_rep_cards = len(y_rep_rows)
    y_rows = cur.execute('SELECT count(*), sum(time)/1000/60 FROM revlog WHERE id >= ? AND id < ?', (yesterday_4am_ms, today_4am_ms)).fetchone()
    yesterday_total_reviews = y_rows[0] or 0
    yesterday_time_mins = round(y_rows[1] or 0.0, 1)

    # Calculate real-time cumulative learned cards in 2. SJ curriculum
    conn.create_collation('unicase', lambda a, b: 0)
    cur.execute("""
        SELECT count(*),
               sum(case when c.reps > 0 or c.type > 0 then 1 else 0 end)
        FROM cards c
        JOIN decks d ON c.did = d.id
        WHERE (lower(d.name) LIKE '%2. sj%' OR lower(d.name) LIKE '%hs 2021%' OR lower(d.name) LIKE '%3. semester%')
          AND lower(d.name) NOT LIKE '%mündlich%'
    """)
    row_curr = cur.fetchone()
    total_curr = (row_curr[0] if row_curr else 0) or 8729
    mastered_curr = (row_curr[1] if row_curr else 0) or 0
    pct_curr = round((mastered_curr / max(1, total_curr)) * 100, 1)

    # Extract deck-level snapshot to keep Render / cloud in exact lockstep
    snapshot_sql = """
        SELECT c.did,
               count(*) as total,
               sum(case when c.reps = 0 and c.queue = 0 then 1 else 0 end) as new_cnt,
               sum(case when c.reps > 0 then 1 else 0 end) as mastered_cnt,
               sum(case when c.queue in (1, 3) then 1 else 0 end) as learning_cnt,
               avg(length(n.flds)) as avg_len
        FROM cards c
        LEFT JOIN notes n ON c.nid = n.id
        GROUP BY c.did
    """
    card_stats = cur.execute(snapshot_sql).fetchall()
    snapshot_decks = []
    for s_did, s_tot, s_new, s_mast, s_lrn, s_len in card_stats:
        raw_name = decks.get(s_did, "")
        if not raw_name:
            continue
        n_low = raw_name.lower()
        if ("2. sj" in n_low) or ("hs 2021" in n_low) or ("3. semester" in n_low):
            if "mündlich" in n_low or "muendlich" in n_low:
                continue
            snapshot_decks.append({
                "deck_id": s_did,
                "deck_name": raw_name,
                "card_count": s_tot,
                "new_cards": s_new or 0,
                "mastered_cards": s_mast or 0,
                "learning_cards": s_lrn or 0,
                "avg_card_chars": round(s_len or 320.0, 1),
                "is_completed": (s_new == 0 and s_mast > 0),
                "is_in_progress": (s_new > 0 and s_mast > 0),
            })

    result = {
        'connected': True,
        'source': 'Anki Desktop (Benutzer 1)',
        'target_date': query_date.isoformat(),
        'is_today': is_today,
        'collection_path': str(target_path),
        'today_reviewed_count': new_cards_count,  # Primary number for "In Anki erledigt" is NEW cards
        'new_cards_count': new_cards_count,
        'repetition_cards_count': repetition_cards_count,
        'total_reviews_count': total_reviews_count,
        'today_time_minutes': today_time_mins,
        'today_session_time_minutes': today_session_time_mins,
        'effective_study_minutes': effective_study_mins,
        'today_lapses_count': today_lapses,
        'today_new_count': new_cards_count,
        'today_review_count': repetition_cards_count,
        'today_deck_breakdown': today_breakdown,
        'new_by_deck': new_by_deck,
        'rep_by_deck': rep_by_deck,
        'yesterday_reviewed_count': yesterday_new_cards,
        'yesterday_new_cards_count': yesterday_new_cards,
        'yesterday_repetition_cards_count': yesterday_rep_cards,
        'yesterday_total_reviews_count': yesterday_total_reviews,
        'yesterday_time_minutes': yesterday_time_mins,
        'due_today_count': due_today_cnt,
        'due_reviews_count': due_today_cnt,
        'cumulative_cards_learned': mastered_curr,
        'total_curriculum_cards': total_curr,
        'curriculum_progress_pct': pct_curr,
        'curriculum_snapshot': snapshot_decks,
        'due_tomorrow_count': tomorrow_count,
        'due_tomorrow_deck_breakdown': tomorrow_breakdown,
        'due_tomorrow_topics': tomorrow_topics,
        'recent_reviews_sample': recent_sample,
        'due_tomorrow_sample': tomorrow_sample,
        'last_sync_timestamp': now.isoformat(),
        'current_day_index': current_day,
        'target_day_index': target_day,
        'next_day_index': next_day,
    }

    if total_reviews_count > 0 or new_cards_count > 0:
        try:
            save_daily_progress(
                target_date=query_date,
                cards_completed=new_cards_count,
                minutes_spent=int(round(effective_study_mins)),
                source='anki_desktop_auto',
                notes=f'Auto-Sync Anki Desktop ({new_cards_count} neue Karten, {repetition_cards_count} Repetitionen, {effective_study_mins}m Session, {today_time_mins}m Fokuszeit)',
                user_id='student',
            )
        except Exception:
            pass

    cache_desktop_sync_state(result)
    return result

def _ensure_cache_table(conn):
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS anki_desktop_sync_cache (
            target_date TEXT PRIMARY KEY,
            state_json TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    cols = [r[1] for r in cur.execute('PRAGMA table_info(anki_desktop_sync_cache)').fetchall()]
    if 'target_date' not in cols:
        cur.execute('DROP TABLE anki_desktop_sync_cache')
        cur.execute('''
            CREATE TABLE anki_desktop_sync_cache (
                target_date TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')

def cache_desktop_sync_state(state):
    try:
        t_date = state.get('target_date') or date.today().isoformat()
        with get_db_connection() as conn:
            _ensure_cache_table(conn)
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO anki_desktop_sync_cache (target_date, state_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(target_date) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = CURRENT_TIMESTAMP;
            ''', (t_date, json.dumps(state)))
    except Exception:
        pass

def get_cached_desktop_sync_state(target_date_str: Optional[str] = None):
    t_date = target_date_str or date.today().isoformat()
    try:
        with get_db_connection() as conn:
            _ensure_cache_table(conn)
            cur = conn.cursor()
            row = cur.execute('SELECT state_json FROM anki_desktop_sync_cache WHERE target_date = ?', (t_date,)).fetchone()
            if row:
                return json.loads(row[0])
    except Exception:
        pass
    return None
