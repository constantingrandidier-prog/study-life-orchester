"""Request schemas for schedule analysis endpoints."""

from datetime import date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.schemas.calendar import FixedEvent


class CustomEventsRequest(BaseModel):
    """Payload for analyzing a direct list of fixed events."""
    target_date: Optional[date] = Field(None, description="Day to analyze (defaults to date of first event or today)")
    day_start_hour: int = Field(7, ge=0, le=23, description="Operational day start hour (0-23)")
    day_end_hour: int = Field(23, ge=1, le=24, description="Operational day end hour (1-24)")
    events: List[FixedEvent] = Field(..., description="List of fixed events")


class GoogleCalendarRequest(BaseModel):
    """Payload containing standard Google Calendar API format JSON."""
    target_date: date = Field(..., description="Day to analyze (YYYY-MM-DD)")
    day_start_hour: int = Field(7, ge=0, le=23, description="Operational day start hour (0-23)")
    day_end_hour: int = Field(23, ge=1, le=24, description="Operational day end hour (1-24)")
    items: List[Dict[str, Any]] = Field(
        ...,
        description="Array of Google Calendar event items with summary, start, end fields"
    )


class ICalRequest(BaseModel):
    """Payload for iCal / ICS calendar format."""
    target_date: date = Field(..., description="Day to analyze (YYYY-MM-DD)")
    day_start_hour: int = Field(7, ge=0, le=23, description="Operational day start hour (0-23)")
    day_end_hour: int = Field(23, ge=1, le=24, description="Operational day end hour (1-24)")
    ics_content: Optional[str] = Field(None, description="Raw iCalendar/ICS text string")
    ics_url: Optional[str] = Field(None, description="HTTP/HTTPS URL to public ICS/iCal feed")
