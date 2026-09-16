"""API endpoints for calendar analysis and free slot calculation."""

from datetime import date, datetime
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
import httpx
from app.core.config import settings
from app.data.dummy_schedule import (
    DEFAULT_DUMMY_DATE,
    get_dummy_events,
    get_dummy_gcal_items,
    get_dummy_ics_string,
)
from app.models import (
    AnkiDeckSummary,
    AnkiTopic,
    AnkiWebSyncRequest,
    AttendanceUpdateRequest,
    CalendarEvent,
    DailyScheduleResponse,
    ManualActivity,
    RolloverResponse,
    SmartScheduleResponse,
    StudyLogCreateRequest,
    SyncCalendarUrlRequest,
    UserProfileModel,
    UserProfileUpdateRequest,
    ExamCreateRequest,
    ExamItem,
    ExamPacingResponse,
    PacingConfigModel,
    PacingConfigUpdateRequest,
    ProgressLogCreateRequest,
    ToggleJokerRequest,
    LectureModeRequest,
    LectureModeResponse,
    AnkiWeaknessResponse,
    ProgressComparisonResponse,
    OlatStatusResponse,
    DailyCurriculumAssignment,
    CurriculumRoadmapResponse,
)
from app.services.curriculum_roadmap_service import (
    get_daily_curriculum_assignment,
    generate_curriculum_roadmap,
)
from app.services.exam_pacing import (
    calculate_exam_pacing,
    log_progress,
    toggle_joker_day,
    update_pacing_preferences,
)
from app.services.lecture_decision_service import (
    evaluate_lecture_value,
    set_event_consumption_mode,
    get_total_time_saved_for_date,
)
from app.services.anki_weakness_service import get_anki_due_and_weaknesses
from app.services.progress_stats_service import get_progress_comparison_stats
from app.services.olat_connector import (
    check_olat_connectivity,
    scan_local_uzh_slides,
    evaluate_slide_against_anki,
)
from app.mock_data import get_mock_events
from app.schemas.calendar import ScheduleResponse
from app.schemas.request import (
    CustomEventsRequest,
    GoogleCalendarRequest,
    ICalRequest,
)
from app.services.anki_analyzer import (
    orchestrate_study_plan,
    parse_anki_apkg_content,
    parse_anki_text_content,
    redistribute_uncompleted_cards,
)
from app.services.calendar_parser import (
    fetch_and_parse_ical_url,
    parse_google_calendar_json,
    parse_ical_content,
)
from app.services.time_grid import build_daily_schedule
from app.services.slot_finder import calculate_free_slots
from app.db import repository
from app.services.ankiweb_service import get_current_ankiweb_stats, sync_ankiweb_data
from app.services.anki_local_service import (
    check_ankiconnect_health,
    detect_local_anki_profiles,
    sync_local_anki_collection,
)
from app.services.efficiency_analyzer import analyze_lecture_efficiency

router = APIRouter(prefix="/schedule", tags=["Schedule Orchestration"])


@router.get(
    "/today",
    response_model=DailyScheduleResponse,
    summary="Get today's schedule with fixed events and free slots",
    description="Returns fixed university lectures/labs and calculated free time slots for today or target date.",
)
async def get_today_schedule(
    target_date: Optional[date] = Query(None, description="Filter date (defaults to today)"),
) -> DailyScheduleResponse:
    """Returns fixed events and calculated free slots for today using persisted real calendar or mock data."""
    from datetime import datetime as dt
    calc_date = target_date or date.today()
    profile = repository.get_user_profile()
    calendar_url = profile.get("calendar_ics_url")

    # 1. Check if we have saved events in DB for this date
    saved_events = repository.get_saved_events(target_date=calc_date)
    saved_acts = repository.get_saved_activities(target_date=calc_date)

    if saved_events or saved_acts:
        cal_events = []
        for ev in saved_events:
            st = dt.fromisoformat(ev["start_time"])
            et = dt.fromisoformat(ev["end_time"])
            duration_min = max(15, round((et - st).total_seconds() / 60))

            ev_title = ev.get("title", "")
            fail_rate = 52.0 if "anatomie" in ev_title.lower() else None
            val_info = evaluate_lecture_value(
                title=ev_title,
                module_name=ev.get("module_name") or "",
                duration_minutes=duration_min,
                anki_fail_rate=fail_rate,
            )

            cal_events.append(
                CalendarEvent(
                    id=ev["id"],
                    title=ev["title"],
                    start_time=st,
                    end_time=et,
                    location=ev.get("location"),
                    description=ev.get("description"),
                    module_name=ev.get("module_name"),
                    lecture_attended=True if ev.get("lecture_attended") == 1 else (False if ev.get("lecture_attended") == 0 else None),
                    consumption_mode=ev.get("consumption_mode"),
                    speed_factor=ev.get("speed_factor") or 1.0,
                    time_saved_minutes=ev.get("time_saved_minutes") or 0,
                    recommendation=val_info["recommendation"],
                    recommendation_reason=val_info["reason"],
                    badge_label=val_info["badge_label"],
                    badge_color=val_info["badge_color"],
                    matched_slide_filename=val_info.get("matched_slide_filename"),
                    slide_coverage_pct=val_info.get("slide_coverage_pct"),
                )
            )
        for act in saved_acts:
            cal_events.append(
                CalendarEvent(
                    title=f"{act['category'].capitalize()}: {act['title']}",
                    start_time=dt.fromisoformat(act["start_time"]),
                    end_time=dt.fromisoformat(act["end_time"]),
                    location=act["category"].upper(),
                    description=act.get("notes") or f"Manuelle Aktivität ({act['category']})",
                )
            )
        return build_daily_schedule(events=cal_events, target_date=calc_date)

    # 2. If no saved events for this date, but user has calendar_url: auto-fetch
    if calendar_url:
        try:
            raw_events = await fetch_and_parse_ical_url(url=calendar_url, target_date=calc_date)
            cal_events = [
                CalendarEvent(
                    title=e.title,
                    start_time=e.start,
                    end_time=e.end,
                    location=e.location,
                    description=e.description,
                )
                for e in raw_events
            ]
            if cal_events:
                repository.save_events(
                    events=[e.model_dump() for e in cal_events],
                    target_date=calc_date,
                )
            return build_daily_schedule(events=cal_events, target_date=calc_date)
        except Exception as e:
            print("Error auto-fetching calendar URL in /today:", e)

    # 3. If user has a calendar URL or saved events in database, an empty date means a free day
    all_events = repository.get_saved_events()
    if calendar_url or all_events:
        return build_daily_schedule(events=[], target_date=calc_date)

    # 4. Fallback for initial demo mode
    events = get_mock_events(target_date=calc_date)
    return build_daily_schedule(events=events, target_date=calc_date)


