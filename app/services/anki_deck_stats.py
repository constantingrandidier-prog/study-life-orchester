"""
Service for comprehensive Anki Deck & Retention Statistics.
Computes retention rates, review counts, recency, and card breakdown
for both major topics (Überthemen) and individual small decks with exact Anki names.
"""

import json
import os
import sqlite3
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.db.repository import get_db_connection
from app.services.anki_desktop_sync import find_local_anki_collection

# Current semester start: 2026-09-14 00:00:00 (ignore previous semester logs and card resets)
SEMESTER_START_TS = int(datetime(2026, 9, 14, 0, 0, 0).timestamp() * 1000)


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


def _normalize_deck_stats_payload(data: Any) -> Any:
    if not isinstance(data, dict):
        return data
    sm = data.get("summary")
    if isinstance(sm, dict):
        sem_ret = sm.get("semester_retention", sm.get("overall_retention", 0.0))
        sm.setdefault("semester_retention", sem_ret)
        sm.setdefault("today_reviews", 0)
        sm.setdefault("today_passes", 0)
        sm.setdefault("today_retention", None)
        sm.setdefault("week_reviews", 0)
        sm.setdefault("week_passes", 0)
        sm.setdefault("week_retention", None)
        sm.setdefault("two_weeks_reviews", 0)
        sm.setdefault("two_weeks_passes", 0)
        sm.setdefault("two_weeks_retention", None)
        sm.setdefault("trend_week_vs_semester", None)
        sm.setdefault("trend_today_vs_semester", None)
    return data


