"""Service for calculating learning comparisons (vortag, week trend, streak, time saved)."""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from app.db.database import get_db_connection
from app.services.lecture_decision_service import get_total_time_saved_for_date


def get_progress_comparison_stats(target_date: Optional[date] = None, user_id: str = "student") -> Dict[str, Any]:
    """
    Calculate comparative progress statistics:
    - Comparison to previous day (Vortagsvergleich)
    - 7-day weekly total and daily average
    - Current learning streak
    - Total lecture minutes saved today via speed streaming or skipping
    """
    curr_date = target_date if target_date is not None else date.today()
    yesterday = curr_date - timedelta(days=1)

    curr_str = curr_date.isoformat()
    yest_str = yesterday.isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Today's cards
        cursor.execute("""
            SELECT cards_completed, minutes_spent
            FROM daily_progress_logs
            WHERE user_id = ? AND log_date = ?;
        """, (user_id, curr_str))
        today_row = cursor.fetchone()
        cards_today = today_row["cards_completed"] if today_row else 0
        minutes_today = today_row["minutes_spent"] if today_row else 0

        # 2. Yesterday's cards
        cursor.execute("""
            SELECT cards_completed, minutes_spent
            FROM daily_progress_logs
            WHERE user_id = ? AND log_date = ?;
        """, (user_id, yest_str))
        yest_row = cursor.fetchone()
        cards_yesterday = yest_row["cards_completed"] if yest_row else 0

        # Diff to yesterday
        diff_cards = cards_today - cards_yesterday
        if cards_yesterday > 0:
            diff_pct = round((diff_cards / cards_yesterday) * 100, 1)
        else:
            diff_pct = 100.0 if cards_today > 0 else 0.0

        # 3. Past 7 days data
        past_7_days_start = (curr_date - timedelta(days=6)).isoformat()
        cursor.execute("""
            SELECT log_date, cards_completed
            FROM daily_progress_logs
            WHERE user_id = ? AND log_date >= ? AND log_date <= ?
            ORDER BY log_date ASC;
        """, (user_id, past_7_days_start, curr_str))
        week_rows = {r["log_date"]: r["cards_completed"] for r in cursor.fetchall()}

        week_total_cards = sum(week_rows.values())
        week_daily_avg = round(week_total_cards / 7.0, 1)

        # 4. Learning streak (consecutive days with cards_completed > 0)
        cursor.execute("""
            SELECT log_date, cards_completed
            FROM daily_progress_logs
            WHERE user_id = ? AND cards_completed > 0
            ORDER BY log_date DESC;
        """, (user_id,))
        active_days = [datetime.strptime(r["log_date"], "%Y-%m-%d").date() for r in cursor.fetchall()]

        streak = 0
        check_day = curr_date
        # Check if today is completed or yesterday was completed
        if active_days and (active_days[0] == curr_date or active_days[0] == yesterday):
            for ad in active_days:
                if ad == check_day or ad == check_day - timedelta(days=1):
                    streak += 1
                    check_day = ad
                else:
                    break
        if streak == 0 and cards_today > 0:
            streak = 1

    # 5. Lecture time saved today
    time_saved_today = get_total_time_saved_for_date(curr_date)

    # Human-readable comparison labels
    if diff_cards > 0:
        diff_label = f"+{diff_cards} Karten vs. gestern (+{diff_pct}%)"
    elif diff_cards < 0:
        diff_label = f"{diff_cards} Karten vs. gestern ({diff_pct}%)"
    else:
        diff_label = "Gleich wie gestern"

    return {
        "target_date": curr_str,
        "cards_today": cards_today,
        "cards_yesterday": cards_yesterday,
        "diff_cards": diff_cards,
        "diff_percentage": diff_pct,
        "diff_label": diff_label,
        "week_total_cards": week_total_cards,
        "week_daily_average": week_daily_avg,
        "current_streak_days": max(1, streak),
        "total_minutes_saved_today": time_saved_today,
        "summary": f"{diff_label} • 7-Tage-Schnitt: {week_daily_avg} Karten/Tag • {time_saved_today} Min gespart",
    }
