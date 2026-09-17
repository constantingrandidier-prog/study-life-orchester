"""Database Repository providing clean CRUD operations for StudyLife Orchestrator."""

import json
from datetime import date as dt_date, datetime
from typing import Any, Dict, List, Optional
from app.db.database import get_db_connection


# ============================================================================
# USER PROFILE & SETTINGS
# ============================================================================

def get_user_profile(username: str = "student") -> Dict[str, Any]:
    """Retrieve user profile and study settings."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_profile WHERE username = ?", (username,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return {
            "username": username,
            "study_program": "Informatik / UZH",
            "semester": 3,
            "wake_time": "07:00",
            "sleep_time": "23:00",
            "max_daily_study_minutes": 180,
            "pomodoro_minutes": 25,
            "calendar_ics_url": None,
            "ankiweb_email": "student@uzh.ch",
            "last_ankiweb_sync": None,
        }


def update_user_profile(
    username: str = "student",
    study_program: Optional[str] = None,
    semester: Optional[int] = None,
    wake_time: Optional[str] = None,
    sleep_time: Optional[str] = None,
    max_daily_study_minutes: Optional[int] = None,
    pomodoro_minutes: Optional[int] = None,
    calendar_ics_url: Optional[str] = None,
    ankiweb_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Update profile and preferences for the user."""
    current = get_user_profile(username=username)

    new_program = study_program if study_program is not None else current["study_program"]
    new_sem = semester if semester is not None else current["semester"]
    new_wake = wake_time if wake_time is not None else current["wake_time"]
    new_sleep = sleep_time if sleep_time is not None else current["sleep_time"]
    new_max = max_daily_study_minutes if max_daily_study_minutes is not None else current["max_daily_study_minutes"]
    new_pomo = pomodoro_minutes if pomodoro_minutes is not None else current["pomodoro_minutes"]
    new_url = calendar_ics_url if calendar_ics_url is not None else current.get("calendar_ics_url")
    new_email = ankiweb_email if ankiweb_email is not None else current.get("ankiweb_email")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE user_profile SET
                study_program = ?,
                semester = ?,
                wake_time = ?,
                sleep_time = ?,
                max_daily_study_minutes = ?,
                pomodoro_minutes = ?,
                calendar_ics_url = ?,
                ankiweb_email = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE username = ?;
        """, (new_program, new_sem, new_wake, new_sleep, new_max, new_pomo, new_url, new_email, username))

    return get_user_profile(username=username)


# ============================================================================
# CALENDAR EVENTS & LECTURE ATTENDANCE
# ============================================================================

def save_events(events: List[Dict[str, Any]], target_date: dt_date, clear_existing: bool = True) -> int:
    """Save parsed calendar events for a specific date."""
    date_str = target_date.isoformat()
    inserted_count = 0
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if clear_existing:
            cursor.execute("DELETE FROM saved_events WHERE target_date = ?", (date_str,))

        for ev in events:
            # Extract module name from title (e.g. 'Informatik I', 'Analysis')
            title = ev.get("title", "")
            module = _extract_module_name(title)
            
            start_iso = ev["start_time"].isoformat() if hasattr(ev["start_time"], "isoformat") else str(ev["start_time"])
            end_iso = ev["end_time"].isoformat() if hasattr(ev["end_time"], "isoformat") else str(ev["end_time"])

            cursor.execute("""
                INSERT INTO saved_events (
                    target_date, title, start_time, end_time, location, description, module_name, lecture_attended
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                date_str,
                title,
                start_iso,
                end_iso,
                ev.get("location"),
                ev.get("description"),
                module,
                ev.get("lecture_attended"),
            ))
            inserted_count += 1

    return inserted_count


