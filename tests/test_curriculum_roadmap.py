"""Tests for didactic curriculum roadmap and daily 100-card Anki assignment engine."""

from datetime import date
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.curriculum_roadmap_service import (
    generate_curriculum_roadmap,
    get_daily_curriculum_assignment,
    get_all_curriculum_decks,
)

client = TestClient(app)


def test_get_all_curriculum_decks():
    """Verify all 111 decks are classified into the 6 medical modules."""
    decks = get_all_curriculum_decks()
    assert len(decks) >= 50
    total_cards = sum(d["card_count"] for d in decks)
    assert total_cards >= 8000

    # Ensure module ordering exists
    modules_present = {d["module_name"] for d in decks}
    assert "1. Blut & Immunsystem" in modules_present
    assert "2. Herz-Kreislauf" in modules_present
    assert "3. Atmung & Lunge" in modules_present
    assert "4. Verdauung & Ernährung" in modules_present
    assert "5. Stoffwechsel & Biochemie" in modules_present
    assert "6. Endokrinologie & Hormone" in modules_present


def test_curriculum_roadmap_generation():
    """Test full semester roadmap schedule generation and revision buffer."""
    roadmap = generate_curriculum_roadmap()

    assert roadmap["start_date"] == "2026-09-14"
    assert roadmap["exam_date"] == "2027-01-19"
    assert roadmap["total_active_days"] > 80
    assert roadmap["daily_quota"] == 100
    assert roadmap["revision_buffer_days"] >= 14
    assert len(roadmap["modules"]) == 6

    # Verify active days have exactly 100 cards and Sundays are rest days
    schedule = roadmap["schedule"]
    assert len(schedule) > 90

    for day in schedule:
        if day["is_rest_day"]:
            assert day["target_cards"] == 0
            assert day["day_of_week"] == "Sonntag"
            assert len(day["topic_slots"]) == 0
        else:
            assert len(day["topic_slots"]) >= 1
            day_total = sum(s["cards_to_learn"] for s in day["topic_slots"])
            assert day["target_cards"] == day_total
            if day["day_number"] < roadmap["total_active_days"]:
                assert day_total == 100
            else:
                assert day_total > 0 and day_total <= 100


def test_daily_curriculum_assignment_day_one():
    """Verify Day 1 (2026-09-14) gives exactly 100 cards in Module 1."""
    assignment = get_daily_curriculum_assignment(target_date=date(2026, 9, 14))

    assert assignment["date"] == "2026-09-14"
    assert assignment["day_of_week"] == "Montag"
    assert assignment["day_number"] == 1
    assert not assignment["is_rest_day"]
    assert assignment["target_cards"] == 100
    assert len(assignment["topic_slots"]) >= 1
    assert sum(s["cards_to_learn"] for s in assignment["topic_slots"]) == 100
    assert "Blut" in assignment["current_module"]
    assert assignment["cumulative_cards_learned"] == 100


def test_daily_curriculum_assignment_sunday_rest():
    """Verify Sunday (2026-09-20) is a designated rest day."""
    assignment = get_daily_curriculum_assignment(target_date=date(2026, 9, 20))

    assert assignment["date"] == "2026-09-20"
    assert assignment["day_of_week"] == "Sonntag"
    assert assignment["is_rest_day"] is True
    assert assignment["target_cards"] == 0
    assert "Ruhetag" in assignment["summary"]


def test_daily_curriculum_assignment_post_completion():
    """Verify dates after semester completion transition into revision phase."""
    assignment = get_daily_curriculum_assignment(target_date=date(2027, 1, 10))

    assert assignment["date"] == "2027-01-10"
    assert assignment["curriculum_progress_pct"] == 100.0
    assert "Revisionsphase" in assignment["current_module"]


def test_api_curriculum_today():
    """Verify /api/v1/schedule/curriculum/today endpoint returns valid daily assignment."""
    res = client.get("/api/v1/schedule/curriculum/today?target_date=2026-09-14")
    assert res.status_code == 200
    data = res.json()

    assert data["date"] == "2026-09-14"
    assert data["day_number"] == 1
    assert data["target_cards"] == 100
    assert len(data["topic_slots"]) >= 1
    assert "short_title" in data["topic_slots"][0]
    assert "cards_to_learn" in data["topic_slots"][0]


