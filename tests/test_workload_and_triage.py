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
    # Restore real forecast cache
    get_workload_forecast(days_ahead=14, daily_budget=350)

def test_backlog_triage_advanced_queries():
    triage = calculate_backlog_triage(max_capacity=150)
    assert "topics" in triage
    assert "themenbloecke" in triage
    assert "urgent_combined_anki_query" in triage
    assert "is:due" in triage["urgent_combined_anki_query"]
    assert "budget_combined_anki_query" in triage
    assert "is:due" in triage["budget_combined_anki_query"]

def test_parse_curriculum_deck():
    from app.services.anki_backlog_triage import parse_curriculum_deck

    # Same professor (Loffing) in different Themenblöcke must parse to distinct TBs
    tb1, prof1 = parse_curriculum_deck("2. SJ - 1\x1fTB Atmung\x1fLoffing\x1fVentilation")
    assert tb1 == "TB Atmung"
    assert prof1 == "Loffing"

    tb2, prof2 = parse_curriculum_deck("2. SJ - 1\x1fTB Herz-Kreislauf\x1fLoffing\x1fRegulation")
    assert tb2 == "TB Herz-Kreislauf"
    assert prof2 == "Loffing"
    assert (tb1, prof1) != (tb2, prof2)

    # Stockmann in TB Blut/Immunsystem
    tb3, prof3 = parse_curriculum_deck("2. SJ - 1::TB Blut/Immunsystem::Stockmann::Hämatopoese")
    assert tb3 == "TB Blut & Immunsystem"
    assert prof3 == "Stockmann"

    # Non-curriculum, oral exam, and Wenger/Sommer decks ignored
    assert parse_curriculum_deck("1. SJ - 1\x1fAnatomie") == (None, None)
    assert parse_curriculum_deck("2. SJ - 1\x1fMündliche Prüfung") == (None, None)
    assert parse_curriculum_deck("Englisch Vokabeln") == (None, None)
    assert parse_curriculum_deck("2. SJ - 1\x1fTB Atmung\x1fAtmung_Physiologie_Wenger") == (None, None)
    assert parse_curriculum_deck("2. SJ - 1\x1fTB Herz-Kreislauf\x1fSommer\x1fHerzentwicklung") == (None, None)

def test_backlog_triage_factors_and_structure():
    triage = calculate_backlog_triage(max_capacity=350)
    for t in triage.get("topics", []):
        assert t["dozent"] not in ("Wenger", "Sommer")
    assert triage["connected"] in (True, False)
    assert "themenbloecke" in triage
    for tb in triage["themenbloecke"]:
        assert "name" in tb
        assert "total_due_today" in tb
        assert "professors" in tb
        for prof in tb["professors"]:
            assert "themenblock" in prof
            assert "dozent" in prof
            assert "avg_ease_pct" in prof
            assert "retention_rate_pct" in prof
            assert "urgency_score" in prof
            assert "anki_filter_query" in prof
            # Verify query targets both TB and professor
            assert prof["themenblock"] in prof["anki_filter_query"]
            assert prof["dozent"] in prof["anki_filter_query"]

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
    # Pause 1 comes after Block 1 (time depends on cards_due)
    assert blocks[1]["is_break"] is True
    # Block 2 (New cards) comes after Pause 1
    assert "Neue Karten" in blocks[2]["title"]
    # Block 2 starts after Block 1 ends (ordering is correct)
    block1_end = blocks[0]["end_time"]
    block2_start = blocks[2]["start_time"]
    assert block2_start > block1_end

def test_api_daily_rhythm_endpoint():
    resp = client.get("/api/v1/schedule/daily-rhythm?target_date=2026-09-15")
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured_start_time"] == "08:30"
    assert "start_time" in data
    assert "blocks" in data
    assert len(data["blocks"]) >= 6


