"""Unit and integration tests for UZH Exam Intelligence & Professor Knowledge Base."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.uzh_exam_intelligence import (
    UZH_PROFESSORS,
    UZH_EXAM_REGULATIONS,
    match_professor_for_topic,
    calculate_uzh_exam_risk_score,
)
from app.services.anki_deck_stats import get_detailed_deck_stats

client = TestClient(app)


def test_professor_dossiers_completeness():
    """Verify that all major UZH professors are defined with complete exam attributes."""
    assert len(UZH_PROFESSORS) >= 12
    required_keys = [
        "name", "title", "institute", "research_focus", "primary_topics",
        "keywords", "exam_style", "high_yield_pearl", "kprim_trap", "uzh_importance"
    ]
    for prof_id, prof in UZH_PROFESSORS.items():
        for k in required_keys:
            assert k in prof, f"Missing key {k} in professor {prof_id}"
            assert prof[k], f"Empty value for {k} in professor {prof_id}"


def test_match_professor_for_topics():
    """Verify accurate matching of medical curriculum topics to responsible professors."""
    # Wenger -> Hypoxie, EPO, Respiration
    p_wenger = match_professor_for_topic("Hypoxie und Höhenanpassung", "Sauerstofftransport", "3. Atmung & Lunge")
    assert p_wenger is not None
    assert "Wenger" in p_wenger["name"]

    # Wagner -> Astrup, Säure-Base
    p_wagner = match_professor_for_topic("Astrup Blutgasanalyse", "Säure-Basen-Status", "1. Blut & Immunsystem")
    assert p_wagner is not None
    assert "Wagner" in p_wagner["name"]

    # Tuzlak -> Immuntoleranz
    p_tuzlak = match_professor_for_topic("Tuzlak :: Immuntoleranz", "Immunsystem", "1. Blut & Immunsystem")
    assert p_tuzlak is not None
    assert "Tuzlak" in p_tuzlak["name"]

    # Manatschal -> Blutgerinnung
    p_manatschal = match_professor_for_topic("Blutgerinnung und Hämostase", "Gerinnungskaskade", "1. Blut & Immunsystem")
    assert p_manatschal is not None
    assert "Manatschal" in p_manatschal["name"]

    # Sommer -> Herzentwicklung
    p_sommer = match_professor_for_topic("Herz- und Gefässentwicklung", "Sommer Embryologie", "2. Herz-Kreislauf")
    assert p_sommer is not None
    assert "Sommer" in p_sommer["name"]

    # Sokolowska -> Steroidhormone / AGS
    p_sokolowska = match_professor_for_topic("Steroidhormone der Nebennierenrinde", "Katecholamine", "6. Endokrinologie")
    assert p_sokolowska is not None
    assert "Sokolowska" in p_sokolowska["name"]

    # Emmert -> Kohlenhydratstoffwechsel
    p_emmert = match_professor_for_topic("Regulation des KH Stw", "Insulin und Glukagon", "5. Stoffwechsel")
    assert p_emmert is not None
    assert "Emmert" in p_emmert["name"]


def test_calculate_uzh_exam_risk_score():
    """Verify evidence-based exam risk calculation."""
    # Critical risk: High-yield deck with low retention (50%) and high card count
    crit = calculate_uzh_exam_risk_score(retention_rate=50.0, card_count=150, is_high_yield=True, last_reviewed_days_ago=10.0)
    assert crit["risk_level"] == "critical"
    assert crit["risk_score"] >= 40.0
    assert "Kprim" in crit["risk_label"]

    # Warning risk: High-yield deck with moderate retention (72%)
    warn = calculate_uzh_exam_risk_score(retention_rate=72.0, card_count=100, is_high_yield=True, last_reviewed_days_ago=3.0)
    assert warn["risk_level"] == "warning"
    assert 15.0 <= warn["risk_score"] < 40.0

    # Safe: Solid retention (88%)
    safe = calculate_uzh_exam_risk_score(retention_rate=88.0, card_count=100, is_high_yield=True, last_reviewed_days_ago=1.0)
    assert safe["risk_level"] == "safe"
    assert safe["risk_score"] < 15.0


def test_api_exam_intelligence_endpoints():
    """Verify that the FastAPI endpoints return valid JSON structures."""
    # 1. Professors
    res_prof = client.get("/api/v1/schedule/exam-intelligence/professors")
    assert res_prof.status_code == 200
    data_prof = res_prof.json()
    assert data_prof["success"] is True
    assert "roland_wenger" in data_prof["professors"]
    assert "carsten_wagner" in data_prof["professors"]

    # 2. Regulations
    res_reg = client.get("/api/v1/schedule/exam-intelligence/regulations")
    assert res_reg.status_code == 200
    data_reg = res_reg.json()
    assert data_reg["success"] is True
    assert len(data_reg["regulations"]["written_exams"]) == 2
    assert data_reg["regulations"]["written_exams"][0]["name"] == "Modulprüfung 1"
    assert data_reg["regulations"]["written_exams"][1]["name"] == "Modulprüfung 2"


def test_deck_stats_has_exam_intelligence():
    """Verify that get_detailed_deck_stats returns decks enriched with professor and risk data."""
    stats = get_detailed_deck_stats()
    all_decks = stats.get("all_decks", [])
    assert len(all_decks) > 0

    first_deck = all_decks[0]
    assert "professor_name" in first_deck
    assert "professor_institute" in first_deck
    assert "exam_risk_score" in first_deck
    assert "exam_risk_level" in first_deck
    assert "exam_risk_label" in first_deck
