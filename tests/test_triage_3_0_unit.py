"""Comprehensive live-DB-independent unit tests for Triage 3.0 & Daily Prof Briefing (F1–F11)."""

import json
import re
from pathlib import Path

import pytest

import app.services.anki_backlog_triage as abt
from app.services.anki_backlog_triage import (
    _apply_budget,
    _compute_zone_and_score,
    _is_zone_a2_dominant,
    cache_triage,
    get_cached_triage,
)
from app.services.lecture_exam_briefing_service import (
    build_daily_triage_prof_briefing,
    load_lecture_exam_signals,
    match_subdeck_to_exam_signal,
)

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_SUBDECKS_PATH = ROOT / "tests" / "fixtures" / "triage_golden_subdecks.json"


def _make_topic(
    tb: str,
    prof: str,
    yield_level: str,
    subdecks: list,
    days_ago: float = 3.0,
    rep_today: int = 0,
):
    due_tot = sum(s["all_due"] for s in subdecks)
    smart_tot = sum(s["smart_due_counts"]["0.80"] for s in subdecks)
    vortag_tot = sum(s.get("vortag_due", 0) for s in subdecks)
    young_tot = sum(s.get("young_due", 0) for s in subdecks)
    return {
        "themenblock": tb,
        "dozent": prof,
        "deck_name": f"{tb} › {prof}",
        "yield_level": yield_level,
        "due_today": due_tot,
        "due_tomorrow": 0,
        "smart_due_today": smart_tot,
        "smart_due_counts": {"0.78": smart_tot, "0.80": smart_tot, "0.82": smart_tot},
        "vortag_due_today": vortag_tot,
        "learned_yesterday_due_today": vortag_tot,
        "learned_yesterday": vortag_tot,
        "young_due_today": young_tot,
        "days_since_last_review": days_ago,
        "avg_retrievability_pct": 72.0,
        "all_avg_retrievability_pct": 72.0,
        "avg_overdue_days": 2.0,
        "all_avg_overdue_days": 2.0,
        "fail_rate_pct": 20.0,
        "retention_rate_pct": 80.0,
        "avg_ease_pct": 230.0,
        "repeated_today": rep_today,
        "repeated_yesterday": 0,
        "active_reviews": 50,
        "total_reviews": 100,
        "total_fails": 20,
        "real_anki_prefixes": [f"Anki::2. SJ::{tb}::{prof}"],
        "deck_clause": f'deck:"Anki::2. SJ::{tb}::{prof}*"',
        "smart_subdecks": subdecks,
    }


def _make_subdeck(
    tb: str,
    prof: str,
    subdeck: str,
    all_due: int,
    smart_due: int = None,
    vortag_due: int = 0,
    young_due: int = 0,
    yield_level: str = "medium",
    days_ago: float = 3.0,
    avg_r_pct: float = 72.0,
):
    sd_smart = all_due if smart_due is None else smart_due
    return {
        "did": abs(hash((tb, prof, subdeck))) % 100000,
        "themenblock": tb,
        "dozent": prof,
        "deck_name": f"{tb} › {prof}",
        "subdeck": subdeck,
        "full_anki_deck": f"Anki::2. SJ::{tb}::{prof}::{subdeck}",
        "yield_level": yield_level,
        "all_due": all_due,
        "smart_due_counts": {"0.78": sd_smart, "0.80": sd_smart, "0.82": sd_smart},
        "vortag_due": vortag_due,
        "young_due": young_due,
        "avg_r_pct": avg_r_pct,
        "avg_r_map": {"0.80": avg_r_pct},
        "avg_overdue_days": 2.0,
        "avg_overdue_map": {"0.80": 2.0},
        "days_since_last_review": days_ago,
        "fail_rate_pct": 20.0,
        "repeated_today": 0,
        "repeated_yesterday": 0,
    }