def get_saved_events(target_date: Optional[dt_date] = None) -> List[Dict[str, Any]]:
    """Retrieve saved calendar events optionally filtered by date."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if target_date:
            cursor.execute(
                "SELECT * FROM saved_events WHERE target_date = ? ORDER BY start_time ASC",
                (target_date.isoformat(),),
            )
        else:
            cursor.execute("SELECT * FROM saved_events ORDER BY start_time ASC")
        return [dict(row) for row in cursor.fetchall()]


get_events_for_date = get_saved_events


def update_lecture_attendance(event_id: int, attended: Optional[bool]) -> bool:
    """Set whether the student attended this specific lecture (1, 0, or NULL)."""
    val = 1 if attended is True else (0 if attended is False else None)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE saved_events SET lecture_attended = ? WHERE id = ?", (val, event_id))
        return cursor.rowcount > 0


# ============================================================================
# MANUAL ACTIVITIES (Gym, Meals, Commute)
# ============================================================================

def save_manual_activity(activity: Dict[str, Any], target_date: dt_date) -> int:
    """Save a user manual activity."""
    start_iso = activity["start_time"].isoformat() if hasattr(activity["start_time"], "isoformat") else str(activity["start_time"])
    end_iso = activity["end_time"].isoformat() if hasattr(activity["end_time"], "isoformat") else str(activity["end_time"])
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO saved_activities (
                target_date, title, category, start_time, end_time, notes
            ) VALUES (?, ?, ?, ?, ?, ?);
        """, (
            target_date.isoformat(),
            activity["title"],
            activity.get("category", "custom"),
            start_iso,
            end_iso,
            activity.get("notes"),
        ))
        return cursor.lastrowid or 0


def get_saved_activities(target_date: Optional[dt_date] = None) -> List[Dict[str, Any]]:
    """Retrieve saved manual activities."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if target_date:
            cursor.execute(
                "SELECT * FROM saved_activities WHERE target_date = ? ORDER BY start_time ASC",
                (target_date.isoformat(),),
            )
        else:
            cursor.execute("SELECT * FROM saved_activities ORDER BY start_time ASC")
        return [dict(row) for row in cursor.fetchall()]


def delete_manual_activity(activity_id: int) -> bool:
    """Delete a saved manual activity by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM saved_activities WHERE id = ?", (activity_id,))
        return cursor.rowcount > 0


# ============================================================================
# ANKI DECKS & TOPICS
# ============================================================================

def save_anki_deck_summary(deck_name: str, total_cards: int, total_minutes: int, topics: List[Dict[str, Any]]) -> int:
    """Persist an uploaded Anki deck and all analyzed topics."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO anki_decks (deck_name, total_cards, total_estimated_minutes)
            VALUES (?, ?, ?);
        """, (deck_name, total_cards, total_minutes))
        deck_id = cursor.lastrowid

        for t in topics:
            cursor.execute("""
                INSERT INTO anki_topics (
                    deck_id, name, cluster_name, card_count, estimated_minutes,
                    difficulty_score, matched_lecture, relevance_score, relevance_reason, urgency
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                deck_id,
                t["name"],
                t.get("cluster_name", "Allgemein"),
                t["card_count"],
                t["estimated_minutes"],
                t.get("difficulty_score", 3.0),
                t.get("matched_lecture"),
                t.get("relevance_score", 0.0),
                t.get("relevance_reason"),
                t.get("urgency", "normal"),
            ))

        return deck_id or 0


def get_latest_anki_deck() -> Optional[Dict[str, Any]]:
    """Retrieve the most recently imported Anki deck and its topics."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM anki_decks ORDER BY imported_at DESC LIMIT 1")
        deck = cursor.fetchone()
        if not deck:
            return None
        deck_dict = dict(deck)
        cursor.execute("SELECT * FROM anki_topics WHERE deck_id = ? ORDER BY relevance_score DESC, difficulty_score DESC", (deck_dict["id"],))
        deck_dict["topics"] = [dict(row) for row in cursor.fetchall()]
        return deck_dict


# ============================================================================
# STUDY SESSION LOGS (For Lecture ROI & Efficiency Analytics)
# ============================================================================

def log_study_session(
    topic_name: str,
    module_name: Optional[str],
    duration_minutes: int,
    cards_reviewed: int,
    seconds_per_card: float,
    retention_rate: float,
    lecture_attended: bool,
    session_date: Optional[dt_date] = None,
) -> int:
    """Log a completed study session with cards reviewed, speed, retention, and attendance."""
    sdate = session_date or dt_date.today()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO study_session_logs (
                session_date, topic_name, module_name, duration_minutes,
                cards_reviewed, seconds_per_card, retention_rate, lecture_attended
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            sdate.isoformat(),
            topic_name,
            module_name or _extract_module_name(topic_name),
            duration_minutes,
            cards_reviewed,
            seconds_per_card,
            retention_rate,
            1 if lecture_attended else 0,
        ))
        return cursor.lastrowid or 0


