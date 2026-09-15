"""Unit tests for time grid free slot calculation and edge cases."""

from datetime import date, datetime, time
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mock_data import get_mock_events
from app.models import CalendarEvent, DailyScheduleResponse
from app.services.time_grid import build_daily_schedule, calculate_free_slots

TEST_DATE = date(2026, 9, 14)


def test_full_day_free():
    """An empty day must produce one continuous free slot from 07:00 to 23:00 (960 minutes)."""
    free_slots = calculate_free_slots(
        events=[],
        target_date=TEST_DATE,
        day_start_hour=7,
        day_end_hour=23,
    )
    assert len(free_slots) == 1
    slot = free_slots[0]
    assert slot.start_time == datetime(2026, 9, 14, 7, 0)
    assert slot.end_time == datetime(2026, 9, 14, 23, 0)
    assert slot.duration_minutes == 16 * 60  # 960 minutes


def test_no_free_slots_single_full_event():
    """A day with a single event spanning the entire 07:00 to 23:00 window yields zero free slots."""
    events = [
        CalendarEvent(
            title="All-Day Hackathon",
            start_time=datetime(2026, 9, 14, 7, 0),
            end_time=datetime(2026, 9, 14, 23, 0),
        )
    ]
    free_slots = calculate_free_slots(
        events=events,
        target_date=TEST_DATE,
        day_start_hour=7,
        day_end_hour=23,
    )
    assert len(free_slots) == 0


def test_no_free_slots_multiple_covering_events():
    """Multiple contiguous events completely covering 07:00 to 23:00 yield zero free slots."""
    events = [
        CalendarEvent(
            title="Morning Block",
            start_time=datetime(2026, 9, 14, 7, 0),
            end_time=datetime(2026, 9, 14, 12, 0),
        ),
        CalendarEvent(
            title="Afternoon Block",
            start_time=datetime(2026, 9, 14, 12, 0),
            end_time=datetime(2026, 9, 14, 18, 0),
        ),
        CalendarEvent(
            title="Evening Block",
            start_time=datetime(2026, 9, 14, 18, 0),
            end_time=datetime(2026, 9, 14, 23, 0),
        ),
    ]
    free_slots = calculate_free_slots(
        events=events,
        target_date=TEST_DATE,
        day_start_hour=7,
        day_end_hour=23,
    )
    assert len(free_slots) == 0


def test_back_to_back_lectures():
    """
    Back-to-back lectures (e.g. 08:15-10:00 and 10:00-11:45) must merge seamlessly
    without generating a phantom 0-minute free slot.
    """
    events = [
        CalendarEvent(
            title="Lecture A",
            start_time=datetime(2026, 9, 14, 8, 15),
            end_time=datetime(2026, 9, 14, 10, 0),
        ),
        CalendarEvent(
            title="Lecture B",
            start_time=datetime(2026, 9, 14, 10, 0),
            end_time=datetime(2026, 9, 14, 11, 45),
        ),
    ]
    free_slots = calculate_free_slots(
        events=events,
        target_date=TEST_DATE,
        day_start_hour=7,
        day_end_hour=23,
    )

    # Expected 2 free slots:
    # 1. 07:00 - 08:15 (75 minutes)
    # 2. 11:45 - 23:00 (11h15m = 675 minutes)
    assert len(free_slots) == 2

    assert free_slots[0].start_time == datetime(2026, 9, 14, 7, 0)
    assert free_slots[0].end_time == datetime(2026, 9, 14, 8, 15)
    assert free_slots[0].duration_minutes == 75

    assert free_slots[1].start_time == datetime(2026, 9, 14, 11, 45)
    assert free_slots[1].end_time == datetime(2026, 9, 14, 23, 0)
    assert free_slots[1].duration_minutes == 675

    # Verify no slot has 0 minutes duration
    for slot in free_slots:
        assert slot.duration_minutes > 0


def test_overlapping_events():
    """Overlapping events must be merged into one continuous busy block."""
    events = [
        CalendarEvent(
            title="Lab Part 1",
            start_time=datetime(2026, 9, 14, 9, 0),
            end_time=datetime(2026, 9, 14, 10, 30),
        ),
        CalendarEvent(
            title="Lab Part 2 (Overlapping)",
            start_time=datetime(2026, 9, 14, 10, 0),
            end_time=datetime(2026, 9, 14, 11, 30),
        ),
    ]
    free_slots = calculate_free_slots(
        events=events,
        target_date=TEST_DATE,
        day_start_hour=7,
        day_end_hour=23,
    )

    # Busy block is 09:00 to 11:30 (150 minutes)
    assert len(free_slots) == 2
    assert free_slots[0].end_time == datetime(2026, 9, 14, 9, 0)
    assert free_slots[0].duration_minutes == 120  # 07:00 - 09:00

    assert free_slots[1].start_time == datetime(2026, 9, 14, 11, 30)
    assert free_slots[1].duration_minutes == 690  # 11:30 - 23:00


