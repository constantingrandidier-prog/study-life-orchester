"""
Service for comprehensive Anki Deck & Retention Statistics.
Computes retention rates, review counts, recency, and card breakdown
for both major topics (Überthemen) and individual small decks with exact Anki names.
"""

import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.db.repository import get_db_connection
from app.services.anki_desktop_sync import find_local_anki_collection


def clean_display_name(raw_name: str) -> str:
    """Converts internal Anki unit separator to ' :: ' and fixes UTF-8 glitches."""
    name = raw_name.replace("\x1f", " :: ")
    reps = {
        "Einf\ufffdhrung": "Einführung",
        "Einfhrung": "Einführung",
        "Mundh\ufffdhle": "Mundhöhle",
        "Mundhhle": "Mundhöhle",
        "Z\ufffdhne": "Zähne",
        "Zhne": "Zähne",
        "Zellul\ufffdre": "Zelluläre",
        "Zellulre": "Zelluläre",
        "Immunit\ufffdt": "Immunität",
        "Immunitt": "Immunität",
        "M\ufffdndlich": "Mündlich",
        "Mndlich": "Mündlich",
        "Atmosph\ufffdre": "Atmosphäre",
        "Gef\ufffd\ufffd": "Gefäss",
        "Gef\ufffdss": "Gefäss",
        "T\ufffdrk": "Türk",
        "Fr\ufffdh": "Früh",
        "Sp\ufffdt": "Spät",
        "Schl\ufffdssel": "Schlüssel",
        "H\ufffdmostase": "Hämostase",
    }
    for k, v in reps.items():
        name = name.replace(k, v)
    return name.strip()


def extract_parent_topic(raw_name: str) -> str:
    """Extracts the major Überthema (Themenblock / Modul) from the deck path."""
    clean = clean_display_name(raw_name)
    parts = [p.strip() for p in clean.split("::")]
    
    # 2. SJ - 1 hierarchy: '2. SJ - 1 :: TB Blut/Immunsystem :: ...'
    for part in parts:
        if part.startswith("TB "):
            return part
    
    if len(parts) >= 2:
        return f"{parts[0]} :: {parts[1]}"
    return parts[0] if parts else "Sonstige Decks"


