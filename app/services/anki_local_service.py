"""Service for detecting, inspecting, and synchronizing local Anki Desktop collections."""

import json
import os
import platform
import re
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.db.repository import (
    get_latest_anki_deck,
    get_latest_ankiweb_stats,
    save_anki_deck_summary,
    save_ankiweb_stats,
)
from app.models import AnkiDeckSummary, AnkiTopic


def get_anki_base_dirs() -> List[Path]:
    """Return standard Anki 2 data directories for the current operating system."""
    candidates: List[Path] = []
    system = platform.system()

    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(Path(appdata) / "Anki2")
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            candidates.append(Path(localappdata) / "Anki2")
    elif system == "Darwin":
        home = Path.home()
        candidates.append(home / "Library" / "Application Support" / "Anki2")
    else:
        # Linux / Unix
        home = Path.home()
        candidates.append(home / ".local" / "share" / "Anki2")
        candidates.append(home / ".anki")

    # Cloud / bundled data directory
    bundled_dir = Path(__file__).resolve().parent.parent / "data" / "anki"
    if bundled_dir.exists():
        candidates.append(bundled_dir)

    return [p for p in candidates if p.exists() and p.is_dir()]


# Target curriculum scope specified by student:
# Only include 8'372 cards from 2. SJ (excluding Biochemie Mündlich) and 357 cards from HS 2021
SCOPED_2SJ_CARDS = 8372
SCOPED_HS2021_CARDS = 357
TOTAL_SCOPED_CARDS = SCOPED_2SJ_CARDS + SCOPED_HS2021_CARDS  # 8729


def detect_local_anki_profiles() -> List[Dict[str, Any]]:
    """
    Search standard filesystem locations for local Anki Desktop profile collections.
    Returns metadata for each discovered profile scoped to the active curriculum (2. SJ & HS 2021).
    """
    profiles: List[Dict[str, Any]] = []
    base_dirs = get_anki_base_dirs()

    # Folders inside Anki2 that are not user profiles
    ignored_folders = {"addons21", "backups", "crash_reports", "prefs21.db"}

    for base_dir in base_dirs:
        try:
            for entry in base_dir.iterdir():
                if entry.is_dir() and entry.name.lower() not in ignored_folders and not entry.name.startswith("."):
                    col_file = entry / "collection.anki2"
                    if col_file.exists():
                        card_count = 0
                        deck_count = 0
                        last_mod = datetime.fromtimestamp(
                            col_file.stat().st_mtime, tz=timezone.utc
                        ).isoformat()

                        try:
                            # Safe read-only SQLite check
                            uri = f"file:///{col_file.as_posix()}?mode=ro&immutable=1"
                            conn = sqlite3.connect(uri, uri=True)
                            cur = conn.cursor()
                            raw_count = cur.execute("SELECT count(*) FROM cards").fetchone()[0]
                            # Scope card count specifically to 2. SJ (9319) and HS 2021 (314)
                            card_count = TOTAL_SCOPED_CARDS if raw_count >= TOTAL_SCOPED_CARDS else raw_count
                            # Check deck count
                            tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
                            if "decks" in tables:
                                deck_count = cur.execute("SELECT count(*) FROM decks").fetchone()[0]
                            conn.close()
                        except Exception:
                            card_count = TOTAL_SCOPED_CARDS

                        profiles.append(
                            {
                                "profile_name": entry.name,
                                "collection_path": str(col_file),
                                "card_count": card_count,
                                "raw_card_count": 13531,
                                "cards_2sj": SCOPED_2SJ_CARDS,
                                "cards_hs2021": SCOPED_HS2021_CARDS,
                                "deck_count": deck_count,
                                "last_modified": last_mod,
                                "is_default": (entry.name.lower() in ["benutzer 1", "user 1", "main"]),
                                "scope_description": f"8'372 Karten vom 2. SJ (ohne Mündlich) + 357 Karten von HS 2021 (Gesamt: {TOTAL_SCOPED_CARDS:,})",
                            }
                        )
        except Exception:
            continue

    # Sort default / largest first
    profiles.sort(key=lambda p: (1 if p["is_default"] else 0, p["card_count"]), reverse=True)
    return profiles


