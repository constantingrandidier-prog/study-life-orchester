import os
import json
import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.services.anki_desktop_sync import find_local_anki_collection, clean_deck_name
from app.db.repository import get_db_connection

def calculate_backlog_triage(col_path=None, max_capacity: Optional[int] = None) -> Dict[str, Any]:
    target_path = Path(col_path) if col_path else find_local_anki_collection()
    now = datetime.now()

    is_cloud = (os.environ.get("APPDATA") is None)
    if is_cloud or not target_path or not target_path.exists():
        cached = get_cached_triage()
        if cached:
            if max_capacity:
                cached["max_capacity"] = max_capacity
                _apply_budget(cached, max_capacity)
            return cached
        if not target_path or not target_path.exists():
            return {
                "connected": False,
                "total_due_today": 0,
                "total_due_tomorrow": 0,
                "is_overloaded": False,
                "topics": [],
                "urgent_topics": [],
                "deferrable_topics": [],
                "summary_advice": "Keine Anki-Datenbank gefunden.",
            }

    uri = f"file:///{target_path.as_posix()}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    cur = conn.cursor()

    crt = cur.execute("SELECT crt FROM col").fetchone()[0]
    current_day = int((now.timestamp() - crt) // 86400)
    next_day = current_day + 1

    decks = {}
    for did, dname in cur.execute("SELECT id, name FROM decks").fetchall():
        decks[did] = clean_deck_name(dname)

    sql_cards = """
    SELECT 
        c.did,
        COUNT(*) as total_cards,
        SUM(CASE WHEN c.queue = 2 AND c.due <= ? THEN 1 ELSE 0 END) as due_now,
        SUM(CASE WHEN c.queue = 2 AND c.due = ? THEN 1 ELSE 0 END) as due_tomorrow,
        SUM(CASE WHEN c.queue = 2 THEN 1 ELSE 0 END) as active_review_cards,
        AVG(CASE WHEN c.queue = 2 AND c.factor > 0 THEN c.factor ELSE NULL END) as avg_ease,
        SUM(c.lapses) as total_lapses,
        SUM(c.reps) as total_reps
    FROM cards c
    WHERE c.queue != -1
    GROUP BY c.did
    """
    cards_stats = cur.execute(sql_cards, (current_day, next_day)).fetchall()

    sql_revs = """
    SELECT c.did, MAX(r.id) as last_ms, COUNT(*) as total_revs,
           SUM(CASE WHEN r.ease = 1 THEN 1 ELSE 0 END) as fail_count
    FROM revlog r
    JOIN cards c ON r.cid = c.id
    GROUP BY c.did
    """
    rev_stats = {r[0]: {"last_ms": r[1], "revs": r[2], "fails": r[3]} for r in cur.execute(sql_revs).fetchall()}

    topics = []
    total_due_today = 0
    total_due_tomorrow = 0

    for r in cards_stats:
        did, total, due_now, due_tom, active, avg_ease, lapses, reps = r
        if active == 0 and due_now == 0 and due_tom == 0:
            continue
        
        dname = decks.get(did, f"Deck {did}")
        r_info = rev_stats.get(did, {"last_ms": 0, "revs": 0, "fails": 0})
        last_ms = r_info["last_ms"]
        
        days_ago = round((now.timestamp() * 1000 - last_ms) / (86400 * 1000), 1) if last_ms else 30.0
        avg_ease_pct = round(avg_ease / 10, 1) if avg_ease else 250.0
        fail_rate = round((r_info["fails"] / r_info["revs"] * 100) if r_info["revs"] > 0 else 0.0, 1)
        retention_rate = round(100.0 - fail_rate, 1)

        total_due_today += due_now
        total_due_tomorrow += due_tom

        time_score = min(30.0, (days_ago / 7.0) * 30.0)
        fail_score = min(40.0, (fail_rate / 45.0) * 40.0)
        ease_penalty = min(20.0, max(0.0, (250.0 - avg_ease_pct) / 40.0 * 20.0))
        volume_score = min(10.0, (max(due_now, due_tom) / 30.0) * 10.0)

        urgency_score = round(time_score + fail_score + ease_penalty + volume_score, 1)

        if urgency_score >= 45.0 or fail_rate >= 35.0:
            urgency_level = "KRITISCH"
            level_badge = "🚨 Höchste Priorität"
            color = "#f85149"
            action = "Unbedingt heute wiederholen (hohes Vergessensrisiko!)"
        elif urgency_score >= 25.0:
            urgency_level = "HOCH"
            level_badge = "⚠️ Mittlere Priorität"
            color = "#d29922"
            action = "Sollte heute gemacht werden"
        else:
            urgency_level = "STABIL"
            level_badge = "✅ Stabil (Kann warten)"
            color = "#3fb950"
            action = "Kann bei Zeitmangel problemlos auf morgen geschoben werden"

        anki_filter_query = f'deck:"{dname}" is:due'
        anki_hard_query = f'deck:"{dname}" is:due (prop:ease<2.3 or lapses>1)'

        topics.append({
            "deck_id": did,
            "deck_name": dname,
            "total_cards": total,
            "due_today": due_now,
            "due_tomorrow": due_tom,
            "active_reviews": active,
            "days_since_last_review": days_ago,
            "avg_ease_pct": avg_ease_pct,
            "fail_rate_pct": fail_rate,
            "retention_rate_pct": retention_rate,
            "urgency_score": urgency_score,
            "urgency_level": urgency_level,
            "level_badge": level_badge,
            "color": color,
            "action_recommendation": action,
            "anki_filter_query": anki_filter_query,
            "anki_hard_query": anki_hard_query,
        })

    topics.sort(key=lambda x: x["urgency_score"], reverse=True)

    urgent_topics = [t for t in topics if t["urgency_level"] in ("KRITISCH", "HOCH")]
    deferrable_topics = [t for t in topics if t["urgency_level"] == "STABIL"]

    is_overloaded = (total_due_today >= 500 or total_due_tomorrow >= 500)

    # Generate combined filter query for top urgent decks (up to 4 decks)
    top_urgent = urgent_topics[:4] if urgent_topics else topics[:3]
    if top_urgent:
        clauses = " or ".join([f'deck:"{t["deck_name"]}"' for t in top_urgent])
        urgent_combined_anki_query = f'({clauses}) is:due'
    else:
        urgent_combined_anki_query = "is:due"

    if total_due_today >= 500:
        summary_advice = f"🚨 Achtung: Du hast heute {total_due_today} Wiederholungen! Konzentriere dich nur auf die {len(urgent_topics)} rot markierten Themen mit höchstem Vergessensrisiko."
    elif total_due_tomorrow >= 100:
        summary_advice = f"Für morgen stehen {total_due_tomorrow} Repetitionen an. Priorisiere die Themen mit der höchsten Fehlerquote zuerst."
    else:
        summary_advice = "Dein Anki-Pensum ist aktuell im grünen Bereich. Alle Themen sind stabil im Plan."

    result = {
        "connected": True,
        "timestamp": now.isoformat(),
        "total_due_today": total_due_today,
        "total_due_tomorrow": total_due_tomorrow,
        "is_overloaded": is_overloaded,
        "topics_count": len(topics),
        "topics": topics,
        "urgent_topics": urgent_topics,
        "deferrable_topics": deferrable_topics,
        "urgent_combined_anki_query": urgent_combined_anki_query,
        "summary_advice": summary_advice,
    }

    if max_capacity:
        _apply_budget(result, max_capacity)

    cache_triage(result)
    return result

def _apply_budget(result: Dict[str, Any], budget: int):
    selected = []
    accumulated = 0
    deferred = []
    for t in result.get("topics", []):
        needed = max(t.get("due_today", 0), t.get("due_tomorrow", 0))
        if needed == 0:
            continue
        if accumulated + needed <= budget or not selected:
            selected.append(t)
            accumulated += needed
        else:
            deferred.append(t)
    result["budget_selected_topics"] = selected
    result["budget_deferred_topics"] = deferred
    result["budget_accumulated_cards"] = accumulated
    result["max_capacity"] = budget
    if selected:
        deck_clauses = " or ".join([f'deck:"{t["deck_name"]}"' for t in selected])
        result["budget_combined_anki_query"] = f'({deck_clauses}) is:due'
    else:
        result["budget_combined_anki_query"] = "is:due"

def cache_triage(data: Dict[str, Any]):
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS anki_backlog_triage_cache (id INTEGER PRIMARY KEY CHECK (id = 1), data_json TEXT NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
            cur.execute("INSERT INTO anki_backlog_triage_cache (id, data_json, updated_at) VALUES (1, ?, CURRENT_TIMESTAMP) ON CONFLICT(id) DO UPDATE SET data_json = excluded.data_json, updated_at = CURRENT_TIMESTAMP;", (json.dumps(data),))
    except Exception:
        pass

def get_cached_triage() -> Optional[Dict[str, Any]]:
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS anki_backlog_triage_cache (id INTEGER PRIMARY KEY CHECK (id = 1), data_json TEXT NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
            row = cur.execute("SELECT data_json FROM anki_backlog_triage_cache WHERE id = 1").fetchone()
            if row:
                return json.loads(row[0])
    except Exception:
        pass
    return None
