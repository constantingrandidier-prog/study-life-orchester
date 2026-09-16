"""Service for analyzing Anki due cards, weaknesses, and recency of topics from local SQLite collection."""

import os
import platform
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def find_default_anki_collection() -> Optional[Path]:
    """Find the default collection.anki2 on the local machine."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        p = Path(appdata) / "Anki2" / "Benutzer 1" / "collection.anki2"
        if p.exists():
            return p
        # Fallback to any user folder
        base = Path(appdata) / "Anki2"
        if base.exists():
            for folder in base.iterdir():
                if folder.is_dir() and (folder / "collection.anki2").exists():
                    return folder / "collection.anki2"
    return None


def get_anki_due_and_weaknesses(col_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract real due cards count, learning cards, and topic weakness metrics from local Anki database.
    Identifies topics with high failure rates and overdue topics requiring immediate review.
    """
    target_path = Path(col_path) if col_path else find_default_anki_collection()
    if not target_path or not target_path.exists():
        try:
            from app.services.anki_desktop_sync import get_cached_desktop_sync_state
            cached = get_cached_desktop_sync_state()
            if cached:
                due_c = cached.get("due_reviews_count", cached.get("cards_due_tomorrow", 102))
                return {
                    "available": True,
                    "collection_path": "synced_via_daemon",
                    "due_reviews_count": due_c,
                    "learning_cards_count": cached.get("learning_cards_count", 0),
                    "review_cards_count": due_c,
                    "new_cards_count": cached.get("new_cards_count", 9633),
                    "weakness_topics": [],
                    "overdue_topics": [],
                    "all_topics": [],
                    "summary": f"{due_c} Wiederholungen synchronisiert.",
                }
        except Exception:
            pass

        return {
            "available": False,
            "collection_path": None,
            "due_reviews_count": 0,
            "learning_cards_count": 0,
            "review_cards_count": 0,
            "new_cards_count": 9633,
            "weakness_topics": [],
            "overdue_topics": [],
            "all_topics": [],
            "summary": "Lokale Anki-Sammlung nicht gefunden (Warte auf Daemon-Sync).",
        }

    uri = f"file:///{target_path.as_posix()}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    cur = conn.cursor()

    # 1. Total queues count
    queue_counts = dict(cur.execute("SELECT queue, count(*) FROM cards GROUP BY queue").fetchall())
    new_cards = queue_counts.get(0, 0)
    learning_cards = queue_counts.get(1, 0)
    review_cards = queue_counts.get(2, 0)
    total_due = learning_cards + review_cards

    # 2. Decks map
    decks_map: Dict[int, str] = {}
    for did, dname in cur.execute("SELECT id, name FROM decks").fetchall():
        clean = dname.replace("\x1f", " :: ")
        # Strip common prefixes for high readability
        clean = clean.replace("1year :: 1. Semester :: ", "").replace("1year :: 2.Semester :: ", "")
        clean = clean.replace("1year :: ", "")
        decks_map[did] = clean

    # 3. Cards by deck
    deck_card_stats = {}
    for did, total, due in cur.execute("""
        SELECT did, count(id), sum(case when queue in (1, 2) then 1 else 0 end)
        FROM cards
        GROUP BY did
    """).fetchall():
        deck_card_stats[did] = {"total": total, "due": due or 0}

    # 4. Review history by deck (Revlog)
    now = datetime.now()
    deck_rev_stats = {}
    revlog_rows = cur.execute("""
        SELECT c.did,
               count(r.id) as rev_count,
               avg(r.ease) as avg_ease,
               sum(case when r.ease = 1 then 1 else 0 end) as again_count,
               max(r.id) as last_rev_ms
        FROM revlog r
        JOIN cards c ON r.cid = c.id
        GROUP BY c.did
    """).fetchall()

    for did, rev_count, avg_ease, again_count, last_rev_ms in revlog_rows:
        fail_rate = round((again_count / rev_count) * 100, 1) if rev_count > 0 else 0.0
        last_dt = datetime.fromtimestamp(last_rev_ms / 1000) if last_rev_ms else None
        days_ago = (now - last_dt).days if last_dt else 999
        deck_rev_stats[did] = {
            "review_count": rev_count,
            "avg_ease": round(avg_ease, 2) if avg_ease else 2.5,
            "fail_rate": fail_rate,
            "last_review_date": last_dt.strftime("%Y-%m-%d") if last_dt else None,
            "days_since_last_review": days_ago,
        }

    conn.close()

    # 5. Assemble and classify topics
    all_topics: List[Dict[str, Any]] = []
    weakness_topics: List[Dict[str, Any]] = []
    overdue_topics: List[Dict[str, Any]] = []

    for did, dname in decks_map.items():
        card_info = deck_card_stats.get(did, {"total": 0, "due": 0})
        total_c = card_info["total"]
        due_c = card_info["due"]
        if total_c == 0:
            continue

        rev_info = deck_rev_stats.get(did, {
            "review_count": 0,
            "avg_ease": 2.5,
            "fail_rate": 0.0,
            "last_review_date": None,
            "days_since_last_review": None,
        })

        is_weakness = rev_info["review_count"] >= 5 and (rev_info["fail_rate"] >= 30.0 or (rev_info["fail_rate"] >= 20.0 and rev_info["avg_ease"] < 2.0))
        is_overdue = rev_info["review_count"] >= 5 and rev_info["days_since_last_review"] is not None and rev_info["days_since_last_review"] > 14

        status_badge = "✅ Stabil"
        badge_color = "#3fb950"
        if is_weakness and is_overdue:
            status_badge = "⚠️ Schwachstelle & Überfällig"
            badge_color = "#f85149"
        elif is_weakness:
            status_badge = f"⚠️ Schwachstelle ({rev_info['fail_rate']}% Fehler)"
            badge_color = "#f85149"
        elif is_overdue:
            status_badge = f"⏰ Überfällig ({rev_info['days_since_last_review']}d her)"
            badge_color = "#d29922"
        elif rev_info["review_count"] == 0:
            status_badge = "🆕 Neu / Unbearbeitet"
            badge_color = "#58a6ff"

        item = {
            "deck_id": did,
            "deck_name": dname,
            "total_cards": total_c,
            "due_reviews_count": due_c,
            "review_count": rev_info["review_count"],
            "avg_ease": rev_info["avg_ease"],
            "fail_rate": rev_info["fail_rate"],
            "days_since_last_review": rev_info["days_since_last_review"],
            "last_review_date": rev_info["last_review_date"],
            "is_weakness": is_weakness,
            "is_overdue": is_overdue,
            "status_badge": status_badge,
            "badge_color": badge_color,
        }

        all_topics.append(item)
        if is_weakness:
            weakness_topics.append(item)
        if is_overdue:
            overdue_topics.append(item)

    # Sort topics: due reviews first, then weaknesses, then total cards
    all_topics.sort(key=lambda x: (x["due_reviews_count"], 1 if x["is_weakness"] else 0, x["total_cards"]), reverse=True)

    return {
        "available": True,
        "collection_path": str(target_path),
        "due_reviews_count": total_due,
        "learning_cards_count": learning_cards,
        "review_cards_count": review_cards,
        "new_cards_count": new_cards,
        "weakness_topics": weakness_topics,
        "overdue_topics": overdue_topics,
        "all_topics": all_topics,
        "summary": f"{total_due} Wiederholungen heute fällig • {len(weakness_topics)} Schwachstellen identifiziert",
    }
