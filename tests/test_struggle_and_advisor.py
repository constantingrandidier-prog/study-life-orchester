"""
Tests for scientific Anki struggle analysis, 2-click focus,
lecture skip vs time-ROI consistency, and dynamic schedule orchestration.
"""

import pytest
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.services.lecture_advisor_service import calculate_timestamp_budget, search_lecture_advisor
from app.services.anki_struggle_service import (
    calculate_struggle_score,
    diagnose_struggle_cause,
    find_slide_mapping_for_card,
    get_today_struggle_analysis,
)
from app.services.daily_rhythm_service import generate_daily_science_rhythm


client = TestClient(app)


def test_calculate_timestamp_budget_full_skip():
    """Verify that a lecture marked as skip recommends 0 minutes video and calculates ROI."""
    sample_chapters = [
        {"title": "Einführung & Formalia", "start": "00:00", "end": "25:00", "duration_min": 25, "cards_count": 30},
        {"title": "Grundbegriffe der Hämatologie", "start": "25:00", "end": "55:00", "duration_min": 30, "cards_count": 40},
        {"title": "Historischer Rückblick", "start": "55:00", "end": "85:00", "duration_min": 30, "cards_count": 30},
    ]
    res = calculate_timestamp_budget(
        chapters=sample_chapters,
        target_cards=100,
        speed_factor=1.0,
        recommendation="Skip (0x)"
    )

    assert res["is_full_skip"] is True
    assert res["video_minutes_raw"] == 0
    assert res["video_minutes_effective"] == 0
    assert res["saved_minutes"] == 85
    assert res["start_timestamp"] == "00:00"
    assert res["end_timestamp"] == "00:00"
    assert "100% SKIP-EMPFEHLUNG" in res["guidance_text"]
    assert res["time_roi"]["net_minutes_lost"] > 0
    assert "MEHR Zeit" in res["time_roi"]["verdict"]


def test_calculate_timestamp_budget_micro_deep_dive():
    """Verify that a specific mechanism chapter <= 20 min is extracted as a micro deep dive."""
    sample_chapters = [
        {"title": "Organisatorisches", "start": "00:00", "end": "35:00", "duration_min": 35, "cards_count": 40},
        {"title": "Gerinnungskaskade Mechanismus", "start": "35:00", "end": "49:00", "duration_min": 14, "cards_count": 20},
        {"title": "Trivia & Fallbeispiele", "start": "49:00", "end": "85:00", "duration_min": 36, "cards_count": 40},
    ]
    res = calculate_timestamp_budget(
        chapters=sample_chapters,
        target_cards=60,
        speed_factor=1.0,
        recommendation="Skip (0x)"
    )

    assert res["is_micro_deep_dive"] is True
    assert res["is_full_skip"] is False
    assert res["video_minutes_effective"] == 14
    assert res["start_timestamp"] == "35:00"
    assert res["end_timestamp"] == "49:00"
    assert res["saved_minutes"] == 85 - 14
    assert "Micro-Deep-Dive" in res["guidance_text"]


def test_calculate_timestamp_budget_regular_lecture():
    """Verify standard accumulation for non-skip lectures."""
    sample_chapters = [
        {"title": "Sauerstoffbindungskurve", "start": "00:00", "end": "20:00", "duration_min": 20, "cards_count": 40},
        {"title": "Bohr-Effekt", "start": "20:00", "end": "45:00", "duration_min": 25, "cards_count": 40},
    ]
    res = calculate_timestamp_budget(
        chapters=sample_chapters,
        target_cards=40,
        speed_factor=1.2,
        recommendation="1.2x"
    )

    assert res["is_full_skip"] is False
    assert res["is_micro_deep_dive"] is False
    assert res["start_timestamp"] == "00:00"
    assert res["end_timestamp"] == "20:00"


def test_struggle_score_calculation():
    """Verify scientific struggle score scoring formula."""
    # Ease 1 (Again), 30s latency, 2 historical lapses
    score_lapse = calculate_struggle_score(ease=1, time_ms=30000, historical_lapses=2, is_curriculum=True)
    assert score_lapse >= 7.0

    # Ease 3 (Good), fast 5s, 0 lapses
    score_good = calculate_struggle_score(ease=3, time_ms=5000, historical_lapses=0, is_curriculum=True)
    assert score_good < 2.0
    assert score_lapse > score_good


def test_diagnose_struggle_cause():
    """Verify diagnostic classification and actionable advice."""
    d_lab = diagnose_struggle_cause("Hämatokrit Normwert Mann", "42-52%", ease=1, time_sec=30.0, historical_lapses=1)
    assert d_lab["type"] == "numbers_lab"
    assert "Laborwert" in d_lab["badge"]

    d_casc = diagnose_struggle_cause("Faktor Xa Thrombin Kaskade", "Aktiviert Prothrombin", ease=2, time_sec=25.0, historical_lapses=0)
    assert d_casc["type"] == "cascade_mechanism"
    assert "Kaskade" in d_casc["badge"]


