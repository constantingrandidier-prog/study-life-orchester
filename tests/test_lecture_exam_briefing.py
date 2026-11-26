"""Automated verification tests for Teil 2 & 3: Verified Lecture & Exam Signals Knowledge Base."""

import json
import pytest

from app.services.lecture_exam_briefing_service import (
    match_subdeck_to_exam_signal,
    validate_signals_against_transcripts,
    verify_anki_subdeck_coverage,
)


def test_lecture_exam_signals_integrity_against_transcripts():
    """Every reference in lecture_exam_signals.json must point to a real transcript summary."""
    audit = validate_signals_against_transcripts()
    assert audit["valid"] is True
    assert audit["missing_files"] == []
    assert audit["invalid_entries"] == []
    assert audit["duplicate_ids"] == []
    assert audit["entry_count"] >= 80
    assert audit["referenced_summary_count"] == audit["total_summary_files"]
    assert audit["unreferenced_summaries"] == []


def test_numbered_and_emoji_subdeck_disambiguation():
    """Numbered subdeck pairs and emoji-decorated Anki names must match their exact entries."""
    m1 = match_subdeck_to_exam_signal("TB Atmung", "Loffing", "Trachea und Bronchien / Loffing")
    m2 = match_subdeck_to_exam_signal("TB Atmung", "Loffing", "Trachea und Bronchien 2 / Loffing")
    assert m1 is not None and m1["id"] == "loffing_trachea_und_bronchien"
    assert m2 is not None and m2["id"] == "loffing_trachea_und_bronchien_2"

    a1 = match_subdeck_to_exam_signal("TB Atmung", "Loffing", "Anatomie der Atmungsorgane / Loffing")
    a2 = match_subdeck_to_exam_signal("TB Atmung", "Loffing", "Anatomie der Atmungsorgane II / Loffing")
    assert a1 is not None and a1["id"] == "loffing_anatomie_atmungsorgane"
    assert a2 is not None and a2["id"] == "loffing_anatomie_atmungsorgane_ii"

    gastro = match_subdeck_to_exam_signal("TB Verdauung", "Rogler", "1 Gastroenterolgie ⚫")
    assert gastro is not None and gastro["match_type"] in ("exact_subdeck", "pattern_subdeck")
    assert len(gastro["exam_highlights"]) >= 1

    vit = match_subdeck_to_exam_signal("TB Verdauung", "Dutzler", "1 fettlösliche Vitamine 🟢")
    assert vit is not None and vit["id"] == "dutzler_fettloesliche_vitamine"

    hypo = match_subdeck_to_exam_signal(
        "TB Endokrinologie", "Jelezarov", "3 Hypothalamische und hypophyäre Hormone 🟢"
    )
    assert hypo is not None and hypo["id"] == "jelezarov_hypothalamus_hypophyse"


def test_live_anki_subdeck_coverage_100_percent():
    """Every active 2. SJ Anki professor & leaf deck must be covered cleanly with zero unmatched decks."""
    cov = verify_anki_subdeck_coverage()
    if not cov.get("connected"):
        pytest.skip("Lokale Anki-DB nicht verbunden")
    assert cov["total_leaf_decks"] >= 80
    assert cov["unmatched_count"] == 0
    assert cov["uncovered_professors"] == []
    assert cov["total_coverage_pct"] == 100.0
    assert cov["exact_coverage_pct"] >= 90.0