@router.get(
    "/dummy",
    response_model=ScheduleResponse,
    summary="Analyze realistic dummy university schedule",
    description=(
        "Returns the analyzed schedule (fixed lectures/labs and calculated free slots) "
        "for a realistic university student day between 07:00 and 23:00."
    ),
)
def get_dummy_analyzed_schedule(
    target_date: date = Query(
        DEFAULT_DUMMY_DATE,
        description="Target date to analyze (defaults to 2026-09-14)",
    ),
    day_start_hour: int = Query(
        settings.default_day_start_hour,
        ge=0,
        le=23,
        description="Operational start hour (0-23)",
    ),
    day_end_hour: int = Query(
        settings.default_day_end_hour,
        ge=1,
        le=24,
        description="Operational end hour (1-24)",
    ),
) -> ScheduleResponse:
    """Analyze the realistic pre-configured university schedule."""
    if day_start_hour >= day_end_hour:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="day_start_hour must be strictly less than day_end_hour",
        )

    events = get_dummy_events(target_date=target_date)
    return calculate_free_slots(
        events=events,
        target_date=target_date,
        day_start_hour=day_start_hour,
        day_end_hour=day_end_hour,
    )


@router.get(
    "/dummy/raw",
    summary="Get raw dummy test fixtures",
    description="Returns raw Google Calendar JSON items and RFC 5545 iCalendar string for testing.",
)
def get_raw_dummy_fixtures(
    target_date: date = Query(DEFAULT_DUMMY_DATE),
):
    """Provide raw fixtures for testing other endpoints."""
    return {
        "target_date": target_date.isoformat(),
        "google_calendar_items": get_dummy_gcal_items(target_date),
        "ical_string": get_dummy_ics_string(target_date),
    }


@router.post(
    "/from-events",
    response_model=ScheduleResponse,
    summary="Calculate free slots from fixed events list",
)
def analyze_from_events(payload: CustomEventsRequest) -> ScheduleResponse:
    """Analyze schedule from an explicit list of fixed events."""
    if payload.day_start_hour >= payload.day_end_hour:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="day_start_hour must be strictly less than day_end_hour",
        )

    # Determine target date: explicit or derived from first event or today
    if payload.target_date:
        calc_date = payload.target_date
    elif payload.events:
        calc_date = payload.events[0].start.date()
    else:
        calc_date = date.today()

    return calculate_free_slots(
        events=payload.events,
        target_date=calc_date,
        day_start_hour=payload.day_start_hour,
        day_end_hour=payload.day_end_hour,
    )


@router.post(
    "/from-gcal",
    response_model=ScheduleResponse,
    summary="Parse Google Calendar JSON and calculate free slots",
)
def analyze_from_google_calendar(payload: GoogleCalendarRequest) -> ScheduleResponse:
    """Parse standard Google Calendar JSON items and calculate free slots."""
    if payload.day_start_hour >= payload.day_end_hour:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="day_start_hour must be strictly less than day_end_hour",
        )

    try:
        events = parse_google_calendar_json(payload.items, target_date=payload.target_date)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse Google Calendar JSON items: {exc}",
        )

    return calculate_free_slots(
        events=events,
        target_date=payload.target_date,
        day_start_hour=payload.day_start_hour,
        day_end_hour=payload.day_end_hour,
    )


@router.post(
    "/from-ical",
    response_model=ScheduleResponse,
    summary="Parse iCal / ICS feed and calculate free slots",
)
async def analyze_from_ical(payload: ICalRequest) -> ScheduleResponse:
    """Parse iCal/ICS content string or remote ICS URL and calculate free slots."""
    if payload.day_start_hour >= payload.day_end_hour:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="day_start_hour must be strictly less than day_end_hour",
        )

    if not payload.ics_content and not payload.ics_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'ics_content' or 'ics_url' must be provided.",
        )

    try:
        if payload.ics_url:
            events = await fetch_and_parse_ical_url(payload.ics_url, target_date=payload.target_date)
        else:
            events = parse_ical_content(payload.ics_content, target_date=payload.target_date)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error fetching remote ICS feed: {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Error parsing iCal content: {exc}",
        )

    return calculate_free_slots(
        events=events,
        target_date=payload.target_date,
        day_start_hour=payload.day_start_hour,
        day_end_hour=payload.day_end_hour,
    )


@router.post(
    "/upload-ics",
    response_model=DailyScheduleResponse,
    summary="Upload .ics calendar file to extract timetable and compute free slots",
    description="Upload an exported .ics calendar file (e.g. from UZH or Google Calendar) to parse events and calculate free time slots.",
)
async def upload_ics_schedule(
    file: UploadFile = File(...),
    target_date: Optional[date] = Query(None, description="Filter date (defaults to first event date or today)"),
) -> DailyScheduleResponse:
    """Parse uploaded .ics timetable and return schedule with free slots."""
    try:
        content = await file.read()
        text = content.decode("utf-8", errors="ignore")
        raw_events = parse_ical_content(text, target_date=target_date)
        cal_events = [
            CalendarEvent(
                title=e.title,
                start_time=e.start,
                end_time=e.end,
                location=e.location,
                description=e.description,
            )
            for e in raw_events
        ]
        calc_date = target_date or (cal_events[0].start_time.date() if cal_events else date.today())
        # Auto-persist to SQLite DB
        if cal_events:
            repository.save_events(
                events=[e.model_dump() for e in cal_events],
                target_date=calc_date,
            )
        return build_daily_schedule(events=cal_events, target_date=calc_date)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Fehler beim Verarbeiten der .ics Datei: {exc}",
        )




class CustomScheduleRequest(BaseModel):
    """Payload to recalculate schedule with manual activities."""
    target_date: Optional[date] = None
    fixed_events: List[CalendarEvent] = Field(default_factory=list)
    manual_activities: List[ManualActivity] = Field(default_factory=list)


@router.post(
    "/custom",
    response_model=DailyScheduleResponse,
    summary="Recalculate schedule with manual activities",
    description="Combine lectures and manual activities (Gym, Meals, Commute) to recalculate remaining free slots.",
)
def recalculate_custom_schedule(payload: CustomScheduleRequest) -> DailyScheduleResponse:
    """Recalculate free time slots taking user manual activities into account."""
    calc_date = payload.target_date or (
        payload.fixed_events[0].start_time.date() if payload.fixed_events else date.today()
    )
    all_events = list(payload.fixed_events)
    for act in payload.manual_activities:
        all_events.append(
            CalendarEvent(
                title=f"{act.category.capitalize()}: {act.title}",
                start_time=act.start_time,
                end_time=act.end_time,
                location=act.category.upper(),
                description=act.notes or f"Manuell eingetragene Aktivität ({act.category})",
            )
        )
    return build_daily_schedule(events=all_events, target_date=calc_date)


