"""Comprehensive test suite for UZH Exam Intelligence Pillars 1 through 4:
- Säule 1: Deep Card Inspection & Kprim Trap Detection (card_yield_engine)
- Säule 2: Slide Cross-Matching & Professor Emphasis Cues (slide_cross_matcher)
- Säule 3: Actionable Yield & Student ROI Optimization (actionable_yield_service)
- Säule 4: Live Exam Score Simulation & Angoff 60% Safety Threshold (exam_score_simulator)
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.card_yield_engine import (
    analyze_card_content,
    get_card_yield_stats,
    CONFUSABLE_PAIRS,
    NEGATION_TRIGGERS,
)
from app.services.slide_cross_matcher import (
    get_slide_cross_match_stats,
    build_slide_cross_match_index,
    extract_lecture_metadata,
)
from app.services.actionable_yield_service import (
    calculate_actionable_deck_roi,
    get_ranked_actionable_yield_list,
)
from app.services.exam_score_simulator import (
    compute_exam_simulation,
    get_full_exam_simulation,
    MP1_CONFIG,
    MP2_CONFIG,
)

client = TestClient(app)


# ============================================================================
# SÄULE 1: CARD YIELD ENGINE & KPRIM TRAP DETECTION
# ============================================================================

def test_analyze_card_content_confusable_pair():
    """Verify that confusable pairs (e.g. PFK-1 vs PFK-2) trigger Kprim trap classification."""
    front = "Was ist der Unterschied zwischen PFK-1 und PFK-2?"
    back = "PFK-1 katalysiert Schritt 3 der Glykolyse; PFK-2 synthetisiert F-2,6-BP."
    res = analyze_card_content(front, back)

    assert res["is_kprim_trap"] is True
    assert res["trap_type"] == "confusable_pair"
    assert "Verwechslung" in res["trap_label"]
    assert res["card_yield_score"] >= 80.0


def test_analyze_card_content_directional_regulation():
    """Verify that reciprocal regulation (stimuliert vs hemmt) triggers causal chain trap."""
    front = "Regulation der Glykolyse durch Insulin"
    back = "Insulin stimuliert PFK-1 via F-2,6-BP und hemmt die Fruktose-1,6-Bisphosphatase reziprok."
    res = analyze_card_content(front, back)

    assert res["is_kprim_trap"] is True
    assert res["directional_count"] >= 2
    assert "Regulation" in res["trap_label"] or "Kausalkette" in res["trap_label"]


def test_analyze_card_content_negation_trap():
    """Verify that negation cues (nicht, ausschliesslich, nie) trigger logic trap."""
    front = "Welche Enzyme sind nicht an der Glukoneogenese beteiligt?"
    back = "Hexokinase wird keinesfalls verwendet, ausschliesslich Glukose-6-Phosphatase."
    res = analyze_card_content(front, back)

    assert res["is_kprim_trap"] is True
    assert res["negation_count"] >= 2
    assert "Verneinung" in res["trap_label"] or "Logikfalle" in res["trap_label"]


def test_get_card_yield_stats_completeness():
    """Verify that card inspection returns valid snapshot data with 25 Todesfallen."""
    stats = get_card_yield_stats()
    assert stats["available"] is True
    assert stats["total_cards_scanned"] >= 5000
    assert stats["total_kprim_traps"] >= 100
    assert len(stats["top_25_todesfallen"]) == 25

    # Check structure of the top pitfall card
    top_trap = stats["top_25_todesfallen"][0]
    assert ("front_snippet" in top_trap) or ("front" in top_trap)
    assert ("back_snippet" in top_trap) or ("back" in top_trap)
    assert "trap_warning" in top_trap
    assert ("professor_name" in top_trap) or ("professor" in top_trap)
    assert top_trap["card_yield_score"] >= 80.0


# ============================================================================
# SÄULE 2: SLIDE CROSS-MATCHER & UZH LECTURE SLIDES
# ============================================================================

def test_slide_cross_matcher_stats():
    """Verify that indexed lecture slides are catalogued with themes and emphasis."""
    stats = get_slide_cross_match_stats()
    assert stats["available"] is True
    assert stats["total_slides_indexed"] >= 20
    assert len(stats["cluster_distribution"]) >= 3

    # Check indexed topics include core UZH themes
    topics = list(stats["cluster_distribution"].keys())
    assert any("blut" in t.lower() or "atmung" in t.lower() or "herz" in t.lower() for t in topics)


# ============================================================================
# SÄULE 3: ACTIONABLE YIELD & STUDENT ROI CALCULATION
# ============================================================================

def test_calculate_actionable_deck_roi():
    """Verify student study ROI calculation prioritizing unlearned high-yield decks."""
    # High-yield unlearned deck
    mock_deck_hy = {
        "deck_id": 101,
        "anki_name": "2. SJ - 1 :: TB Stoffwechsel :: Emmert :: 5 Regulation Kohlenhydrat Stoffwechsel",
        "parent_topic": "5. Stoffwechsel",
        "professor_name": "Prof. Dr. med. Emmert",
        "card_count": 80,
        "retention_rate": 55.0,
        "total_reviews": 5,
        "due_count": 30,
        "last_reviewed_days_ago": 8.0,
    }
    res_hy = calculate_actionable_deck_roi(mock_deck_hy, kprim_traps_count=6)
    assert res_hy["yield_level"] == "high"
    assert res_hy["urgency"] == "critical_gap"
    assert res_hy["roi_score"] >= 70.0
    assert "Modulprüfung 2" in res_hy["target_exam"]

    # Safe high-yield deck (already mastered at 92%)
    mock_deck_safe = {
        "deck_id": 102,
        "anki_name": "2. SJ - 1 :: TB Blut/Immunsystem :: Manatschal :: 3 Blutgerinnung",
        "parent_topic": "1. Blut & Immunsystem",
        "professor_name": "Prof. Dr. med. Wenger",
        "card_count": 60,
        "retention_rate": 92.0,
        "total_reviews": 40,
        "due_count": 0,
        "last_reviewed_days_ago": 1.0,
    }
    res_safe = calculate_actionable_deck_roi(mock_deck_safe, kprim_traps_count=2)
    assert res_safe["urgency"] == "mastered"
    assert res_safe["roi_score"] < res_hy["roi_score"]
    assert "Modulprüfung 1" in res_safe["target_exam"]


def test_get_ranked_actionable_yield_list():
    """Verify that get_ranked_actionable_yield_list returns top 10 leverage decks sorted by ROI."""
    ranked = get_ranked_actionable_yield_list()
    assert ranked["available"] is True
    assert ranked["total_decks_evaluated"] > 0
    assert len(ranked["top_10_leverage_decks"]) <= 10

    # Ensure strictly descending order of ROI
    rois = [d["roi_score"] for d in ranked["top_10_leverage_decks"]]
    assert rois == sorted(rois, reverse=True)


# ============================================================================
# SÄULE 4: LIVE EXAM SCORE SIMULATOR & ANGOFF PASS THRESHOLD
# ============================================================================

def test_compute_exam_simulation_structure():
    """Verify simulation calculates predicted score, Angoff cutoff, coverage, and potential scores."""
    mock_decks = [
        {"anki_name": "TB Blut :: Manatschal :: Gerinnung", "parent_topic": "1. Blut", "card_count": 100, "retention_rate": 85.0, "total_reviews": 10},
        {"anki_name": "TB Herz :: Kurtcuoglu :: EKG", "parent_topic": "2. Herz", "card_count": 120, "retention_rate": 75.0, "total_reviews": 15},
        {"anki_name": "TB Atmung :: Wenger :: Hypoxie", "parent_topic": "3. Atmung", "card_count": 90, "retention_rate": 80.0, "total_reviews": 20},
    ]
    sim = compute_exam_simulation(MP1_CONFIG, mock_decks)
    assert sim["exam_name"] == "Modulprüfung 1 (Theorie)"
    assert sim["angoff_cutoff"] == 60.0
    assert sim["safety_target"] == 75.0
    assert sim["coverage_pct"] == 100.0
    assert sim["predicted_score"] > 60.0
    assert sim["potential_score"] > 60.0
    assert sim["safety_margin"] > 0
    assert len(sim["topic_breakdown"]) == 3

    # Test realistic scenario with partially studied curriculum
    partial_decks = [
        {"anki_name": "TB Blut :: Manatschal :: Gerinnung", "parent_topic": "1. Blut", "card_count": 100, "retention_rate": 80.0, "total_reviews": 10},
        {"anki_name": "TB Herz :: Kurtcuoglu :: EKG", "parent_topic": "2. Herz", "card_count": 900, "retention_rate": None, "total_reviews": 0},
    ]
    partial_sim = compute_exam_simulation(MP1_CONFIG, partial_decks)
    assert partial_sim["coverage_pct"] == 10.0
    assert partial_sim["predicted_score"] < 60.0  # realistic: unstudied material is penalized


def test_get_full_exam_simulation():
    """Verify full dual exam simulation covers both MP1 (14 ECTS) and MP2 (16 ECTS)."""
    full_sim = get_full_exam_simulation()
    assert full_sim["available"] is True
    assert "modulpruefung_1" in full_sim
    assert "modulpruefung_2" in full_sim
    assert full_sim["total_ects"] == 30

    mp1 = full_sim["modulpruefung_1"]
    assert mp1["ects"] == 14
    assert mp1["duration_min"] == 150
    assert mp1["predicted_score"] >= 0.0

    mp2 = full_sim["modulpruefung_2"]
    assert mp2["ects"] == 16
    assert mp2["duration_min"] == 150
    assert mp2["predicted_score"] >= 0.0


# ============================================================================
# API INTEGRATION TESTS FOR ALL 4 PILLAR ENDPOINTS
# ============================================================================

def test_api_pillar_endpoints():
    """Test all new FastAPI endpoints for status 200 and schema adherence."""
    # 1. Simulation endpoint
    res_sim = client.get("/api/v1/schedule/exam-intelligence/simulation")
    assert res_sim.status_code == 200
    d_sim = res_sim.json()
    assert d_sim["success"] is True
    assert "modulpruefung_1" in d_sim["simulation"]
    assert "modulpruefung_2" in d_sim["simulation"]

    # 2. Actionable ROI endpoint
    res_roi = client.get("/api/v1/schedule/exam-intelligence/actionable-roi")
    assert res_roi.status_code == 200
    d_roi = res_roi.json()
    assert d_roi["success"] is True
    assert len(d_roi["actionable_roi"]["top_10_leverage_decks"]) > 0

    # 3. Card traps endpoint
    res_traps = client.get("/api/v1/schedule/exam-intelligence/card-traps")
    assert res_traps.status_code == 200
    d_traps = res_traps.json()
    assert d_traps["success"] is True
    assert len(d_traps["card_stats"]["top_25_todesfallen"]) == 25

    # 4. Slides endpoint
    res_slides = client.get("/api/v1/schedule/exam-intelligence/slides")
    assert res_slides.status_code == 200
    d_slides = res_slides.json()
    assert d_slides["success"] is True
    assert d_slides["slides"]["total_slides_indexed"] >= 20