def test_daily_prof_briefing_strict_today_scope_and_budget_scaling(monkeypatch, tmp_path):
    """Teil 3 (a) & (b): Briefing contains ONLY today's selected subdecks and grows synchronously from 350 to 600."""
    from fastapi.testclient import TestClient
    from app.main import app
    import app.services.anki_backlog_triage as abt

    # Isolate snapshot writes to tmp_path so tests never overwrite the real repo snapshot
    tmp_snap = tmp_path / "cached_backlog_triage.json"
    monkeypatch.setattr(abt, "BACKLOG_TRIAGE_SNAPSHOT_PATH", tmp_snap)
    monkeypatch.setattr(abt, "_MEM_TRIAGE_CACHE", {"ts": 0.0, "data": None})

    client = TestClient(app)
    r350 = client.get("/api/v1/schedule/anki/backlog-triage?max_capacity=350").json()
    r600 = client.get("/api/v1/schedule/anki/backlog-triage?max_capacity=600").json()

    b350 = r350.get("daily_prof_briefing")
    b600 = r600.get("daily_prof_briefing")
    assert b350 is not None and b600 is not None

    # (a) Exact 1:1 correspondence between selected_subdecks and daily_prof_briefing subdecks
    sel_350_set = {sd["full_anki_deck"] for sd in r350.get("selected_subdecks", [])}
    brief_350_set = {
        s["full_anki_deck"]
        for item in b350.get("items", [])
        for s in item.get("subdecks", [])
    }
    assert brief_350_set == sel_350_set
    assert b350["total_subdecks_covered"] == len(r350.get("selected_subdecks", []))
    assert b350["total_briefing_cards"] == r350["budget_accumulated_cards"]

    # Every item must have rank #1, #2, ... and real exam_highlights
    ranks = [item["rank"] for item in b350.get("items", [])]
    assert ranks == list(range(1, len(ranks) + 1))
    for item in b350.get("items", []):
        assert len(item["exam_highlights"]) >= 1
        assert item["header_summary"]

    # (b) Growing budget 350 -> 600 grows briefing synchronously
    sel_600_set = {sd["full_anki_deck"] for sd in r600.get("selected_subdecks", [])}
    brief_600_set = {
        s["full_anki_deck"]
        for item in b600.get("items", [])
        for s in item.get("subdecks", [])
    }
    assert brief_600_set == sel_600_set
    assert sel_350_set.issubset(sel_600_set)
    if r600["active_focus_pool_due"] > 350:
        assert b600["total_briefing_cards"] > b350["total_briefing_cards"]
        assert b600["total_subdecks_covered"] >= b350["total_subdecks_covered"]


def test_daily_prof_briefing_cloud_sync_and_snapshot_parity(monkeypatch, tmp_path):
    """Teil 3 (c): Cloud snapshot + /anki/triage-sync + cached _apply_budget produce identical live briefings on Render/iPad."""
    from fastapi.testclient import TestClient
    from app.main import app
    import app.services.anki_backlog_triage as abt
    from app.services.anki_backlog_triage import (
        _apply_budget,
        calculate_backlog_triage,
        get_cached_triage,
    )

    # Isolate snapshot writes so the real repo cached_backlog_triage.json is never mutated by tests
    tmp_snap = tmp_path / "cached_backlog_triage.json"
    monkeypatch.setattr(abt, "BACKLOG_TRIAGE_SNAPSHOT_PATH", tmp_snap)
    monkeypatch.setattr(abt, "_MEM_TRIAGE_CACHE", {"ts": 0.0, "data": None})

    client = TestClient(app)
    live_350 = calculate_backlog_triage(max_capacity=350)
    if not live_350.get("connected"):
        pytest.skip("Lokale Anki-DB nicht verbunden")
    assert "daily_prof_briefing" in live_350

    # Sync payload via /api/v1/schedule/anki/triage-sync (even if daily_prof_briefing stripped, backend must rebuild it)
    payload_without_briefing = json.loads(json.dumps(live_350))
    payload_without_briefing.pop("daily_prof_briefing", None)
    resp = client.post("/api/v1/schedule/anki/triage-sync", json=payload_without_briefing)
    assert resp.status_code == 200
    assert resp.json().get("cached") is True

    # Verify isolated snapshot and get_cached_triage() both include daily_prof_briefing
    assert tmp_snap.exists()
    snap = json.loads(tmp_snap.read_text(encoding="utf-8"))
    assert "daily_prof_briefing" in snap
    assert len(snap["daily_prof_briefing"]["items"]) == len(live_350["daily_prof_briefing"]["items"])

    cached = get_cached_triage()
    assert cached is not None and "daily_prof_briefing" in cached

    # Simulate Render/iPad switching budget from 350 -> 600 purely on the cached snapshot
    cached_copy = json.loads(json.dumps(cached))
    _apply_budget(cached_copy, 600, focus_mode="smart", r_threshold=0.80)
    live_600 = calculate_backlog_triage(max_capacity=600)
    assert cached_copy["daily_prof_briefing"]["total_subdecks_covered"] == live_600["daily_prof_briefing"]["total_subdecks_covered"]
    assert cached_copy["daily_prof_briefing"]["total_briefing_cards"] == live_600["daily_prof_briefing"]["total_briefing_cards"]

