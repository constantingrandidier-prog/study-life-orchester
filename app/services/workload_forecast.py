import os
import json
import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.services.anki_desktop_sync import find_local_anki_collection, clean_deck_name
from app.db.repository import get_db_connection

def get_workload_forecast(col_path=None, days_ahead: int = 14) -> Dict[str, Any]:
    """
    Computes a 14-day forward-looking workload forecast from Anki's review queue.
    Identifies workload spikes and generates smoothing tips for medical exam preparation.
    """
    target_path = Path(col_path) if col_path else find_local_anki_collection()
    now = datetime.now()
    today = date.today()

    is_cloud = (os.environ.get("APPDATA") is None)
    if is_cloud or not target_path or not target_path.exists():
        cached = get_cached_workload_forecast()
        if cached:
            return cached
        if not target_path or not target_path.exists():
            return {
                "connected": False,
                "days_ahead": days_ahead,
                "days": [],
                "max_day_cards": 0,
                "average_daily_due": 0.0,
                "has_spike": False,
                "spike_days": [],
                "smoothing_advice": "Keine Anki-Datenbank für Prognose gefunden.",
            }

    uri = f"file:///{target_path.as_posix()}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    cur = conn.cursor()

    crt = cur.execute("SELECT crt FROM col").fetchone()[0]
    curr_day = int((now.timestamp() - crt) // 86400)
    end_day = curr_day + days_ahead

    decks = {}
    for did, dname in cur.execute("SELECT id, name FROM decks").fetchall():
        decks[did] = clean_deck_name(dname)

    # Fetch daily due sums and deck breakdown for the next N days
    sql_due = """
    SELECT c.due, c.did, COUNT(*) as card_count
    FROM cards c
    WHERE c.queue = 2 AND c.due >= ? AND c.due <= ?
    GROUP BY c.due, c.did
    ORDER BY c.due ASC, card_count DESC
    """
    rows = cur.execute(sql_due, (curr_day, end_day)).fetchall()

    day_data: Dict[int, Dict[str, Any]] = {}
    for offset in range(days_ahead + 1):
        target_due = curr_day + offset
        d_date = today + timedelta(days=offset)
        day_name = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][d_date.weekday()]
        day_data[target_due] = {
            "due_index": target_due,
            "day_offset": offset,
            "date": d_date.isoformat(),
            "formatted_date": f"{day_name} {d_date.strftime('%d.%m')}",
            "day_name": day_name,
            "total_due": 0,
            "deck_breakdown": [],
            "workload_level": "low",
            "level_color": "#3fb950",
            "is_spike": False,
        }

    for due_val, did, count in rows:
        if due_val in day_data:
            day_data[due_val]["total_due"] += count
            dname = decks.get(did, f"Deck {did}")
            day_data[due_val]["deck_breakdown"].append({
                "deck_name": dname,
                "count": count
            })

    days_list = list(day_data.values())
    total_cards = sum(d["total_due"] for d in days_list)
    avg_cards = round(total_cards / len(days_list), 1) if days_list else 0.0
    max_cards = max((d["total_due"] for d in days_list), default=0)

    spike_days = []
    for d in days_list:
        cnt = d["total_due"]
        if cnt >= 350:
            d["workload_level"] = "extreme"
            d["level_color"] = "#f85149"
            d["is_spike"] = True
            spike_days.append(d["formatted_date"])
        elif cnt >= 200:
            d["workload_level"] = "high"
            d["level_color"] = "#d29922"
            d["is_spike"] = True
            spike_days.append(d["formatted_date"])
        elif cnt >= 80:
            d["workload_level"] = "moderate"
            d["level_color"] = "#58a6ff"
        else:
            d["workload_level"] = "low"
            d["level_color"] = "#3fb950"

    has_spike = len(spike_days) > 0
    if has_spike:
        smoothing_advice = f"⚠️ Belastungsspitzen erkannt an: {', '.join(spike_days[:3])}. Ziehe an schwächeren Tagen vorab jeweils 20–30 Wiederholungen vor."
    elif avg_cards > 150:
        smoothing_advice = "Stetig hohes Lernpensum. Plane tägliche Morgen-Sessions (30–45 Min.) fest ein."
    else:
        smoothing_advice = "Sehr stabiler, gleichmäßiger Workload für die nächsten 14 Tage."

    result = {
        "connected": True,
        "timestamp": now.isoformat(),
        "days_ahead": days_ahead,
        "days": days_list,
        "total_due_14d": total_cards,
        "max_day_cards": max_cards,
        "average_daily_due": avg_cards,
        "has_spike": has_spike,
        "spike_days": spike_days,
        "smoothing_advice": smoothing_advice,
    }

    cache_workload_forecast(result)
    return result

def cache_workload_forecast(data: Dict[str, Any]):
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS anki_workload_forecast_cache (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    data_json TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                INSERT INTO anki_workload_forecast_cache (id, data_json, updated_at)
                VALUES (1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    data_json = excluded.data_json,
                    updated_at = CURRENT_TIMESTAMP;
            """, (json.dumps(data),))
    except Exception:
        pass

def get_cached_workload_forecast() -> Optional[Dict[str, Any]]:
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS anki_workload_forecast_cache (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    data_json TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            row = cur.execute("SELECT data_json FROM anki_workload_forecast_cache WHERE id = 1").fetchone()
            if row:
                return json.loads(row[0])
    except Exception:
        pass
    return None
