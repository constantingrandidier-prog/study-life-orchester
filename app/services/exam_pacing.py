"""Service for calculating exam-oriented study pacing, daily card targets, and progress tracking."""

import math
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from app.db.repository import (
    delete_exam,
    get_daily_progress_for_date,
    get_exams,
    get_latest_ankiweb_stats,
    get_pacing_config,
    get_total_cards_completed_all_time,
    save_daily_progress,
    save_exam,
    save_pacing_config,
)


WEEKDAY_NAMES_DE = [
    "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"
]


def calculate_exam_pacing(target_date: Optional[date] = None, user_id: str = "student") -> Dict[str, Any]:
    """
    Calculate dynamic study pacing up to the first exam deadline.
    Considers configured rest days (e.g. Sundays), spontaneous joker dates,
    and a 14-day pure revision buffer before exam day.
    """
    curr_date = target_date if target_date is not None else date.today()

    # 1. Fetch exams
    exams_raw = get_exams(user_id=user_id)
    if not exams_raw:
        # Seed default exams if missing
        save_exam("Medizin 2. SJ – Prüfung 1", "2027-01-19", 8729, "Erste Modulprüfung 2. Studienjahr UZH", user_id)
        save_exam("Medizin 2. SJ – Prüfung 2", "2027-01-21", 8729, "Zweite Modulprüfung 2. Studienjahr UZH", user_id)
        exams_raw = get_exams(user_id=user_id)

    formatted_exams: List[Dict[str, Any]] = []
    next_exam: Optional[Dict[str, Any]] = None

    for ex in exams_raw:
        try:
            ex_date = datetime.strptime(ex["exam_date"], "%Y-%m-%d").date()
        except ValueError:
            continue
        days_left = (ex_date - curr_date).days
        item = {
            "id": ex["id"],
            "subject_name": ex["subject_name"],
            "exam_date": ex["exam_date"],
            "target_cards": ex.get("target_cards", 8729),
            "days_left": days_left,
            "notes": ex.get("notes"),
        }
        formatted_exams.append(item)
        if days_left >= 0 and (next_exam is None or days_left < next_exam["days_left"]):
            next_exam = item

    if not next_exam and formatted_exams:
        next_exam = formatted_exams[0]

    # Target exam date
    if next_exam:
        exam_target_date = datetime.strptime(next_exam["exam_date"], "%Y-%m-%d").date()
    else:
        exam_target_date = date(2027, 1, 19)

    calendar_days_to_exam = max(0, (exam_target_date - curr_date).days)

    # 2. Fetch user pacing configuration
    cfg = get_pacing_config(user_id=user_id)
    free_weekdays = set(cfg.get("free_weekdays", [6]))  # 6 = Sunday
    joker_dates = set(cfg.get("joker_dates", []))
    revision_buffer_days = int(cfg.get("revision_buffer_days", 14))
    total_curriculum_cards = int(cfg.get("total_curriculum_cards", 8729))

    revision_start_date = max(curr_date, exam_target_date - timedelta(days=revision_buffer_days))

    # 3. Calculate remaining active learning days (before revision buffer starts)
    learning_days_remaining = 0
    scan_day = curr_date
    while scan_day < revision_start_date:
        is_free_weekday = scan_day.weekday() in free_weekdays
        is_joker = scan_day.isoformat() in joker_dates
        if not is_free_weekday and not is_joker:
            learning_days_remaining += 1
        scan_day += timedelta(days=1)

    # Safety floor
    if learning_days_remaining == 0 and calendar_days_to_exam > 0:
        learning_days_remaining = max(1, calendar_days_to_exam)

    # 4. Check if today is a rest day
    curr_date_str = curr_date.isoformat()
    is_joker_day = curr_date_str in joker_dates
    is_weekday_free = curr_date.weekday() in free_weekdays
    is_revision_phase = curr_date >= revision_start_date and curr_date <= exam_target_date

    is_rest_day = is_joker_day or is_weekday_free
    rest_day_reason: Optional[str] = None
    if is_joker_day:
        rest_day_reason = "Joker-Tag aktiv (Spontane Pause)"
    elif is_weekday_free:
        day_name = WEEKDAY_NAMES_DE[curr_date.weekday()]
        rest_day_reason = f"Regulärer Ruhetag ({day_name})"
    elif is_revision_phase:
        rest_day_reason = "14-Tage Revisionsphase (Reines Wiederholen, keine neuen Karten)"

    # 5. Semester Timeline & Cumulative Backlog Metrics
    SEMESTER_START_DATE = date(2026, 9, 14)

    # Total active learning days across the whole semester (before revision buffer)
    total_semester_learning_days = 0
    s_day = SEMESTER_START_DATE
    while s_day < revision_start_date:
        if s_day.weekday() not in free_weekdays and s_day.isoformat() not in joker_dates:
            total_semester_learning_days += 1
        s_day += timedelta(days=1)
    total_semester_learning_days = max(1, total_semester_learning_days)
    base_daily_quota = math.ceil(total_curriculum_cards / total_semester_learning_days)

    # Active learning days strictly elapsed before curr_date
    elapsed_learning_days = 0
    e_day = SEMESTER_START_DATE
    while e_day < curr_date:
        if e_day.weekday() not in free_weekdays and e_day.isoformat() not in joker_dates:
            elapsed_learning_days += 1
        e_day += timedelta(days=1)

    # Cards completed strictly before curr_date
    from app.db.repository import get_db_connection
    cards_completed_prior = 0
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COALESCE(SUM(cards_completed), 0) FROM daily_progress_logs WHERE user_id = ? AND log_date < ?",
                (user_id, curr_date.isoformat())
            )
            cards_completed_prior = cur.fetchone()[0] or 0
    except Exception:
        cards_completed_prior = 0

    expected_cards_prior = elapsed_learning_days * base_daily_quota
    cumulative_backlog = max(0, expected_cards_prior - cards_completed_prior)
    backlog_spread_per_day = math.ceil(cumulative_backlog / max(1, learning_days_remaining)) if (cumulative_backlog > 0 and learning_days_remaining > 0) else 0

    # Remaining cards to complete across remaining learning days
    remaining_curriculum_cards_for_quota = max(0, total_curriculum_cards - cards_completed_prior)

    # Calculate daily target
    if is_rest_day or is_revision_phase:
        daily_target_cards = 0
    else:
        daily_target_cards = math.ceil(remaining_curriculum_cards_for_quota / max(1, learning_days_remaining))

    # Detailed backlog explanation
    if is_rest_day:
        backlog_explanation = f"Eingeplanter Ruhetag: {rest_day_reason}"
    elif cumulative_backlog > 0:
        backlog_explanation = (
            f"⚖️ +{backlog_spread_per_day} Karten/Tag aus kumulativem Rückstand "
            f"({cumulative_backlog} Karten Rückstand aus {elapsed_learning_days} Tagen über {learning_days_remaining} verbleibende Lerntage verteilt: "
            f"Basis {base_daily_quota} + {backlog_spread_per_day} = {daily_target_cards} neue Karten heute)."
        )
    elif cards_completed_prior > expected_cards_prior:
        surplus = cards_completed_prior - expected_cards_prior
        backlog_explanation = (
            f"🎉 {surplus} Karten Vorsprung erarbeitet! Dein Tagespensum ist entlastet "
            f"({daily_target_cards} statt Basis {base_daily_quota} neue Karten heute)."
        )
    else:
        backlog_explanation = f"Standard-Tagesziel von {base_daily_quota} neuen Karten (Voll im Soll)."

    # All-time card progress metrics (including today)
    total_cards_completed = get_total_cards_completed_all_time(user_id=user_id)
    remaining_curriculum_cards = max(0, total_curriculum_cards - total_cards_completed)

    # Today's actual logged cards (auto-synchronized with Anki Desktop - ONLY NEW CARDS)
    cards_completed_today = 0
    today_log = get_daily_progress_for_date(curr_date, user_id=user_id)
    if today_log and today_log.get("source") == "manual":
        cards_completed_today = today_log.get("cards_completed", 0)
    else:
        try:
            if user_id == "student":
                from app.services.anki_desktop_sync import read_live_anki_desktop_state
                sync_res = read_live_anki_desktop_state(target_date_str=curr_date.isoformat())
                if sync_res and sync_res.get("connected"):
                    auto_cnt = sync_res.get("new_cards_count", sync_res.get("today_reviewed_count", 0))
                    if auto_cnt is not None:
                        cards_completed_today = auto_cnt
        except Exception:
            pass

    if cards_completed_today == 0 and today_log:
        cards_completed_today = today_log.get("cards_completed", 0)

    cards_remaining_today = max(0, daily_target_cards - cards_completed_today)

    if daily_target_cards > 0:
        completion_percentage_today = round(min(100.0, (cards_completed_today / daily_target_cards) * 100), 1)
    else:
        completion_percentage_today = 100.0 if (is_rest_day or cards_completed_today > 0) else 0.0

    overall_progress_percentage = round(
        min(100.0, (total_cards_completed / total_curriculum_cards) * 100), 1
    ) if total_curriculum_cards > 0 else 0.0

    # Scenarios: 7d, 6d (Sonntag frei), 5d (Wochenende frei)
    days_to_buffer = max(1, (revision_start_date - curr_date).days)
    pace_7d = math.ceil(remaining_curriculum_cards / days_to_buffer)
    pace_6d = math.ceil(remaining_curriculum_cards / max(1, math.floor(days_to_buffer * 6 / 7)))
    pace_5d = math.ceil(remaining_curriculum_cards / max(1, math.floor(days_to_buffer * 5 / 7)))

    # Readiness calculation incorporating retention rate
    anki_stats = get_latest_ankiweb_stats() or {}
    # Exam readiness: based on curriculum completed scaled by retention quality
    if overall_progress_percentage <= 0.0:
        exam_readiness_score = 0.0
    else:
        retention = anki_stats.get("retention_rate", 85.0) / 100.0
        retention_quality = min(1.0, max(0.5, retention))
        exam_readiness_score = round(overall_progress_percentage * retention_quality, 1)

    # 6. Real Anki Due Reviews & Weakness Metrics
    due_reviews = 0
    weakness_summary = None
    try:
        from app.services.anki_weakness_service import get_anki_due_and_weaknesses
        anki_info = get_anki_due_and_weaknesses()
        due_reviews = anki_info.get("due_reviews_count", 0)
        weaks = anki_info.get("weakness_topics", [])
        if weaks:
            top_w = weaks[0]
            weakness_summary = f"⚠️ Schwachstelle: {top_w['deck_name']} ({top_w['fail_rate']}% Fehler)"
    except Exception:
        due_reviews = 0

    total_daily_cards_needed = daily_target_cards + due_reviews

    # Tailored Advice
    if is_rest_day:
        advice = f"Genieße deine Pause! {rest_day_reason}. Deine tägliche Pacing-Kurve hat diesen Ruhetag bereits eingerechnet."
    elif cards_completed_today >= daily_target_cards and daily_target_cards > 0:
        advice = f"🎉 Exzellent! Du hast {cards_completed_today} Karten in Anki gemeistert (Tagesziel von {daily_target_cards} zu {round(cards_completed_today/daily_target_cards*100)}% übererfüllt). Voll auf Kurs!"
    elif cards_completed_today > 0:
        advice = f"🟢 Live aus Anki: {cards_completed_today} Karten erledigt – noch {cards_remaining_today} Karten bis zum Tagesziel ({daily_target_cards} Karten)."
    else:
        advice = f"Heutiges Soll: {daily_target_cards} neue Karten + {due_reviews} Wiederholungen ({total_daily_cards_needed} gesamt). Exakt im Plan für den 19.01.2027!"

    return {
        "target_date": curr_date_str,
        "is_rest_day": is_rest_day,
        "rest_day_reason": rest_day_reason,
        "next_exam": next_exam,
        "all_exams": formatted_exams,
        "calendar_days_to_exam": calendar_days_to_exam,
        "learning_days_remaining": learning_days_remaining,
        "revision_buffer_days": revision_buffer_days,
        "revision_start_date": revision_start_date.isoformat(),
        "total_curriculum_cards": total_curriculum_cards,
        "total_cards_completed": total_cards_completed,
        "remaining_curriculum_cards": remaining_curriculum_cards,
        "daily_target_cards": daily_target_cards,
        "due_reviews_today": due_reviews,
        "total_daily_cards_needed": total_daily_cards_needed,
        "weakness_summary": weakness_summary,
        "cards_completed_today": cards_completed_today,
        "cards_remaining_today": cards_remaining_today,
        "completion_percentage_today": completion_percentage_today,
        "overall_progress_percentage": overall_progress_percentage,
        "exam_readiness_score": exam_readiness_score,
        "pacing_scenarios": {
            "7_days_week": pace_7d,
            "6_days_week": pace_6d,
            "5_days_week": pace_5d,
        },
        "base_daily_quota": base_daily_quota,
        "cumulative_backlog": cumulative_backlog,
        "backlog_spread_per_day": backlog_spread_per_day,
        "backlog_explanation": backlog_explanation,
        "elapsed_learning_days": elapsed_learning_days,
        "cards_completed_prior": cards_completed_prior,
        "expected_cards_prior": expected_cards_prior,
        "advice": advice,
    }