def test_events_outside_window_clamped_and_filtered():
    """Events before 07:00 or after 23:00 must be clamped to the operational window."""
    events = [
        CalendarEvent(
            title="Early Run (Completely Outside)",
            start_time=datetime(2026, 9, 14, 5, 0),
            end_time=datetime(2026, 9, 14, 6, 30),
        ),
        CalendarEvent(
            title="Early Study (Straddles Window Start)",
            start_time=datetime(2026, 9, 14, 6, 0),
            end_time=datetime(2026, 9, 14, 8, 0),
        ),
        CalendarEvent(
            title="Late Social (Straddles Window End)",
            start_time=datetime(2026, 9, 14, 22, 0),
            end_time=datetime(2026, 9, 15, 1, 0),
        ),
    ]
    free_slots = calculate_free_slots(
        events=events,
        target_date=TEST_DATE,
        day_start_hour=7,
        day_end_hour=23,
    )

    # Busy: 07:00-08:00 (clamped) and 22:00-23:00 (clamped)
    # Available free slot: 08:00 to 22:00 (14 hours = 840 minutes)
    assert len(free_slots) == 1
    assert free_slots[0].start_time == datetime(2026, 9, 14, 8, 0)
    assert free_slots[0].end_time == datetime(2026, 9, 14, 22, 0)
    assert free_slots[0].duration_minutes == 840


def test_unsorted_events_handled_correctly():
    """Events passed in non-chronological order should produce the correct sorted free slots."""
    events = [
        CalendarEvent(
            title="Evening Seminar",
            start_time=datetime(2026, 9, 14, 18, 0),
            end_time=datetime(2026, 9, 14, 20, 0),
        ),
        CalendarEvent(
            title="Morning Lecture",
            start_time=datetime(2026, 9, 14, 9, 0),
            end_time=datetime(2026, 9, 14, 11, 0),
        ),
    ]
    free_slots = calculate_free_slots(
        events=events,
        target_date=TEST_DATE,
        day_start_hour=7,
        day_end_hour=23,
    )
    # Slots: 07:00-09:00 (120m), 11:00-18:00 (420m), 20:00-23:00 (180m)
    assert len(free_slots) == 3
    assert [s.duration_minutes for s in free_slots] == [120, 420, 180]


def test_build_daily_schedule_summary():
    """build_daily_schedule returns a full DailyScheduleResponse with correct summary metrics."""
    events = [
        CalendarEvent(
            title="Lecture",
            start_time=datetime(2026, 9, 14, 9, 0),
            end_time=datetime(2026, 9, 14, 11, 0),
        )
    ]
    response = build_daily_schedule(
        events=events,
        target_date=TEST_DATE,
        day_start_hour=7,
        day_end_hour=23,
    )
    assert isinstance(response, DailyScheduleResponse)
    assert response.date == TEST_DATE
    assert response.summary.total_window_minutes == 960
    assert response.summary.total_busy_minutes == 120
    assert response.summary.total_free_minutes == 840
    assert response.summary.fixed_event_count == 1
    assert response.summary.free_slot_count == 2


def test_realistic_mock_student_schedule():
    """Verify mock student schedule produces expected free slots."""
    mock_events = get_mock_events(target_date=TEST_DATE)
    assert len(mock_events) == 4

    free_slots = calculate_free_slots(
        events=mock_events,
        target_date=TEST_DATE,
        day_start_hour=7,
        day_end_hour=23,
    )

    # 08:15-10:00 Lecture
    # 10:15-12:00 Lab
    # 14:15-16:00 Seminar
    # 16:30-18:00 Exercise Session
    # Free slots:
    # 1. 07:00 - 08:15 (75m)
    # 2. 10:00 - 10:15 (15m break)
    # 3. 12:00 - 14:15 (135m lunch + study block)
    # 4. 16:00 - 16:30 (30m break)
    # 5. 18:00 - 23:00 (300m evening study / gym / dinner)
    assert len(free_slots) == 5
    durations = [s.duration_minutes for s in free_slots]
    assert durations == [75, 15, 135, 30, 300]
    assert sum(durations) == 555


def test_api_get_today_endpoint():
    """Verify GET /api/v1/schedule/today endpoint returns HTTP 200 and valid schema."""
    client = TestClient(app)

    # 1. Test with explicit target date that contains scheduled lectures
    response = client.get("/api/v1/schedule/today?target_date=2026-09-14")
    assert response.status_code == 200
    data = response.json()

    assert "date" in data
    assert "fixed_events" in data
    assert "free_slots" in data
    assert len(data["fixed_events"]) > 0
    assert len(data["free_slots"]) > 0

    # Verify event structure
    first_event = data["fixed_events"][0]
    assert "title" in first_event
    assert "start_time" in first_event
    assert "end_time" in first_event

    # Verify free slot structure
    first_slot = data["free_slots"][0]
    assert "start_time" in first_slot
    assert "end_time" in first_slot
    assert "duration_minutes" in first_slot
    assert first_slot["duration_minutes"] > 0

    # 2. Test default call (today's date) returns 200 and valid schema
    today_resp = client.get("/api/v1/schedule/today")
    assert today_resp.status_code == 200
    today_data = today_resp.json()
    assert "date" in today_data
    assert "fixed_events" in today_data
    assert "free_slots" in today_data
    assert isinstance(today_data["fixed_events"], list)
    assert isinstance(today_data["free_slots"], list)
