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
