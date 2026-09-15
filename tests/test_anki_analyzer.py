"""Unit tests for Anki deck analysis, topic-to-lecture matching, and smart study orchestration."""

from datetime import date, datetime
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    AnkiTopic,
    CalendarEvent,
    ManualActivity,
)
from app.services.anki_analyzer import (
    match_topics_with_lectures,
    orchestrate_study_plan,
    parse_anki_text_content,
    redistribute_uncompleted_cards,
)

TARGET_DATE = date(2026, 9, 14)


def test_parse_anki_text_content():
    """Verify parsing of tab-separated notes into topics and card counts."""
    tsv_content = (
        "# Anki Export\n"
        "What is Dijkstra's algorithm?\tShortest path algorithm\talgorithms::graphs\n"
        "What is a B-Tree?\tSelf balancing search tree\talgorithms::trees\n"
        "What is a deadlock?\tCircular wait condition\tsystems::concurrency\n"
    )
    summary = parse_anki_text_content(tsv_content, filename="cs_exam.txt")
    assert summary.total_cards == 3
    assert len(summary.topics) > 0
    topic_names = [t.name for t in summary.topics]
    assert any("Algorithms" in name or "Trees" in name or "Graphs" in name for name in topic_names)


def test_match_topics_with_lectures():
    """Verify that topics matching upcoming lectures receive high relevance scores."""
    topics = [
        AnkiTopic(
            name="Graph Algorithms",
            card_count=30,
            estimated_minutes=25,
            urgency="normal",
        ),
        AnkiTopic(
            name="Ancient Roman History",
            card_count=15,
            estimated_minutes=15,
            urgency="normal",
        ),
    ]

    events = [
        CalendarEvent(
            title="Lecture: Advanced Algorithms & Data Structures",
            start_time=datetime(2026, 9, 14, 8, 15),
            end_time=datetime(2026, 9, 14, 10, 0),
            location="Auditorium 1",
            description="Focus on graph search and shortest path",
        )
    ]

    analyzed = match_topics_with_lectures(topics, events)

    # Graph algorithms should be matched with the lecture and have higher relevance
    graph_topic = next(t for t in analyzed if "Graph" in t.name)
    assert graph_topic.matched_lecture == "Lecture: Advanced Algorithms & Data Structures"
    assert graph_topic.relevance_score > 0.7
    assert graph_topic.urgency == "high"


def test_orchestrate_study_plan_places_blocks_in_free_slots():
    """Verify smart study planning places study sessions into available free windows."""
    events = [
        CalendarEvent(
            title="Algorithms Lecture",
            start_time=datetime(2026, 9, 14, 10, 0),
            end_time=datetime(2026, 9, 14, 12, 0),
        )
    ]
    activities = [
        ManualActivity(
            title="Lunch",
            category="meal",
            start_time=datetime(2026, 9, 14, 12, 0),
            end_time=datetime(2026, 9, 14, 13, 0),
        )
    ]
    topics = [
        AnkiTopic(
            name="Graph Algorithms",
            card_count=30,
            estimated_minutes=30,
            matched_lecture="Algorithms Lecture",
            relevance_score=0.9,
            urgency="high",
        )
    ]

    response = orchestrate_study_plan(
        events=events,
        manual_activities=activities,
        anki_topics=topics,
        target_date=TARGET_DATE,
        day_start_hour=7,
        day_end_hour=23,
    )

    assert len(response.study_sessions) >= 1
    session = response.study_sessions[0]
    assert session.topic_name == "Graph Algorithms"
    assert session.duration_minutes > 0
    assert len(response.recommendations) > 0


def test_api_upload_and_custom_endpoints():
    """Integration test for /custom and /anki/orchestrate endpoints."""
    client = TestClient(app)

    # Test /custom schedule recalculation
    custom_payload = {
        "target_date": "2026-09-14",
        "fixed_events": [
            {
                "title": "Math",
                "start_time": "2026-09-14T09:00:00",
                "end_time": "2026-09-14T11:00:00",
            }
        ],
        "manual_activities": [
            {
                "title": "Gym",
                "category": "gym",
                "start_time": "2026-09-14T11:30:00",
                "end_time": "2026-09-14T13:00:00",
            }
        ],
    }
    res = client.post("/api/v1/schedule/custom", json=custom_payload)
    assert res.status_code == 200
    data = res.json()
    assert len(data["free_slots"]) >= 2

    # Test GET / serves JSON for API clients and HTML for browser clients
    root_res = client.get("/")
    assert root_res.status_code == 200
    assert "Study-Life Orchestrator" in root_res.text

    # Test browser GET with text/html and direct /app route
    html_res = client.get("/", headers={"Accept": "text/html"})
    assert html_res.status_code == 200
    assert "StudyLife Orchestrator" in html_res.text

    app_res = client.get("/app")
    assert app_res.status_code == 200
    assert "StudyLife Orchestrator" in app_res.text


def test_rollover_uncompleted_cards():
    """Verify redistribution of incomplete cards across upcoming days preserving clusters."""
    topics = [
        AnkiTopic(
            name="Graph Algorithms",
            cluster_name="Theoretische Informatik & Algorithmen",
            card_count=30,
            estimated_minutes=25,
            urgency="high",
        ),
        AnkiTopic(
            name="Operating Systems",
            cluster_name="Systemnahe Programmierung & OS",
            card_count=20,
            estimated_minutes=15,
            urgency="high",
        ),
    ]

    rollover = redistribute_uncompleted_cards(topics, target_date=TARGET_DATE, days_ahead=3)
    assert rollover.total_uncompleted_cards == 50
    assert len(rollover.redistribution) >= 2
    # Ensure tomorrow has allocated cards
    tomorrow_items = [r for r in rollover.redistribution if r.day_offset == 1]
    assert len(tomorrow_items) >= 1
    assert tomorrow_items[0].cards_count > 0
    assert len(rollover.advice) > 0


def test_api_rollover_endpoint():
    """Integration test for POST /api/v1/schedule/anki/rollover."""
    client = TestClient(app)
    payload = {
        "target_date": "2026-09-14",
        "uncompleted_topics": [
            {
                "name": "Dynamic Programming",
                "cluster_name": "Theoretische Informatik",
                "card_count": 25,
                "estimated_minutes": 20,
            }
        ],
        "days_ahead": 3,
    }
    res = client.post("/api/v1/schedule/anki/rollover", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["total_uncompleted_cards"] == 25
    assert len(data["redistribution"]) > 0
    assert "erfolgreich" in data["message"]