def get_study_session_logs(module_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve historical study logs, optionally filtered by module."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if module_name:
            cursor.execute(
                "SELECT * FROM study_session_logs WHERE module_name = ? ORDER BY session_date DESC, logged_at DESC",
                (module_name,),
            )
        else:
            cursor.execute("SELECT * FROM study_session_logs ORDER BY session_date DESC, logged_at DESC")
        return [dict(row) for row in cursor.fetchall()]


# ============================================================================
# ANKIWEB STATS PERSISTENCE
# ============================================================================

def save_ankiweb_stats(
    account_email: str,
    total_cards_reviewed: int,
    overall_retention_rate: float,
    avg_seconds_per_card: float,
    mature_cards_count: int,
    young_cards_count: int,
    streak_days: int,
    deck_name: Optional[str] = None,
    deck_scope: str = "curriculum",
    total_cards: int = 9319,
    first_reviewed_at: Optional[str] = None,
    last_reviewed_at: Optional[str] = None,
) -> int:
    """Save synced Anki / AnkiWeb statistics with deck scoping."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ankiweb_stats (
                account_email, total_cards_reviewed, overall_retention_rate,
                avg_seconds_per_card, mature_cards_count, young_cards_count, streak_days,
                deck_name, deck_scope, total_cards, first_reviewed_at, last_reviewed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            account_email,
            total_cards_reviewed,
            overall_retention_rate,
            avg_seconds_per_card,
            mature_cards_count,
            young_cards_count,
            streak_days,
            deck_name,
            deck_scope,
            total_cards,
            first_reviewed_at,
            last_reviewed_at,
        ))

        # Update last sync time in user_profile
        cursor.execute("""
            UPDATE user_profile SET
                ankiweb_email = ?,
                last_ankiweb_sync = CURRENT_TIMESTAMP
            WHERE username = 'student';
        """, (account_email,))

        return cursor.lastrowid or 0


def get_latest_ankiweb_stats(deck_scope: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve the latest synced AnkiWeb statistics, optionally filtered by deck_scope."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if deck_scope:
            cursor.execute(
                "SELECT * FROM ankiweb_stats WHERE deck_scope = ? ORDER BY synced_at DESC LIMIT 1",
                (deck_scope,)
            )
        else:
            cursor.execute("SELECT * FROM ankiweb_stats ORDER BY synced_at DESC LIMIT 1")
        row = cursor.fetchone()
        return dict(row) if row else None


# ============================================================================
# PHASE 1: EXAMS, PACING CONFIG & DAILY PROGRESS REPOSITORY METHODS
# ============================================================================

def get_exams(user_id: str = "student") -> List[Dict[str, Any]]:
    """Retrieve all exams for a user ordered by exam date."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, subject_name, exam_date, target_cards, notes, created_at
            FROM exams
            WHERE user_id = ?
            ORDER BY exam_date ASC;
        """, (user_id,))
        return [dict(r) for r in cursor.fetchall()]


def save_exam(
    subject_name: str,
    exam_date: str,
    target_cards: int = 8729,
    notes: Optional[str] = None,
    user_id: str = "student"
) -> int:
    """Insert or update an exam entry."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO exams (user_id, subject_name, exam_date, target_cards, notes)
            VALUES (?, ?, ?, ?, ?);
        """, (user_id, subject_name, exam_date, target_cards, notes))
        return cursor.lastrowid or 0


def delete_exam(exam_id: int, user_id: str = "student") -> bool:
    """Delete an exam by id."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM exams WHERE id = ? AND user_id = ?", (exam_id, user_id))
        return cursor.rowcount > 0


