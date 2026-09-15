"""Unit tests for calendar parsing (Google Calendar JSON and iCalendar / ICS)."""

from datetime import date, datetime
from app.data.dummy_schedule import (
    DEFAULT_DUMMY_DATE,
    get_dummy_gcal_items,
    get_dummy_ics_string,
)
from app.services.calendar_parser import (
    parse_google_calendar_json,
    parse_ical_content,
)


def test_parse_google_calendar_json():
    """Verify parsing standard Google Calendar JSON items."""
    gcal_items = get_dummy_gcal_items(DEFAULT_DUMMY_DATE)
    events = parse_google_calendar_json(gcal_items, target_date=DEFAULT_DUMMY_DATE)

    assert len(events) == 5
    first = events[0]
    assert first.title == "Lecture: Algorithms & Data Structures"
    assert first.start == datetime(2026, 9, 14, 8, 15)
    assert first.end == datetime(2026, 9, 14, 10, 0)
    assert first.location == "Auditorium 101"


def test_parse_google_calendar_filters_by_date():
    """Events on another date should be filtered out when target_date is given."""
    items = [
        {
            "summary": "Wrong Day Event",
            "start": {"dateTime": "2026-09-15T10:00:00"},
            "end": {"dateTime": "2026-09-15T12:00:00"},
        },
        {
            "summary": "Target Day Event",
            "start": {"dateTime": "2026-09-14T10:00:00"},
            "end": {"dateTime": "2026-09-14T12:00:00"},
        },
    ]
    events = parse_google_calendar_json(items, target_date=date(2026, 9, 14))
    assert len(events) == 1
    assert events[0].title == "Target Day Event"


def test_parse_ical_content():
    """Verify parsing RFC 5545 iCalendar string."""
    ics_str = get_dummy_ics_string(DEFAULT_DUMMY_DATE)
    events = parse_ical_content(ics_str, target_date=DEFAULT_DUMMY_DATE)

    assert len(events) == 5
    assert events[0].title == "Lecture: Algorithms & Data Structures"
    assert events[0].start == datetime(2026, 9, 14, 8, 15)
    assert events[0].end == datetime(2026, 9, 14, 10, 0)
    assert events[0].location == "Auditorium 101"

    last = events[-1]
    assert last.title == "Office Hours: Professor Consultation"
    assert last.start == datetime(2026, 9, 14, 18, 0)
    assert last.end == datetime(2026, 9, 14, 18, 45)
