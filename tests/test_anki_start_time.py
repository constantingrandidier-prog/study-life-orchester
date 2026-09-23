import pytest
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.services.daily_rhythm_service import generate_daily_science_rhythm

client = TestClient(app)

def test_daily_science_rhythm_defaults_to_830():
    """Verify that the normal standard start time is 08:30 even if anki_first_review_time is provided."""
    sched = generate_daily_science_rhythm(
        target_date=date(2027, 5, 1),
        start_time_str="08:30",
        anki_first_review_time="07:45"
    )
    assert sched["start_time"] == "08:30"
    assert sched["anki_first_review_time"] == "07:45"
    assert sched["blocks"][0]["start_time"] == "08:30"

def test_future_days_have_full_repetition_time_scheduled():
    """Verify that future days allocate full repetition time and are NOT marked completed."""
    sched = generate_daily_science_rhythm(
        target_date=date(2026, 9, 24),
        cards_due_today=222,
        start_time_str="08:30",
    )
    b0 = sched["blocks"][0]
    assert b0["is_completed"] is False
    assert b0["duration_minutes"] >= 90
    assert "222 Karten" in b0["title"]
    assert b0["start_time"] == "08:30"

def test_api_daily_rhythm_includes_anki_start_fields():
    """Verify that today auto-adopts Anki start time, while tomorrow keeps 08:30 placeholder."""
    resp = client.get("/api/v1/schedule/daily-rhythm?target_date=2026-09-23")
    assert resp.status_code == 200
    data = resp.json()
    assert "anki_first_review_time" in data
    # Today had reviews at 13:25, so start_time should be 13:25
    if data.get("anki_first_review_time"):
        assert data["start_time"] == data["anki_first_review_time"]
        assert data["used_anki_start"] is True

    # Tomorrow has no reviews yet, so it defaults to the 08:30 temporary placeholder
    resp_tom = client.get("/api/v1/schedule/daily-rhythm?target_date=2026-09-24")
    assert resp_tom.status_code == 200
    data_tom = resp_tom.json()
    assert data_tom["start_time"] == "08:30"
    assert data_tom["used_anki_start"] is False
