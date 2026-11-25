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
    assert data["focus_mode"] == "smart"
    assert "focus_plan_open" in data
    assert "multi_day_rollover" in data
    assert "coverage_pct" in data
    assert "deferred_cards_count" in data
    assert "smart_total_due_today" in data
    assert "solid_total_due_today" in data

    active_pool = data.get("active_focus_pool_due", data.get("total_due_today", 0))
    already_rep = data.get("already_repeated_today", 0)
    open_plan = data.get("focus_plan_open", [])
    if active_pool > 0 and already_rep < 350:
        assigned_sum = sum(item["assigned_cards"] for item in open_plan)
        expected_open = min(active_pool, 350 - already_rep)
        assert assigned_sum == expected_open
        # Verify strict top-to-bottom urgency score ordering
        scores = [item["urgency_score"] for item in open_plan]
        assert scores == sorted(scores, reverse=True)
        # If any topic has is_vortag_new=True and active_due_today>0, it must be Rank #1
        has_vortag = any(
            t.get("is_vortag_new") and t.get("active_due_today", t.get("due_today", 0)) > 0
            for t in data.get("topics", [])
        )
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
    selected_sds = triage.get("selected_subdecks", [])
    assert len(selected_sds) > 0
    for sd in selected_sds:
        exact_deck = sd.get("full_anki_deck")
        if exact_deck:
            assert f'deck:"{exact_deck}"' in bq
    # Coarse wildcard professor prefixes must NOT be used when exact subdecks are available
    assert '*" or deck:"' not in bq

    # Verify deck stats also exclude Wenger and Sommer
    dstats = get_detailed_deck_stats()
    for d in dstats.get("all_decks", []):
        assert not is_ignored_deck_name(d.get("anki_name"))


