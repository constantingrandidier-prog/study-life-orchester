import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.anki_deck_stats import (
    clean_display_name,
    extract_parent_topic,
    get_detailed_deck_stats,
    cache_deck_stats,
    get_cached_deck_stats,
)

client = TestClient(app)

def test_clean_display_name():
    raw = "2. SJ - 1\x1fTB Blut/Immunsystem\x1fEinf\ufffdhrung und Abschluss"
    cleaned = clean_display_name(raw)
    assert " :: " in cleaned
    assert "Einführung und Abschluss" in cleaned

def test_extract_parent_topic():
    raw1 = "2. SJ - 1\x1fTB Blut/Immunsystem\x1fManatschal\x1f3 Blutgerinnung"
    assert extract_parent_topic(raw1) == "TB Blut/Immunsystem"

    raw2 = "2. SJ - 1\x1fTB Atmung\x1fLoffing\x1fLunge"
    assert extract_parent_topic(raw2) == "TB Atmung"

    raw3 = "Vorklinik\x1f2. SJ - 1\x1f1. Biochemie - Mündlich"
    assert "Vorklinik" in extract_parent_topic(raw3)

def test_get_deck_stats_endpoint():
    resp = client.get("/api/v1/schedule/anki/deck-retention-stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "available" in data
    assert "topics" in data
    assert "all_decks" in data
    assert "summary" in data
    assert "total_decks" in data["summary"]
    assert "overall_retention" in data["summary"]

def test_post_deck_stats_sync_endpoint():
    mock_payload = {
        "available": True,
        "topics": [{
            "topic_name": "TB Test",
            "decks_count": 1,
            "total_cards": 50,
            "total_reviews": 100,
            "retention_rate": 85.0,
            "subdecks": [{
                "deck_id": 9999,
                "anki_name": "2. SJ - 1 :: TB Test :: Deck 1",
                "parent_topic": "TB Test",
                "card_count": 50,
                "total_reviews": 100,
                "retention_rate": 85.0,
                "status": "strong",
            }]
        }],
        "all_decks": [{
            "deck_id": 9999,
            "anki_name": "2. SJ - 1 :: TB Test :: Deck 1",
            "parent_topic": "TB Test",
            "card_count": 50,
            "total_reviews": 100,
            "retention_rate": 85.0,
            "status": "strong",
        }],
        "summary": {
            "total_topics": 1,
            "total_decks": 1,
            "total_cards": 50,
            "total_reviews": 100,
            "overall_retention": 85.0,
            "weak_decks_count": 0,
            "neglected_decks_count": 0,
        }
    }
    resp = client.post("/api/v1/schedule/anki/deck-retention-sync", json=mock_payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    cached = get_cached_deck_stats()
    assert cached is not None
    assert cached["summary"]["total_decks"] == 1
    assert cached["summary"]["overall_retention"] == 85.0
