# Study-Life Orchestrator - Phase 1: Foundation

A FastAPI-based orchestrator that analyzes your university schedule, parses fixed commitments (from iCal/ICS or Google Calendar JSON), and calculates all available free time blocks between 07:00 and 23:00.

---

## Features Implemented in Phase 1

1. **Clean Architecture**:
   - `app/core`: Application configuration, customizable day operating window (07:00 - 23:00).
   - `app/schemas`: Pydantic models for `FixedEvent`, `FreeSlot`, `DayWindow`, and `ScheduleResponse`.
   - `app/services/slot_finder`: Interval math algorithm handling overlapping events, back-to-back classes, and boundary clamping.
   - `app/services/calendar_parser`: Parsers for RFC 5545 iCalendar (`.ics` string / URL) and Google Calendar JSON items.
   - `app/data/dummy_schedule`: Realistic university student schedule fixtures (lectures, labs, group work, consultation).
   - `app/api/v1`: Typed REST API endpoints.

2. **Endpoints**:
   - `GET /api/v1/schedule/dummy` - Instantly returns the analyzed realistic university schedule with all free time slots.
   - `GET /api/v1/schedule/dummy/raw` - Provides raw Google Calendar JSON items and RFC 5545 iCal string for testing.
   - `POST /api/v1/schedule/from-events` - Calculate free slots from a list of fixed events.
   - `POST /api/v1/schedule/from-gcal` - Parses Google Calendar JSON items and calculates free slots.
   - `POST /api/v1/schedule/from-ical` - Parses an iCal string or fetches a remote `.ics` URL and calculates free slots.
   - `GET /docs` - Interactive Swagger UI.
   - `GET /health` - API healthcheck.

---

## Setup & Running

### 1. Requirements
- Python 3.9+

### 2. Activate Virtual Environment & Install Dependencies
If using PowerShell on Windows:
```powershell
# Create venv (if not already created)
python -m venv .venv

# Activate venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 3. Start the Backend Server
```powershell
python -m uvicorn app.main:app --reload --port 8000
```
The server starts at `http://127.0.0.1:8000`.

### 4. Interactive Documentation (Swagger UI)
Open your browser and navigate to:
```
http://127.0.0.1:8000/docs
```

---

## Testing the API Immediately

### Option A: Via Browser or cURL
Fetch the analyzed dummy university schedule:
```bash
curl http://127.0.0.1:8000/api/v1/schedule/dummy
```

Example JSON response:
```json
{
  "date": "2026-09-14",
  "day_window": {
    "start": "2026-09-14T07:00:00",
    "end": "2026-09-14T23:00:00"
  },
  "fixed_events": [
    {
      "title": "Lecture: Algorithms & Data Structures",
      "start": "2026-09-14T08:15:00",
      "end": "2026-09-14T10:00:00",
      "location": "Auditorium 101"
    },
    {
      "title": "Exercise Session: Software Engineering",
      "start": "2026-09-14T10:15:00",
      "end": "2026-09-14T12:00:00",
      "location": "Lab Room 3B"
    }
  ],
  "free_slots": [
    {
      "start": "2026-09-14T07:00:00",
      "end": "2026-09-14T08:15:00",
      "duration_minutes": 75
    },
    {
      "start": "2026-09-14T10:00:00",
      "end": "2026-09-14T10:15:00",
      "duration_minutes": 15
    },
    {
      "start": "2026-09-14T12:00:00",
      "end": "2026-09-14T13:00:00",
      "duration_minutes": 60
    },
    {
      "start": "2026-09-14T14:30:00",
      "end": "2026-09-14T16:00:00",
      "duration_minutes": 90
    },
    {
      "start": "2026-09-14T18:45:00",
      "end": "2026-09-14T23:00:00",
      "duration_minutes": 255
    }
  ],
  "summary": {
    "total_window_minutes": 960,
    "total_busy_minutes": 465,
    "total_free_minutes": 495,
    "fixed_event_count": 5,
    "free_slot_count": 5
  }
}
```

---

## Running Automated Tests

Run the full test suite with `pytest`:
```powershell
.\.venv\Scripts\pytest -v
```
All unit tests cover interval merging, edge cases (empty day, fully booked day, overlapping events, out-of-bounds events), calendar parsers, and FastAPI endpoints.