def test_api_curriculum_roadmap():
    """Verify /api/v1/schedule/curriculum/roadmap endpoint returns entire semester plan."""
    res = client.get("/api/v1/schedule/curriculum/roadmap")
    assert res.status_code == 200
    data = res.json()

    assert data["start_date"] == "2026-09-14"
    assert data["exam_date"] == "2027-01-19"
    assert len(data["modules"]) == 6
    assert len(data["schedule"]) > 90


def test_clean_topic_display():
    """Verify raw Anki hierarchy strings are cleanly converted to titles, lecturer, and breadcrumbs."""
    from app.services.curriculum_roadmap_service import clean_topic_display

    raw1 = "2. SJ :: 3. Semester :: Blut / Immunsystem :: 2 Manatschal :: 1 Hämoglobin"
    clean1 = clean_topic_display(raw1, "1. Blut & Immunsystem")
    assert clean1["clean_title"] == "Hämoglobin"
    assert clean1["lecturer"] == "Manatschal"
    assert clean1["breadcrumb"] == "Blut & Immunsystem › Manatschal"

    raw2 = "2. SJ :: 02 Herz-Kreislauf :: Sommer :: 01 Herzmechanik & Klappen"
    clean2 = clean_topic_display(raw2, "2. Herz-Kreislauf")
    assert clean2["clean_title"] == "Herzmechanik & Klappen"
    assert clean2["lecturer"] == "Sommer"
    assert clean2["breadcrumb"] == "Herz-Kreislauf › Sommer"

    raw3 = "2. SJ :: 04 Verdauung :: Magenphysiologie"
    clean3 = clean_topic_display(raw3, "4. Verdauung & Ernährung")
    assert clean3["clean_title"] == "Magenphysiologie"
    assert clean3["lecturer"] is None
    assert clean3["breadcrumb"] == "Verdauung & Ernährung"


def test_dynamic_daily_quota_surplus(monkeypatch):
    """Verify surplus on day N deducts exactly half of surplus from day N+1 target."""
    from app.services.curriculum_roadmap_service import calculate_dynamic_daily_quota
    from app.db import repository

    # Mock yesterday's log: target was 100, completed 140 (surplus = 40)
    fake_logs = [
        {"date": "2026-09-14", "cards_target": 100, "cards_completed": 140}
    ]
    monkeypatch.setattr(repository, "get_daily_progress_logs", lambda user_id: fake_logs)

    # Calculate for next day (Tuesday 2026-09-15)
    dyn = calculate_dynamic_daily_quota(date(2026, 9, 15), user_id="test_user", base_quota=100)

    # Half of surplus (40 // 2 = 20) should be deducted
    assert dyn["surplus_deduction"] == 20
    assert dyn["adjusted_target_cards"] == 80
    assert dyn["target_cards"] == 80
    assert "20 Karten Bonus abgezogen" in dyn["quota_adjustment_reason"]


def test_dynamic_daily_quota_deficit(monkeypatch):
    """Verify deficit on day N spreads evenly across remaining active study days."""
    from app.services.curriculum_roadmap_service import calculate_dynamic_daily_quota
    from app.db import repository

    # Mock yesterday's log: target was 100, completed 60 (deficit = 40)
    fake_logs = [
        {"date": "2026-09-14", "cards_target": 100, "cards_completed": 60}
    ]
    monkeypatch.setattr(repository, "get_daily_progress_logs", lambda user_id: fake_logs)

    dyn = calculate_dynamic_daily_quota(date(2026, 9, 15), user_id="test_user", base_quota=100)

    assert dyn["surplus_deduction"] == 0
    assert dyn["deficit_distributed"] >= 1
    assert dyn["adjusted_target_cards"] > 100
    assert "verteilt aus vorherigem Rückstand" in dyn["quota_adjustment_reason"]


def test_assignment_adapts_to_surplus(monkeypatch):
    """Verify get_daily_curriculum_assignment scales topic slots to match adjusted target."""
    from app.db import repository

    fake_logs = [
        {"date": "2026-09-14", "cards_target": 100, "cards_completed": 140}
    ]
    monkeypatch.setattr(repository, "get_daily_progress_logs", lambda user_id: fake_logs)

    assignment = get_daily_curriculum_assignment(date(2026, 9, 15), user_id="test_user")
    assert assignment["target_cards"] == 80
    assert assignment["adjusted_target_cards"] == 80
    assert sum(s["cards_to_learn"] for s in assignment["topic_slots"]) == 80
    assert all("clean_title" in s for s in assignment["topic_slots"])
    assert all("breadcrumb" in s for s in assignment["topic_slots"])