def test_fsrs_retrievability_and_smart_focus_efficiency():
    """Verify FSRS retrievability formula, >=7d unseen time-risk guard, undiluted recall scoring, and mode switching."""
    import json
    import time
    from app.services.anki_backlog_triage import (
        compute_fsrs_retrievability,
        evaluate_due_card_smart_focus,
        _score_and_describe_topic,
        _apply_budget,
    )

    now_ts = time.time()
    unseen_cutoff_ms = (now_ts - 6 * 86400) * 1000.0
    recent_rev_ms = (now_ts - 2 * 86400) * 1000.0
    week_old_rev_ms = (now_ts - 10 * 86400) * 1000.0

    # High stability reviewed recently -> high retrievability (>= 0.85)
    solid_json = json.dumps({"s": 20.0, "decay": 0.281, "lrt": now_ts - 2 * 86400})
    r_solid = compute_fsrs_retrievability(solid_json, now_ts)
    assert r_solid > 0.85

    # Low stability / long elapsed -> low retrievability (< 0.78)
    weak_json = json.dumps({"s": 2.0, "decay": 0.281, "lrt": now_ts - 8 * 86400})
    r_weak = compute_fsrs_retrievability(weak_json, now_ts)
    assert r_weak < 0.78

    # Learning / relearning cards (queue 1/3) always flagged weak
    assert compute_fsrs_retrievability(None, now_ts, queue=1) == 0.50

    # Time-unseen guard: card at R=0.83 is skipped if seen 2 days ago,
    # but flagged as time_risk if unseen >=7d with lapses>=2, reps<=2, or >=6d overdue!
    _, time_recent, need_recent = evaluate_due_card_smart_focus(
        r_prob=0.83, is_vortag=False, last_rev_ms=recent_rev_ms,
        unseen_cutoff_ms=unseen_cutoff_ms, lapses=2, overdue_days=0, r_threshold=0.80, reps=2,
    )
    assert need_recent is False and time_recent is False

    _, time_old_lapses, need_old_lapses = evaluate_due_card_smart_focus(
        r_prob=0.83, is_vortag=False, last_rev_ms=week_old_rev_ms,
        unseen_cutoff_ms=unseen_cutoff_ms, lapses=2, overdue_days=0, r_threshold=0.80, reps=5,
    )
    assert need_old_lapses is True and time_old_lapses is True

    _, time_old_fresh, need_old_fresh = evaluate_due_card_smart_focus(
        r_prob=0.83, is_vortag=False, last_rev_ms=week_old_rev_ms,
        unseen_cutoff_ms=unseen_cutoff_ms, lapses=0, overdue_days=1, r_threshold=0.80, reps=2,
    )
    assert need_old_fresh is True and time_old_fresh is True

    _, time_old_overdue, need_old_overdue = evaluate_due_card_smart_focus(
        r_prob=0.84, is_vortag=False, last_rev_ms=week_old_rev_ms,
        unseen_cutoff_ms=unseen_cutoff_ms, lapses=0, overdue_days=6, r_threshold=0.80, reps=5,
    )
    assert need_old_overdue is True and time_old_overdue is True

    # Rock-solid card above target retention (R=0.90 >= 0.85) stays skipped
    _, time_rock_solid, need_rock_solid = evaluate_due_card_smart_focus(
        r_prob=0.90, is_vortag=False, last_rev_ms=week_old_rev_ms,
        unseen_cutoff_ms=unseen_cutoff_ms, lapses=0, overdue_days=6, r_threshold=0.80, reps=5,
    )
    assert need_rock_solid is False and time_rock_solid is False

    # Verify zero-smart-due deck (due_today > 0 but smart_due_today == 0) is STABIL, not KRITISCH
    zero_smart_topic = {
        "themenblock": "TB Atmung", "dozent": "Einführung & Abschluss",
        "due_today": 8, "active_reviews": 40, "total_reviews": 30, "due_tomorrow": 0,
        "vortag_due_today": 0, "learned_yesterday": 100, "learned_yesterday_due_today": 0,
        "smart_due_counts": {"0.78": 0, "0.80": 0, "0.82": 0},
        "weak_due_counts": {"0.78": 0, "0.80": 0, "0.82": 0},
        "time_risk_due_counts": {"0.78": 0, "0.80": 0, "0.82": 0},
        "all_avg_retrievability_pct": 85.3,
        "smart_avg_retrievability_map": {"0.80": 85.3},
        "all_avg_overdue_days": 1.0,
        "smart_avg_overdue_map": {"0.80": 0.0},
        "smart_avg_unseen_map": {"0.80": 7.0},
        "days_since_last_review": 7.0,
    }
    _score_and_describe_topic(zero_smart_topic, eff_mode="smart", eff_r_val=0.80, eff_r_key="0.80")
    assert zero_smart_topic["is_vortag_new"] is False
    assert zero_smart_topic["urgency_level"] == "STABIL"
    assert zero_smart_topic["urgency_score"] <= 12.0

    r78 = client.get("/api/v1/schedule/anki/backlog-triage?max_capacity=350&focus_mode=smart&r_threshold=0.78").json()
    r80 = client.get("/api/v1/schedule/anki/backlog-triage?max_capacity=350&focus_mode=smart&r_threshold=0.80").json()
    r82 = client.get("/api/v1/schedule/anki/backlog-triage?max_capacity=350&focus_mode=smart&r_threshold=0.82").json()
    r_all = client.get("/api/v1/schedule/anki/backlog-triage?max_capacity=350&focus_mode=all").json()

    assert r78["smart_total_due_today"] <= r80["smart_total_due_today"] <= r82["smart_total_due_today"] <= r_all["total_due_today"]
    if r80.get("budget_selected_topics"):
        bq = r80["budget_combined_anki_query"]
        assert "introduced:2 or prop:r<0.80" in bq
        assert "-rated:7 prop:r<0.85 (prop:lapses>=2 or prop:reps<=2 or prop:due<=-6)" in bq
    if r_all.get("budget_selected_topics"):
        assert "prop:r<" not in r_all["budget_combined_anki_query"]
        assert r_all["total_solid_skipped_today"] == 0

    # Verify Vortag cards pushed >1 day out (learned_yesterday > due_today) are NOT forced into today's pool
    for t in r80.get("topics", []):
        assert t.get("vortag_due_today", 0) <= t.get("due_today", 0)

    # Verify idempotent cloud switching on a single cached payload
    cached_copy = json.loads(json.dumps(r80))
    _apply_budget(cached_copy, 350, focus_mode="all", r_threshold=0.80)
    assert cached_copy["focus_mode"] == "all"
    assert cached_copy["active_focus_pool_due"] == cached_copy["total_due_today"]
    _apply_budget(cached_copy, 350, focus_mode="smart", r_threshold=0.78)
    assert cached_copy["focus_mode"] == "smart"
    assert cached_copy["active_focus_pool_due"] == r78["smart_total_due_today"]