def get_pacing_config(user_id: str = "student") -> Dict[str, Any]:
    """Retrieve study schedule configuration (free weekdays, joker dates, revision buffer)."""
    import json
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM study_schedule_config WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            res = dict(row)
            try:
                res["free_weekdays"] = json.loads(res.get("free_weekdays") or "[6]")
            except Exception:
                res["free_weekdays"] = [6]
            try:
                res["joker_dates"] = json.loads(res.get("joker_dates") or "[]")
            except Exception:
                res["joker_dates"] = []
            return res
        return {
            "user_id": user_id,
            "free_weekdays": [6],
            "joker_dates": [],
            "revision_buffer_days": 14,
            "total_curriculum_cards": 8729,
        }


def save_pacing_config(
    free_weekdays: Optional[List[int]] = None,
    joker_dates: Optional[List[str]] = None,
    revision_buffer_days: Optional[int] = None,
    total_curriculum_cards: Optional[int] = None,
    user_id: str = "student"
) -> Dict[str, Any]:
    """Save or update schedule configuration."""
    import json
    current = get_pacing_config(user_id=user_id)
    new_weekdays = free_weekdays if free_weekdays is not None else current["free_weekdays"]
    new_jokers = joker_dates if joker_dates is not None else current["joker_dates"]
    new_buffer = revision_buffer_days if revision_buffer_days is not None else current["revision_buffer_days"]
    new_total = total_curriculum_cards if total_curriculum_cards is not None else current["total_curriculum_cards"]

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO study_schedule_config (
                user_id, free_weekdays, joker_dates, revision_buffer_days, total_curriculum_cards, updated_at
            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                free_weekdays = excluded.free_weekdays,
                joker_dates = excluded.joker_dates,
                revision_buffer_days = excluded.revision_buffer_days,
                total_curriculum_cards = excluded.total_curriculum_cards,
                updated_at = CURRENT_TIMESTAMP;
        """, (
            user_id,
            json.dumps(new_weekdays),
            json.dumps(new_jokers),
            new_buffer,
            new_total
        ))

    return get_pacing_config(user_id=user_id)


def get_daily_progress_for_date(target_date: dt_date, user_id: str = "student") -> Optional[Dict[str, Any]]:
    """Retrieve logged progress for a specific calendar date."""
    date_str = target_date.isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, log_date, cards_completed, minutes_spent, source, notes, logged_at
            FROM daily_progress_logs
            WHERE user_id = ? AND log_date = ?;
        """, (user_id, date_str))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_daily_progress_logs(user_id: str = "student") -> List[Dict[str, Any]]:
    """Retrieve all daily progress logs for a user ordered chronologically."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, log_date as date, log_date, cards_completed, minutes_spent, source, notes, logged_at
            FROM daily_progress_logs
            WHERE user_id = ?
            ORDER BY log_date ASC;
        """, (user_id,))
        return [dict(r) for r in cursor.fetchall()]


def save_daily_progress(
    target_date: dt_date,
    cards_completed: int,
    minutes_spent: int = 0,
    source: str = "manual",
    notes: Optional[str] = None,
    user_id: str = "student"
) -> Dict[str, Any]:
    """Record or update completed cards for a day."""
    date_str = target_date.isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO daily_progress_logs (
                user_id, log_date, cards_completed, minutes_spent, source, notes, logged_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, log_date) DO UPDATE SET
                cards_completed = excluded.cards_completed,
                minutes_spent = excluded.minutes_spent,
                source = excluded.source,
                notes = excluded.notes,
                logged_at = CURRENT_TIMESTAMP;
        """, (user_id, date_str, cards_completed, minutes_spent, source, notes))

    return get_daily_progress_for_date(target_date, user_id=user_id) or {
        "user_id": user_id,
        "log_date": date_str,
        "cards_completed": cards_completed,
        "minutes_spent": minutes_spent,
        "source": source,
    }


def get_total_cards_completed_all_time(user_id: str = "student") -> int:
    """Sum of all completed cards across historical progress logs."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(SUM(cards_completed), 0) FROM daily_progress_logs WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row[0] if row else 0


# ============================================================================
# UTILITIES
# ============================================================================

def _extract_module_name(text: str) -> str:
    """Extract clean university module title (e.g., 'Informatik I', 'Analysis', 'Biochemie')."""
    clean = text.replace("Vorlesung:", "").replace("Lecture:", "").replace("Übung:", "").strip()
    # Split by colon, dash or parens
    for delimiter in [":", "-", "(", ","]:
        if delimiter in clean:
            clean = clean.split(delimiter)[0].strip()
    return clean or "Allgemeines Modul"


