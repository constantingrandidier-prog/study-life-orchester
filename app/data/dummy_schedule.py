"""Realistic university day dummy data for testing."""

from datetime import date, datetime
from typing import Any, Dict, List
from app.schemas.calendar import FixedEvent

DEFAULT_DUMMY_DATE = date(2026, 9, 14)  # Monday


def get_dummy_events(target_date: date = DEFAULT_DUMMY_DATE) -> List[FixedEvent]:
    """Generate realistic fixed university events for the given date."""
    d = target_date
    return [
        FixedEvent(
            title="Lecture: Algorithms & Data Structures",
            start=datetime(d.year, d.month, d.day, 8, 15),
            end=datetime(d.year, d.month, d.day, 10, 0),
            location="Auditorium 101",
            description="Graph algorithms: Dijkstra, Bellman-Ford, and complexity proofs."
        ),
        FixedEvent(
            title="Exercise Session: Software Engineering",
            start=datetime(d.year, d.month, d.day, 10, 15),
            end=datetime(d.year, d.month, d.day, 12, 0),
            location="Lab Room 3B",
            description="Hands-on git branching and CI/CD workflow exercises."
        ),
        FixedEvent(
            title="Group Meeting: Distributed Systems Project",
            start=datetime(d.year, d.month, d.day, 13, 0),
            end=datetime(d.year, d.month, d.day, 14, 30),
            location="Library Study Room 4",
            description="Sprint planning and consensus algorithm review."
        ),
        FixedEvent(
            title="Lecture: Machine Learning",
            start=datetime(d.year, d.month, d.day, 16, 0),
            end=datetime(d.year, d.month, d.day, 18, 0),
            location="Main Building Room 204",
            description="Neural network backpropagation and gradient descent optimization."
        ),
        FixedEvent(
            title="Office Hours: Professor Consultation",
            start=datetime(d.year, d.month, d.day, 18, 0),
            end=datetime(d.year, d.month, d.day, 18, 45),
            location="Faculty Office 4.12",
            description="Clarification of midterm exam questions."
        ),
    ]


def get_dummy_gcal_items(target_date: date = DEFAULT_DUMMY_DATE) -> List[Dict[str, Any]]:
    """Return realistic university events formatted as Google Calendar API items."""
    d_str = target_date.isoformat()
    return [
        {
            "id": "event_alg_01",
            "summary": "Lecture: Algorithms & Data Structures",
            "description": "Graph algorithms: Dijkstra, Bellman-Ford, and complexity proofs.",
            "location": "Auditorium 101",
            "start": {"dateTime": f"{d_str}T08:15:00"},
            "end": {"dateTime": f"{d_str}T10:00:00"},
            "status": "confirmed"
        },
        {
            "id": "event_se_02",
            "summary": "Exercise Session: Software Engineering",
            "description": "Hands-on git branching and CI/CD workflow exercises.",
            "location": "Lab Room 3B",
            "start": {"dateTime": f"{d_str}T10:15:00"},
            "end": {"dateTime": f"{d_str}T12:00:00"},
            "status": "confirmed"
        },
        {
            "id": "event_ds_03",
            "summary": "Group Meeting: Distributed Systems Project",
            "description": "Sprint planning and consensus algorithm review.",
            "location": "Library Study Room 4",
            "start": {"dateTime": f"{d_str}T13:00:00"},
            "end": {"dateTime": f"{d_str}T14:30:00"},
            "status": "confirmed"
        },
        {
            "id": "event_ml_04",
            "summary": "Lecture: Machine Learning",
            "description": "Neural network backpropagation and gradient descent optimization.",
            "location": "Main Building Room 204",
            "start": {"dateTime": f"{d_str}T16:00:00"},
            "end": {"dateTime": f"{d_str}T18:00:00"},
            "status": "confirmed"
        },
        {
            "id": "event_oh_05",
            "summary": "Office Hours: Professor Consultation",
            "description": "Clarification of midterm exam questions.",
            "location": "Faculty Office 4.12",
            "start": {"dateTime": f"{d_str}T18:00:00"},
            "end": {"dateTime": f"{d_str}T18:45:00"},
            "status": "confirmed"
        }
    ]


def get_dummy_ics_string(target_date: date = DEFAULT_DUMMY_DATE) -> str:
    """Return realistic university events formatted as an RFC 5545 iCalendar string."""
    d_compact = target_date.strftime("%Y%m%d")
    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Study-Life Orchestrator//University Schedule//EN
CALSCALE:GREGORIAN
BEGIN:VEVENT
UID:dummy-alg-1@orchestrator
SUMMARY:Lecture: Algorithms & Data Structures
DESCRIPTION:Graph algorithms: Dijkstra and Bellman-Ford.
LOCATION:Auditorium 101
DTSTART:{d_compact}T081500
DTEND:{d_compact}T100000
END:VEVENT
BEGIN:VEVENT
UID:dummy-se-2@orchestrator
SUMMARY:Exercise Session: Software Engineering
DESCRIPTION:CI/CD workflows and git.
LOCATION:Lab Room 3B
DTSTART:{d_compact}T101500
DTEND:{d_compact}T120000
END:VEVENT
BEGIN:VEVENT
UID:dummy-ds-3@orchestrator
SUMMARY:Group Meeting: Distributed Systems Project
DESCRIPTION:Sprint planning and consensus.
LOCATION:Library Study Room 4
DTSTART:{d_compact}T130000
DTEND:{d_compact}T143000
END:VEVENT
BEGIN:VEVENT
UID:dummy-ml-4@orchestrator
SUMMARY:Lecture: Machine Learning
DESCRIPTION:Neural networks and backpropagation.
LOCATION:Main Building Room 204
DTSTART:{d_compact}T160000
DTEND:{d_compact}T180000
END:VEVENT
BEGIN:VEVENT
UID:dummy-oh-5@orchestrator
SUMMARY:Office Hours: Professor Consultation
DESCRIPTION:Clarification of midterm exam questions.
LOCATION:Faculty Office 4.12
DTSTART:{d_compact}T180000
DTEND:{d_compact}T184500
END:VEVENT
END:VCALENDAR"""