@router.post(
    "/anki/upload",
    response_model=AnkiDeckSummary,
    summary="Upload and analyze Anki deck (.apkg, .txt, .csv)",
    description="Analyzes card counts, tags, topics, and difficulty metrics from an uploaded Anki deck.",
)
async def upload_anki_deck(file: UploadFile = File(...)) -> AnkiDeckSummary:
    """Upload and inspect Anki deck cards, topics, and difficulty."""
    try:
        content = await file.read()
        fname = file.filename or "deck.apkg"
        if fname.endswith(".apkg") or fname.endswith(".zip"):
            summary = parse_anki_apkg_content(content, filename=fname)
        else:
            text = content.decode("utf-8", errors="ignore")
            summary = parse_anki_text_content(text, filename=fname)
        
        # Auto-persist deck summary to SQLite
        repository.save_anki_deck_summary(
            deck_name=summary.deck_name,
            total_cards=summary.total_cards,
            total_minutes=summary.total_estimated_minutes,
            topics=[t.model_dump() for t in summary.topics],
        )
        return summary
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Fehler beim Analysieren des Anki-Decks: {exc}",
        )


class StudyOrchestrationRequest(BaseModel):
    """Payload to dynamically schedule Anki topics around lectures and activities."""
    target_date: Optional[date] = None
    fixed_events: List[CalendarEvent] = Field(default_factory=list)
    manual_activities: List[ManualActivity] = Field(default_factory=list)
    anki_topics: List[AnkiTopic] = Field(default_factory=list)


@router.post(
    "/anki/orchestrate",
    response_model=SmartScheduleResponse,
    summary="Orchestrate Anki topics into calendar free slots based on lecture priority",
    description="Matches deck topics to scheduled lectures and places optimal study blocks into free calendar windows.",
)
def orchestrate_anki_study(payload: StudyOrchestrationRequest) -> SmartScheduleResponse:
    """Generate smart daily study plan combining timetable, activities, and prioritized Anki topics."""
    return orchestrate_study_plan(
        events=payload.fixed_events,
        manual_activities=payload.manual_activities,
        anki_topics=payload.anki_topics,
        target_date=payload.target_date,
    )


class RolloverStudyRequest(BaseModel):
    """Payload to redistribute uncompleted study topics across subsequent days."""
    target_date: Optional[date] = None
    uncompleted_topics: List[AnkiTopic] = Field(default_factory=list)
    days_ahead: int = Field(default=3, ge=1, le=7)


@router.post(
    "/anki/rollover",
    response_model=RolloverResponse,
    summary="Redistribute uncompleted study topics across upcoming days",
    description="Intelligently redistributes missed or incomplete flashcard batches across the next 2-3 days while preserving thematic clustering.",
)
def rollover_uncompleted_study(payload: RolloverStudyRequest) -> RolloverResponse:
    """Redistribute uncompleted cards across subsequent days."""
    return redistribute_uncompleted_cards(
        uncompleted_topics=payload.uncompleted_topics,
        target_date=payload.target_date,
        days_ahead=payload.days_ahead,
    )


# ============================================================================
# PHASE 3: CALENDAR URL SYNC, PERSISTENCE, ANKIWEB & EFFICIENCY ENDPOINTS
# ============================================================================

@router.post(
    "/sync-url",
    response_model=DailyScheduleResponse,
    summary="Subscribe / import timetable via iCal or webcal URL",
    description="Fetches a remote calendar URL (e.g. university portal or Google Calendar), persists events to SQLite, and computes free slots.",
)
async def sync_calendar_url(payload: SyncCalendarUrlRequest) -> DailyScheduleResponse:
    """Fetch remote timetable URL, persist to DB, and return schedule with free slots."""
    if not payload.url or not payload.url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kalender-URL darf nicht leer sein.",
        )
    try:
        url = payload.url.strip()
        # Convert webcal:// or webcals:// to https://
        if url.startswith("webcal://"):
            url = "https://" + url[len("webcal://"):]
        elif url.startswith("webcals://"):
            url = "https://" + url[len("webcals://"):]

        # Always update user profile with the saved calendar URL!
        repository.update_user_profile(calendar_ics_url=payload.url)

        # Parse ALL events from feed (no date filter) to populate all dates across the semester
        all_raw_events = await fetch_and_parse_ical_url(url=url, target_date=None)

        calc_date = payload.target_date or date.today()

        if payload.save_to_db and all_raw_events:
            events_by_date = {}
            for e in all_raw_events:
                d = e.start.date()
                if d not in events_by_date:
                    events_by_date[d] = []
                events_by_date[d].append({
                    "title": e.title,
                    "start_time": e.start,
                    "end_time": e.end,
                    "location": e.location,
                    "description": e.description,
                })
            for d, ev_list in events_by_date.items():
                repository.save_events(events=ev_list, target_date=d, clear_existing=True)

        day_events = [
            CalendarEvent(
                title=e.title,
                start_time=e.start,
                end_time=e.end,
                location=e.location,
                description=e.description,
            )
            for e in all_raw_events
            if e.start.date() == calc_date
        ]

        # Include any manual activities on calc_date
        saved_acts = repository.get_saved_activities(target_date=calc_date)
        from datetime import datetime as dt
        for act in saved_acts:
            day_events.append(
                CalendarEvent(
                    title=f"{act['category'].capitalize()}: {act['title']}",
                    start_time=dt.fromisoformat(act["start_time"]),
                    end_time=dt.fromisoformat(act["end_time"]),
                    location=act["category"].upper(),
                    description=act.get("notes") or f"Manuelle Aktivität ({act['category']})",
                )
            )

        return build_daily_schedule(events=day_events, target_date=calc_date)
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Fehler beim Abrufen der Kalender-URL: {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Fehler beim Verarbeiten der Kalender-URL: {exc}",
        )


@router.get(
    "/profile",
    response_model=UserProfileModel,
    summary="Get student profile and scheduling preferences",
)
def get_user_profile_endpoint() -> UserProfileModel:
    """Retrieve saved student profile settings from SQLite."""
    data = repository.get_user_profile()
    return UserProfileModel(**data)


