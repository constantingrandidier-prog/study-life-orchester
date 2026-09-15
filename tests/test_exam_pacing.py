"""Tests for Phase 1 Exam Pacing, Free Days, Joker Days, and Daily Progress Tracking."""

from datetime import date
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.exam_pacing import (
    calculate_exam_pacing,
    log_progress,
    toggle_joker_day,
    update_pacing_preferences,
)
from app.db.repository import (
    get_daily_progress_for_date,
    save_daily_progress,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_exam_pacing_defaults():
    """Verify default pacing up to 19.01.2027 with Sunday off and 14-day revision buffer."""
    res = calculate_exam_pacing(target_date=date(2026, 9, 14), user_id="test_student_pacing")
    assert res["target_date"] == "2026-09-14"
    assert res["calendar_days_to_exam"] == 127
    assert res["learning_days_remaining"] == 97  # 113 - 16 Sundays
    assert res["daily_target_cards"] >= 99
    assert res["is_rest_day"] is False
    assert "7_days_week" in res["pacing_scenarios"]
    assert "6_days_week" in res["pacing_scenarios"]
    assert "5_days_week" in res["pacing_scenarios"]
    assert res["total_curriculum_cards"] == 9633


def test_sunday_scheduled_rest_day():
    """Verify Sunday is automatically treated as a scheduled rest day."""
    sunday = date(2026, 9, 20)
    res = calculate_exam_pacing(target_date=sunday, user_id="test_student_pacing")
    assert res["is_rest_day"] is True
    assert res["daily_target_cards"] == 0
    assert "Sonntag" in (res["rest_day_reason"] or "")


def test_joker_day_toggle():
    """Verify that toggling a joker day turns a learning day into a rest day and rebalances."""
    test_date = "2026-09-15"
    # Toggle ON
    res_on = toggle_joker_day(test_date, user_id="test_student_pacing")
    assert res_on["is_rest_day"] is True
    assert "Joker" in (res_on["rest_day_reason"] or "")
    assert res_on["daily_target_cards"] == 0

    # Toggle OFF
    res_off = toggle_joker_day(test_date, user_id="test_student_pacing")
    assert res_off["is_rest_day"] is False
    assert res_off["daily_target_cards"] > 0


def test_log_daily_progress():
    """Verify logging completed cards updates remaining cards and percentage."""
    test_d = date(2026, 9, 16)
    res = log_progress(
        cards_completed=50,
        minutes_spent=30,
        target_date=test_d,
        source="manual",
        user_id="test_student_pacing",
    )
    assert res["cards_completed_today"] == 50
    assert res["cards_remaining_today"] == max(0, res["daily_target_cards"] - 50)
    assert res["completion_percentage_today"] > 0


def test_pacing_rest_api_endpoints(client):
    """Verify HTTP REST endpoints for exam pacing."""
    # 1. GET Pacing
    resp = client.get("/api/v1/schedule/exam/pacing?target_date=2026-09-14")
    assert resp.status_code == 200
    data = resp.json()
    assert data["calendar_days_to_exam"] == 127
    assert data["total_curriculum_cards"] == 9633

    # 2. POST Log Progress
    log_resp = client.post(
        "/api/v1/schedule/exam/log-progress",
        json={"cards_completed": 60, "minutes_spent": 35, "log_date": "2026-09-14"}
    )
    assert log_resp.status_code == 200
    log_data = log_resp.json()
    assert log_data["cards_completed_today"] == 60

    # 3. POST Toggle Joker Day
    joker_resp = client.post(
        "/api/v1/schedule/exam/toggle-joker",
        json={"date_str": "2026-09-18"}
    )
    assert joker_resp.status_code == 200

    # 4. GET Exams list
    exams_resp = client.get("/api/v1/schedule/exam/list")
    assert exams_resp.status_code == 200
    exams = exams_resp.json()
    assert len(exams) >= 2
    assert any("2027-01-19" in ex["exam_date"] for ex in exams)

    # Cleanup test data for student to keep production DB clean
    from app.db.database import get_db_connection
    with get_db_connection() as conn:
        conn.execute("DELETE FROM daily_progress_logs WHERE user_id = 'student'")
    # Toggle back joker day outside DB transaction lock
    client.post("/api/v1/schedule/exam/toggle-joker", json={"date_str": "2026-09-18"})
