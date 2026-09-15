"""Pydantic models for fixed events, free slots, and day schedule."""

from datetime import date as dt_date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class FixedEvent(BaseModel):
    """Represents a scheduled fixed commitment (e.g. lecture, lab, seminar, appointment)."""
    title: str = Field(..., description="Title of the event")
    start: datetime = Field(..., description="Start datetime of the event")
    end: datetime = Field(..., description="End datetime of the event")
    location: Optional[str] = Field(None, description="Location or room of the event")
    description: Optional[str] = Field(None, description="Additional details or description")

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Algorithms & Data Structures",
                "start": "2026-09-14T08:15:00",
                "end": "2026-09-14T10:00:00",
                "location": "Auditorium A",
                "description": "Weekly lecture on graph traversal"
            }
        }
    }


class FreeSlot(BaseModel):
    """Represents an open time window available for studying, workouts, or meals."""
    start: datetime = Field(..., description="Start datetime of the free slot")
    end: datetime = Field(..., description="End datetime of the free slot")
    duration_minutes: int = Field(..., description="Duration of the free slot in minutes")

    model_config = {
        "json_schema_extra": {
            "example": {
                "start": "2026-09-14T10:00:00",
                "end": "2026-09-14T11:15:00",
                "duration_minutes": 75
            }
        }
    }


class DayWindow(BaseModel):
    """The operating bounds of the analyzed day (e.g. 07:00 to 23:00)."""
    start: datetime = Field(..., description="Operational day start")
    end: datetime = Field(..., description="Operational day end")


class ScheduleSummary(BaseModel):
    """Statistical summary of the day's time allocation."""
    total_window_minutes: int = Field(..., description="Total minutes in the operational day window")
    total_busy_minutes: int = Field(..., description="Total minutes occupied by fixed events (merged)")
    total_free_minutes: int = Field(..., description="Total free minutes available")
    fixed_event_count: int = Field(..., description="Number of fixed events input")
    free_slot_count: int = Field(..., description="Number of distinct free slots calculated")


class ScheduleResponse(BaseModel):
    """Clean, typed response listing fixed events and computed free time slots."""
    date: dt_date = Field(..., description="Date being analyzed")
    day_window: DayWindow = Field(..., description="Daily time analysis window")
    fixed_events: List[FixedEvent] = Field(default_factory=list, description="List of fixed commitments")
    free_slots: List[FreeSlot] = Field(default_factory=list, description="Calculated available free slots")
    summary: ScheduleSummary = Field(..., description="Day summary metrics")