@router.post(
    "/profile",
    response_model=UserProfileModel,
    summary="Update student profile and scheduling preferences",
)
def update_user_profile_endpoint(payload: UserProfileUpdateRequest) -> UserProfileModel:
    """Update profile and bio-rhythm preferences in SQLite."""
    data = repository.update_user_profile(
        study_program=payload.study_program,
        semester=payload.semester,
        wake_time=payload.wake_time,
        sleep_time=payload.sleep_time,
        max_daily_study_minutes=payload.max_daily_study_minutes,
        pomodoro_minutes=payload.pomodoro_minutes,
        calendar_ics_url=payload.calendar_ics_url,
        ankiweb_email=payload.ankiweb_email,
    )
    return UserProfileModel(**data)


@router.get(
    "/persisted",
    response_model=DailyScheduleResponse,
    summary="Load persisted calendar schedule & manual activities from SQLite",
)
def get_persisted_schedule_endpoint(
    target_date: Optional[date] = Query(None, description="Date to load"),
) -> DailyScheduleResponse:
    """Load user's saved timetable and activities from SQLite; falls back to mock data if empty."""
    from datetime import datetime as dt
    calc_date = target_date or date.today()
    saved_events = repository.get_saved_events(target_date=calc_date)
    saved_acts = repository.get_saved_activities(target_date=calc_date)

    if not saved_events and not saved_acts:
        events = get_mock_events(target_date=calc_date)
        return build_daily_schedule(events=events, target_date=calc_date)

    cal_events = []
    for ev in saved_events:
        cal_events.append(
            CalendarEvent(
                title=ev["title"],
                start_time=dt.fromisoformat(ev["start_time"]),
                end_time=dt.fromisoformat(ev["end_time"]),
                location=ev.get("location"),
                description=ev.get("description"),
            )
        )
    for act in saved_acts:
        cal_events.append(
            CalendarEvent(
                title=f"{act['category'].capitalize()}: {act['title']}",
                start_time=dt.fromisoformat(act["start_time"]),
                end_time=dt.fromisoformat(act["end_time"]),
                location=act["category"].upper(),
                description=act.get("notes") or f"Manuelle Aktivität ({act['category']})",
            )
        )
    return build_daily_schedule(events=cal_events, target_date=calc_date)


@router.post(
    "/attendance",
    summary="Update whether a lecture was attended by the student",
)
def update_attendance_endpoint(payload: AttendanceUpdateRequest):
    """Mark a lecture as attended (1) or skipped (0) for efficiency analytics."""
    success = repository.update_lecture_attendance(
        event_id=payload.event_id,
        attended=payload.attended,
    )
    return {"success": success, "event_id": payload.event_id, "attended": payload.attended}


@router.post(
    "/persisted/activity",
    summary="Save a manual activity to SQLite",
)
def save_activity_endpoint(activity: ManualActivity, target_date: Optional[date] = None):
    """Persist a gym, meal, or commute activity to SQLite."""
    calc_date = target_date or activity.start_time.date()
    act_id = repository.save_manual_activity(
        activity=activity.model_dump(),
        target_date=calc_date,
    )
    return {"success": True, "activity_id": act_id}


@router.delete(
    "/persisted/activity/{activity_id}",
    summary="Delete a manual activity from SQLite",
)
def delete_activity_endpoint(activity_id: int):
    """Remove a saved activity."""
    success = repository.delete_manual_activity(activity_id=activity_id)
    return {"success": success}


@router.get(
    "/persisted/anki",
    summary="Retrieve latest saved Anki deck and topics from SQLite",
)
def get_persisted_anki_endpoint():
    """Get the active Anki deck and parsed topics saved in SQLite."""
    deck = repository.get_latest_anki_deck()
    return {"deck": deck}


@router.post(
    "/ankiweb/sync",
    summary="Trigger live AnkiWeb data synchronization",
    description="Synchronizes flashcard stats, review velocity (s/card), and retention rate from AnkiWeb or local Anki database into SQLite.",
)
def sync_ankiweb_endpoint(payload: AnkiWebSyncRequest):
    """Sync learning telemetry from AnkiWeb or local Anki Desktop database."""
    return sync_ankiweb_data(
        email=payload.email,
        password=payload.password,
        api_token=payload.api_token,
    )


@router.get(
    "/anki/detect-local",
    summary="Detect local Anki Desktop installations and profiles",
    description="Scans standard filesystem paths for collection.anki2 and checks AnkiConnect health.",
)
def detect_local_anki_endpoint():
    """Detect available local Anki Desktop profiles and AnkiConnect status."""
    profiles = detect_local_anki_profiles()
    ankiconnect = check_ankiconnect_health()
    return {
        "status": "success",
        "found_profiles": profiles,
        "primary_profile": profiles[0] if profiles else None,
        "ankiconnect": ankiconnect,
    }


@router.post(
    "/anki/local-sync",
    summary="One-click synchronization of local Anki Desktop collection",
    description="Reads cards, decks, and revlog telemetry strictly scoped to the target deck needed right now.",
)
def sync_local_anki_endpoint(
    profile_name: Optional[str] = None,
    deck_scope: Optional[str] = "curriculum",
):
    """Sync real flashcards and learning telemetry from local Anki installation."""
    try:
        return sync_local_anki_collection(profile_name=profile_name, deck_scope=deck_scope or "curriculum")
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fehler beim Einlesen der lokalen Anki-Sammlung: {exc}",
        )


@router.get(
    "/ankiweb/stats",
    summary="Get current AnkiWeb telemetry metrics scoped to the target deck",
)
def get_ankiweb_stats_endpoint(deck_scope: Optional[str] = "curriculum"):
    """Retrieve the latest synced Anki metrics scoped strictly to the target deck (e.g. 'curriculum' or 'module')."""
    return get_current_ankiweb_stats(deck_scope=deck_scope or "curriculum")


@router.get(
    "/anki/deck-stats",
    summary="Get deck-scoped Anki statistics and medical module breakdown",
    description="Returns all-time telemetry for the deck needed right now (2. SJ / active module) and breakdown for all 6 modules.",
)
def get_anki_deck_stats_endpoint(deck_scope: Optional[str] = "curriculum"):
    """Get all-time telemetry for specifically the requested deck."""
    return get_current_ankiweb_stats(deck_scope=deck_scope or "curriculum")


