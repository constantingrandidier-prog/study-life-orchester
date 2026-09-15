"""Realistic dummy schedule data for a university student."""

from datetime import date, datetime
from typing import List, Optional
from app.models import CalendarEvent


def get_mock_events(target_date: Optional[date] = None) -> List[CalendarEvent]:
    """
    Generate a realistic university student schedule for a given date (defaults to today).
    Includes typical university timetable blocks:
    - 08:15 - 10:00: Lecture (Algorithms & Data Structures)
    - 10:15 - 12:00: Lab (Systems Architecture)
    - 14:15 - 16:00: Seminar (Artificial Intelligence)
    - 16:30 - 18:00: Exercise Session (Software Engineering)
    """
    if target_date is None:
        target_date = date.today()

    return [
        CalendarEvent(
            title="Lecture: Algorithms & Data Structures",
            start_time=datetime(target_date.year, target_date.month, target_date.day, 8, 15),
            end_time=datetime(target_date.year, target_date.month, target_date.day, 10, 0),
            location="Auditorium 101",
            description="Core computer science lecture covering graph traversal and dynamic programming",
        ),
        CalendarEvent(
            title="Lab: Systems Architecture",
            start_time=datetime(target_date.year, target_date.month, target_date.day, 10, 15),
            end_time=datetime(target_date.year, target_date.month, target_date.day, 12, 0),
            location="Computer Lab 3B",
            description="Hands-on operating systems and concurrency programming lab",
        ),
        CalendarEvent(
            title="Seminar: Artificial Intelligence",
            start_time=datetime(target_date.year, target_date.month, target_date.day, 14, 15),
            end_time=datetime(target_date.year, target_date.month, target_date.day, 16, 0),
            location="Seminar Room 204",
            description="Discussion and paper presentations on modern transformer architectures",
        ),
        CalendarEvent(
            title="Exercise Session: Software Engineering",
            start_time=datetime(target_date.year, target_date.month, target_date.day, 16, 30),
            end_time=datetime(target_date.year, target_date.month, target_date.day, 18, 0),
            location="Room 105",
            description="Team sprint planning and code review session",
        ),
    ]