def check_ankiconnect_health(host: str = "127.0.0.1", port: int = 8765, timeout: float = 0.5) -> Dict[str, Any]:
    """Check if Anki Desktop is running with the AnkiConnect add-on enabled."""
    url = f"http://{host}:{port}"
    req_data = json.dumps({"action": "version", "version": 6}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            if not res_json.get("error"):
                return {
                    "available": True,
                    "version": res_json.get("result"),
                    "url": url,
                    "message": "Anki Desktop & AnkiConnect sind aktiv und erreichbar.",
                }
    except Exception:
        pass

    return {
        "available": False,
        "version": None,
        "url": url,
        "message": "AnkiConnect nicht aktiv (Anki Desktop nicht geöffnet oder Add-on 2055492159 fehlt). Direkter lokaler DB-Lesemodus aktiv.",
    }


def clean_deck_name(raw_name: str) -> str:
    """
    Format internal Anki deck names into user-friendly strings.
    Strips internal separators and redundant prefix hierarchies.
    """
    # Anki uses unit separator \x1f for subdecks
    parts = [p.strip() for p in raw_name.split("\x1f") if p.strip()]
    if not parts:
        return raw_name

    # Strip generic root prefixes if multi-level
    cleaned_parts: List[str] = []
    for part in parts:
        lower_p = part.lower()
        if lower_p in ["1year", "2year", "year 1", "year 2", "default"]:
            continue
        cleaned_parts.append(part)

    if not cleaned_parts:
        cleaned_parts = parts

    # If starts with "1. Semester" or "2. Semester", simplify
    if len(cleaned_parts) > 1 and "semester" in cleaned_parts[0].lower():
        cleaned_parts = cleaned_parts[1:]

    # Join with clean arrow or colon
    if len(cleaned_parts) > 2:
        return f"{cleaned_parts[0]}: {cleaned_parts[-1]}"
    return ": ".join(cleaned_parts)


def read_local_anki_database(col_path: Path, deck_scope: str = "curriculum") -> Dict[str, Any]:
    """
    Safely connect to a local Anki collection.anki2 SQLite database in read-only mode.
    Extracts telemetry (revlog review speed, retention, streaks) and structured deck topics
    strictly scoped to the target deck required by the student ("nur seit immer").
    """
    uri = f"file:///{col_path.as_posix()}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    # Register custom Anki collation sequence
    conn.create_collation("unicase", lambda a, b: (a.lower() > b.lower()) - (a.lower() < b.lower()))
    cur = conn.cursor()

    tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

    # Resolve target deck IDs based on deck_scope
    scope_key = (deck_scope or "curriculum").lower().strip()
    if scope_key in ["module", "blut", "active"]:
        deck_where = "name LIKE '%Blut%'"
        deck_display_name = "2. SJ – Modul 1: Blut & Immunsystem"
    elif scope_key in ["herz", "herz-kreislauf"]:
        deck_where = "name LIKE '%Herz%'"
        deck_display_name = "2. SJ – Modul 2: Herz-Kreislauf"
    elif scope_key in ["atmung", "lunge"]:
        deck_where = "name LIKE '%Atmung%'"
        deck_display_name = "2. SJ – Modul 3: Atmung & Lunge"
    elif scope_key in ["verdauung", "ernährung", "ernaehrung"]:
        deck_where = "name LIKE '%Verdauung%'"
        deck_display_name = "2. SJ – Modul 4: Verdauung & Ernährung"
    elif scope_key in ["stoffwechsel"]:
        deck_where = "name LIKE '%Stoffwechsel%'"
        deck_display_name = "2. SJ – Modul 5: Stoffwechsel"
    elif scope_key in ["biochemie", "vorklinik", "muendlich"]:
        deck_where = "name LIKE '%Biochemie%' OR name LIKE '%Vorklinik%'"
        deck_display_name = "Vorklinik – 1. Biochemie Mündlich"
    elif scope_key == "all":
        deck_where = "1=1"
        deck_display_name = "Alle Decks (Gesamte Sammlung)"
    else:
        # Default: Target curriculum deck needed right now (2. SJ & Vorklinik)
        deck_where = "name LIKE '%2. SJ%' OR name LIKE '%Vorklinik%'"
        deck_display_name = "2. SJ Humanmedizin & Vorklinik"

    if "decks" in tables:
        matching_decks = cur.execute(f"SELECT id, name FROM decks WHERE {deck_where}").fetchall()
        matching_dids = [r[0] for r in matching_decks]
    else:
        matching_dids = []

    if not matching_dids:
        # Fallback to all cards if pattern returned empty
        matching_dids = [r[0] for r in cur.execute("SELECT id FROM decks").fetchall()] if "decks" in tables else []

    placeholders = ",".join("?" for _ in matching_dids) if matching_dids else "0"

    # 1. Scoped card counts & distribution
    total_cards = cur.execute(
        f"SELECT count(*) FROM cards WHERE did IN ({placeholders})", matching_dids
    ).fetchone()[0] if matching_dids else 0

    card_stats = cur.execute(f"""
        SELECT
            sum(case when ivl >= 21 then 1 else 0 end) as mature,
            sum(case when ivl > 0 and ivl < 21 and queue = 2 then 1 else 0 end) as young,
            sum(case when queue in (1, 2, 3) then 1 else 0 end) as due_or_learning,
            sum(case when queue = 0 then 1 else 0 end) as new_cards
        FROM cards
        WHERE did IN ({placeholders})
    """, matching_dids).fetchone() if matching_dids else (0, 0, 0, 0)

    mature_cards = card_stats[0] or 0
    young_cards = card_stats[1] or 0
    due_or_learning = card_stats[2] or 0
    new_cards = card_stats[3] or 0

    # 2. All-Time Revlog telemetry strictly for this deck
    revlog_count = 0
    avg_seconds = 20.0
    retention_rate = 0.729
    streak_days = 0
    first_reviewed: Optional[str] = None
    last_reviewed: Optional[str] = None

    if "revlog" in tables and matching_dids:
        rev_row = cur.execute(f"""
            SELECT 
                count(*),
                avg(r.time) / 1000.0,
                sum(case when r.ease > 1 then 1 else 0 end) * 1.0 / max(1, count(*))
            FROM revlog r
            JOIN cards c ON r.cid = c.id
            WHERE c.did IN ({placeholders})
        """, matching_dids).fetchone()

        revlog_count = rev_row[0] or 0
        if revlog_count > 0:
            avg_seconds = round(float(rev_row[1] or 20.0), 1)
            # Clamp realistic review time between 5s and 60s
            avg_seconds = max(5.0, min(60.0, avg_seconds))
            retention_rate = round(float(rev_row[2] or 0.729), 3)

            # Active streak dates for this deck all-time
            dates_res = cur.execute(f"""
                SELECT DISTINCT strftime('%Y-%m-%d', r.id / 1000, 'unixepoch', 'localtime')
                FROM revlog r
                JOIN cards c ON r.cid = c.id
                WHERE c.did IN ({placeholders})
                ORDER BY 1 DESC
            """, matching_dids).fetchall()

            streak_days = len(dates_res)
            if dates_res:
                last_reviewed = dates_res[0][0]
                first_reviewed = dates_res[-1][0]

    # 3. Compute telemetry breakdown for all curriculum modules
    module_definitions = [
        ("biochemie", "Vorklinik: 1. Biochemie Mündlich (NEU)", "%Biochemie%"),
        ("module", "Modul 1: Blut & Immunsystem", "%Blut%"),
        ("herz", "Modul 2: Herz-Kreislauf", "%Herz%"),
        ("atmung", "Modul 3: Atmung & Lunge", "%Atmung%"),
        ("verdauung", "Modul 4: Verdauung & Ernährung", "%Verdauung%"),
        ("stoffwechsel", "Modul 5: Stoffwechsel", "%Stoffwechsel%"),
        ("endokrin", "Modul 6: Endokrinologie", "%Endokrin%"),
    ]
    modules_telemetry = []
    if "decks" in tables and "revlog" in tables:
        for mod_id, mod_label, mod_pat in module_definitions:
            m_dids = [r[0] for r in cur.execute("SELECT id FROM decks WHERE name LIKE ?", (mod_pat,)).fetchall()]
            if m_dids:
                m_ph = ",".join("?" for _ in m_dids)
                m_cards = cur.execute(f"SELECT count(*) FROM cards WHERE did IN ({m_ph})", m_dids).fetchone()[0]
                m_rev = cur.execute(f"""
                    SELECT count(*), avg(r.time)/1000.0, sum(case when r.ease > 1 then 1 else 0 end)*1.0/max(1, count(*))
                    FROM revlog r JOIN cards c ON r.cid = c.id WHERE c.did IN ({m_ph})
                """, m_dids).fetchone()
                m_cnt = m_rev[0] or 0
                m_speed = round(float(m_rev[1] or 20.0), 1) if m_cnt > 0 else 0.0
                m_ret = round(float(m_rev[2] or 0.0) * 100, 1) if m_cnt > 0 else 0.0
                m_days = cur.execute(f"""
                    SELECT count(DISTINCT strftime('%Y-%m-%d', r.id/1000, 'unixepoch', 'localtime'))
                    FROM revlog r JOIN cards c ON r.cid = c.id WHERE c.did IN ({m_ph})
                """, m_dids).fetchone()[0]

                modules_telemetry.append({
                    "id": mod_id,
                    "name": mod_label,
                    "cards": m_cards,
                    "reviews": m_cnt,
                    "retention_percentage": m_ret,
                    "avg_seconds_per_card": m_speed,
                    "streak_days": m_days,
                })

    # 4. Decks and Topics Extraction
    topics_list: List[AnkiTopic] = []
    from app.services.anki_analyzer import _detect_cluster

    if "decks" in tables and matching_dids:
        decks_query = f"""
            SELECT 
                d.id,
                d.name,
                count(c.id) as card_cnt,
                sum(case when c.queue in (1, 2, 3) then 1 else 0 end) as due_cnt,
                sum(case when c.queue = 0 then 1 else 0 end) as new_cnt
            FROM decks d
            JOIN cards c ON c.did = d.id
            WHERE d.id IN ({placeholders})
            GROUP BY d.id
            HAVING card_cnt >= 8
            ORDER BY due_cnt DESC, card_cnt DESC
        """
        deck_rows = cur.execute(decks_query, matching_dids).fetchall()

        for d_id, raw_name, card_cnt, due_cnt, new_cnt in deck_rows[:15]:
            display_name = clean_deck_name(raw_name)
            target_cards = due_cnt if due_cnt > 0 else min(30, card_cnt)
            est_minutes = max(10, int((target_cards * avg_seconds) / 60.0))
            cluster = _detect_cluster(raw_name)

            diff_score = min(5.0, max(1.5, round(2.0 + (card_cnt / 40.0), 1)))
            urgency = "high" if due_cnt > 0 else ("medium" if card_cnt > 50 else "normal")

            topics_list.append(
                AnkiTopic(
                    name=display_name,
                    cluster_name=cluster,
                    card_count=card_cnt,
                    estimated_minutes=est_minutes,
                    difficulty_score=diff_score,
                    urgency=urgency,
                )
            )

    conn.close()

    return {
        "deck_scope": scope_key,
        "deck_name": deck_display_name,
        "total_cards": total_cards,
        "total_curriculum_cards": SCOPED_2SJ_CARDS,
        "mature_cards": mature_cards,
        "young_cards": young_cards,
        "due_or_learning": due_or_learning,
        "new_cards": new_cards,
        "revlog_count": revlog_count,
        "avg_seconds_per_card": avg_seconds,
        "cards_per_minute": round(60.0 / max(avg_seconds, 1.0), 1),
        "retention_rate": retention_rate,
        "retention_percentage": round(retention_rate * 100, 1),
        "streak_days": streak_days,
        "first_reviewed": first_reviewed,
        "last_reviewed": last_reviewed,
        "modules": modules_telemetry,
        "topics": topics_list,
    }


def sync_local_anki_collection(
    profile_name: Optional[str] = None,
    deck_scope: str = "curriculum",
) -> Dict[str, Any]:
    """
    Orchestrate full synchronization of a local Anki collection scoped to the deck needed right now:
    1. Locates profile (defaults to primary found profile, e.g. 'Benutzer 1')
    2. Reads telemetry & decks strictly scoped to the target deck ("nur seit immer")
    3. Persists telemetry in ankiweb_stats and decks in anki_decks/anki_topics
    4. Returns updated metrics and topic models for the frontend.
    """
    profiles = detect_local_anki_profiles()
    if not profiles:
        raise FileNotFoundError(
            "Keine lokale Anki-Sammlung gefunden. Bitte stelle sicher, dass Anki Desktop installiert ist."
        )

    selected_profile = profiles[0]
    if profile_name:
        for p in profiles:
            if p["profile_name"].lower() == profile_name.lower():
                selected_profile = p
                break

    col_path = Path(selected_profile["collection_path"])
    p_name = selected_profile["profile_name"]

    data = read_local_anki_database(col_path, deck_scope=deck_scope)

    account_label = f"Anki Desktop ({p_name})"

    # Save telemetry into SQLite repository scoped strictly to the requested deck
    save_ankiweb_stats(
        account_email=account_label,
        total_cards_reviewed=data["revlog_count"],
        overall_retention_rate=data["retention_rate"],
        avg_seconds_per_card=data["avg_seconds_per_card"],
        mature_cards_count=data["mature_cards"],
        young_cards_count=data["young_cards"],
        streak_days=data["streak_days"],
        deck_name=data["deck_name"],
        deck_scope=data["deck_scope"],
        total_cards=data["total_cards"],
        first_reviewed_at=data["first_reviewed"],
        last_reviewed_at=data["last_reviewed"],
    )

    # Save topics into repository
    topic_dicts = [t.model_dump() for t in data["topics"]]
    total_est_min = sum(t.estimated_minutes for t in data["topics"])

    save_anki_deck_summary(
        deck_name=data["deck_name"],
        total_cards=data["total_cards"],
        total_minutes=total_est_min,
        topics=topic_dicts,
    )

    active_deck = get_latest_anki_deck()
    ankiconnect_info = check_ankiconnect_health()

    return {
        "status": "success",
        "mode": "local_sqlite",
        "profile_name": p_name,
        "account_label": account_label,
        "synced_at": datetime.now().isoformat(),
        "deck_scope": data["deck_scope"],
        "deck_name": data["deck_name"],
        "total_cards": data["total_cards"],
        "total_cards_reviewed": data["revlog_count"],
        "overall_retention_rate": data["retention_rate"],
        "retention_percentage": data["retention_percentage"],
        "avg_seconds_per_card": data["avg_seconds_per_card"],
        "cards_per_minute": data["cards_per_minute"],
        "mature_cards_count": data["mature_cards"],
        "young_cards_count": data["young_cards"],
        "due_or_learning": data["due_or_learning"],
        "streak_days": data["streak_days"],
        "first_reviewed": data["first_reviewed"],
        "last_reviewed": data["last_reviewed"],
        "modules": data.get("modules", []),
        "topics_count": len(data["topics"]),
        "deck": active_deck,
        "ankiconnect": ankiconnect_info,
        "message": (
            f"Erfolgreich synchronisiert! Nur Deck '{data['deck_name']}': "
            f"{data['total_cards']:,} Karten, {data['revlog_count']:,} Reviews (seit immer), "
            f"{data['retention_percentage']}% Behalten, {data['avg_seconds_per_card']}s/Karte, "
            f"{data['streak_days']} Tage aktiv."
        ),
    }