@router.post(
    "/study/log",
    summary="Log a completed study session",
    description="Records flashcard review speed and retention to refine lecture efficiency correlations.",
)
def log_study_endpoint(payload: StudyLogCreateRequest):
    """Record a completed study block in the historical study log."""
    log_id = repository.log_study_session(
        topic_name=payload.topic_name,
        module_name=payload.module_name,
        duration_minutes=payload.duration_minutes,
        cards_reviewed=payload.cards_reviewed,
        seconds_per_card=payload.seconds_per_card,
        retention_rate=payload.retention_rate,
        lecture_attended=payload.lecture_attended,
    )
    return {"success": True, "log_id": log_id}


@router.get(
    "/analytics/efficiency",
    summary="Comprehensive Lecture ROI and Learning Efficiency Analysis",
    description="Compares learning speed and retention with vs without lecture attendance, calculating net time balance and module recommendations.",
)
def get_lecture_efficiency_analytics():
    """Data-driven analysis: How much more efficient are you when attending lectures vs pure Anki self-study?"""
    return analyze_lecture_efficiency()


# ============================================================================
# PHASE 1: EXAM PACING & PROGRESS TRACKING ENDPOINTS
# ============================================================================

@router.get(
    "/exam/pacing",
    response_model=ExamPacingResponse,
    summary="Calculate dynamic exam pacing and daily target cards",
    description="Computes target cards/day up to January 2027 exams taking into account free days, joker days, and revision buffers.",
)
def get_exam_pacing_endpoint(target_date: Optional[date] = None) -> ExamPacingResponse:
    """Retrieve daily pacing metrics, remaining learning days, and daily target volume."""
    res = calculate_exam_pacing(target_date=target_date, user_id="student")
    return ExamPacingResponse(**res)


@router.post(
    "/exam/log-progress",
    response_model=ExamPacingResponse,
    summary="Log actual completed cards for the day",
    description="Records completed flashcards and immediately rebalances the pacing curve.",
)
def log_daily_progress_endpoint(payload: ProgressLogCreateRequest) -> ExamPacingResponse:
    """Record completed cards today (Ist-Erfassung) and return updated pacing."""
    t_date = None
    if payload.log_date:
        try:
            t_date = datetime.strptime(payload.log_date, "%Y-%m-%d").date()
        except ValueError:
            pass
    res = log_progress(
        cards_completed=payload.cards_completed,
        minutes_spent=payload.minutes_spent,
        target_date=t_date,
        source=payload.source,
        notes=payload.notes,
        user_id="student",
    )
    return ExamPacingResponse(**res)


@router.post(
    "/exam/toggle-joker",
    response_model=ExamPacingResponse,
    summary="Toggle a date as spontaneous Joker-Day (rest day)",
    description="Marks or unmarks a date as off-day. Rebalances target cards across all remaining days.",
)
def toggle_joker_day_endpoint(payload: ToggleJokerRequest) -> ExamPacingResponse:
    """Toggle a date as Joker-Tag (rest day)."""
    res = toggle_joker_day(date_str=payload.date_str, user_id="student")
    return ExamPacingResponse(**res)


@router.post(
    "/exam/config",
    response_model=ExamPacingResponse,
    summary="Update pacing preferences (free weekdays, buffer)",
    description="Adjusts weekly rest days (e.g. Sunday free) and revision buffer duration.",
)
def update_pacing_config_endpoint(payload: PacingConfigUpdateRequest) -> ExamPacingResponse:
    """Update study pacing preferences."""
    res = update_pacing_preferences(
        free_weekdays=payload.free_weekdays,
        joker_dates=payload.joker_dates,
        revision_buffer_days=payload.revision_buffer_days,
        total_curriculum_cards=payload.total_curriculum_cards,
        user_id="student",
    )
    return ExamPacingResponse(**res)


@router.get(
    "/exam/list",
    response_model=List[ExamItem],
    summary="List registered exam deadlines",
)
def list_exams_endpoint() -> List[ExamItem]:
    """Retrieve all upcoming exams for the student."""
    raw = repository.get_exams(user_id="student")
    today = date.today()
    out: List[ExamItem] = []
    for ex in raw:
        try:
            ex_d = datetime.strptime(ex["exam_date"], "%Y-%m-%d").date()
            days_left = (ex_d - today).days
        except ValueError:
            days_left = 0
        out.append(
            ExamItem(
                id=ex["id"],
                subject_name=ex["subject_name"],
                exam_date=ex["exam_date"],
                target_cards=ex.get("target_cards", 9633),
                days_left=days_left,
                notes=ex.get("notes"),
            )
        )
    return out


# ============================================================================
# PHASE 2: LECTURE DECISION, WEAKNESS & OLAT ENDPOINTS
# ============================================================================

@router.post(
    "/lecture/mode",
    response_model=LectureModeResponse,
    summary="Set consumption mode for a lecture event",
    description="Updates the event mode (live, 1.25x, 1.5x, 1.75x, 2.0x, slides_only, skipped) and calculates minutes saved.",
)
def set_lecture_mode_endpoint(payload: LectureModeRequest) -> LectureModeResponse:
    """Set consumption mode for a lecture and compute time savings."""
    try:
        chosen_mode = payload.consumption_mode or payload.mode or "live_1_0"
        res = set_event_consumption_mode(event_id=payload.event_id, mode=chosen_mode)
        return LectureModeResponse(**res)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get(
    "/anki/weaknesses",
    response_model=AnkiWeaknessResponse,
    summary="Get real due reviews and topic weakness analysis",
    description="Extracts due review cards, learning cards, failure rates, and overdue topics from local Anki collection.",
)
def get_anki_weaknesses_endpoint() -> AnkiWeaknessResponse:
    """Retrieve detailed topic weakness and due reviews breakdown from local Anki database."""
    res = get_anki_due_and_weaknesses()
    return AnkiWeaknessResponse(**res)


@router.get(
    "/stats/comparison",
    response_model=ProgressComparisonResponse,
    summary="Get learning progress comparisons and time savings",
    description="Compares today's completed cards with yesterday, computes 7-day average and total minutes saved.",
)
def get_stats_comparison_endpoint(target_date: Optional[date] = None) -> ProgressComparisonResponse:
    """Retrieve comparative progress metrics for the student."""
    res = get_progress_comparison_stats(target_date=target_date, user_id="student")
    return ProgressComparisonResponse(**res)


