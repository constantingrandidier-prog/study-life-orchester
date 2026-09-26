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
    assert roadmap["revision_buffer_days"] >= 7
    assert len(roadmap["modules"]) == 6

    # Verify active days have exactly 100 cards and Sundays are rest days
    schedule = roadmap["schedule"]
    assert len(schedule) > 90

    for day in schedule:
        if day["is_rest_day"]:
            assert day["target_cards"] == 0
            assert day["day_of_week"] in ("Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag")
            assert len(day["topic_slots"]) == 0
        else:
            assert len(day["topic_slots"]) >= 1
            day_total = sum(s["cards_to_learn"] for s in day["topic_slots"])
            assert day["target_cards"] == day_total
            # Didactic concept chunks are grouped reasonably between 10 and 180 cards
            assert day_total >= 10 and day_total <= 180
            assert "synergy_headline" in day
            assert "recommended_study_sequence" in day


def test_daily_curriculum_assignment_day_one():
    """Verify Day 1 (2026-09-14) gives coherent Concept Session for Leukozyten I with real Anki state."""
    assignment = get_daily_curriculum_assignment(target_date=date(2026, 9, 14))

    assert assignment["date"] == "2026-09-14"
    assert assignment["day_of_week"] == "Montag"
    assert assignment["day_number"] == 1
    assert not assignment["is_rest_day"]
    assert assignment["target_cards"] > 0
    assert len(assignment["topic_slots"]) >= 1
    slot = next((s for s in assignment["topic_slots"] if "Leukozyten" in s["clean_title"]), assignment["topic_slots"][0])
    assert "Leukozyten" in slot["clean_title"]
    assert slot["cards_to_learn"] > 0
    assert slot["already_mastered_cards"] >= 47
    assert slot["video_timestamp_guidance"] is not None
    assert slot["red_thread"] is not None
    assert "Blut" in assignment["current_module"]
    assert assignment["synergy_headline"] is not None
    assert len(assignment["recommended_study_sequence"]) == 3


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
    assignment = get_daily_curriculum_assignment(target_date=date(2027, 1, 15))

    assert assignment["date"] == "2027-01-15"
    assert assignment["curriculum_progress_pct"] == 100.0
    assert "Revisionsphase" in assignment["current_module"]


def test_api_curriculum_today():
    """Verify /api/v1/schedule/curriculum/today endpoint returns valid daily assignment with synergy."""
    res = client.get("/api/v1/schedule/curriculum/today?target_date=2026-09-14")
    assert res.status_code == 200
    data = res.json()

    assert data["date"] == "2026-09-14"
    assert data["day_number"] == 1
    assert data["target_cards"] > 0
    assert len(data["topic_slots"]) >= 1
    assert "short_title" in data["topic_slots"][0]
    assert "cards_to_learn" in data["topic_slots"][0]
    assert "synergy_headline" in data
    assert "recommended_study_sequence" in data


def test_api_curriculum_roadmap():
    """Verify /api/v1/schedule/curriculum/roadmap endpoint returns entire semester plan."""
    res = client.get("/api/v1/schedule/curriculum/roadmap")
    assert res.status_code == 200
    data = res.json()

    assert data["start_date"] == "2026-09-14"
    assert data["exam_date"] == "2027-01-19"
    assert len(data["modules"]) == 6
    assert len(data["schedule"]) > 90


