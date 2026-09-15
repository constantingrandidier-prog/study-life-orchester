"""Service for calculating non-overlapping free time windows from fixed calendar events."""

from datetime import date, datetime, time, timedelta
from typing import List, Optional, Tuple

from app.models import (
    CalendarEvent,
    DailyScheduleResponse,
    DayWindow,
    FreeSlot,
    ScheduleSummary,
)


def _ensure_compatible_tz(dt: datetime, reference_tz) -> datetime:
    """Ensure datetime has the same timezone awareness as reference."""
    if reference_tz is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=reference_tz)
    if reference_tz is None and dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def calculate_free_slots(
    events: List[CalendarEvent],
    target_date: Optional[date] = None,
    day_start_hour: int = 7,
    day_end_hour: int = 23,
) -> List[FreeSlot]:
    """
    Calculate all non-overlapping free time windows for a given day between
    day_start_hour:00 and day_end_hour:00 (default: 07:00 - 23:00).

    Algorithm handles:
    - Overlapping events (merged into continuous busy blocks)
    - Back-to-back lectures (seamlessly merged with no 0-min phantom gaps)
    - Events outside the operational window (clamped or filtered)
    - Empty schedule (entire day window is returned as a single free slot)
    - Fully booked day (returns an empty list of free slots)
    - Unsorted event lists (automatically sorted)
    """
    # Infer date if not provided
    if target_date is None:
        if events:
            target_date = events[0].start_time.date()
        else:
            target_date = date.today()

    # Detect reference timezone from events
    ref_tz = None
    for ev in events:
        if ev.start_time.tzinfo is not None:
            ref_tz = ev.start_time.tzinfo
            break

    # Construct daily operating window boundaries
    win_start = datetime.combine(target_date, time(hour=day_start_hour, minute=0, second=0))
    if day_end_hour >= 24:
        win_end = datetime.combine(target_date + timedelta(days=1), time(0, 0, 0))
    else:
        win_end = datetime.combine(target_date, time(hour=day_end_hour, minute=0, second=0))

    win_start = _ensure_compatible_tz(win_start, ref_tz)
    win_end = _ensure_compatible_tz(win_end, ref_tz)

    if win_start >= win_end:
        raise ValueError(f"day_start_hour ({day_start_hour}) must be less than day_end_hour ({day_end_hour})")

    # 1. Clamp events to operating window & filter out-of-bound events
    clamped_intervals: List[Tuple[datetime, datetime]] = []
    for ev in events:
        ev_start = _ensure_compatible_tz(ev.start_time, ref_tz)
        ev_end = _ensure_compatible_tz(ev.end_time, ref_tz)

        # Ignore invalid non-positive intervals
        if ev_start >= ev_end:
            continue

        # Check intersection with operating window
        if ev_end > win_start and ev_start < win_end:
            c_start = max(ev_start, win_start)
            c_end = min(ev_end, win_end)
            if c_start < c_end:
                clamped_intervals.append((c_start, c_end))

    # 2. Sort busy intervals chronologically
    clamped_intervals.sort(key=lambda x: (x[0], x[1]))

    # 3. Merge overlapping and adjacent (back-to-back) busy blocks
    merged_busy: List[List[datetime]] = []
    for start, end in clamped_intervals:
        if not merged_busy:
            merged_busy.append([start, end])
        else:
            last = merged_busy[-1]
            if start <= last[1]:  # Overlapping or contiguous (back-to-back)
                last[1] = max(last[1], end)
            else:
                merged_busy.append([start, end])

    # 4. Invert merged busy blocks to calculate free slots
    free_slots: List[FreeSlot] = []
    current_time = win_start

    for b_start, b_end in merged_busy:
        if b_start > current_time:
            duration = int((b_start - current_time).total_seconds() / 60)
            if duration > 0:
                free_slots.append(
                    FreeSlot(
                        start_time=current_time,
                        end_time=b_start,
                        duration_minutes=duration,
                    )
                )
        current_time = max(current_time, b_end)

    # Free time remaining after last event until day end
    if current_time < win_end:
        duration = int((win_end - current_time).total_seconds() / 60)
        if duration > 0:
            free_slots.append(
                FreeSlot(
                    start_time=current_time,
                    end_time=win_end,
                    duration_minutes=duration,
                )
            )

    return free_slots


def build_daily_schedule(
    events: List[CalendarEvent],
    target_date: Optional[date] = None,
    day_start_hour: int = 7,
    day_end_hour: int = 23,
) -> DailyScheduleResponse:
    """
    Build a complete DailyScheduleResponse including fixed events,
    calculated free slots, operational day window, and summary metrics.
    """
    if target_date is None:
        if events:
            target_date = events[0].start_time.date()
        else:
            target_date = date.today()

    free_slots = calculate_free_slots(
        events=events,
        target_date=target_date,
        day_start_hour=day_start_hour,
        day_end_hour=day_end_hour,
    )

    win_start = datetime.combine(target_date, time(day_start_hour, 0, 0))
    if day_end_hour >= 24:
        win_end = datetime.combine(target_date + timedelta(days=1), time(0, 0, 0))
    else:
        win_end = datetime.combine(target_date, time(day_end_hour, 0, 0))

    total_window_minutes = int((win_end - win_start).total_seconds() / 60)
    total_free_minutes = sum(s.duration_minutes for s in free_slots)
    total_busy_minutes = max(0, total_window_minutes - total_free_minutes)

    summary = ScheduleSummary(
        total_window_minutes=total_window_minutes,
        total_busy_minutes=total_busy_minutes,
        total_free_minutes=total_free_minutes,
        fixed_event_count=len(events),
        free_slot_count=len(free_slots),
    )

    day_window = DayWindow(start_time=win_start, end_time=win_end)

    return DailyScheduleResponse(
        date=target_date,
        day_window=day_window,
        fixed_events=events,
        free_slots=free_slots,
        summary=summary,
    )
