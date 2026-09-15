"""Service for computing free time blocks around fixed commitments."""

from datetime import date, datetime, time, timedelta
from typing import List, Tuple
from app.schemas.calendar import (
    DayWindow,
    FixedEvent,
    FreeSlot,
    ScheduleResponse,
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
    events: List[FixedEvent],
    target_date: date,
    day_start_hour: int = 7,
    day_end_hour: int = 23,
) -> ScheduleResponse:
    """
    Given a list of fixed events and a target date, compute all available free slots
    within the operational day window [day_start_hour:00, day_end_hour:00].
    
    Handles:
    - Events outside or partially overlapping the daily window (clamped to window)
    - Overlapping fixed events (merged into continuous busy blocks)
    - Back-to-back events (seamlessly merged without phantom 0-minute gaps)
    - Empty days (entire window is free)
    - Fully booked days (zero free slots)
    """
    # Detect if any event has timezone information to ensure consistent comparisons
    ref_tz = None
    for ev in events:
        if ev.start.tzinfo is not None:
            ref_tz = ev.start.tzinfo
            break

    # Build window boundaries
    win_start = datetime.combine(target_date, time(hour=day_start_hour, minute=0, second=0))
    if day_end_hour == 24:
        win_end = datetime.combine(target_date + timedelta(days=1), time(0, 0, 0))
    else:
        win_end = datetime.combine(target_date, time(hour=day_end_hour, minute=0, second=0))

    win_start = _ensure_compatible_tz(win_start, ref_tz)
    win_end = _ensure_compatible_tz(win_end, ref_tz)

    # 1. Normalize events & clamp to window
    clamped_intervals: List[Tuple[datetime, datetime]] = []
    filtered_events: List[FixedEvent] = []

    for ev in events:
        ev_start = _ensure_compatible_tz(ev.start, ref_tz)
        ev_end = _ensure_compatible_tz(ev.end, ref_tz)

        # Check if event intersects with day window
        if ev_end > win_start and ev_start < win_end:
            c_start = max(ev_start, win_start)
            c_end = min(ev_end, win_end)
            if c_start < c_end:
                clamped_intervals.append((c_start, c_end))
                filtered_events.append(ev)

    # 2. Sort intervals by start datetime
    clamped_intervals.sort(key=lambda x: (x[0], x[1]))

    # 3. Merge overlapping and adjacent busy intervals
    merged_busy: List[List[datetime]] = []
    for start, end in clamped_intervals:
        if not merged_busy:
            merged_busy.append([start, end])
        else:
            last = merged_busy[-1]
            if start <= last[1]:  # Overlapping or contiguous
                last[1] = max(last[1], end)
            else:
                merged_busy.append([start, end])

    # 4. Invert busy intervals to find free slots
    free_slots: List[FreeSlot] = []
    current_time = win_start

    for b_start, b_end in merged_busy:
        if b_start > current_time:
            duration = int((b_start - current_time).total_seconds() / 60)
            if duration > 0:
                free_slots.append(
                    FreeSlot(
                        start=current_time,
                        end=b_start,
                        duration_minutes=duration,
                    )
                )
        current_time = max(current_time, b_end)

    if current_time < win_end:
        duration = int((win_end - current_time).total_seconds() / 60)
        if duration > 0:
            free_slots.append(
                FreeSlot(
                    start=current_time,
                    end=win_end,
                    duration_minutes=duration,
                )
            )

    # 5. Compute summary statistics
    total_window_minutes = int((win_end - win_start).total_seconds() / 60)
    total_busy_minutes = sum(
        int((end - start).total_seconds() / 60) for start, end in merged_busy
    )
    total_free_minutes = sum(slot.duration_minutes for slot in free_slots)

    summary = ScheduleSummary(
        total_window_minutes=total_window_minutes,
        total_busy_minutes=total_busy_minutes,
        total_free_minutes=total_free_minutes,
        fixed_event_count=len(events),
        free_slot_count=len(free_slots),
    )

    day_window = DayWindow(start=win_start, end=win_end)

    return ScheduleResponse(
        date=target_date,
        day_window=day_window,
        fixed_events=events,
        free_slots=free_slots,
        summary=summary,
    )