def test_triage_default_350_focus_and_rollover():
    resp = client.get("/api/v1/schedule/anki/backlog-triage")
    assert resp.status_code == 200
    data = resp.json()
    assert data["max_capacity"] == 350
    assert "focus_plan_open" in data
    assert "multi_day_rollover" in data
    assert "coverage_pct" in data
    assert "deferred_cards_count" in data

    total_due = data.get("total_due_today", 0)
    already_rep = data.get("already_repeated_today", 0)
    open_plan = data.get("focus_plan_open", [])
    if total_due > 0 and already_rep < 350:
        assigned_sum = sum(item["assigned_cards"] for item in open_plan)
        expected_open = min(total_due, 350 - already_rep)
        assert assigned_sum == expected_open
        # Verify strict top-to-bottom urgency score ordering
        scores = [item["urgency_score"] for item in open_plan]
        assert scores == sorted(scores, reverse=True)
        # If any topic has is_vortag_new=True and due_today>0, it must be Rank #1
        has_vortag = any(t.get("is_vortag_new") and t.get("due_today", 0) > 0 for t in data.get("topics", []))
        if has_vortag:
            assert open_plan[0]["is_vortag_new"] is True
            assert open_plan[0]["rank"] == 1


def test_triage_custom_budget_and_forecast_rollover():
    resp = client.get("/api/v1/schedule/anki/backlog-triage?max_capacity=250")
    assert resp.status_code == 200
    data = resp.json()
    assert data["max_capacity"] == 250

    fc_resp = client.get("/api/v1/schedule/anki/workload-forecast?daily_budget=350")
    assert fc_resp.status_code == 200
    fc = fc_resp.json()
    assert fc.get("daily_budget") == 350
    if fc.get("days"):
        assert "planned_due" in fc["days"][0]
        assert fc["days"][0]["planned_due"] <= 350


def test_real_anki_prefix_queries_and_central_ignore():
    """Verify that budget_combined_anki_query and topic queries include exact Anki hierarchy prefixes and exclude Wenger/Sommer everywhere."""
    from app.services.semester_config import (
        SEMESTER_START_DATE,
        TARGET_EXAM_DATE,
        is_ignored_dozent,
        is_ignored_deck_name,
        build_anki_deck_clause,
    )
    from app.services.anki_deck_stats import get_detailed_deck_stats

    assert str(SEMESTER_START_DATE) == "2026-09-14"
    assert str(TARGET_EXAM_DATE) == "2027-01-19"
    assert is_ignored_dozent("Wenger") is True
    assert is_ignored_dozent("Sommer") is True
    assert is_ignored_dozent("Stockmann") is False

    # Schneider subdeck mentioning '/ Wenger' must NOT be ignored!
    assert is_ignored_deck_name("2. SJ - 1 :: TB Blut/Immunsystem :: Schneider :: Erythrozyten / Wenger") is False
    assert is_ignored_deck_name("2. SJ - 1 :: TB Atmung :: Atmung_Physiologie_Wenger") is True
    assert is_ignored_deck_name("2. SJ - 1 :: TB Herz-Kreislauf :: Sommer :: Herzentwicklung") is True

    clause = build_anki_deck_clause(
        ["2. SJ - 1::TB Blut/Immunsystem::Tuzlak (jetzt Becher)"],
        "TB Blut & Immunsystem",
        "Tuzlak / Becher",
    )
    assert 'deck:"2. SJ - 1::TB Blut/Immunsystem::Tuzlak (jetzt Becher)*"' in clause

    triage = calculate_backlog_triage(max_capacity=350)
    bq = triage.get("budget_combined_anki_query", "")
    selected = triage.get("budget_selected_topics", [])
    for sel in selected:
        for pfx in sel.get("real_anki_prefixes", []):
            assert f'deck:"{pfx}*"' in bq

    # Verify deck stats also exclude Wenger and Sommer
    dstats = get_detailed_deck_stats()
    for d in dstats.get("all_decks", []):
        assert not is_ignored_deck_name(d.get("anki_name"))



