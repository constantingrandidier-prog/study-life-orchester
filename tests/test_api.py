"""Integration tests for FastAPI endpoints."""

from fastapi.testclient import TestClient
from app.data.dummy_schedule import (
    DEFAULT_DUMMY_DATE,
    get_dummy_gcal_items,
    get_dummy_ics_string,
)
from app.main import app

client = TestClient(app)


def test_health_check():
    """Verify health endpoint returns 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_root_endpoint():
    """Verify root discovery endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "online"


def test_get_dummy_schedule():
    """Verify the dummy university schedule endpoint."""
    response = client.get("/api/v1/schedule/dummy")
    assert response.status_code == 200
    data = response.json()

    assert data["date"] == DEFAULT_DUMMY_DATE.isoformat()
    assert len(data["fixed_events"]) == 5
    assert len(data["free_slots"]) == 5
    assert data["summary"]["total_window_minutes"] == 960
    assert data["summary"]["total_free_minutes"] == 495
    assert data["summary"]["total_busy_minutes"] == 465

    # Check that each free slot has start, end, and duration_minutes
    for slot in data["free_slots"]:
        assert "start" in slot
        assert "end" in slot
        assert "duration_minutes" in slot
        assert slot["duration_minutes"] > 0


def test_get_raw_dummy_fixtures():
    """Verify raw fixtures endpoint."""
    response = client.get("/api/v1/schedule/dummy/raw")
    assert response.status_code == 200
    data = response.json()
    assert "google_calendar_items" in data
    assert "ical_string" in data
    assert len(data["google_calendar_items"]) == 5


def test_post_from_events():
    """Verify /from-events endpoint."""
    payload = {
        "target_date": "2026-09-14",
        "day_start_hour": 8,
        "day_end_hour": 18,
        "events": [
            {
                "title": "Math Lecture",
                "start": "2026-09-14T09:00:00",
                "end": "2026-09-14T11:00:00",
            },
            {
                "title": "Physics Seminar",
                "start": "2026-09-14T14:00:00",
                "end": "2026-09-14T16:00:00",
            }
        ]
    }
    response = client.post("/api/v1/schedule/from-events", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["fixed_events"]) == 2
    # Slots: 08:00-09:00 (60m), 11:00-14:00 (180m), 16:00-18:00 (120m)
    assert len(data["free_slots"]) == 3
    assert [s["duration_minutes"] for s in data["free_slots"]] == [60, 180, 120]


def test_post_from_gcal():
    """Verify /from-gcal endpoint using dummy google calendar items."""
    gcal_items = get_dummy_gcal_items(DEFAULT_DUMMY_DATE)
    payload = {
        "target_date": DEFAULT_DUMMY_DATE.isoformat(),
        "day_start_hour": 7,
        "day_end_hour": 23,
        "items": gcal_items
    }
    response = client.post("/api/v1/schedule/from-gcal", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["fixed_events"]) == 5
    assert len(data["free_slots"]) == 5


def test_post_from_ical():
    """Verify /from-ical endpoint using dummy ical string."""
    ics_str = get_dummy_ics_string(DEFAULT_DUMMY_DATE)
    payload = {
        "target_date": DEFAULT_DUMMY_DATE.isoformat(),
        "day_start_hour": 7,
        "day_end_hour": 23,
        "ics_content": ics_str
    }
    response = client.post("/api/v1/schedule/from-ical", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["fixed_events"]) == 5
    assert len(data["free_slots"]) == 5


def test_invalid_hours_returns_400():
    """Providing start_hour >= end_hour should return 400 Bad Request."""
    response = client.get("/api/v1/schedule/dummy?day_start_hour=18&day_end_hour=10")
    assert response.status_code == 400


def test_get_efficiency_analytics_endpoint():
    """Verify the lecture ROI & efficiency analytics endpoint."""
    response = client.get("/api/v1/schedule/analytics/efficiency")
    assert response.status_code == 200
    data = response.json()
    assert "overall_summary" in data
    assert "modules" in data
    assert len(data["modules"]) > 0


def test_post_study_log_endpoint():
    """Verify logging a study session through the API."""
    payload = {
        "topic_name": "Informatik I - Sortieralgorithmen",
        "module_name": "Informatik I",
        "duration_minutes": 25,
        "cards_reviewed": 75,
        "seconds_per_card": 20.0,
        "retention_rate": 0.90,
        "lecture_attended": True,
    }
    response = client.post("/api/v1/schedule/study/log", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "log_id" in data


def test_get_profile_endpoint():
    """Verify user profile endpoint returns settings."""
    response = client.get("/api/v1/schedule/profile")
    assert response.status_code == 200
    data = response.json()
    assert "username" in data
    assert "study_program" in data


def test_sync_calendar_url_validation():
    """Verify sync-url endpoint validates empty URL properly."""
    response = client.post("/api/v1/schedule/sync-url", json={"url": ""})
    assert response.status_code == 400