def log_progress(
    cards_completed: int,
    minutes_spent: int = 0,
    target_date: Optional[date] = None,
    source: str = "manual",
    notes: Optional[str] = None,
    user_id: str = "student",
) -> Dict[str, Any]:
    """Record completed cards for a day and return updated pacing summary."""
    curr_date = target_date if target_date is not None else date.today()
    save_daily_progress(
        target_date=curr_date,
        cards_completed=cards_completed,
        minutes_spent=minutes_spent,
        source=source,
        notes=notes,
        user_id=user_id,
    )
    return calculate_exam_pacing(target_date=curr_date, user_id=user_id)


def toggle_joker_day(date_str: str, user_id: str = "student") -> Dict[str, Any]:
    """Toggle a specific calendar date as a spontaneous rest/joker day."""
    cfg = get_pacing_config(user_id=user_id)
    jokers = set(cfg.get("joker_dates", []))
    if date_str in jokers:
        jokers.remove(date_str)
    else:
        jokers.add(date_str)
    
    save_pacing_config(joker_dates=sorted(list(jokers)), user_id=user_id)
    try:
        t_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        t_date = date.today()
    return calculate_exam_pacing(target_date=t_date, user_id=user_id)


def update_pacing_preferences(
    free_weekdays: Optional[List[int]] = None,
    joker_dates: Optional[List[str]] = None,
    revision_buffer_days: Optional[int] = None,
    total_curriculum_cards: Optional[int] = None,
    user_id: str = "student",
) -> Dict[str, Any]:
    """Update general pacing preferences (e.g. change free day from Sunday to Saturday)."""
    save_pacing_config(
        free_weekdays=free_weekdays,
        joker_dates=joker_dates,
        revision_buffer_days=revision_buffer_days,
        total_curriculum_cards=total_curriculum_cards,
        user_id=user_id,
    )
    return calculate_exam_pacing(user_id=user_id)