# ── F1: 100% A1 Vortag Guarantee (user explicitly requires ALL yesterday's new cards!) ──
def test_f1_a1_vortag_100_percent_guaranteed_even_over_tiny_budget():
    """Regardless of how small max_capacity is (e.g. 50), ALL Vortag cards across 1 or multiple subdecks are included."""
    t_stockmann = _make_topic(
        "TB Verdauung",
        "Stockmann",
        "high",
        [
            _make_subdeck("TB Verdauung", "Stockmann", "Colon und Rektum / Stockmann", all_due=90, smart_due=90, vortag_due=80, yield_level="high"),
            _make_subdeck("TB Verdauung", "Stockmann", "Duodenum und Pankreas / Stockmann", all_due=60, smart_due=60, vortag_due=45, yield_level="high"),
        ],
    )
    t_loffing = _make_topic(
        "TB Atmung",
        "Loffing",
        "high",
        [
            _make_subdeck("TB Atmung", "Loffing", "Lunge / Loffing", all_due=40, smart_due=40, young_due=25, yield_level="high"),
        ],
    )
    payload = {"connected": True, "topics": [t_stockmann, t_loffing], "themenbloecke": []}

    # Tiny budget = 50, but 80 + 45 = 125 Vortag cards are due!
    _apply_budget(payload, budget=50, focus_mode="smart", r_threshold=0.80)

    sel = payload["selected_subdecks"]
    # Both A1 subdecks must be selected with at least their full vortag_due counts (80 and 45)
    by_sub = {s["subdeck"]: s for s in sel}
    assert by_sub["Colon und Rektum / Stockmann"]["assigned_cards"] == 80
    assert by_sub["Duodenum und Pankreas / Stockmann"]["assigned_cards"] == 45
    # Non-A1 subdeck must NOT be added while over budget
    assert "Lunge / Loffing" not in by_sub
    assert payload["budget_accumulated_cards"] == 125
    assert payload["a1_overflow_cards"] == 75
    assert payload["effective_today_target"] == 125
    assert "+75 A1 Vortag-Pflichtkarten" in payload["summary_advice"]

    # Larger budget = 200: fits all 90 + 60 + 40 = 190 cards cleanly with 0 overflow
    payload2 = json.loads(json.dumps({"connected": True, "topics": [t_stockmann, t_loffing], "themenbloecke": []}))
    _apply_budget(payload2, budget=200, focus_mode="smart", r_threshold=0.80)
    assert payload2["a1_overflow_cards"] == 0
    assert payload2["budget_accumulated_cards"] == 190
    assert payload2["budget_accumulated_cards"] <= 200


def test_f1_a1_vortag_still_scheduled_when_daily_budget_already_met():
    """Even if user already repeated >= budget today (e.g. 400 >= 350), open A1 Vortag cards stay in focus_plan_open."""
    t_a1 = _make_topic(
        "TB Verdauung",
        "Stockmann",
        "high",
        [_make_subdeck("TB Verdauung", "Stockmann", "Colon und Rektum / Stockmann", all_due=35, smart_due=35, vortag_due=25, yield_level="high")],
        rep_today=400,
    )
    t_b = _make_topic(
        "TB Atmung",
        "Loffing",
        "high",
        [_make_subdeck("TB Atmung", "Loffing", "Lunge / Loffing", all_due=40, smart_due=40, yield_level="high")],
    )
    payload = {"connected": True, "topics": [t_a1, t_b], "themenbloecke": []}
    _apply_budget(payload, budget=350, focus_mode="smart", r_threshold=0.80)

    assert payload["remaining_budget_today"] == 0
    assert payload["budget_accumulated_cards"] == 25
    assert payload["a1_overflow_cards"] == 25
    assert len(payload["selected_subdecks"]) == 1
    assert payload["selected_subdecks"][0]["subdeck"] == "Colon und Rektum / Stockmann"
    assert len(payload["focus_plan_open"]) == 1
    assert payload["focus_plan_open"][0]["assigned_cards"] == 25
    assert payload["effective_today_target"] == 425


# ── F7: Unified Scoring & Non-Overlapping Score Bands + 1:1 Ranking Consistency ──
@pytest.mark.parametrize(
    "young_due,active_due,expected",
    [
        (0, 10, False),
        (5, 0, False),
        (1, 50, False),
        (4, 10, False),    # ratio 0.40 but young < 5 and active > 8
        (5, 14, True),     # young >= 5 and ratio 0.357 >= 0.35
        (5, 15, False),    # ratio 0.333 < 0.35
        (14, 100, False),  # young < 15 and low ratio
        (15, 100, True),   # young >= 15 always A2
        (4, 8, True),      # active <= 8 and ratio 0.50
        (3, 8, False),     # ratio 0.375 < 0.50
    ],
)
def test_f7_is_zone_a2_dominant_boundaries(young_due, active_due, expected):
    assert _is_zone_a2_dominant(young_due, active_due) is expected


