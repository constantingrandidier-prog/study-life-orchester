"""Unit and integration tests for local Anki Desktop detection and synchronization."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.anki_local_service import (
    check_ankiconnect_health,
    clean_deck_name,
    detect_local_anki_profiles,
)

client = TestClient(app)


def test_clean_deck_name():
    """Verify internal Anki hierarchical names are formatted cleanly."""
    raw = "1year\x1f1. Semester\x1fAnatomie: Bewegungsapparat\x1fEinführung\x1fEinführung Gelenke"
    cleaned = clean_deck_name(raw)
    assert "Einführung Gelenke" in cleaned
    assert "1year" not in cleaned


def test_ankiconnect_health_format():
    """Verify check_ankiconnect_health returns valid structured response."""
    res = check_ankiconnect_health(timeout=0.1)
    assert "available" in res
    assert "url" in res
    assert "message" in res
    assert isinstance(res["available"], bool)


def test_detect_local_anki_profiles():
    """Verify local profile detection returns list and detects default profile if present."""
    profiles = detect_local_anki_profiles()
    assert isinstance(profiles, list)
    if profiles:
        primary = profiles[0]
        assert "profile_name" in primary
        assert "collection_path" in primary
        assert "card_count" in primary
        assert primary["card_count"] >= 0


def test_detect_local_anki_endpoint():
    """Verify GET /api/v1/schedule/anki/detect-local endpoint."""
    response = client.get("/api/v1/schedule/anki/detect-local")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "found_profiles" in data
    assert "ankiconnect" in data


def test_local_sync_endpoint():
    """Verify POST /api/v1/schedule/anki/local-sync endpoint with deck_scope."""
    response = client.post("/api/v1/schedule/anki/local-sync?deck_scope=curriculum")
    # If a local profile exists on the test machine, status is 200; otherwise 404
    if response.status_code == 200:
        data = response.json()
        assert data["status"] == "success"
        assert data["mode"] == "local_sqlite"
        assert "total_cards" in data
        assert "deck" in data
        assert data["deck_scope"] == "curriculum"
        assert "total_cards_reviewed" in data
        assert "retention_percentage" in data
    else:
        assert response.status_code == 404


def test_anki_scoped_stats_endpoints():
    """Verify GET /api/v1/schedule/ankiweb/stats and /anki/deck-stats return scoped metrics."""
    res1 = client.get("/api/v1/schedule/ankiweb/stats?deck_scope=curriculum")
    assert res1.status_code == 200
    d1 = res1.json()
    assert "total_cards_reviewed" in d1
    assert "overall_retention_rate" in d1

    res2 = client.get("/api/v1/schedule/anki/deck-stats?deck_scope=module")
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["deck_scope"] in ["module", "curriculum"]
    assert "avg_seconds_per_card" in d2