def cache_deck_stats(stats: Dict[str, Any]):
    try:
        norm = _normalize_deck_stats_payload(stats)
        with get_db_connection() as conn:
            _ensure_cache_table(conn)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO anki_deck_stats_cache (id, payload_json, updated_at)
                VALUES (1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP;
            """, (json.dumps(norm),))
    except Exception:
        pass


def get_cached_deck_stats() -> Optional[Dict[str, Any]]:
    try:
        with get_db_connection() as conn:
            _ensure_cache_table(conn)
            cur = conn.cursor()
            row = cur.execute("SELECT payload_json FROM anki_deck_stats_cache WHERE id = 1").fetchone()
            if row:
                return _normalize_deck_stats_payload(json.loads(row[0]))
    except Exception:
        pass
    return None


def get_detailed_deck_stats(col_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes comprehensive retention and recency statistics for all decks.
    Works directly with local collection.anki2 or falls back to cached daemon state.
    """
    is_cloud = (os.environ.get("RENDER") is not None or os.environ.get("APPDATA") is None)
    if is_cloud:
        cached = get_cached_deck_stats()
        if cached:
            return cached

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
            avg(case when c.factor > 0 then c.factor else null end) as avg_factor,
            sum(case when c.queue in (1, 2, 3) or c.reps > 0 then 1 else 0 end) as cards_studied
        FROM cards c
        GROUP BY c.did
    """
    card_data = {r[0]: r for r in cur.execute(card_sql, (today_anki_day,)).fetchall()}

    # 3. Revlog stats per deck (scoped strictly to active semester, excluding card resets type=4)
    now_dt = datetime.now()
    today_midnight = datetime(now_dt.year, now_dt.month, now_dt.day)
    today_start_ts = int(today_midnight.timestamp() * 1000)
    seven_days_ts = int((today_midnight - timedelta(days=7)).timestamp() * 1000)
    fourteen_days_ts = int((today_midnight - timedelta(days=14)).timestamp() * 1000)

    rev_sql = """
        SELECT 
            c.did,
            count(r.id) as total_reviews,
            sum(case when r.ease in (2, 3, 4) then 1 else 0 end) as pass_reviews,
            sum(case when r.ease = 1 then 1 else 0 end) as fail_reviews,
            -- Semester true reviews (type 1=Review, 2=Relearn, 3=Cram)
            sum(case when r.type in (1, 2, 3) then 1 else 0 end) as rep_reviews,
            sum(case when r.type in (1, 2, 3) and r.ease in (2, 3, 4) then 1 else 0 end) as rep_passes,
            -- Learn steps (type 0)
            sum(case when r.type = 0 then 1 else 0 end) as learn_reviews,
            sum(case when r.type = 0 and r.ease in (2, 3, 4) then 1 else 0 end) as learn_passes,
            max(r.id) as last_rev_ts,
            sum(r.time) as total_time_ms,
            -- Today (since 00:00)
            sum(case when r.id >= ? then 1 else 0 end) as today_reviews,
            sum(case when r.id >= ? and r.ease in (2, 3, 4) then 1 else 0 end) as today_passes,
            sum(case when r.id >= ? and r.type in (1, 2, 3) then 1 else 0 end) as today_rep_reviews,
            sum(case when r.id >= ? and r.type in (1, 2, 3) and r.ease in (2, 3, 4) then 1 else 0 end) as today_rep_passes,
            -- Last 7 days
            sum(case when r.id >= ? then 1 else 0 end) as week_reviews,
            sum(case when r.id >= ? and r.ease in (2, 3, 4) then 1 else 0 end) as week_passes,
            sum(case when r.id >= ? and r.type in (1, 2, 3) then 1 else 0 end) as week_rep_reviews,
            sum(case when r.id >= ? and r.type in (1, 2, 3) and r.ease in (2, 3, 4) then 1 else 0 end) as week_rep_passes,
            -- Last 14 days (2 weeks)
            sum(case when r.id >= ? then 1 else 0 end) as two_weeks_reviews,
            sum(case when r.id >= ? and r.ease in (2, 3, 4) then 1 else 0 end) as two_weeks_passes,
            sum(case when r.id >= ? and r.type in (1, 2, 3) then 1 else 0 end) as two_weeks_rep_reviews,
            sum(case when r.id >= ? and r.type in (1, 2, 3) and r.ease in (2, 3, 4) then 1 else 0 end) as two_weeks_rep_passes
        FROM revlog r
        JOIN cards c ON r.cid = c.id
        WHERE r.id >= ? AND r.type != 4 AND r.ease in (1, 2, 3, 4)
        GROUP BY c.did
    """
    rev_params = (
        today_start_ts, today_start_ts, today_start_ts, today_start_ts,
        seven_days_ts, seven_days_ts, seven_days_ts, seven_days_ts,
        fourteen_days_ts, fourteen_days_ts, fourteen_days_ts, fourteen_days_ts,
        SEMESTER_START_TS,
    )
    rev_data = {r[0]: r for r in cur.execute(rev_sql, rev_params).fetchall()}
    conn.close()

    all_decks = []
    total_reviews_all = 0
    total_passes_all = 0
    total_rep_reviews_all = 0
    total_rep_passes_all = 0
    total_cards_all = 0
    total_today_reviews_all = 0
    total_today_passes_all = 0
    total_today_rep_reviews_all = 0
    total_today_rep_passes_all = 0
    total_week_reviews_all = 0
    total_week_passes_all = 0
    total_week_rep_reviews_all = 0
    total_week_rep_passes_all = 0
    total_two_weeks_reviews_all = 0
    total_two_weeks_passes_all = 0
    total_two_weeks_rep_reviews_all = 0
    total_two_weeks_rep_passes_all = 0
    weak_decks_count = 0
    neglected_decks_count = 0

    for did, dmeta in decks_info.items():
        c_row = card_data.get(did)
        r_row = rev_data.get(did)

        # Ignore empty root container decks that contain 0 cards directly and 0 reviews
        total_cards = c_row[1] if c_row else 0
        cards_studied = c_row[8] if c_row else 0

        if total_cards == 0 and cards_studied == 0:
            continue

        new_c = c_row[2] if c_row else 0
        learning_c = c_row[3] if c_row else 0
        mature_c = c_row[4] if c_row else 0
        young_c = c_row[5] if c_row else 0
        due_c = c_row[6] if c_row else 0
        raw_factor = c_row[7] if c_row else None
        avg_ease = round(raw_factor / 10.0, 1) if raw_factor else 250.0

        # Strictly check if this deck has been studied by the student this semester:
        if cards_studied == 0 or not r_row or r_row[1] == 0:
            total_revs = 0
            passes = 0
            fails = 0
            rep_revs = 0
            rep_passes = 0
            learn_revs = 0
            learn_passes = 0
            last_rev_ts = None
            time_ms = 0
            retention_rate = None
            rep_retention_rate = None
            days_ago = None
            recency_str = "Noch nicht gestartet"
            status = "unreviewed"
            status_label = "Noch nicht gelernt"
            badge_color = "#8b949e"
            is_neglected = False
            revs_per_card = 0.0
            time_minutes = 0.0
            today_revs = 0
            today_passes = 0
            today_rep_revs = 0
            today_rep_passes = 0
            today_retention = None
            week_revs = 0
            week_passes = 0
            week_rep_revs = 0
            week_rep_passes = 0
            week_retention = None
            two_weeks_revs = 0
            two_weeks_passes = 0
            two_weeks_rep_revs = 0
            two_weeks_rep_passes = 0
            two_weeks_retention = None
            retention_basis = "Noch nicht gelernt"
            is_learning_phase = False
        else:
            total_revs = r_row[1]
            passes = r_row[2]
            fails = r_row[3]
            rep_revs = r_row[4]
            rep_passes = r_row[5]
            learn_revs = r_row[6]
            learn_passes = r_row[7]
            last_rev_ts = r_row[8]
            time_ms = r_row[9]

            today_revs = r_row[10] or 0
            today_passes = r_row[11] or 0
            today_rep_revs = r_row[12] or 0
            today_rep_passes = r_row[13] or 0
            today_retention = round((today_rep_passes / today_rep_revs * 100), 1) if today_rep_revs > 0 else (
                round((today_passes / today_revs * 100), 1) if today_revs > 0 else None
            )

            week_revs = r_row[14] or 0
            week_passes = r_row[15] or 0
            week_rep_revs = r_row[16] or 0
            week_rep_passes = r_row[17] or 0
            week_retention = round((week_rep_passes / week_rep_revs * 100), 1) if week_rep_revs > 0 else (
                round((week_passes / week_revs * 100), 1) if week_revs > 0 else None
            )

            two_weeks_revs = r_row[18] or 0
            two_weeks_passes = r_row[19] or 0
            two_weeks_rep_revs = r_row[20] or 0
            two_weeks_rep_passes = r_row[21] or 0
            two_weeks_retention = round((two_weeks_rep_passes / two_weeks_rep_revs * 100), 1) if two_weeks_rep_revs > 0 else (
                round((two_weeks_passes / two_weeks_revs * 100), 1) if two_weeks_reviews > 0 else None
            )

            # 1. True Scientific Review Retention Rate (excludes initial memorization / learning steps type 0)
            rep_retention_rate = round((rep_passes / rep_revs * 100), 1) if rep_revs > 0 else None

            # 2. Dynamic Effective Retention (Prioritizing recent retention when practicing a deck):
            # As the student reviews the deck over time, recent reviews (last 7-14 days) reflect current knowledge!
            if week_retention is not None and week_rep_revs >= 10:
                effective_retention = round(0.75 * week_retention + 0.25 * (rep_retention_rate or week_retention), 1)
                retention_basis = "7 Tage (Aktuell)"
            elif two_weeks_retention is not None and two_weeks_rep_revs >= 10:
                effective_retention = round(0.70 * two_weeks_retention + 0.30 * (rep_retention_rate or two_weeks_retention), 1)
                retention_basis = "14 Tage (Aktuell)"
            elif rep_retention_rate is not None:
                effective_retention = rep_retention_rate
                retention_basis = "Wiederholungen (Semester)"
            elif total_revs > 0:
                effective_retention = round((passes / total_revs * 100), 1)
                retention_basis = "In Erarbeitung (Lernphase)"
            else:
                effective_retention = None
                retention_basis = "Noch nicht gelernt"

            retention_rate = effective_retention

            days_ago = round((now_ms - last_rev_ts) / (86400 * 1000), 1) if last_rev_ts else None
            revs_per_card = round(total_revs / max(1, total_cards), 1) if total_cards > 0 else 0.0
            time_minutes = round(time_ms / 1000 / 60, 1)

            # Friendly recency text
            if days_ago is None:
                recency_str = "Noch nicht gestartet"
            elif days_ago < 0.05:
                recency_str = "Gerade eben"
            elif days_ago < 1.0:
                recency_str = "Heute"
            elif days_ago < 2.0:
                recency_str = "Gestern"
            elif days_ago < 7.0:
                recency_str = f"vor {int(days_ago)} Tagen"
            else:
                recency_str = f"vor {int(days_ago)} Tagen"

            is_learning_phase = (rep_revs < 10 and total_cards > 0 and (total_revs > 0 or learning_c > 0))

            # Classification: Decks in learning phase vs actual performance
            if is_learning_phase and rep_revs == 0:
                status = "learning"
                status_label = "In Erarbeitung"
                badge_color = "#388bfd"
            elif rep_revs >= 15 and retention_rate is not None and retention_rate < 70.0:
                status = "weak"
                status_label = "Schwachstelle"
                badge_color = "#f85149"
                weak_decks_count += 1
            elif (rep_revs >= 15 or week_rep_revs >= 10) and retention_rate is not None and retention_rate >= 80.0:
                status = "strong"
                status_label = "Sehr gut"
                badge_color = "#3fb950"
            else:
                status = "medium"
                status_label = "Solide"
                badge_color = "#d29922"

            is_neglected = (days_ago is not None and days_ago > 7.0 and total_revs > 0)
            if is_neglected:
                neglected_decks_count += 1

        total_reviews_all += total_revs
        total_passes_all += passes
        total_rep_reviews_all += rep_revs
        total_rep_passes_all += rep_passes
        total_cards_all += total_cards
        total_today_reviews_all += today_revs
        total_today_passes_all += today_passes
        total_today_rep_reviews_all += today_rep_revs
        total_today_rep_passes_all += today_rep_passes
        total_week_reviews_all += week_revs
        total_week_passes_all += week_passes
        total_week_rep_reviews_all += week_rep_revs
        total_week_rep_passes_all += week_rep_passes
        total_two_weeks_reviews_all += two_weeks_revs
        total_two_weeks_passes_all += two_weeks_passes
        total_two_weeks_rep_reviews_all += two_weeks_rep_revs
        total_two_weeks_rep_passes_all += two_weeks_rep_passes

        primary_ret = today_retention if today_retention is not None else retention_rate
        primary_ret_lbl = "Heute" if today_retention is not None else retention_basis

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
            "semester_retention": retention_rate,
            "rep_retention_rate": rep_retention_rate,
            "today_reviews": today_revs,
            "today_passes": today_passes,
            "today_retention": today_retention,
            "week_reviews": week_revs,
            "week_passes": week_passes,
            "week_retention": week_retention,
            "two_weeks_reviews": two_weeks_revs,
            "two_weeks_passes": two_weeks_passes,
            "two_weeks_retention": two_weeks_retention,
            "primary_retention": primary_ret,
            "primary_retention_label": primary_ret_lbl,
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
                "total_rep_reviews": 0,
                "total_rep_passes": 0,
                "today_reviews": 0,
                "today_passes": 0,
                "today_rep_reviews": 0,
                "today_rep_passes": 0,
                "week_reviews": 0,
                "week_passes": 0,
                "week_rep_reviews": 0,
                "week_rep_passes": 0,
                "two_weeks_reviews": 0,
                "two_weeks_passes": 0,
                "two_weeks_rep_reviews": 0,
                "two_weeks_rep_passes": 0,
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
        t["total_rep_reviews"] += d.get("rep_reviews", 0)
        t["total_rep_passes"] += d.get("rep_passes", 0)
        t["today_reviews"] += d["today_reviews"]
        t["today_passes"] += d["today_passes"]
        t["today_rep_reviews"] += d.get("today_rep_reviews", 0)
        t["today_rep_passes"] += d.get("today_rep_passes", 0)
        t["week_reviews"] += d["week_reviews"]
        t["week_passes"] += d["week_passes"]
        t["week_rep_reviews"] += d.get("week_rep_reviews", 0)
        t["week_rep_passes"] += d.get("week_rep_passes", 0)
        t["two_weeks_reviews"] += d["two_weeks_reviews"]
        t["two_weeks_passes"] += d["two_weeks_passes"]
        t["two_weeks_rep_reviews"] += d.get("two_weeks_rep_reviews", 0)
        t["two_weeks_rep_passes"] += d.get("two_weeks_rep_passes", 0)
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
        total_revs_topic = t["total_reviews"]
        rep_revs_topic = t["total_rep_reviews"]
        rep_passes_topic = t["total_rep_passes"]
        rep_ret_topic = round((rep_passes_topic / rep_revs_topic * 100), 1) if rep_revs_topic > 0 else None

        today_rep_revs_top = t["today_rep_reviews"]
        today_rep_passes_top = t["today_rep_passes"]
        today_ret_topic = round((today_rep_passes_top / today_rep_revs_top * 100), 1) if today_rep_revs_top > 0 else (
            round((t["today_passes"] / t["today_reviews"] * 100), 1) if t["today_reviews"] > 0 else None
        )

        week_rep_revs_top = t["week_rep_reviews"]
        week_rep_passes_top = t["week_rep_passes"]
        week_ret_topic = round((week_rep_passes_top / week_rep_revs_top * 100), 1) if week_rep_revs_top > 0 else (
            round((t["week_passes"] / t["week_reviews"] * 100), 1) if t["week_reviews"] > 0 else None
        )

        two_weeks_rep_revs_top = t["two_weeks_rep_reviews"]
        two_weeks_rep_passes_top = t["two_weeks_rep_passes"]
        two_weeks_ret_topic = round((two_weeks_rep_passes_top / two_weeks_rep_revs_top * 100), 1) if two_weeks_rep_revs_top > 0 else (
            round((t["two_weeks_passes"] / t["two_weeks_reviews"] * 100), 1) if t["two_weeks_reviews"] > 0 else None
        )

        # Topic-level effective retention: prioritize recent review retention
        if week_ret_topic is not None and week_rep_revs_top >= 20:
            effective_topic_ret = round(0.75 * week_ret_topic + 0.25 * (rep_ret_topic or week_ret_topic), 1)
        elif two_weeks_ret_topic is not None and two_weeks_rep_revs_top >= 20:
            effective_topic_ret = round(0.70 * two_weeks_ret_topic + 0.30 * (rep_ret_topic or two_weeks_ret_topic), 1)
        elif rep_ret_topic is not None:
            effective_topic_ret = rep_ret_topic
        elif total_revs_topic > 0:
            effective_topic_ret = round((t["total_passes"] / total_revs_topic * 100), 1)
        else:
            effective_topic_ret = None

        ret_rate = effective_topic_ret

        if t["min_days_ago"] is None or total_revs_topic == 0:
            last_text = "Noch nicht gestartet"
        elif t["min_days_ago"] < 0.05:
            last_text = "Gerade eben"
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
            "rep_reviews": rep_revs_topic,
            "retention_rate": ret_rate,
            "semester_retention": ret_rate,
            "rep_retention_rate": rep_ret_topic,
            "today_reviews": t["today_reviews"],
            "today_retention": today_ret_topic,
            "week_reviews": t["week_reviews"],
            "week_retention": week_ret_topic,
            "two_weeks_reviews": t["two_weeks_reviews"],
            "two_weeks_retention": two_weeks_ret_topic,
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

    # Global true review metrics (scientific retention excluding initial learning steps)
    overall_retention = round((total_rep_passes_all / total_rep_reviews_all * 100), 1) if total_rep_reviews_all > 0 else (
        round((total_passes_all / total_reviews_all * 100), 1) if total_reviews_all > 0 else 0.0
    )
    today_overall = round((total_today_rep_passes_all / total_today_rep_reviews_all * 100), 1) if total_today_rep_reviews_all > 0 else (
        round((total_today_passes_all / total_today_reviews_all * 100), 1) if total_today_reviews_all > 0 else None
    )
    week_overall = round((total_week_rep_passes_all / total_week_rep_reviews_all * 100), 1) if total_week_rep_reviews_all > 0 else (
        round((total_week_passes_all / total_week_reviews_all * 100), 1) if total_week_reviews_all > 0 else None
    )
    two_weeks_overall = round((total_two_weeks_rep_passes_all / total_two_weeks_rep_reviews_all * 100), 1) if total_two_weeks_rep_reviews_all > 0 else (
        round((total_two_weeks_passes_all / total_two_weeks_reviews_all * 100), 1) if total_two_weeks_reviews_all > 0 else None
    )
    all_reviews_mixed_ret = round((total_passes_all / total_reviews_all * 100), 1) if total_reviews_all > 0 else 0.0

    trend_vs_semester = round(week_overall - overall_retention, 1) if (week_overall is not None and overall_retention > 0) else 0.0
    trend_today_vs_semester = round(today_overall - overall_retention, 1) if (today_overall is not None and overall_retention > 0) else None

    result = {
        "available": True,
        "collection_path": str(target_path),
        "topics": topics_list,
        "all_decks": sorted(all_decks, key=lambda x: (
            0 if x["status"] == "weak" else (1 if x["status"] == "learning" else 2),
            x["retention_rate"] if x["retention_rate"] is not None else 999,
            -x["total_reviews"]
        )),
        "summary": {
            "total_topics": len(topics_list),
            "total_decks": len(all_decks),
            "total_cards": total_cards_all,
            "total_reviews": total_reviews_all,
            "total_rep_reviews": total_rep_reviews_all,
            "overall_retention": overall_retention,
            "semester_retention": overall_retention,
            "all_reviews_retention": all_reviews_mixed_ret,
            "today_reviews": total_today_reviews_all,
            "today_rep_reviews": total_today_rep_reviews_all,
            "today_retention": today_overall,
            "week_reviews": total_week_reviews_all,
            "week_rep_reviews": total_week_rep_reviews_all,
            "week_retention": week_overall,
            "two_weeks_reviews": total_two_weeks_reviews_all,
            "two_weeks_rep_reviews": total_two_weeks_rep_reviews_all,
            "two_weeks_retention": two_weeks_overall,
            "trend_week_vs_semester": trend_vs_semester,
            "trend_today_vs_semester": trend_today_vs_semester,
            "weak_decks_count": weak_decks_count,
            "neglected_decks_count": neglected_decks_count,
            "updated_at": datetime.now().isoformat(),
        }
    }

    cache_deck_stats(result)
    return result