@router.get(
    "/olat/status",
    response_model=OlatStatusResponse,
    summary="Check UZH OpenOLAT platform status and local slides",
    description="Checks lms.uzh.ch connectivity, WebDAV access instructions, and scans local UZH OneDrive course slides.",
)
def get_olat_status_endpoint() -> OlatStatusResponse:
    """Check connectivity to UZH OpenOLAT and scan local UZH course materials."""
    status_info = check_olat_connectivity()
    slides = scan_local_uzh_slides()
    return OlatStatusResponse(
        platform=status_info["platform"],
        url=status_info["url"],
        webdav_url=status_info["webdav_url"],
        online=status_info["online"],
        status_code=status_info["status_code"],
        message=status_info["message"],
        auth_methods=status_info["auth_methods"],
        local_slides_count=len(slides),
        sample_slides=slides[:5],
        webdav_configured=status_info.get("webdav_configured", True),
        webdav_user=status_info.get("webdav_user", "553131393539353502@uzh.ch"),
        course_url=status_info.get("course_url", "https://lms.uzh.ch/auth/RepositoryEntry/666697737/CourseNode/76022446801983"),
        needs_vpn=status_info.get("needs_vpn", False),
        vpn_instruction=status_info.get("vpn_instruction"),
    )


# ============================================================================
# PHASE 3: DIDACTIC CURRICULUM ROADMAP & DAILY 100-ANKI ASSIGNMENT ENDPOINTS
# ============================================================================

@router.get(
    "/curriculum/today",
    response_model=DailyCurriculumAssignment,
    summary="Get exact prescriptive daily curriculum assignment (100 cards)",
    description="Returns the exact subtopic breakdown and card quota for today (e.g. 48 cards Deck A + 52 cards Deck B), linked to slides.",
)
def get_curriculum_today_endpoint(
    target_date: Optional[date] = Query(None, description="Date to retrieve assignment for (YYYY-MM-DD). Defaults to current semester day."),
) -> DailyCurriculumAssignment:
    """Retrieve the exact prescriptive daily 100-card Anki assignment for the student."""
    res = get_daily_curriculum_assignment(target_date=target_date)
    return DailyCurriculumAssignment(**res)


@router.get(
    "/curriculum/roadmap",
    response_model=CurriculumRoadmapResponse,
    summary="Get full didactic semester roadmap (9,633 cards, 6 modules, 97 days)",
    description="Returns the complete semester study sequence across all 111 decks and 6 medical modules with exam revision buffer.",
)
def get_curriculum_roadmap_endpoint() -> CurriculumRoadmapResponse:
    """Retrieve the full semester roadmap across all 6 modules and 9,633 Anki cards."""
    res = generate_curriculum_roadmap()
    return CurriculumRoadmapResponse(**res)


class CurriculumSwapDaysRequest(BaseModel):
    date1: str
    date2: str
    day_num1: Optional[int] = None
    day_num2: Optional[int] = None

@router.post(
    "/curriculum/swap-days",
    summary="Swap learning packages between two roadmap days",
)
def swap_curriculum_days_endpoint(req: CurriculumSwapDaysRequest):
    from app.db import repository
    res = repository.swap_curriculum_days(
        date1=req.date1,
        date2=req.date2,
        day_num1=req.day_num1,
        day_num2=req.day_num2,
    )
    return res


@router.post(
    "/curriculum/reset-swaps",
    summary="Reset all curriculum day swaps back to original chronological order",
)
def reset_curriculum_swaps_endpoint():
    from app.db import repository
    return repository.reset_curriculum_schedule_overrides()


# ============================================================================
# PHASE 4: ANKI DESKTOP DIRECT SYNC (No AnkiWeb, Automatic Progress)
# ============================================================================

from app.services.anki_desktop_sync import (
    read_live_anki_desktop_state,
    cache_desktop_sync_state,
    get_cached_desktop_sync_state,
)