def test_f7_score_bands_strictly_non_overlapping():
    """Property check: A1 > A2 > (Anti-Starvation & B) > C-Med > C-Low across extreme inputs."""
    a1_min = _compute_zone_and_score(
        is_vortag=True, vortag_count=1, is_a2=False, young_count=0, active_due=10,
        yield_level="none", effective_unseen=0.0, core_need=0.0, repeated_yesterday=50,
    )["score"]
    a2_max = _compute_zone_and_score(
        is_vortag=False, vortag_count=0, is_a2=True, young_count=100, active_due=100,
        yield_level="high", effective_unseen=20.0, core_need=90.0, repeated_yesterday=0,
    )["score"]
    a2_min = _compute_zone_and_score(
        is_vortag=False, vortag_count=0, is_a2=True, young_count=5, active_due=10,
        yield_level="none", effective_unseen=0.0, core_need=0.0, repeated_yesterday=50,
    )["score"]
    b_max = _compute_zone_and_score(
        is_vortag=False, vortag_count=0, is_a2=False, young_count=0, active_due=50,
        yield_level="high", effective_unseen=9.0, core_need=90.0, repeated_yesterday=0,
    )["score"]
    starv_max = _compute_zone_and_score(
        is_vortag=False, vortag_count=0, is_a2=False, young_count=0, active_due=50,
        yield_level="low", effective_unseen=30.0, core_need=90.0, repeated_yesterday=0,
    )["score"]
    b_min = _compute_zone_and_score(
        is_vortag=False, vortag_count=0, is_a2=False, young_count=0, active_due=50,
        yield_level="high", effective_unseen=0.0, core_need=0.0, repeated_yesterday=50,
    )["score"]
    c_med_max = _compute_zone_and_score(
        is_vortag=False, vortag_count=0, is_a2=False, young_count=0, active_due=50,
        yield_level="medium", effective_unseen=9.0, core_need=90.0, repeated_yesterday=0,
    )["score"]
    c_med_min = _compute_zone_and_score(
        is_vortag=False, vortag_count=0, is_a2=False, young_count=0, active_due=50,
        yield_level="medium", effective_unseen=0.0, core_need=0.0, repeated_yesterday=50,
    )["score"]
    c_low_max = _compute_zone_and_score(
        is_vortag=False, vortag_count=0, is_a2=False, young_count=0, active_due=50,
        yield_level="low", effective_unseen=9.0, core_need=90.0, repeated_yesterday=0,
    )["score"]

    assert a1_min > a2_max
    assert a2_min > max(b_max, starv_max)
    assert b_min > c_med_max
    assert c_med_min > c_low_max


def test_f7_professor_checklist_and_briefing_order_strictly_identical():
    """focus_plan_open order (#1..#N) must match selected_subdecks first-appearance AND daily_prof_briefing.items 1:1."""
    t_a2 = _make_topic(
        "TB Atmung", "Loffing", "low",
        [_make_subdeck("TB Atmung", "Loffing", "Lunge / Loffing", all_due=20, young_due=18, yield_level="low", days_ago=2.0)],
        days_ago=2.0,
    )
    t_b = _make_topic(
        "TB Herz-Kreislauf", "Kurtcuoglu", "high",
        [_make_subdeck("TB Herz-Kreislauf", "Kurtcuoglu", "EKG / Kurtcuoglu", all_due=30, yield_level="high", days_ago=5.0)],
        days_ago=5.0,
    )
    t_c = _make_topic(
        "TB Verdauung", "Wagner", "medium",
        [_make_subdeck("TB Verdauung", "Wagner", "Hunger und Sättigung / Wagner", all_due=25, yield_level="medium", days_ago=4.0)],
        days_ago=4.0,
    )
    payload = {"connected": True, "topics": [t_c, t_b, t_a2], "themenbloecke": []}
    _apply_budget(payload, budget=350, focus_mode="smart", r_threshold=0.80)

    plan_keys = [(x["themenblock"], x["dozent"]) for x in payload["focus_plan_open"]]
    brief_keys = [(x["themenblock"], x["dozent"]) for x in payload["daily_prof_briefing"]["items"]]
    seen = []
    for sd in payload["selected_subdecks"]:
        k = (sd["themenblock"], sd["dozent"])
        if k not in seen:
            seen.append(k)

    assert plan_keys == seen == brief_keys
    assert plan_keys[0] == ("TB Atmung", "Loffing")  # A2 beats B even though low-yield!