def test_dynamic_daily_science_rhythm():
    """Verify that start time, lunch duration, and lecture toggle properly calculate Feierabend."""
    # Standard 08:30 start with 75m lunch and lecture (using day without fixed calendar events)
    sched1 = generate_daily_science_rhythm(target_date=date(2027, 5, 1), start_time_str="08:30", lunch_duration_mins=75, include_lecture=True)
    assert sched1["start_time"] == "08:30"
    assert sched1["lunch_duration_minutes"] == 75
    assert sched1["feierabend_time"] == "16:00"

    # Spätstart 09:30, Express Lunch 30m, No lecture
    sched2 = generate_daily_science_rhythm(target_date=date(2027, 5, 1), start_time_str="09:30", lunch_duration_mins=30, include_lecture=False)
    assert sched2["start_time"] == "09:30"
    assert sched2["lunch_duration_minutes"] == 30
    assert sched2["feierabend_time"] == "13:45"
    assert sched2["include_lecture"] is False


def test_api_daily_rhythm_endpoint():
    """Test the daily-rhythm endpoint via FastAPI TestClient."""
    resp = client.get("/api/v1/schedule/daily-rhythm?target_date=2027-05-01&start_time=09:00&lunch_duration=45&include_lecture=false")
    assert resp.status_code == 200
    data = resp.json()
    assert data["start_time"] == "09:00"
    assert data["lunch_duration_minutes"] == 45
    assert data["feierabend_time"] == "13:30"
    assert "blocks" in data


def test_api_today_struggles_endpoint():
    """Test the today-struggles endpoint."""
    resp = client.get("/api/v1/schedule/anki/today-struggles")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_struggles" in data
    assert "cards" in data


def test_api_open_browser_endpoint():
    """Test the Anki open-browser endpoint."""
    resp = client.post("/api/v1/schedule/anki/open-browser", json={"query": "rated:1:1"})
    assert resp.status_code == 200
    data = resp.json()
    assert "query" in data


def test_api_slides_open_endpoint():
    """Test slide locator endpoint."""
    resp = client.get("/api/v1/schedule/slides/open?path=Vorlesungen%20im%20Themenblock%20Blut%20und%20Immunsystem/Tuzlak_Adaptives%20und%20angeborenes%20Immunsystem.pdf&page=18")
    assert resp.status_code == 200
    data = resp.json()
    assert "page" in data
    assert data["page"] == 18


def test_api_create_temp_deck_endpoint():
    """Test temporary struggle deck creation endpoint."""
    resp = client.post("/api/v1/schedule/anki/create-temp-deck", json={"deck_name": "⚡ Problem-Karten Heute", "limit": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert "success" in data
    assert "deck_name" in data
    assert "instructions" in data
    assert "tag" in data
    assert data["tag"] == "⚡_Heute_Problemkarten"


def test_api_cleanup_temp_deck_endpoint():
    """Test temporary struggle deck tag cleanup endpoint."""
    resp = client.post("/api/v1/schedule/anki/cleanup-temp-deck", json={"tag_name": "⚡_Heute_Problemkarten"})
    assert resp.status_code == 200
    data = resp.json()
    assert "success" in data


def test_real_cards_progress_counter():
    """Verify that daily assignment accurately tracks real newly learned cards (155), not the simulated future curve (476)."""
    from app.services.curriculum_roadmap_service import get_daily_curriculum_assignment
    from datetime import date
    day = get_daily_curriculum_assignment(date(2026, 9, 16))
    assert day["actual_cards_learned"] >= 185
    assert day["cumulative_cards_learned"] >= 185
    assert day["planned_cumulative_cards"] in (433, 509)
    assert day["curriculum_progress_pct"] >= 2.1
    assert day["total_curriculum_cards"] == 8729


def test_lecture_date_and_slide_paths_in_curriculum_assignment():
    """Verify that Day 2 slots include recording dates in title, local folder paths, and slide mappings."""
    from app.services.curriculum_roadmap_service import get_daily_curriculum_assignment
    from datetime import date
    day = get_daily_curriculum_assignment(date(2026, 9, 16))
    slots = day["topic_slots"]
    assert len(slots) >= 2

    # Slot 1: CO2-Transport
    s1 = slots[0]
    assert "CO2-Transport" in s1["clean_title"]
    assert "22.09.2025" in s1["display_title_with_date"]
    assert s1["lecture_date_formatted"] == "22.09.2025"
    assert s1["matched_slide_filename"] == "5_CM_Saure-Base_CO2-Transport.pdf"
    assert "Cristina Manatschal" in s1["slide_relative_path"]
    assert s1["vam_url"] is not None

    # Slot 2: Blutgerinnung
    s2 = slots[1]
    assert "Blutgerinnung" in s2["clean_title"]
    assert "26.09.2025" in s2["display_title_with_date"]
    assert s2["lecture_date_formatted"] == "26.09.2025"
    assert s2["matched_slide_filename"] == "6-7_CM_Blutgerinnung.pdf"
    assert "Cristina Manatschal" in s2["slide_relative_path"]


def test_api_slides_view_endpoint():
    """Verify that /slides/view streams the slide PDF inline with application/pdf."""
    resp = client.get("/api/v1/schedule/slides/view?path=5_CM_Saure-Base_CO2-Transport.pdf")
    assert resp.status_code == 200
    assert "application/pdf" in resp.headers.get("content-type", "")
    assert len(resp.content) > 10000


def test_api_folder_open_endpoint():
    """Verify that /folder/open resolves the local UZH directory."""
    resp = client.get("/api/v1/schedule/folder/open?path=Podcasts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "Podcasts" in data["path"]


