"""Automated verification tests for Teil 2: Verified Lecture & Exam Signals Knowledge Base."""

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
    assert audit["referenced_summary_count"] >= 37


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
    if cov.get("connected"):
        assert cov["total_leaf_decks"] >= 80
        assert cov["unmatched_count"] == 0
        assert cov["uncovered_professors"] == []
        assert cov["total_coverage_pct"] == 100.0
        assert cov["exact_coverage_pct"] >= 90.0