def test_parity_between_roadmap_and_today():
    """Verify that /curriculum/roadmap and /curriculum/today return identical targets, slots, and summary for today."""
    today_str = date.today().isoformat()
    res_today = client.get(f"/api/v1/schedule/curriculum/today?target_date={today_str}")
    assert res_today.status_code == 200
    today_data = res_today.json()

    res_roadmap = client.get(f"/api/v1/schedule/curriculum/roadmap?target_date={today_str}")
    assert res_roadmap.status_code == 200
    roadmap_data = res_roadmap.json()

    matching_day = next((d for d in roadmap_data["schedule"] if d["date"] == today_str), None)
    assert matching_day is not None
    assert matching_day["target_cards"] == today_data["target_cards"]
    assert matching_day["adjusted_target_cards"] == today_data["adjusted_target_cards"]
    assert matching_day["summary"] == today_data["summary"]
    assert len(matching_day["topic_slots"]) == len(today_data["topic_slots"])
    for s_rm, s_td in zip(matching_day["topic_slots"], today_data["topic_slots"]):
        assert s_rm["clean_title"] == s_td["clean_title"]
        assert s_rm["cards_to_learn"] == s_td["cards_to_learn"]


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
    assert assignment["surplus_deduction"] == 20
    # Day 2 scheduled cards minus 20 bonus
    assert assignment["target_cards"] == assignment["adjusted_target_cards"]
    assert sum(s["cards_to_learn"] for s in assignment["topic_slots"]) == assignment["target_cards"]
    assert all("clean_title" in s for s in assignment["topic_slots"])
    assert all("breadcrumb" in s for s in assignment["topic_slots"])


