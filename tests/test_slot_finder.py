"""Unit tests for the free time slot calculation algorithm."""

from datetime import date, datetime
import pytest
from app.data.dummy_schedule import get_dummy_events
from app.schemas.calendar import FixedEvent
from app.services.slot_finder import calculate_free_slots

TARGET_DATE = date(2026, 9, 14)


def test_empty_day_returns_full_window():
    """An empty day should produce one continuous free slot from 07:00 to 23:00 (16 hours = 960 mins)."""
    response = calculate_free_slots(
        events=[],
        target_date=TARGET_DATE,
        day_start_hour=7,
        day_end_hour=23,
    )
    assert len(response.free_slots) == 1
    slot = response.free_slots[0]
    assert slot.start == datetime(2026, 9, 14, 7, 0)
    assert slot.end == datetime(2026, 9, 14, 23, 0)
    assert slot.duration_minutes == 16 * 60
    assert response.summary.total_free_minutes == 960
    assert response.summary.total_busy_minutes == 0


def test_single_event_splits_day_into_two_slots():
    """A single 2-hour event in the morning produces 2 free slots."""
    event = FixedEvent(
        title="Lecture",
        start=datetime(2026, 9, 14, 9, 0),
        end=datetime(2026, 9, 14, 11, 0),
    )
    response = calculate_free_slots(
        events=[event],
        target_date=TARGET_DATE,
        day_start_hour=7,
        day_end_hour=23,
    )
    assert len(response.free_slots) == 2

    # Slot 1: 07:00 - 09:00 (120 mins)
    assert response.free_slots[0].start == datetime(2026, 9, 14, 7, 0)
    assert response.free_slots[0].end == datetime(2026, 9, 14, 9, 0)
    assert response.free_slots[0].duration_minutes == 120

    # Slot 2: 11:00 - 23:00 (720 mins)
    assert response.free_slots[1].start == datetime(2026, 9, 14, 11, 0)
    assert response.free_slots[1].end == datetime(2026, 9, 14, 23, 0)
    assert response.free_slots[1].duration_minutes == 720

    assert response.summary.total_busy_minutes == 120
    assert response.summary.total_free_minutes == 840


def test_overlapping_and_adjacent_events_are_merged():
    """Events that overlap or touch back-to-back should be merged without 0-minute gaps."""
    events = [
        FixedEvent(
            title="Lecture A",
            start=datetime(2026, 9, 14, 9, 0),
            end=datetime(2026, 9, 14, 10, 30),
        ),
        FixedEvent(
            title="Meeting overlapping",
            start=datetime(2026, 9, 14, 10, 0),
            end=datetime(2026, 9, 14, 11, 30),
        ),
        FixedEvent(
            title="Lab adjacent",
            start=datetime(2026, 9, 14, 11, 30),
            end=datetime(2026, 9, 14, 13, 0),
        ),
    ]
    response = calculate_free_slots(
        events=events,
        target_date=TARGET_DATE,
        day_start_hour=7,
        day_end_hour=23,
    )
    # The 3 events merge into one busy block from 09:00 to 13:00 (240 min)
    assert len(response.free_slots) == 2
    assert response.free_slots[0].end == datetime(2026, 9, 14, 9, 0)
    assert response.free_slots[1].start == datetime(2026, 9, 14, 13, 0)
    assert response.summary.total_busy_minutes == 240


def test_clamping_events_outside_window():
    """Events starting before 07:00 or ending after 23:00 are clamped properly."""
    events = [
        FixedEvent(
            title="Early run",
            start=datetime(2026, 9, 14, 6, 0),
            end=datetime(2026, 9, 14, 8, 0),
        ),
        FixedEvent(
            title="Late party",
            start=datetime(2026, 9, 14, 22, 0),
            end=datetime(2026, 9, 15, 1, 0),
        ),
        FixedEvent(
            title="Completely outside",
            start=datetime(2026, 9, 14, 3, 0),
            end=datetime(2026, 9, 14, 5, 0),
        ),
    ]
    response = calculate_free_slots(
        events=events,
        target_date=TARGET_DATE,
        day_start_hour=7,
        day_end_hour=23,
    )
    # Busy: 07:00-08:00 (60 min) and 22:00-23:00 (60 min)
    assert len(response.free_slots) == 1
    slot = response.free_slots[0]
    assert slot.start == datetime(2026, 9, 14, 8, 0)
    assert slot.end == datetime(2026, 9, 14, 22, 0)
    assert slot.duration_minutes == 14 * 60
    assert response.summary.total_busy_minutes == 120


def test_fully_booked_day():
    """A day with a continuous event spanning the entire window has zero free slots."""
    events = [
        FixedEvent(
            title="Hackathon",
            start=datetime(2026, 9, 14, 7, 0),
            end=datetime(2026, 9, 14, 23, 0),
        )
    ]
    response = calculate_free_slots(
        events=events,
        target_date=TARGET_DATE,
        day_start_hour=7,
        day_end_hour=23,
    )
    assert len(response.free_slots) == 0
    assert response.summary.total_free_minutes == 0
    assert response.summary.total_busy_minutes == 960


def test_realistic_university_schedule_dummy():
    """Verify calculation for the realistic student dummy schedule."""
    events = get_dummy_events(TARGET_DATE)
    response = calculate_free_slots(
        events=events,
        target_date=TARGET_DATE,
        day_start_hour=7,
        day_end_hour=23,
    )
    assert len(response.fixed_events) == 5
    # Expected free slots:
    # 1. 07:00 - 08:15 (75m)
    # 2. 10:00 - 10:15 (15m)
    # 3. 12:00 - 13:00 (60m) - Lunch break
    # 4. 14:30 - 16:00 (90m) - Afternoon study slot
    # 5. 18:45 - 23:00 (255m) - Evening slot
    assert len(response.free_slots) == 5
    expected_durations = [75, 15, 60, 90, 255]
    assert [s.duration_minutes for s in response.free_slots] == expected_durations
    assert response.summary.total_free_minutes == sum(expected_durations)
    assert response.summary.total_free_minutes + response.summary.total_busy_minutes == 960
