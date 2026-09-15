"""Service for parsing Google Calendar JSON and iCal/ICS formats into FixedEvent models."""

from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional
import httpx
import icalendar
from dateutil import parser as dt_parser
from app.schemas.calendar import FixedEvent


def _to_datetime(val: Any, default_time: time = time(0, 0, 0)) -> datetime:
    """Convert a date, datetime, or ISO string to a datetime instance."""
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime.combine(val, default_time)
    if isinstance(val, str):
        parsed = dt_parser.isoparse(val)
        if isinstance(parsed, datetime):
            return parsed
        return datetime.combine(parsed, default_time)
    raise ValueError(f"Cannot convert {val!r} to datetime")


def parse_google_calendar_json(
    items: List[Dict[str, Any]],
    target_date: Optional[date] = None,
) -> List[FixedEvent]:
    """
    Parse a list of Google Calendar event items into FixedEvent objects.
    Optionally filters to events that intersect the target_date.
    """
    fixed_events: List[FixedEvent] = []

    for item in items:
        # Ignore cancelled events
        if item.get("status") == "cancelled":
            continue

        summary = item.get("summary", "Untitled Event")
        start_dict = item.get("start", {})
        end_dict = item.get("end", {})

        start_val = start_dict.get("dateTime") or start_dict.get("date")
        end_val = end_dict.get("dateTime") or end_dict.get("date")

        if not start_val or not end_val:
            continue

        # If it's a full-day event (date only), default start is 00:00 and end is next day 00:00
        start_dt = _to_datetime(start_val, default_time=time(0, 0, 0))
        end_dt = _to_datetime(end_val, default_time=time(23, 59, 59))

        # Check if event touches target_date
        if target_date:
            day_start = datetime.combine(target_date, time(0, 0, 0))
            day_end = datetime.combine(target_date, time(23, 59, 59))

            # Make naive or tz-compatible
            if start_dt.tzinfo is not None:
                day_start = day_start.replace(tzinfo=start_dt.tzinfo)
                day_end = day_end.replace(tzinfo=start_dt.tzinfo)

            if end_dt <= day_start or start_dt >= day_end:
                continue

        fixed_events.append(
            FixedEvent(
                title=summary,
                start=start_dt,
                end=end_dt,
                location=item.get("location"),
                description=item.get("description"),
            )
        )

    return fixed_events


def parse_ical_content(
    ics_text: str,
    target_date: Optional[date] = None,
) -> List[FixedEvent]:
    """
    Parse an iCalendar (.ics) string into FixedEvent objects.
    Optionally filters to events that intersect target_date.
    """
    cal = icalendar.Calendar.from_ical(ics_text)
    fixed_events: List[FixedEvent] = []

    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        summary = str(component.get("summary", "Untitled Event"))
        location = str(component.get("location")) if component.get("location") else None
        description = str(component.get("description")) if component.get("description") else None

        dtstart_prop = component.get("dtstart")
        dtend_prop = component.get("dtend")

        if not dtstart_prop:
            continue

        raw_start = dtstart_prop.dt
        start_dt = _to_datetime(raw_start, default_time=time(0, 0, 0))

        if dtend_prop:
            raw_end = dtend_prop.dt
            end_dt = _to_datetime(raw_end, default_time=time(23, 59, 59))
        else:
            # If no end time, default to start + duration or start + 1 hour
            duration_prop = component.get("duration")
            if duration_prop:
                end_dt = start_dt + duration_prop.dt
            else:
                end_dt = start_dt + timedelta(hours=1)

        # Check filter by target_date
        if target_date:
            day_start = datetime.combine(target_date, time(0, 0, 0))
            day_end = datetime.combine(target_date, time(23, 59, 59))

            if start_dt.tzinfo is not None:
                day_start = day_start.replace(tzinfo=start_dt.tzinfo)
                day_end = day_end.replace(tzinfo=start_dt.tzinfo)

            if end_dt <= day_start or start_dt >= day_end:
                continue

        fixed_events.append(
            FixedEvent(
                title=summary,
                start=start_dt,
                end=end_dt,
                location=location,
                description=description,
            )
        )

    # Sort events chronologically
    fixed_events.sort(key=lambda x: x.start)
    return fixed_events


async def fetch_and_parse_ical_url(
    url: str,
    target_date: Optional[date] = None,
) -> List[FixedEvent]:
    """Fetch remote .ics feed over HTTP/webcal and parse into FixedEvent objects."""
    clean_url = url.strip()
    if clean_url.startswith("webcal://"):
        clean_url = "https://" + clean_url[len("webcal://"):]
    elif clean_url.startswith("webcals://"):
        clean_url = "https://" + clean_url[len("webcals://"):]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) StudyLifeOrchestrator/1.0"
    }

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers, verify=False) as client:
        response = await client.get(clean_url)
        response.raise_for_status()
        return parse_ical_content(response.text, target_date=target_date)
