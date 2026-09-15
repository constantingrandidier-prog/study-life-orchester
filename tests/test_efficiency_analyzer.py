"""Unit tests for Lecture ROI and Learning Efficiency Analyzer."""

import pytest
from app.db.repository import get_study_session_logs, log_study_session
from app.services.efficiency_analyzer import (
    DEFAULT_MODULE_BENCHMARKS,
    analyze_lecture_efficiency,
    ensure_baseline_logs_exist,
)


def test_ensure_baseline_logs_exist():
    """Verify default benchmark baseline logs are seeded into the database."""
    ensure_baseline_logs_exist()
    logs = get_study_session_logs()
    assert len(logs) >= len(DEFAULT_MODULE_BENCHMARKS) * 2

    # Check that both lecture_attended True and False exist
    attended = [l for l in logs if l["lecture_attended"] == 1]
    not_attended = [l for l in logs if l["lecture_attended"] == 0]
    assert len(attended) > 0
    assert len(not_attended) > 0


def test_analyze_lecture_efficiency_structure():
    """Verify comprehensive structure and calculation of analyze_lecture_efficiency."""
    result = analyze_lecture_efficiency()

    assert "overall_summary" in result
    assert "modules" in result

    summary = result["overall_summary"]
    assert "overall_speedup_ratio" in summary
    assert "avg_seconds_with_lecture" in summary
    assert "avg_seconds_without_lecture" in summary
    assert "retention_with_lecture" in summary
    assert "retention_without_lecture" in summary
    assert "conclusion" in summary

    assert summary["overall_speedup_ratio"] > 0
    assert summary["avg_seconds_with_lecture"] > 0
    assert summary["avg_seconds_without_lecture"] > 0

    modules = result["modules"]
    assert len(modules) >= len(DEFAULT_MODULE_BENCHMARKS)

    for mod in modules:
        assert "module_name" in mod
        assert "speedup_ratio" in mod
        assert "retention_delta_percent" in mod
        assert "verdict" in mod
        assert "verdict_badge" in mod
        assert "efficiency_summary" in mod
        assert "recommendation" in mod
        assert "with_lecture" in mod
        assert "without_lecture" in mod
        assert "time_saved_on_anki_mins" in mod
        assert "net_time_balance_mins" in mod


def test_custom_study_session_logging():
    """Verify logging a new study session affects the efficiency calculations."""
    test_module = "Test Spezialmodul Quantencomputing"
    
    # Log with lecture: super fast (10s), high retention (98%)
    log_study_session(
        topic_name=f"{test_module} - Vorlesungsnachbereitung",
        module_name=test_module,
        duration_minutes=15,
        cards_reviewed=90,
        seconds_per_card=10.0,
        retention_rate=0.98,
        lecture_attended=True,
    )

    # Log without lecture: slow (45s), lower retention (60%)
    log_study_session(
        topic_name=f"{test_module} - Skript Selbststudium",
        module_name=test_module,
        duration_minutes=60,
        cards_reviewed=80,
        seconds_per_card=45.0,
        retention_rate=0.60,
        lecture_attended=False,
    )

    result = analyze_lecture_efficiency()
    mod_report = next((m for m in result["modules"] if m["module_name"] == test_module), None)

    assert mod_report is not None
    assert mod_report["speedup_ratio"] == round(45.0 / 10.0, 2)
    assert mod_report["retention_delta_percent"] == round((0.98 - 0.60) * 100, 1)
    assert "VORLESUNG BESUCHEN" in mod_report["verdict"]
    assert mod_report["verdict_badge"] == "success"