def test_triage_3_0_three_zones_and_anti_starvation():
    """Teil 1: Verify strict 3-zone cascade (A1 > A2 > B > C Med > C Low), no volume bias, and >=10d Anti-Starvation."""
    from app.services.anki_backlog_triage import _apply_budget, _score_subdeck_entry

    def _mk_topic(tb, prof, subdecks, yield_level="medium", days=3.0):
        all_due = sum(s["all_due"] for s in subdecks)
        smart_80 = sum(s["smart_due_counts"]["0.80"] for s in subdecks)
        vort = sum(s.get("vortag_due", 0) for s in subdecks)
        young = sum(s.get("young_due", 0) for s in subdecks)
        return {
            "themenblock": tb,
            "dozent": prof,
            "deck_name": f"{tb} › {prof}",
            "real_anki_prefixes": [f"2. SJ - 1::{tb}::{prof}"],
            "deck_clause": f'deck:"2. SJ - 1::{tb}::{prof}*"',
            "due_today": all_due,
            "vortag_due_today": vort,
            "young_due_today": young,
            "yield_level": yield_level,
            "smart_due_counts": {"0.78": smart_80, "0.80": smart_80, "0.82": smart_80},
            "weak_due_counts": {"0.78": max(0, smart_80 - vort), "0.80": max(0, smart_80 - vort), "0.82": max(0, smart_80 - vort)},
            "time_risk_due_counts": {"0.78": 0, "0.80": 0, "0.82": 0},
            "all_avg_retrievability_pct": 74.0,
            "smart_avg_retrievability_map": {"0.78": 74.0, "0.80": 74.0, "0.82": 74.0},
            "all_avg_overdue_days": days,
            "smart_avg_overdue_map": {"0.78": days, "0.80": days, "0.82": days},
            "smart_avg_unseen_map": {"0.78": days, "0.80": days, "0.82": days},
            "days_since_last_review": days,
            "active_reviews": 100,
            "total_reviews": 50,
            "fail_rate_pct": 20.0,
            "retention_rate_pct": 80.0,
            "repeated_today": 0,
            "repeated_yesterday": 0,
            "smart_subdecks": subdecks,
        }

    sd_a1 = {
        "subdeck": "VL Vortag", "full_anki_deck": "2. SJ - 1::TB Verdauung::Stockmann::VL Vortag",
        "yield_level": "medium", "all_due": 25, "vortag_due": 25, "young_due": 0,
        "smart_due_counts": {"0.78": 25, "0.80": 25, "0.82": 25},
        "avg_r_pct": 70.0, "avg_r_map": {"0.80": 70.0}, "days_since_last_review": 1.0, "fail_rate_pct": 15.0,
    }
    sd_a2 = {
        "subdeck": "VL Jung 3d", "full_anki_deck": "2. SJ - 1::TB Verdauung::Rogler::VL Jung 3d",
        "yield_level": "medium", "all_due": 20, "vortag_due": 0, "young_due": 16,
        "smart_due_counts": {"0.78": 20, "0.80": 20, "0.82": 20},
        "avg_r_pct": 75.0, "avg_r_map": {"0.80": 75.0}, "days_since_last_review": 3.0, "fail_rate_pct": 20.0,
    }
    sd_b_small = {
        "subdeck": "VL High-Yield Klein", "full_anki_deck": "2. SJ - 1::TB Blut & Immunsystem::Manatschal::VL High-Yield Klein",
        "yield_level": "high", "all_due": 6, "vortag_due": 0, "young_due": 0,
        "smart_due_counts": {"0.78": 6, "0.80": 6, "0.82": 6},
        "avg_r_pct": 72.0, "avg_r_map": {"0.80": 72.0}, "days_since_last_review": 4.0, "fail_rate_pct": 25.0,
    }
    sd_c_med_huge = {
        "subdeck": "VL Med-Yield Riesig", "full_anki_deck": "2. SJ - 1::TB Stoffwechsel::Robert::VL Med-Yield Riesig",
        "yield_level": "medium", "all_due": 200, "vortag_due": 0, "young_due": 0,
        "smart_due_counts": {"0.78": 200, "0.80": 200, "0.82": 200},
        "avg_r_pct": 72.0, "avg_r_map": {"0.80": 72.0}, "days_since_last_review": 4.0, "fail_rate_pct": 25.0,
    }
    sd_c_low_fresh = {
        "subdeck": "VL Low-Yield Frisch", "full_anki_deck": "2. SJ - 1::TB Verdauung::Dutzler::VL Low-Yield Frisch",
        "yield_level": "low", "all_due": 15, "vortag_due": 0, "young_due": 0,
        "smart_due_counts": {"0.78": 15, "0.80": 15, "0.82": 15},
        "avg_r_pct": 76.0, "avg_r_map": {"0.80": 76.0}, "days_since_last_review": 2.0, "fail_rate_pct": 10.0,
    }
    sd_c_low_starved = {
        "subdeck": "VL Low-Yield 11d Alt", "full_anki_deck": "2. SJ - 1::TB Verdauung::Dutzler::VL Low-Yield 11d Alt",
        "yield_level": "low", "all_due": 12, "vortag_due": 0, "young_due": 0,
        "smart_due_counts": {"0.78": 12, "0.80": 12, "0.82": 12},
        "avg_r_pct": 74.0, "avg_r_map": {"0.80": 74.0}, "days_since_last_review": 11.0, "fail_rate_pct": 18.0,
    }

    payload = {
        "connected": True,
        "topics": [
            _mk_topic("TB Verdauung", "Stockmann", [sd_a1], yield_level="medium", days=1.0),
            _mk_topic("TB Verdauung", "Rogler", [sd_a2], yield_level="medium", days=3.0),
            _mk_topic("TB Blut & Immunsystem", "Manatschal", [sd_b_small], yield_level="high", days=4.0),
            _mk_topic("TB Stoffwechsel", "Robert", [sd_c_med_huge], yield_level="medium", days=4.0),
            _mk_topic("TB Verdauung", "Dutzler", [sd_c_low_fresh, sd_c_low_starved], yield_level="low", days=2.0),
        ],
        "themenbloecke": [],
    }

    # Pack with large budget to inspect full strict order across all 6 subdecks
    _apply_budget(payload, budget=500, focus_mode="smart", r_threshold=0.80)
    ordered_names = [s["subdeck"] for s in payload["selected_subdecks"]]

    # (a) A1 Vortag is ALWAYS #1, followed by A2 Jung <=5d
    assert ordered_names[0] == "VL Vortag"
    assert ordered_names[1] == "VL Jung 3d"
    # (b) Starved Low-Yield (>=10d) & small High-Yield beat huge 200-card Med-Yield (no volume bias!)
    assert ordered_names.index("VL High-Yield Klein") < ordered_names.index("VL Med-Yield Riesig")
    assert ordered_names.index("VL Low-Yield 11d Alt") < ordered_names.index("VL Med-Yield Riesig")
    # (c) Fresh Low-Yield is NEVER hidden/deleted, but stays strictly at the very end of Zone C
    assert "VL Low-Yield Frisch" in ordered_names
    assert ordered_names[-1] == "VL Low-Yield Frisch"

    # (d) Tight budget (e.g. 60 cards): A1 (25) + A2 (20) + Starved Low-Yield (12) + High-Yield (3) fit,
    #     while fresh Low-Yield & huge Med-Yield wait for rollover
    _apply_budget(payload, budget=60, focus_mode="smart", r_threshold=0.80)
    sel_names_60 = [s["subdeck"] for s in payload["selected_subdecks"]]
    assert "VL Vortag" in sel_names_60
    assert "VL Jung 3d" in sel_names_60
    assert "VL Low-Yield 11d Alt" in sel_names_60
    assert "VL Low-Yield Frisch" not in sel_names_60
    # Verify exact subdeck path in Anki query (Dutzler's starved subdeck included, fresh subdeck NOT pulled in!)
    bq = payload["budget_combined_anki_query"]
    assert 'deck:"2. SJ - 1::TB Verdauung::Dutzler::VL Low-Yield 11d Alt"' in bq
    assert 'deck:"2. SJ - 1::TB Verdauung::Dutzler::VL Low-Yield Frisch"' not in bq
    assert "prop:ivl<=5" in bq


