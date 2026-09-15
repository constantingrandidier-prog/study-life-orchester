from datetime import date
from app.services.workload_forecast import get_workload_forecast, cache_workload_forecast, get_cached_workload_forecast
from app.services.anki_backlog_triage import calculate_backlog_triage

def test_workload_forecast_structure():
    forecast = get_workload_forecast(days_ahead=14)
    assert "days" in forecast
    assert "max_day_cards" in forecast
    assert "has_spike" in forecast
    assert "smoothing_advice" in forecast
    assert len(forecast["days"]) == 15  # 0 to 14

def test_workload_forecast_caching():
    dummy = {
        "connected": True,
        "days_ahead": 14,
        "days": [{"total_due": 20}],
        "total_due_14d": 20,
        "max_day_cards": 20,
        "average_daily_due": 20.0,
        "has_spike": False,
        "spike_days": [],
        "smoothing_advice": "Test OK",
    }
    cache_workload_forecast(dummy)
    cached = get_cached_workload_forecast()
    assert cached is not None
    assert cached["smoothing_advice"] == "Test OK"

def test_backlog_triage_advanced_queries():
    triage = calculate_backlog_triage(max_capacity=150)
    assert "topics" in triage
    assert "urgent_combined_anki_query" in triage
    assert "is:due" in triage["urgent_combined_anki_query"]
    assert "budget_combined_anki_query" in triage
    assert "is:due" in triage["budget_combined_anki_query"]

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_api_workload_forecast_endpoint():
    resp = client.get("/api/v1/schedule/anki/workload-forecast")
    assert resp.status_code == 200
    data = resp.json()
    assert "days" in data
    assert "total_due_14d" in data

def test_api_backlog_triage_with_budget():
    resp = client.get("/api/v1/schedule/anki/backlog-triage?max_capacity=100")
    assert resp.status_code == 200
    data = resp.json()
    assert "budget_selected_topics" in data
    assert "budget_combined_anki_query" in data

from app.services.daily_rhythm_service import (
    generate_daily_science_rhythm,
    is_mandatory_practical,
    tag_event_mandatory_status,
)
from app.models import CalendarEvent
from datetime import datetime

def test_mandatory_practical_detection():
    assert is_mandatory_practical("Praktikum klinische Anatomie") is True
    assert is_mandatory_practical("Untersuchungskurs Kardiologie") is True
    assert is_mandatory_practical("Vorlesung Physiologie Blut") is False
    assert is_mandatory_practical("Testat Histologie") is True

    ev = CalendarEvent(
        title="Praktikum Hämatologie",
        start_time=datetime(2026, 9, 15, 14, 0),
        end_time=datetime(2026, 9, 15, 16, 0),
    )
    tagged = tag_event_mandatory_status(ev)
    assert tagged.is_mandatory is True
    assert tagged.badge_color == "#a371f7"
    assert "OBLIGATORISCH" in tagged.badge_label

def test_daily_science_rhythm_starts_at_830():
    rhythm = generate_daily_science_rhythm(target_date=date(2026, 9, 15))
    assert rhythm["start_time"] == "08:30"
    blocks = rhythm["blocks"]
    assert len(blocks) >= 6
    # Block 1 starts at 08:30
    assert blocks[0]["start_time"] == "08:30"
    assert "Morgen-Repetitionen" in blocks[0]["title"]
    # Pause 1 at 09:30
    assert blocks[1]["start_time"] == "09:30"
    assert blocks[1]["is_break"] is True
    # Block 2 (New cards) starts at 09:45
    assert blocks[2]["start_time"] == "09:45"
    assert "100 Neue Karten" in blocks[2]["title"]

def test_api_daily_rhythm_endpoint():
    resp = client.get("/api/v1/schedule/daily-rhythm?target_date=2026-09-15")
    assert resp.status_code == 200
    data = resp.json()
    assert data["start_time"] == "08:30"
    assert "blocks" in data
    assert len(data["blocks"]) >= 6

