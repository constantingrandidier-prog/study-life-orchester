from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_advisor_all_lectures():
    response = client.get("/api/v1/schedule/advisor/all")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 38
    assert len(data["lectures"]) == 38
    # Check sample lecture structure
    sample = data["lectures"][0]
    assert "title" in sample
    assert "recommendation" in sample
    assert "tradeoff_reason" in sample
    assert "anki_facts" in sample


def test_advisor_search_topics():
    # Test 1: Hämoglobin
    resp = client.get("/api/v1/schedule/advisor/search?q=Hämoglobin")
    assert resp.status_code == 200
    d = resp.json()
    assert d["summary"]["total_matching"] >= 1
    assert "Hämoglobin" in d["top_match"]["title"]
    assert d["top_match"]["recommendation"] == "1.2x"

    # Test 2: Komplement (should be Skip 0x)
    resp2 = client.get("/api/v1/schedule/advisor/search?q=Komplementsystem")
    assert resp2.status_code == 200
    d2 = resp2.json()
    assert "Skip" in d2["top_match"]["recommendation"]
    assert len(d2["top_match"]["anki_facts"]) == 3

    # Test 3: Fasten (should be Audio-Only candidate)
    resp3 = client.get("/api/v1/schedule/advisor/search?q=Fasten")
    assert resp3.status_code == 200
    d3 = resp3.json()
    assert d3["top_match"]["is_audio_only"] is True


def test_advisor_filter_mode():
    resp = client.get("/api/v1/schedule/advisor/search?mode=skip")
    assert resp.status_code == 200
    d = resp.json()
    for item in d["results"]:
        assert "Skip" in item["recommendation"]


def test_advisor_typo_search_and_timestamps():
    # Test user query with typo in lecturer: 'TB Blut/ immunsystem von manataschal'
    resp = client.get("/api/v1/schedule/advisor/search?q=TB%20Blut/%20immunsystem%20von%20manataschal&cards=100")
    assert resp.status_code == 200
    d = resp.json()
    
    # Must find multiple matches
    assert len(d["top_matches"]) >= 3
    # Top matches must all be Prof. Manatschal
    for m in d["top_matches"][:4]:
        assert "Manatschal" in m["lecturer"]
        assert "1. Blut & Immunsystem" in m["module"]
        # Must have timestamp guidance
        guidance = m["timestamp_guidance"]
        assert guidance["target_cards"] == 100
        assert guidance["start_timestamp"] == "00:00"
        assert ":" in guidance["end_timestamp"]
        assert guidance["saved_minutes"] > 0
        assert len(m["chapters"]) >= 3