@router.get(
    "/anki/desktop-status",
    summary="Get live Anki Desktop connection status and today's auto-tracked reviews",
    description="Directly reads collection.anki2 to automatically count reviews done today and cards due tomorrow for repetition.",
)
def get_anki_desktop_status_endpoint(target_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD")):
    """Retrieve live stats directly from local Anki desktop collection."""
    return read_live_anki_desktop_state(target_date_str=target_date)


from app.services.anki_backlog_triage import (
    calculate_backlog_triage,
    cache_triage,
)

@router.post(
    "/anki/desktop-sync",
    summary="Receive sync payload from laptop background watcher",
    description="Allows local laptop sync script to push live reviews and due forecast to cloud server.",
)
def post_anki_desktop_sync_endpoint(payload: dict):
    """Receive live sync payload from local Anki watcher."""
    cache_desktop_sync_state(payload)
    new_cnt = payload.get("new_cards_count", payload.get("today_reviewed_count", 0))
    today_mins = int(payload.get("today_time_minutes", 0))
    try:
        t_date_str = payload.get("target_date")
        p_date = date.fromisoformat(t_date_str) if t_date_str else date.today()
        repository.save_daily_progress(
            target_date=p_date,
            cards_completed=new_cnt,
            minutes_spent=today_mins,
            source="anki_desktop_auto",
            notes=f"Auto-Sync Anki Desktop ({new_cnt} neue Karten)",
            user_id="student",
        )
    except Exception:
        pass
    return {"status": "ok", "synced": True, "cards_logged": new_cnt}


@router.get(
    "/anki/backlog-triage",
    summary="Get Anki Backlog Triage and Emergency Priority for Topics",
    description="Analyzes due review burden, lapse rates, and time since review to prioritize topics when daily reviews exceed capacity (>500 reviews).",
)
def get_anki_backlog_triage_endpoint(max_capacity: Optional[int] = Query(None, description="Max cards student can manage today")):
    """Retrieve backlog triage and priority ranking for Anki topics."""
    return calculate_backlog_triage(max_capacity=max_capacity)


@router.post(
    "/anki/triage-sync",
    summary="Receive triage payload from laptop background watcher",
    description="Syncs pre-calculated triage matrix to cloud server.",
)
def post_anki_triage_sync_endpoint(payload: dict):
    """Cache triage state on cloud."""
    cache_triage(payload)
    return {"status": "ok", "cached": True}


from app.services.workload_forecast import (
    get_workload_forecast,
    cache_workload_forecast,
)

@router.get(
    "/anki/workload-forecast",
    summary="Get 14-day Anki workload forecast and spike warnings",
    description="Forecasts upcoming review volumes per day for the next 14 days, identifying load peaks and smoothing tips.",
)
def get_anki_workload_forecast_endpoint(days_ahead: int = Query(14, ge=1, le=30)):
    """Retrieve 14-day review forecast from local Anki collection or cloud cache."""
    return get_workload_forecast(days_ahead=days_ahead)


@router.post(
    "/anki/workload-sync",
    summary="Receive workload forecast payload from laptop background watcher",
    description="Syncs pre-calculated 14-day workload curve to cloud server.",
)
def post_anki_workload_sync_endpoint(payload: dict):
    """Cache workload forecast state on cloud."""
    cache_workload_forecast(payload)
    return {"status": "ok", "cached": True}


from app.services.daily_rhythm_service import generate_daily_science_rhythm

class RhythmActionRequest(BaseModel):
    source_date: str
    action: str  # 'delete' or 'postpone'
    block_id: str
    target_date: Optional[str] = None
    block_payload: Optional[dict] = None

class RhythmRestoreRequest(BaseModel):
    source_date: str
    block_id: Optional[str] = None

@router.get(
    "/daily-rhythm",
    summary="Get dynamic scientific study rhythm with customizable start time and lunch",
    description="Calculates the science-backed study schedule. Supports custom start_time, lunch_duration, and include_lecture toggle. Highlights mandatory practicals and embeds today's struggle cards.",
)
def get_daily_rhythm_endpoint(
    target_date: Optional[str] = Query(None, description="Target date YYYY-MM-DD"),
    start_time: str = Query("08:30", description="Start time HH:MM"),
    lunch_duration: int = Query(75, description="Lunch break duration in minutes (30, 45, 60, 75)"),
    include_lecture: bool = Query(True, description="Whether to include lecture/podcast blocks"),
    removed_blocks: Optional[str] = Query(None, description="Comma-separated block IDs to omit"),
):
    """Returns the dynamic scientific study schedule for the student."""
    t_date = None
    if target_date:
        try:
            t_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            pass
    t_date = t_date or date.today()
    
    from app.db import repository
    events_raw = repository.get_saved_events(t_date)
    cal_events = [CalendarEvent(**e) for e in events_raw] if events_raw else []

    from app.services.anki_desktop_sync import read_live_anki_desktop_state
    anki_st = read_live_anki_desktop_state(target_date_str=t_date.isoformat())
    due_today = anki_st.get("due_today_count", 100) or 100
    
    from app.services.curriculum_roadmap_service import get_daily_curriculum_assignment
    curr_assign = get_daily_curriculum_assignment(t_date)
    new_target = curr_assign.get("adjusted_target_cards", 101)

    rem_list = [b.strip() for b in removed_blocks.split(",") if b.strip()] if removed_blocks else None

    return generate_daily_science_rhythm(
        target_date=t_date,
        events=cal_events,
        cards_due_today=due_today,
        new_cards_target=new_target,
        start_time_str=start_time or "08:30",
        lunch_duration_mins=lunch_duration if lunch_duration is not None else 75,
        include_lecture=include_lecture if include_lecture is not None else True,
        curriculum_assignment=curr_assign,
        removed_block_ids=rem_list,
    )


@router.post(
    "/rhythm-action",
    summary="Save rhythm block action (delete or postpone to tomorrow)",
)
def post_rhythm_action_endpoint(req: RhythmActionRequest):
    from app.db import repository
    res = repository.save_rhythm_action(
        source_date=req.source_date,
        block_id=req.block_id,
        action=req.action,
        target_date=req.target_date,
        block_payload=req.block_payload,
    )
    return res


@router.post(
    "/rhythm-action/restore",
    summary="Restore removed or postponed rhythm blocks for a date",
)
def restore_rhythm_action_endpoint(req: RhythmRestoreRequest):
    from app.db import repository
    res = repository.restore_rhythm_action(
        source_date=req.source_date,
        block_id=req.block_id,
    )
    return res


@router.get(
    "/rhythm-actions",
    summary="Get active rhythm adjustments (removed and postponed blocks) for a date",
)
def get_rhythm_actions_endpoint(
    target_date: Optional[str] = Query(None, description="Date YYYY-MM-DD"),
):
    from app.db import repository
    t_str = target_date or date.today().isoformat()
    return repository.get_rhythm_actions_for_date(t_str)


from app.services.lecture_advisor_service import (
    get_all_advisor_lectures,
    search_lecture_advisor,
)

@router.get(
    "/advisor/search",
    summary="Search lecture & Anki advisor recommendations",
    description="Look up which lecture to watch for which Anki topics, speed recommendations, cognitive load trade-offs, and pure Anki facts.",
)
def search_advisor_endpoint(
    q: Optional[str] = Query("", description="Search query for topic, deck, or keyword"),
    mode: Optional[str] = Query(None, description="Filter by recommendation (skip, 1.0x, 1.2x, 1.4x, audio)"),
    module: Optional[str] = Query(None, description="Filter by module"),
    cards: Optional[int] = Query(100, description="Target Anki cards to calculate required timestamp range"),
):
    return search_lecture_advisor(query=q or "", filter_mode=mode, filter_module=module, target_cards=cards)


@router.get(
    "/advisor/all",
    summary="Get all 38 UZH lectures with clinical & cognitive recommendations",
)
def get_all_advisor_lectures_endpoint():
    lectures = get_all_advisor_lectures()
    return {
        "total": len(lectures),
        "lectures": lectures,
    }


@router.get(
    "/advisor/lecture/{lecture_id}",
    summary="Get specific lecture advisor detail",
)
def get_advisor_lecture_detail_endpoint(lecture_id: str):
    all_l = get_all_advisor_lectures()
    found = next((l for l in all_l if l["id"] == lecture_id), None)
    if not found:
        raise HTTPException(status_code=404, detail=f"Lecture {lecture_id} not found")
    return found


# --- Scientific Struggle & Relapse Analysis Endpoints ---

from app.services.anki_struggle_service import (
    get_today_struggle_analysis,
    trigger_anki_browse,
    prepare_temporary_struggle_deck,
    cleanup_struggle_deck_tags,
)

@router.get(
    "/anki/today-struggles",
    summary="Get scientific struggle analysis of today's Anki reviews",
    description="Extracts today's lapses (Again), high latency hesitation cards, and calculates cognitive diagnoses with slide links.",
)
def get_today_struggles_endpoint(
    target_date: Optional[str] = Query(None, description="Target date YYYY-MM-DD"),
    limit: Optional[int] = Query(15, description="Max cards to return"),
):
    t_date = None
    if target_date:
        try:
            t_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            pass
    return get_today_struggle_analysis(query_date=t_date, limit=limit or 15)


@router.post(
    "/anki/open-browser",
    summary="Open Anki Desktop card browser with struggle query",
    description="Invokes AnkiConnect guiBrowse to directly inspect the struggle cards inside Anki Desktop.",
)
def post_anki_open_browser_endpoint(payload: dict = Body(...)):
    query = payload.get("query", "rated:1:1")
    return trigger_anki_browse(query=query)


@router.post(
    "/anki/create-temp-deck",
    summary="Create temporary filtered deck for today's problem cards in Anki",
    description="Tags today's struggle cards with '⚡_Heute_Problemkarten', opens Anki Browser and returns instructions for 100% safe filtered deck.",
)
def post_anki_create_temp_deck_endpoint(payload: dict = Body(default={})):
    deck_name = payload.get("deck_name", "⚡ Problem-Karten Heute")
    tag_name = payload.get("tag_name", "⚡_Heute_Problemkarten")
    limit = payload.get("limit", 15)
    target_date = payload.get("target_date")
    t_date = None
    if target_date:
        try:
            t_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            pass
    return prepare_temporary_struggle_deck(deck_name=deck_name, tag_name=tag_name, query_date=t_date, limit=limit)


@router.post(
    "/anki/cleanup-temp-deck",
    summary="Clean up temporary struggle tags in Anki Desktop",
    description="Removes the temporary tag '⚡_Heute_Problemkarten' from cards in Anki Desktop.",
)
def post_anki_cleanup_temp_deck_endpoint(payload: dict = Body(default={})):
    tag_name = payload.get("tag_name", "⚡_Heute_Problemkarten")
    return cleanup_struggle_deck_tags(tag_name=tag_name)


def _resolve_uzh_file_or_folder(path: Optional[str]) -> Optional[Path]:
    """Helper to locate a local UZH course file or folder across known directories."""
    from pathlib import Path
    
    base_dirs = [
        Path(r"C:\Users\Constantin Grandidie\OneDrive - Universität Zürich UZH\Desktop\UNI sem app"),
        Path(r"C:\Users\Constantin Grandidie\OneDrive - Universität Zürich UZH\alles\Studium"),
        Path(r"C:\Users\Constantin Grandidie\OneDrive - Universität Zürich UZH\Desktop"),
        Path(__file__).resolve().parent.parent.parent.parent / "UNI sem app",
        Path(__file__).resolve().parent.parent.parent,
    ]
    if not path:
        return base_dirs[0] if base_dirs[0].exists() else None

    clean_p = path.strip().replace("/", "\\")
    cand = Path(clean_p)
    if cand.is_absolute() and cand.exists():
        return cand

    for b in base_dirs:
        cand = b / clean_p
        if cand.exists():
            return cand
        fname = Path(clean_p).name
        try:
            cands = list(b.glob(f"**/{fname}"))
            if cands:
                return cands[0]
        except Exception:
            pass
    return None


@router.get(
    "/slides/open",
    summary="Opens or locates a lecture PDF slide",
    description="Locates the UZH lecture slide PDF on disk and opens it in the default system viewer at the specified page.",
)
def open_slide_endpoint(
    path: str = Query(..., description="Relative path or name of the slide PDF"),
    page: Optional[int] = Query(1, description="Target page number"),
):
    import os
    found_file = _resolve_uzh_file_or_folder(path)

    if not found_file or not found_file.exists():
        return {
            "success": False,
            "message": f"Folie '{path}' lokal noch nicht abgelegt.",
            "path": path,
            "page": page or 1,
        }

    try:
        os.startfile(str(found_file))
        return {
            "success": True,
            "message": f"Folie '{found_file.name}' auf Seite {page or 1} geöffnet!",
            "file": str(found_file),
            "page": page or 1,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "file": str(found_file),
            "page": page or 1,
        }


@router.get(
    "/slides/view",
    summary="Streams/views a lecture PDF slide in browser",
    description="Serves the lecture slide PDF directly to the browser for in-tab preview.",
)
def view_slide_endpoint(
    path: str = Query(..., description="Relative path or name of the slide PDF"),
):
    from fastapi.responses import FileResponse
    found = _resolve_uzh_file_or_folder(path)
    if not found or not found.exists() or not found.is_file():
        raise HTTPException(status_code=404, detail=f"Folie '{path}' nicht gefunden.")
    return FileResponse(
        str(found),
        media_type="application/pdf",
        filename=found.name,
        headers={"Content-Disposition": f"inline; filename=\"{found.name}\""}
    )


@router.get(
    "/folder/open",
    summary="Opens a local UZH folder or file in Windows Explorer",
    description="Opens the folder or selects the file directly in Windows Explorer.",
)
def open_folder_endpoint(
    path: Optional[str] = Query(None, description="Path to folder or file"),
):
    import os
    import subprocess
    from pathlib import Path

    found = _resolve_uzh_file_or_folder(path)
    if not found or not found.exists():
        base = Path(r"C:\Users\Constantin Grandidie\OneDrive - Universität Zürich UZH\Desktop\UNI sem app")
        if base.exists():
            found = base
        else:
            return {
                "success": False,
                "message": f"Pfad '{path}' konnte lokal nicht gefunden werden.",
                "path": path,
            }

    try:
        if found.is_file():
            subprocess.Popen(["explorer.exe", f"/select,{str(found)}"])
            return {
                "success": True,
                "message": f"Datei '{found.name}' im Windows Explorer markiert!",
                "path": str(found),
                "folder": str(found.parent),
            }
        else:
            # Check if this podcast folder contains a Folienansicht MP4 video
            folien_vids = list(found.glob("*Folien*.mp4")) or list(found.glob("*.mp4"))
            if folien_vids:
                target_file = folien_vids[0]
                subprocess.Popen(["explorer.exe", f"/select,{str(target_file)}"])
                return {
                    "success": True,
                    "message": f"Folienansicht '{target_file.name}' im Explorer markiert!",
                    "path": str(target_file),
                    "folder": str(found),
                }
            os.startfile(str(found))
            return {
                "success": True,
                "message": f"Ordner '{found.name}' im Windows Explorer geöffnet!",
                "path": str(found),
            }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "path": str(found),
        }


@router.get(
    "/podcast/open",
    summary="Directly launches the podcast Folienansicht MP4 video",
)
def open_podcast_video_endpoint(
    path: Optional[str] = Query(None, description="Folder or video name"),
):
    import os
    found = _resolve_uzh_file_or_folder(path)
    if found:
        if found.is_dir():
            folien_vids = list(found.glob("*Folien*.mp4")) or list(found.glob("*.mp4"))
            if folien_vids:
                found = folien_vids[0]
        if found.is_file():
            try:
                os.startfile(str(found))
                return {"success": True, "message": f"Video '{found.name}' gestartet!", "file": str(found)}
            except Exception as e:
                return {"success": False, "error": str(e)}
    return {"success": False, "message": "Podcast-Video konnte lokal nicht geöffnet werden."}



