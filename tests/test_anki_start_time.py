import pytest
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.services.daily_rhythm_service import generate_daily_science_rhythm

client = TestClient(app)

def test_daily_science_rhythm_defaults_to_830():
    """Verify that future dates ignore anki_first_review_time and use start_time_str."""
    sched = generate_daily_science_rhythm(
        target_date=date(2027, 5, 1),
        start_time_str="08:30",
        anki_first_review_time="07:45"
    )
    # For a future date, anki_first_review_time is NOT used (only today/past are auto-adopted)
    assert sched["start_time"] == "08:30"
    assert sched["anki_first_review_time"] == "07:45"
    assert sched["used_anki_start"] is False
    assert sched["blocks"][0]["start_time"] == "08:30"

def test_manual_start_overrides_anki_auto():
    """Verify that is_manual_start=True forces the given start_time even when Anki reviews exist."""
    from datetime import date, timedelta
    # Use yesterday (past date that has reviews) – but supply manual override
    yesterday = date.today() - timedelta(days=1)
    sched = generate_daily_science_rhythm(
        target_date=yesterday,
        start_time_str="09:00",
        anki_first_review_time="08:44",
        is_manual_start=True,
    )
    assert sched["start_time"] == "09:00", f"Expected 09:00 but got {sched['start_time']}"
    assert sched["used_anki_start"] is False

def test_future_days_have_full_repetition_time_scheduled():
    """Verify that future days allocate full repetition time and are NOT marked completed."""
    sched = generate_daily_science_rhythm(
        target_date=date(2027, 5, 1),
        cards_due_today=222,
        start_time_str="08:30",
    )
    b0 = sched["blocks"][0]
    assert b0["is_completed"] is False
    assert b0["duration_minutes"] >= 90
    assert "222 Karten" in b0["title"]
    assert b0["start_time"] == "08:30"

def test_api_daily_rhythm_includes_anki_start_fields():
    """Verify that today auto-adopts Anki start time, while a future day keeps 08:30 placeholder."""
    resp = client.get("/api/v1/schedule/daily-rhythm?target_date=2026-09-23")
    assert resp.status_code == 200
    data = resp.json()
    assert "anki_first_review_time" in data
    # 2026-09-23 had reviews at 13:25, so start_time should be 13:25
    if data.get("anki_first_review_time"):
        assert data["start_time"] == data["anki_first_review_time"]
        assert data["used_anki_start"] is True

    # Future day has no reviews yet, so it defaults to the 08:30 temporary placeholder
    resp_future = client.get("/api/v1/schedule/daily-rhythm?target_date=2027-05-01")
    assert resp_future.status_code == 200
    data_future = resp_future.json()
    assert data_future["start_time"] == "08:30"
    assert data_future["used_anki_start"] is False