# ============================================================================
# RHYTHM BLOCK ACTIONS (Delete, Postpone to Tomorrow)
# ============================================================================

def save_rhythm_action(
    source_date: str,
    block_id: str,
    action: str,
    target_date: Optional[str] = None,
    block_payload: Optional[Dict[str, Any]] = None,
    user_id: str = "student",
) -> Dict[str, Any]:
    """Saves a block action (delete, postpone, complete, uncomplete, or custom). Overwrites existing action for same block and source date."""
    if action == "uncomplete":
        return restore_rhythm_action(source_date=source_date, block_id=block_id, user_id=user_id)

    payload_json = json.dumps(block_payload, ensure_ascii=False) if block_payload else None
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Remove any existing record for this block & source date to avoid duplicates
        cursor.execute("""
            DELETE FROM rhythm_block_actions
            WHERE user_id = ? AND source_date = ? AND block_id = ?;
        """, (user_id, source_date, block_id))

        cursor.execute("""
            INSERT INTO rhythm_block_actions (
                user_id, source_date, target_date, block_id, action, block_payload, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
        """, (user_id, source_date, target_date, block_id, action, payload_json))

    return {
        "status": "ok",
        "source_date": source_date,
        "block_id": block_id,
        "action": action,
        "target_date": target_date,
    }


def get_rhythm_actions_for_date(target_date: str, user_id: str = "student") -> Dict[str, Any]:
    """
    Returns rhythm adjustments for a given date:
    - removed_block_ids: blocks deleted or postponed out of this date
    - completed_block_ids: blocks marked as completed
    - custom_blocks: dict of block_id -> custom payload overrides
    - postponed_blocks: blocks postponed from a previous date INTO this target_date
    - custom_order: list of block IDs in custom user-reordered sequence
    - custom_durations: dict of block_id -> minutes
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # 1. Blocks removed/postponed/completed/reordered FROM this date
        cursor.execute("""
            SELECT block_id, action, block_payload FROM rhythm_block_actions
            WHERE user_id = ? AND source_date = ?;
        """, (user_id, target_date))
        rows = cursor.fetchall()
        removed_ids = []
        completed_ids = []
        custom_blocks = {}
        custom_order = []
        custom_durations = {}
        for row in rows:
            act = row["action"]
            bid = row["block_id"]
            if act in ("delete", "postpone") and bid not in ("__custom_order__", "__custom_durations__"):
                removed_ids.append(bid)
            elif act in ("complete", "completed"):
                completed_ids.append(bid)
                if row["block_payload"]:
                    try:
                        custom_blocks[bid] = json.loads(row["block_payload"])
                    except Exception:
                        pass
            elif act in ("custom", "update") and row["block_payload"]:
                try:
                    custom_blocks[bid] = json.loads(row["block_payload"])
                except Exception:
                    pass
            elif act == "reorder" and row["block_payload"]:
                try:
                    payload = json.loads(row["block_payload"])
                    custom_order = payload.get("order", [])
                except Exception:
                    custom_order = []
            elif act == "durations" and row["block_payload"]:
                try:
                    payload = json.loads(row["block_payload"])
                    custom_durations = payload.get("durations", {})
                except Exception:
                    custom_durations = {}

        # 2. Blocks postponed INTO this target_date
        cursor.execute("""
            SELECT id, source_date, target_date, block_id, action, block_payload
            FROM rhythm_block_actions
            WHERE user_id = ? AND target_date = ? AND action = 'postpone';
        """, (user_id, target_date))
        postponed = []
        for row in cursor.fetchall():
            payload = {}
            if row["block_payload"]:
                try:
                    payload = json.loads(row["block_payload"])
                except Exception:
                    payload = {}
            payload["_action_id"] = row["id"]
            payload["_postponed_from"] = row["source_date"]
            payload["_postponed_to"] = row["target_date"]
            postponed.append(payload)

    return {
        "removed_block_ids": removed_ids,
        "completed_block_ids": completed_ids,
        "custom_blocks": custom_blocks,
        "postponed_blocks": postponed,
        "custom_order": custom_order,
        "custom_durations": custom_durations,
    }


def restore_rhythm_action(
    source_date: str,
    block_id: Optional[str] = None,
    user_id: str = "student",
) -> Dict[str, Any]:
    """Restores removed or postponed blocks back to original state for a date."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if block_id:
            cursor.execute("""
                DELETE FROM rhythm_block_actions
                WHERE user_id = ? AND source_date = ? AND block_id = ?;
            """, (user_id, source_date, block_id))
        else:
            cursor.execute("""
                DELETE FROM rhythm_block_actions
                WHERE user_id = ? AND source_date = ?;
            """, (user_id, source_date))

    return {"status": "restored", "source_date": source_date, "block_id": block_id}