def test_triage_3_0_exact_subdeck_query_scaling_live_db():
    """Teil 1: Verify exact subdeck queries scale cleanly across 350, 500, 700, and All on real collection.anki2."""
    r350 = calculate_backlog_triage(max_capacity=350)
    r500 = calculate_backlog_triage(max_capacity=500)
    r700 = calculate_backlog_triage(max_capacity=700)
    rall = calculate_backlog_triage(max_capacity=5000)

    assert r350.get("triage_version") == "3.0"
    assert "zone_summary" in r350
    assert len(r350["selected_subdecks"]) <= len(r500["selected_subdecks"]) <= len(r700["selected_subdecks"]) <= len(rall["selected_subdecks"])
    assert r350["budget_accumulated_cards"] <= r500["budget_accumulated_cards"] <= r700["budget_accumulated_cards"] <= rall["budget_accumulated_cards"]

    # Every A1 Vortag subdeck must be 100% present already at default budget 350
    all_vortag_decks = {sd["full_anki_deck"] for sd in rall["selected_subdecks"] if sd.get("vortag_due", 0) > 0}
    sel_350_decks = {sd["full_anki_deck"] for sd in r350["selected_subdecks"]}
    assert all_vortag_decks.issubset(sel_350_decks)
    assert "prop:ivl<=5" in r350["budget_combined_anki_query"]