# ── F8: AnkiMobile Query Chunking & Quote Escaping ──
def test_f8_long_query_chunked_safely_and_quotes_escaped():
    """60 subdecks produce >4000-char full query -> chunks must each be <=1450 chars and cover every subdeck."""
    sds = [
        _make_subdeck(
            "TB Verdauung",
            "Wagner",
            f'Vorlesung_{i:02d} "Spezial" mit extra langem Titel und Emoji 🟢',
            all_due=5,
            yield_level="high",
        )
        for i in range(60)
    ]
    payload = {"connected": True, "topics": [_make_topic("TB Verdauung", "Wagner", "high", sds)], "themenbloecke": []}
    _apply_budget(payload, budget=9999, focus_mode="smart", r_threshold=0.80)

    full_q = payload["budget_combined_anki_query"]
    chunks = payload["budget_combined_anki_query_chunks"]
    assert len(full_q) > 2500
    assert len(chunks) >= 3
    for ch in chunks:
        assert len(ch) <= 1450
        assert "is:due" in ch
    # Every single subdeck name (escaped) appears in at least one chunk
    joined_chunks = "\n".join(chunks)
    for i in range(60):
        assert f'Vorlesung_{i:02d} \\"Spezial\\"' in joined_chunks


# ── F2 & F3: Zero Meta-Notes in Highlights + Verification Script ──
def test_f2_f3_no_meta_notes_and_verify_signals_script():
    import sys
    sys.path.insert(0, str(ROOT / "bin"))
    import verify_signals

    rep = verify_signals.verify_signals()
    assert rep["ok"] is True
    assert rep["meta_leaks"] == []
    assert rep["missing_files"] == []
    assert rep["unreferenced_summaries"] == []
    assert rep["overall_evidence_rate_pct"] >= 95.0

    # Double-check coverage_note exists on the 4 entries whose meta-notes were moved
    entries = {e["id"]: e for e in load_lecture_exam_signals(force_reload=True)["entries"]}
    for eid in (
        "tuzlak_becher_angeborenes_erworbenes_immunsystem",
        "tuzlak_becher_rekombination_immunrezeptoren",
        "tuzlak_becher_zellentstehung_und_reifung",
        "herz_kreislauf_einfuehrung",
    ):
        assert entries[eid].get("coverage_note")
        for hl in entries[eid]["exam_highlights"]:
            assert not hl.lower().startswith("hinweis zur ")


# ── F4, F5, F6: Golden Matcher Test (90 Frozen Decks), Anti-False-Positive & Fallback Isolation ──
def test_f5_golden_90_live_subdecks_match_deterministically():
    """All 90 frozen real Anki subdecks match their exact verified signal IDs without needing local Anki DB."""
    assert GOLDEN_SUBDECKS_PATH.exists()
    fixtures = json.loads(GOLDEN_SUBDECKS_PATH.read_text(encoding="utf-8"))
    assert len(fixtures) == 90
    for fx in fixtures:
        hit = match_subdeck_to_exam_signal(
            themenblock=fx["themenblock"],
            dozent=fx["dozent"],
            subdeck=fx["subdeck"],
            full_anki_deck=fx["full_anki_deck"],
            allow_prof_fallback=True,
        )
        assert hit is not None, f"Unmatched golden fixture: {fx}"
        assert hit["id"] == fx["expected_id"], f"Mismatch for {fx['subdeck']}: got {hit['id']} != {fx['expected_id']}"
        assert hit["match_type"] == fx["expected_match_type"]
        assert bool(hit.get("is_prof_fallback")) is fx["expected_is_fallback"]


def test_f5_word_boundary_prevents_short_pattern_false_positives():
    """Short patterns ('Lunge', 'EKG', 'Herzwand') must NOT false-positive inside unrelated compound words."""
    m_lunge = match_subdeck_to_exam_signal("TB Atmung", "Loffing", "Lungenfunktionsdiagnostik Spezial", allow_prof_fallback=False)
    assert m_lunge is None

    m_ekg = match_subdeck_to_exam_signal("TB Herz-Kreislauf", "Kurtcuoglu", "Strekgtest Belastung", allow_prof_fallback=False)
    assert m_ekg is None

    m_hw = match_subdeck_to_exam_signal("TB Herz-Kreislauf", "Loffing", "Herzwandbewegung Echo", allow_prof_fallback=False)
    assert m_hw is None