# ============================================================================
# CURRICULUM DAY SWAPS & SCHEDULE OVERRIDES
# ============================================================================

def get_curriculum_schedule_overrides(user_id: str = "student") -> Dict[str, int]:
    """Returns mapping of target_date -> assigned_day_number (e.g. {'2026-09-17': 5, '2026-09-18': 4})."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS curriculum_schedule_overrides (
                user_id TEXT NOT NULL DEFAULT 'student',
                target_date TEXT NOT NULL,
                assigned_day_number INTEGER NOT NULL,
                PRIMARY KEY (user_id, target_date)
            );
        """)
        cursor.execute("""
            SELECT target_date, assigned_day_number
            FROM curriculum_schedule_overrides
            WHERE user_id = ?;
        """, (user_id,))
        return {row["target_date"]: row["assigned_day_number"] for row in cursor.fetchall()}


def save_curriculum_schedule_override(
    target_date: str,
    assigned_day_number: int,
    user_id: str = "student",
) -> None:
    """Saves or updates an assigned day number for a target date."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO curriculum_schedule_overrides (user_id, target_date, assigned_day_number)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, target_date) DO UPDATE SET
                assigned_day_number = excluded.assigned_day_number;
        """, (user_id, target_date, assigned_day_number))


def swap_curriculum_days(
    date1: str,
    date2: str,
    day_num1: Optional[int] = None,
    day_num2: Optional[int] = None,
    user_id: str = "student",
) -> Dict[str, Any]:
    """
    Swaps learning packages between two dates.
    If day_num1 and day_num2 are provided, date1 gets day_num2 and date2 gets day_num1.
    Otherwise looks up current assignments and swaps them.
    """
    current_overrides = get_curriculum_schedule_overrides(user_id=user_id)
    actual_num1 = day_num1 if day_num1 is not None else current_overrides.get(date1)
    actual_num2 = day_num2 if day_num2 is not None else current_overrides.get(date2)

    if actual_num1 is None or actual_num2 is None:
        # Fallback: calculate canonical active day numbers from SEMESTER_START_DATE (2026-09-14)
        from datetime import datetime as dt
        d1 = dt.strptime(date1, "%Y-%m-%d").date()
        d2 = dt.strptime(date2, "%Y-%m-%d").date()
        start = dt.strptime("2026-09-14", "%Y-%m-%d").date()

        def get_canonical_day_num(target):
            cur = start
            active_cnt = 0
            while cur <= target:
                if cur.weekday() != 6:
                    active_cnt += 1
                cur += timedelta(days=1)
            return active_cnt

        from datetime import timedelta
        if actual_num1 is None:
            actual_num1 = get_canonical_day_num(d1)
        if actual_num2 is None:
            actual_num2 = get_canonical_day_num(d2)

    # Swap assignments: date1 gets actual_num2, date2 gets actual_num1
    save_curriculum_schedule_override(date1, actual_num2, user_id=user_id)
    save_curriculum_schedule_override(date2, actual_num1, user_id=user_id)

    return {
        "status": "ok",
        "swapped": [
            {"date": date1, "assigned_day_number": actual_num2, "previous_day_number": actual_num1},
            {"date": date2, "assigned_day_number": actual_num1, "previous_day_number": actual_num2},
        ],
    }


def reset_curriculum_schedule_overrides(user_id: str = "student") -> Dict[str, Any]:
    """Clears all custom curriculum day swaps back to chronological sequence."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM curriculum_schedule_overrides WHERE user_id = ?;", (user_id,))
    return {"status": "reset", "user_id": user_id}