def _ensure_cache_table(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS anki_deck_stats_cache (
            id INTEGER PRIMARY KEY,
            payload_json TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)


def cache_deck_stats(stats: Dict[str, Any]):
    try:
        with get_db_connection() as conn:
            _ensure_cache_table(conn)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO anki_deck_stats_cache (id, payload_json, updated_at)
                VALUES (1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP;
            """, (json.dumps(stats),))
    except Exception:
        pass


def get_cached_deck_stats() -> Optional[Dict[str, Any]]:
    try:
        with get_db_connection() as conn:
            _ensure_cache_table(conn)
            cur = conn.cursor()
            row = cur.execute("SELECT payload_json FROM anki_deck_stats_cache WHERE id = 1").fetchone()
            if row:
                return json.loads(row[0])
    except Exception:
        pass
    return None


def get_detailed_deck_stats(col_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes comprehensive retention and recency statistics for all decks.
    Works directly with local collection.anki2 or falls back to cached daemon state.
    """
    target_path = Path(col_path) if col_path else find_local_anki_collection()
    now_ms = time.time() * 1000

    if not target_path or not target_path.exists():
        cached = get_cached_deck_stats()
        if cached:
            return cached
        return {
            "available": False,
            "message": "Keine lokale Anki-Sammlung gefunden und noch kein Cache vorhanden.",
            "topics": [],
            "all_decks": [],
            "summary": {
                "total_decks": 0,
                "total_cards": 0,
                "total_reviews": 0,
                "overall_retention": 0.0,
                "weak_decks_count": 0,
                "neglected_decks_count": 0,
            }
        }

    uri = f"file:///{target_path.as_posix()}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    cur = conn.cursor()

    # Get current Anki day index
    crt = cur.execute("SELECT crt FROM col").fetchone()[0]
    today_anki_day = int((time.time() - crt) / 86400)

    # 1. Decks metadata
    raw_decks = cur.execute("SELECT id, name FROM decks").fetchall()
    decks_info = {}
    for did, dname in raw_decks:
        clean_name = clean_display_name(dname)
        parent_topic = extract_parent_topic(dname)
        decks_info[did] = {
            "deck_id": did,
            "raw_name": dname,
            "anki_name": clean_name,
            "parent_topic": parent_topic,
        }

    # 2. Card stats per deck
    card_sql = """
        SELECT 
            c.did,
            count(c.id) as total_cards,
            sum(case when c.queue = 0 then 1 else 0 end) as new_cards,
            sum(case when c.queue in (1, 3) then 1 else 0 end) as learning_cards,
            sum(case when c.queue = 2 and c.ivl >= 21 then 1 else 0 end) as mature_cards,
            sum(case when c.queue = 2 and c.ivl < 21 then 1 else 0 end) as young_cards,
            sum(case when c.queue = 1 or (c.queue = 2 and c.due <= ?) then 1 else 0 end) as due_cards,
            avg(case when c.factor > 0 then c.factor else null end) as avg_factor
        FROM cards c
        GROUP BY c.did
    """
    card_data = {r[0]: r for r in cur.execute(card_sql, (today_anki_day,)).fetchall()}

    # 3. Revlog stats per deck
    rev_sql = """
        SELECT 
            c.did,
            count(r.id) as total_reviews,
            sum(case when r.ease in (2, 3, 4) then 1 else 0 end) as pass_reviews,
            sum(case when r.ease = 1 then 1 else 0 end) as fail_reviews,
            sum(case when r.type in (1, 2) then 1 else 0 end) as rep_reviews,
            sum(case when r.type in (1, 2) and r.ease in (2, 3, 4) then 1 else 0 end) as rep_passes,
            max(r.id) as last_rev_ts,
            sum(r.time) as total_time_ms
        FROM revlog r
        JOIN cards c ON r.cid = c.id
        GROUP BY c.did
    """
    rev_data = {r[0]: r for r in cur.execute(rev_sql).fetchall()}
    conn.close()

    # 4. Build individual deck list
    all_decks = []
    total_reviews_all = 0
    total_passes_all = 0
    total_cards_all = 0
    weak_decks_count = 0
    neglected_decks_count = 0

    for did, dmeta in decks_info.items():
        c_row = card_data.get(did)
        r_row = rev_data.get(did)

        # Ignore empty root container decks that contain 0 cards directly and 0 reviews
        total_cards = c_row[1] if c_row else 0
        total_revs = r_row[1] if r_row else 0

        if total_cards == 0 and total_revs == 0:
            continue

        new_c = c_row[2] if c_row else 0
        learning_c = c_row[3] if c_row else 0
        mature_c = c_row[4] if c_row else 0
        young_c = c_row[5] if c_row else 0
        due_c = c_row[6] if c_row else 0
        raw_factor = c_row[7] if c_row else None
        avg_ease = round(raw_factor / 10.0, 1) if raw_factor else 250.0

        passes = r_row[2] if r_row else 0
        fails = r_row[3] if r_row else 0
        rep_revs = r_row[4] if r_row else 0
        rep_passes = r_row[5] if r_row else 0
        last_rev_ts = r_row[6] if r_row else None
        time_ms = r_row[7] if r_row else 0

        retention_rate = round((passes / total_revs * 100), 1) if total_revs > 0 else None
        rep_retention_rate = round((rep_passes / rep_revs * 100), 1) if rep_revs > 0 else retention_rate

        days_ago = round((now_ms - last_rev_ts) / (86400 * 1000), 1) if last_rev_ts else None
        revs_per_card = round(total_revs / max(1, total_cards), 1) if total_cards > 0 else 0.0
        time_minutes = round(time_ms / 1000 / 60, 1)

        # Classification
        if total_revs == 0:
            status = "unreviewed"
            status_label = "Unberührt"
            badge_color = "#8b949e"
        elif total_revs >= 10 and retention_rate < 70.0:
            status = "weak"
            status_label = "Schwachstelle"
            badge_color = "#f85149"
            weak_decks_count += 1
        elif total_revs >= 10 and retention_rate >= 85.0:
            status = "strong"
            status_label = "Sehr gut"
            badge_color = "#3fb950"
        else:
            status = "medium"
            status_label = "Mittel"
            badge_color = "#d29922"

        is_neglected = (days_ago is not None and days_ago > 7.0 and total_revs > 0)
        if is_neglected:
            neglected_decks_count += 1

        total_reviews_all += total_revs
        total_passes_all += passes
        total_cards_all += total_cards

        # Friendly recency text
        if days_ago is None:
            recency_str = "Noch nie"
        elif days_ago < 1.0:
            recency_str = "Heute"
        elif days_ago < 2.0:
            recency_str = "Gestern"
        elif days_ago < 7.0:
            recency_str = f"vor {int(days_ago)} Tagen"
        else:
            recency_str = f"vor {int(days_ago)} Tagen"

        all_decks.append({
            "deck_id": did,
            "anki_name": dmeta["anki_name"],
            "raw_name": dmeta["raw_name"],
            "parent_topic": dmeta["parent_topic"],
            "card_count": total_cards,
            "new_count": new_c,
            "learning_count": learning_c,
            "mature_count": mature_c,
            "young_count": young_c,
            "due_count": due_c,
            "total_reviews": total_revs,
            "pass_count": passes,
            "fail_count": fails,
            "retention_rate": retention_rate,
            "rep_retention_rate": rep_retention_rate,
            "avg_reviews_per_card": revs_per_card,
            "avg_ease_factor": avg_ease,
            "last_reviewed_days_ago": days_ago,
            "last_reviewed_text": recency_str,
            "time_minutes": time_minutes,
            "status": status,
            "status_label": status_label,
            "badge_color": badge_color,
            "is_neglected": is_neglected,
        })

    # 5. Group by Grosse Überthemen (Themenblöcke)
    topics_dict = {}
    for d in all_decks:
        pt = d["parent_topic"]
        if pt not in topics_dict:
            topics_dict[pt] = {
                "topic_name": pt,
                "total_cards": 0,
                "new_cards": 0,
                "learning_cards": 0,
                "mature_cards": 0,
                "young_cards": 0,
                "due_cards": 0,
                "total_reviews": 0,
                "total_passes": 0,
                "total_fails": 0,
                "total_time_minutes": 0.0,
                "min_days_ago": None,
                "weak_decks_count": 0,
                "neglected_decks_count": 0,
                "subdecks": [],
            }
        t = topics_dict[pt]
        t["total_cards"] += d["card_count"]
        t["new_cards"] += d["new_count"]
        t["learning_cards"] += d["learning_count"]
        t["mature_cards"] += d["mature_count"]
        t["young_cards"] += d["young_count"]
        t["due_cards"] += d["due_count"]
        t["total_reviews"] += d["total_reviews"]
        t["total_passes"] += d["pass_count"]
        t["total_fails"] += d["fail_count"]
        t["total_time_minutes"] += d["time_minutes"]
        if d["status"] == "weak":
            t["weak_decks_count"] += 1
        if d["is_neglected"]:
            t["neglected_decks_count"] += 1
        if d["last_reviewed_days_ago"] is not None:
            if t["min_days_ago"] is None or d["last_reviewed_days_ago"] < t["min_days_ago"]:
                t["min_days_ago"] = d["last_reviewed_days_ago"]
        t["subdecks"].append(d)

    topics_list = []
    for pt, t in topics_dict.items():
        ret_rate = round((t["total_passes"] / t["total_reviews"] * 100), 1) if t["total_reviews"] > 0 else None
        
        if t["min_days_ago"] is None:
            last_text = "Noch nie gelernt"
        elif t["min_days_ago"] < 1.0:
            last_text = "Heute aktiv"
        elif t["min_days_ago"] < 2.0:
            last_text = "Gestern aktiv"
        else:
            last_text = f"vor {int(t['min_days_ago'])} Tagen"

        # Sort subdecks: lowest retention / most reviewed first
        t["subdecks"].sort(key=lambda x: (
            0 if x["status"] == "weak" else 1,
            x["retention_rate"] if x["retention_rate"] is not None else 999,
            -x["total_reviews"]
        ))

        topics_list.append({
            "topic_name": pt,
            "decks_count": len(t["subdecks"]),
            "total_cards": t["total_cards"],
            "new_cards": t["new_cards"],
            "learning_cards": t["learning_cards"],
            "mature_cards": t["mature_cards"],
            "young_cards": t["young_cards"],
            "due_cards": t["due_cards"],
            "total_reviews": t["total_reviews"],
            "retention_rate": ret_rate,
            "total_time_minutes": round(t["total_time_minutes"], 1),
            "last_reviewed_days_ago": t["min_days_ago"],
            "last_reviewed_text": last_text,
            "weak_decks_count": t["weak_decks_count"],
            "neglected_decks_count": t["neglected_decks_count"],
            "subdecks": t["subdecks"],
        })

    # Sort topics: 2. SJ Themenblöcke first, then by total reviews
    def topic_sort_key(t):
        name = t["topic_name"]
        order = ["TB Blut/Immunsystem", "TB Herz-Kreislauf", "TB Atmung", "TB Verdauung", "TB Endokrinologie", "TB Stoffwechsel"]
        for idx, o in enumerate(order):
            if o.lower() in name.lower():
                return (0, idx)
        return (1, -t["total_reviews"])

    topics_list.sort(key=topic_sort_key)

    overall_retention = round((total_passes_all / total_reviews_all * 100), 1) if total_reviews_all > 0 else 0.0

    result = {
        "available": True,
        "collection_path": str(target_path),
        "topics": topics_list,
        "all_decks": sorted(all_decks, key=lambda x: (
            0 if x["status"] == "weak" else 1,
            x["retention_rate"] if x["retention_rate"] is not None else 999,
            -x["total_reviews"]
        )),
        "summary": {
            "total_topics": len(topics_list),
            "total_decks": len(all_decks),
            "total_cards": total_cards_all,
            "total_reviews": total_reviews_all,
            "overall_retention": overall_retention,
            "weak_decks_count": weak_decks_count,
            "neglected_decks_count": neglected_decks_count,
            "updated_at": datetime.now().isoformat(),
        }
    }

    cache_deck_stats(result)
    return result
