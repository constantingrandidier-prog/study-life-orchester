"""Tests for Phase 2: Lecture Decision Ampel, Speed Simulator, Anki Weakness Analysis, and OLAT Connector."""

from datetime import date
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.lecture_decision_service import (
    calculate_mode_time_savings,
    evaluate_lecture_value,
    set_event_consumption_mode,
)
from app.services.anki_weakness_service import get_anki_due_and_weaknesses
from app.services.progress_stats_service import get_progress_comparison_stats
from app.services.olat_connector import check_olat_connectivity, evaluate_slide_against_anki
from app.db import repository


@pytest.fixture
def client():
    return TestClient(app)


def test_evaluate_lecture_ampel():
    """Verify lecture recommendation ampel logic for medical subjects."""
    # 1. Mandatory Clinical Anatomy Practice -> Attend (Presenzpflicht)
    anat = evaluate_lecture_value(
        title="Praktikum klinische Anatomie",
        module_name="Anatomie",
        duration_minutes=90,
    )
    assert anat["recommendation"] == "attend"
    assert "OBLIGATORISCH" in anat["badge_label"]
    assert anat["badge_color"] == "#a371f7"
    assert "Praktikum" in anat["reason"]

    # 1b. High Anki Failure Rate Lecture -> Stream 1.5x Focus
    weak = evaluate_lecture_value(
        title="Vorlesung Klinische Anatomie",
        module_name="Anatomie",
        duration_minutes=90,
        anki_fail_rate=52.0,
    )
    assert weak["recommendation"] == "stream"
    assert weak["recommended_mode"] == "stream_1_5"
    assert "1.5x Focus Stream" in weak["badge_label"]
    assert "Fehlerquote" in weak["reason"]

    # 2. Myelopoiese (Factual cell lineages) -> Skip / Anki
    myelo = evaluate_lecture_value(
        title="Myelopoiese und Erythropoiese",
        module_name="Blut/Immunsystem",
        duration_minutes=45,
    )
    assert myelo["recommendation"] == "skip"
    assert "Skippen" in myelo["badge_label"]
    assert myelo["badge_color"] == "#f85149"

    # 3. Overview Introduction -> 2.0x Stream
    intro = evaluate_lecture_value(
        title="Einführung TB Blut/Immunsystem",
        module_name="Blut/Immunsystem",
        duration_minutes=45,
    )
    assert intro["recommendation"] == "stream"
    assert intro["recommended_mode"] == "stream_2_0"
    assert "2.0x High-Speed Stream" in intro["badge_label"]

    # 4. Complex Physiology Killer Concept -> 1.5x Focus Stream
    wiggers = evaluate_lecture_value(
        title="Herzmechanik und Wiggers-Diagramm",
        module_name="Herz/Kreislauf",
        duration_minutes=90,
    )
    assert wiggers["recommendation"] == "stream"
    assert wiggers["recommended_mode"] == "stream_1_5"
    assert "1.5x Focus Stream" in wiggers["badge_label"]


def test_calculate_mode_time_savings():
    """Verify exact time calculation and savings across playback speeds."""
    # Live: 90 spent, 0 saved
    res_live = calculate_mode_time_savings(90, "live")
    assert res_live["duration_minutes"] == 90
    assert res_live["time_saved_minutes"] == 0

    # 1.5x: 60 spent, 30 saved
    res_1_5 = calculate_mode_time_savings(90, "stream_1_5")
    assert res_1_5["duration_minutes"] == 60
    assert res_1_5["time_saved_minutes"] == 30

    # 2.0x: 45 spent, 45 saved
    res_2_0 = calculate_mode_time_savings(90, "stream_2_0")
    assert res_2_0["duration_minutes"] == 45
    assert res_2_0["time_saved_minutes"] == 45

    # Skipped: 0 spent, 90 saved
    res_skip = calculate_mode_time_savings(90, "skipped")
    assert res_skip["duration_minutes"] == 0
    assert res_skip["time_saved_minutes"] == 90


def test_anki_weakness_service():
    """Verify local Anki due reviews and topic weakness detection."""
    data = get_anki_due_and_weaknesses()
    assert data["available"] is True
    assert data["due_reviews_count"] >= 0
    assert len(data["all_topics"]) >= 2

    # Check that weakness topics or topics are detected
    assert "weakness_topics" in data


def test_progress_comparison_stats():
    """Verify daily comparison and streak computation."""
    stats = get_progress_comparison_stats(target_date=date(2026, 9, 14))
    assert "cards_today" in stats
    assert "cards_yesterday" in stats
    assert "diff_label" in stats
    assert stats["current_streak_days"] >= 0


def test_olat_connectivity():
    """Verify connection probe to UZH OpenOLAT."""
    olat = check_olat_connectivity()
    assert olat["platform"] == "UZH OpenOLAT"
    assert olat["online"] is True
    assert "webdav" in olat["webdav_url"]


def test_phase2_rest_api_endpoints(client):
    """Verify REST endpoints for lecture modes, weaknesses, comparisons, and OLAT."""
    # 1. GET Anki Weaknesses
    resp_weak = client.get("/api/v1/schedule/anki/weaknesses")
    assert resp_weak.status_code == 200
    assert resp_weak.json()["due_reviews_count"] >= 0

    # 2. GET Stats Comparison
    resp_stats = client.get("/api/v1/schedule/stats/comparison?target_date=2026-09-14")
    assert resp_stats.status_code == 200
    assert "diff_label" in resp_stats.json()

    # 3. GET OLAT status
    resp_olat = client.get("/api/v1/schedule/olat/status")
    assert resp_olat.status_code == 200
    assert resp_olat.json()["online"] is True

    # 4. POST Lecture Mode
    # Seed an event first
    events = repository.get_saved_events(date(2026, 9, 14))
    if events:
        ev_id = events[0]["id"]
        resp_mode = client.post(
            "/api/v1/schedule/lecture/mode",
            json={"event_id": ev_id, "mode": "stream_1_5"}
        )
        assert resp_mode.status_code == 200
        data = resp_mode.json()
        assert data["consumption_mode"] == "stream_1_5"
        assert data["time_saved_minutes"] > 0