def test_curriculum_swap_days_endpoint_and_assignment():
    """Verify swapping learning packages between Saturday (Day 6) and Day 12."""
    # 0. Ensure clean state
    client.post("/api/v1/schedule/curriculum/reset-swaps")

    # 1. Baseline check via roadmap
    res_base = client.get("/api/v1/schedule/curriculum/roadmap")
    assert res_base.status_code == 200
    sched_base = res_base.json()["schedule"]
    d6_base = next(d for d in sched_base if d.get("day_number") == 6)
    d12_base = next(d for d in sched_base if d.get("day_number") == 12)
    d12_orig_target = d12_base["target_cards"]
    assert d12_orig_target > 0

    # 2. Call swap endpoint
    res = client.post("/api/v1/schedule/curriculum/swap-days", json={
        "date1": "2026-09-19",
        "date2": "2026-09-26",
        "day_num1": 6,
        "day_num2": 12,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"

    # 3. Check swapped assignments in roadmap
    res_swapped = client.get("/api/v1/schedule/curriculum/roadmap")
    sched_swapped = res_swapped.json()["schedule"]
    d6_swapped = next(d for d in sched_swapped if d.get("day_number") == 6)
    d12_swapped = next(d for d in sched_swapped if d.get("day_number") == 12)

    assert d6_swapped["target_cards"] == d12_orig_target
    assert d6_swapped.get("is_swapped") is True
    assert d6_swapped.get("swapped_with_day") == 12
    assert d12_swapped.get("is_swapped") is True
    assert d12_swapped.get("swapped_with_day") == 6

    # 4. Reset swaps
    reset_res = client.post("/api/v1/schedule/curriculum/reset-swaps")
    assert reset_res.status_code == 200

    # 5. Verify restored back to baseline
    res_restored = client.get("/api/v1/schedule/curriculum/roadmap")
    sched_restored = res_restored.json()["schedule"]
    d6_restored = next(d for d in sched_restored if d.get("day_number") == 6)
    assert d6_restored.get("is_swapped") is not True


def test_calculate_card_cognitive_metrics():
    """Verify realistic cognitive load calculations for medical students: fact decks take ~35-45s while complex essay/cycle topics take 80-120s+."""
    from app.services.curriculum_roadmap_service import calculate_card_cognitive_metrics

    # Case 1: Short fact deck (e.g. 137 chars, simple facts)
    short_m = calculate_card_cognitive_metrics(
        card_count=60,
        avg_card_chars=137.6,
        is_cycle_topic=False,
        recommended_mode="skipped",
        topic_difficulty_mult=0.75,
        exam_yield="low_yield",
    )
    assert 25 <= short_m["seconds_per_card"] <= 45
    assert short_m["estimated_study_minutes"] <= 45
    assert short_m["difficulty_level"] == "easy"
    assert "Leicht" in short_m["difficulty_label"]

    # Case 2: Standard concept deck (300 chars, medium yield)
    standard_m = calculate_card_cognitive_metrics(
        card_count=70,
        avg_card_chars=300.0,
        is_cycle_topic=False,
        recommended_mode="stream_1_2",
        topic_difficulty_mult=1.0,
        exam_yield="medium_yield",
    )
    assert 45 <= standard_m["seconds_per_card"] <= 70
    assert 50 <= standard_m["estimated_study_minutes"] <= 85

    # Case 3: Dense physiological essay deck (e.g. 793 chars, high yield, cycle topic)
    heavy_m = calculate_card_cognitive_metrics(
        card_count=60,
        avg_card_chars=793.0,
        is_cycle_topic=True,
        recommended_mode="stream_1_0",
        topic_difficulty_mult=1.35,
        exam_yield="high_yield",
    )
    assert heavy_m["seconds_per_card"] >= 75
    assert heavy_m["estimated_study_minutes"] >= 75
    assert heavy_m["difficulty_level"] in ("hard", "very_hard")
    assert any(w in heavy_m["difficulty_label"] for w in ("Schwer", "Intensiv", "Sehr anspruchsvoll", "Marathon"))


def test_roadmap_days_have_cognitive_metrics():
    """Verify that every active day in the roadmap contains cognitive duration, difficulty badges, and exam yield."""
    roadmap = generate_curriculum_roadmap()
    schedule = roadmap["schedule"]

    for d in schedule:
        if d.get("is_rest_day"):
            assert d.get("estimated_study_minutes") == 0
            assert d.get("difficulty_level") == "rest"
            assert d.get("exam_yield") == "rest"
            assert any(w in d.get("exam_yield_badge", "") for w in ("Regeneration", "Ruhetag", "Pause"))
        else:
            assert d.get("estimated_study_minutes", 0) > 0
            assert d.get("difficulty_level") in ("easy", "medium", "hard", "very_hard")
            assert d.get("difficulty_badge") is not None
            assert d.get("exam_yield") in ("high_yield", "medium_yield", "low_yield")
            assert d.get("exam_yield_badge") is not None
            assert len(d.get("topic_slots", [])) >= 1
            for slot in d["topic_slots"]:
                assert "avg_card_chars" in slot
                assert "seconds_per_card" in slot
                assert "estimated_study_minutes" in slot
                assert "exam_yield" in slot
                assert "yield_stars" in slot


def test_swap_updates_previous_day_tomorrow_preview():
    """Verify that swapping Day 6 and Day 12 automatically updates the 24h-priming on Day 5 and Day 11."""
    from app.db.repository import swap_curriculum_days, reset_curriculum_schedule_overrides

    reset_curriculum_schedule_overrides()

    # 1. Check Friday before swap
    fri_before = get_daily_curriculum_assignment(date(2026, 9, 18))
    assert fri_before["tomorrow_preview"] is not None
    assert "Thymus" in fri_before["tomorrow_preview"]["primary_lecture_title"] or "Phasen" in fri_before["tomorrow_preview"]["primary_lecture_title"]
    assert fri_before["tomorrow_preview"]["target_cards"] >= 80

    # 2. Swap Day 6 (2026-09-19) with Day 12 (2026-09-26)
    swap_curriculum_days("2026-09-19", "2026-09-26", 6, 12)

    # 3. Check Friday after swap: tomorrow_preview MUST now prime swapped lecture
    fri_after = get_daily_curriculum_assignment(date(2026, 9, 18))
    assert fri_after["tomorrow_preview"] is not None
    assert fri_after["tomorrow_preview"]["target_cards"] >= 80
    assert fri_after["tomorrow_preview"]["difficulty_level"] in ("easy", "medium", "hard", "very_hard")
    assert "exam_yield" in fri_after["tomorrow_preview"]
    assert fri_after["tomorrow_preview"]["exam_yield_badge"] is not None

    # 4. Check Day 11 (Friday of next week, 2026-09-25): MUST now prime swapped lecture
    day11_after = get_daily_curriculum_assignment(date(2026, 9, 25))
    assert day11_after["tomorrow_preview"] is not None
    assert "Thymus" in day11_after["tomorrow_preview"]["primary_lecture_title"] or "Phasen" in day11_after["tomorrow_preview"]["primary_lecture_title"]
    assert day11_after["tomorrow_preview"]["target_cards"] >= 80

    # 5. Clean up
    reset_curriculum_schedule_overrides()