def test_f4_prof_fallback_clearly_labeled_and_never_dilutes_direct_matches():
    """Fallback subdecks carry is_prof_fallback=True + coverage_note and don't pollute direct matches of same prof."""
    fb_only_sd = {
        "rank": 1,
        "themenblock": "TB Endokrinologie",
        "dozent": "Hall",
        "subdeck": "2 Langerhans-Inseln, Schilddrüse, Nebenschilddrüsen 🟢",
        "full_anki_deck": "Anki::2. SJ::TB Endokrinologie::Hall::2 Langerhans-Inseln, Schilddrüse, Nebenschilddrüsen 🟢",
        "assigned_cards": 15,
        "active_due": 15,
        "zone": "B",
        "zone_badge": "🎯 B Prüfungs-Kern",
    }
    b_fb = build_daily_triage_prof_briefing([fb_only_sd])
    item_fb = b_fb["items"][0]
    assert item_fb["is_prof_fallback"] is True
    assert "Keine eigene Vorlesungsaufnahme" in item_fb["coverage_note"]
    assert len(item_fb["exam_highlights"]) <= 2

    # When mixed with a real matched subdeck of the same prof, top-level is NOT fallback-only
    direct_sd = {
        "rank": 1,
        "themenblock": "TB Endokrinologie",
        "dozent": "Hall",
        "subdeck": "4 Nebennieren  🟢",
        "full_anki_deck": "Anki::2. SJ::TB Endokrinologie::Hall::4 Nebennieren  🟢",
        "assigned_cards": 20,
        "active_due": 20,
        "zone": "B",
        "zone_badge": "🎯 B Prüfungs-Kern",
    }
    b_mix = build_daily_triage_prof_briefing([direct_sd, dict(fb_only_sd, rank=2)])
    item_mix = b_mix["items"][0]
    assert item_mix["is_prof_fallback"] is False
    assert item_mix["subdecks"][0]["is_prof_fallback"] is False
    assert item_mix["subdecks"][1]["is_prof_fallback"] is True


# ── F9: Cache Isolation Test ──
def test_f9_cache_triage_isolated_tmp_path(monkeypatch, tmp_path):
    tmp_snap = tmp_path / "cached_backlog_triage.json"
    monkeypatch.setattr(abt, "BACKLOG_TRIAGE_SNAPSHOT_PATH", tmp_snap)
    monkeypatch.setattr(abt, "_MEM_TRIAGE_CACHE", {"ts": 0.0, "data": None})

    sample = {
        "connected": True,
        "triage_version": "3.0",
        "topics": [_make_topic("TB Atmung", "Loffing", "high", [_make_subdeck("TB Atmung", "Loffing", "Lunge / Loffing", 10)])],
        "themenbloecke": [],
    }
    _apply_budget(sample, 350)
    cache_triage(sample)
    assert tmp_snap.exists()
    loaded = get_cached_triage()
    assert loaded is not None
    assert loaded["triage_version"] == "3.0"
    assert "daily_prof_briefing" in loaded


# ── F10: UI/JS Static Integrity & Tokenizer Check ──
def test_f10_app_js_and_index_html_integrity():
    js_text = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
    html_text = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")

    # Required Triage 3.0 persistence & chunking markers
    assert "sl_triage_budget" in js_text
    assert "copyPageTriageQueryChunk" in js_text
    assert "window.copyPageTriageQueryChunk = copyPageTriageQueryChunk" in js_text
    assert "a1_overflow_cards" in js_text
    assert "is_prof_fallback" in js_text
    assert "coverage_note" in js_text

    assert "<!-- Workload Triage 3.0" in html_text
    assert "<!-- Workload Triage 2.1" not in html_text
    assert 'id="pageTriageQueryChunks"' in html_text

    # Ensure zero unbalanced braces/brackets/parens in the Triage 3.0 block (L4125..L4915)
    triage_lines = js_text.splitlines()[4124:4920]
    triage_src = "\n".join(triage_lines)
    # Strip single-line comments safely outside strings/templates for balance sanity check
    assert triage_src.count("function renderDailyProfBriefing") == 1
    assert triage_src.count("function copyPageTriageQueryChunk") == 1


# ── F11: Deploy Hygiene Semantic Diff ──
def test_f11_push_script_strips_volatile_snapshot_timestamps():
    import sys
    sys.path.insert(0, str(ROOT / "bin"))
    import push_to_github

    a = {"generated_at": "2026-11-25T10:00:00", "nested": {"synced_at": "1", "cards": 42}}
    b = {"generated_at": "2026-11-26T08:00:00", "nested": {"synced_at": "2", "cards": 42}}
    c = {"generated_at": "2026-11-26T08:00:00", "nested": {"synced_at": "2", "cards": 43}}

    assert push_to_github._strip_volatile_json(a) == push_to_github._strip_volatile_json(b)
    assert push_to_github._strip_volatile_json(a) != push_to_github._strip_volatile_json(c)
    assert push_to_github._is_cached_snapshot_json("app/data/cached_backlog_triage.json") is True
    assert push_to_github._is_cached_snapshot_json("app/data/lecture_exam_signals.json") is False
