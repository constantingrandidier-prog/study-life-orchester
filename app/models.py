"""Pydantic schemas for calendar events, free time slots, and schedule responses."""

from datetime import date as dt_date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CalendarEvent(BaseModel):
    """Represents a fixed scheduled commitment (e.g. lecture, lab, seminar, appointment)."""

    title: str = Field(..., description="Title or course name of the event")
    start_time: datetime = Field(..., description="Start datetime of the event")
    end_time: datetime = Field(..., description="End datetime of the event")
    location: Optional[str] = Field(None, description="Location or room of the event")
    description: Optional[str] = Field(None, description="Additional details or description")
    id: Optional[int] = Field(None, description="Database ID of saved event")
    module_name: Optional[str] = Field(None, description="Extracted module name")
    lecture_attended: Optional[bool] = Field(None, description="Attendance status")
    consumption_mode: Optional[str] = Field(None, description="'live', 'stream_1_25', 'stream_1_5', 'stream_2_0', 'slides_only', 'skipped'")
    speed_factor: Optional[float] = Field(1.0, description="Playback speed factor")
    time_saved_minutes: Optional[int] = Field(0, description="Minutes saved by choosing this mode")
    recommendation: Optional[str] = Field(None, description="'attend', 'stream', or 'skip'")
    recommendation_reason: Optional[str] = Field(None, description="Reason for the recommendation")
    badge_label: Optional[str] = Field(None, description="Human-readable badge text")
    badge_color: Optional[str] = Field(None, description="Badge highlight color")
    matched_slide_filename: Optional[str] = Field(None, description="Filename of matching local lecture slide PDF")
    slide_coverage_pct: Optional[float] = Field(None, description="Measured percentage overlap with Anki cards")
    is_mandatory: Optional[bool] = Field(False, description="True if mandatory in-person session with attendance check (Praktikum, Testat)")

    @property
    def start(self) -> datetime:
        """Alias for start_time for backwards/cross compatibility."""
        return self.start_time

    @property
    def end(self) -> datetime:
        """Alias for end_time for backwards/cross compatibility."""
        return self.end_time

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Lecture: Algorithms & Data Structures",
                "start_time": "2026-09-14T08:15:00",
                "end_time": "2026-09-14T10:00:00",
                "location": "Auditorium 101",
                "description": "Weekly lecture on graph algorithms",
            }
        }
    }


class FreeSlot(BaseModel):
    """Represents an open time window available for study, workouts, meals, or rest."""

    start_time: datetime = Field(..., description="Start datetime of the free slot")
    end_time: datetime = Field(..., description="End datetime of the free slot")
    duration_minutes: int = Field(..., description="Duration of the free slot in minutes")

    @property
    def start(self) -> datetime:
        """Alias for start_time."""
        return self.start_time

    @property
    def end(self) -> datetime:
        """Alias for end_time."""
        return self.end_time

    model_config = {
        "json_schema_extra": {
            "example": {
                "start_time": "2026-09-14T10:00:00",
                "end_time": "2026-09-14T10:15:00",
                "duration_minutes": 15,
            }
        }
    }


class DayWindow(BaseModel):
    """The operating bounds of the analyzed day (e.g. 07:00 to 23:00)."""

    start_time: datetime = Field(..., description="Operational day start")
    end_time: datetime = Field(..., description="Operational day end")


class ScheduleSummary(BaseModel):
    """Statistical summary of the day's time allocation."""

    total_window_minutes: int = Field(..., description="Total minutes in the operational day window")
    total_busy_minutes: int = Field(..., description="Total minutes occupied by fixed events")
    total_free_minutes: int = Field(..., description="Total free minutes available")
    fixed_event_count: int = Field(..., description="Number of fixed events input")
    free_slot_count: int = Field(..., description="Number of distinct free slots calculated")


class DailyScheduleResponse(BaseModel):
    """Typed response listing fixed events and computed free time slots for a day."""

    date: dt_date = Field(..., description="Date being analyzed")
    day_window: Optional[DayWindow] = Field(None, description="Daily time analysis window")
    fixed_events: List[CalendarEvent] = Field(default_factory=list, description="List of fixed commitments")
    free_slots: List[FreeSlot] = Field(default_factory=list, description="Calculated available free slots")
    summary: Optional[ScheduleSummary] = Field(None, description="Day summary metrics")

    @property
    def events(self) -> List[CalendarEvent]:
        """Convenience accessor for fixed_events."""
        return self.fixed_events


class ManualActivity(BaseModel):
    """User-defined manual activity such as Workout, Meal, Commute, or Study."""

    title: str = Field(..., description="Name of the activity (e.g. Gym, Lunch, Commute)")
    category: str = Field(default="custom", description="Category: gym, meal, commute, break, study, custom")
    start_time: datetime = Field(..., description="Start datetime of the activity")
    end_time: datetime = Field(..., description="End datetime of the activity")
    notes: Optional[str] = Field(None, description="Optional notes or details")

    @property
    def start(self) -> datetime:
        return self.start_time

    @property
    def end(self) -> datetime:
        return self.end_time


class AnkiTopic(BaseModel):
    """An analyzed topic or tag cluster from an Anki deck."""

    name: str = Field(..., description="Topic name (derived from tag, subdeck, or keyword)")
    cluster_name: str = Field(default="Allgemeines Grundwissen", description="Thematic cluster uniting conceptually connected topics")
    card_count: int = Field(..., description="Number of cards in this topic")
    estimated_minutes: int = Field(..., description="Estimated review duration in minutes")
    difficulty_score: float = Field(default=3.0, description="Estimated difficulty from 1.0 (easy) to 5.0 (hard)")
    matched_lecture: Optional[str] = Field(None, description="Lecture title this topic prepares for or reinforces")
    relevance_score: float = Field(default=0.0, description="Relevance score (0.0 to 1.0) based on upcoming timetable")
    relevance_reason: Optional[str] = Field(None, description="Explanation of why this topic is important for upcoming lectures")
    urgency: str = Field(default="normal", description="'high', 'medium', or 'normal'")


class AnkiDeckSummary(BaseModel):
    """Analysis results for an imported Anki deck."""

    deck_name: str = Field(..., description="Name of the imported deck or file")
    total_cards: int = Field(..., description="Total number of cards analyzed")
    total_estimated_minutes: int = Field(..., description="Total review time in minutes")
    topics: List[AnkiTopic] = Field(default_factory=list, description="Categorized topics and clusters")


class ScheduledStudyBlock(BaseModel):
    """A recommended study session scheduled into a free calendar slot."""

    topic_name: str = Field(..., description="Anki topic to review")
    cluster_name: Optional[str] = Field(None, description="Thematic cluster grouping connected topics")
    start_time: datetime = Field(..., description="Start datetime of the study block")
    end_time: datetime = Field(..., description="End datetime of the study block")
    duration_minutes: int = Field(..., description="Duration of the study block")
    cards_to_review: int = Field(..., description="Target number of cards to review")
    reason: str = Field(..., description="Pedagogical recommendation (e.g. Prepares for 14:15 Seminar)")
    completed: bool = Field(default=False, description="Whether the student finished this session")


class SmartScheduleResponse(BaseModel):
    """Holistic orchestrated day schedule combining lectures, activities, and study blocks."""

    date: dt_date = Field(..., description="Date being analyzed")
    fixed_events: List[CalendarEvent] = Field(default_factory=list, description="Fixed lectures and labs")
    manual_activities: List[ManualActivity] = Field(default_factory=list, description="User manual commitments")
    study_sessions: List[ScheduledStudyBlock] = Field(default_factory=list, description="Orchestrated Anki study sessions")
    remaining_free_slots: List[FreeSlot] = Field(default_factory=list, description="Unallocated free time remaining")
    day_window: Optional[DayWindow] = Field(None, description="Operating day bounds")
    summary: Optional[ScheduleSummary] = Field(None, description="Day metrics summary")
    recommendations: List[str] = Field(default_factory=list, description="Actionable AI insights for the student")


class RolloverItem(BaseModel):
    """A planned batch of uncompleted cards redistributed to a future day."""
    day_offset: int = Field(..., description="1 = Tomorrow, 2 = Day after tomorrow, etc.")
    target_date: dt_date = Field(..., description="Date to review these cards")
    topic_name: str = Field(..., description="Topic being continued")
    cluster_name: str = Field(..., description="Thematic cluster")
    cards_count: int = Field(..., description="Number of cards assigned to this day")
    estimated_minutes: int = Field(..., description="Estimated time for this batch")


class RolloverResponse(BaseModel):
    """Result of redistributing uncompleted study goals across subsequent days."""
    message: str
    total_uncompleted_cards: int
    redistribution: List[RolloverItem]
    advice: str


# ============================================================================
# PHASE 3: PERSISTENCE, CALENDAR URL SYNC, PROFILE & EFFICIENCY MODELS
# ============================================================================

class UserProfileModel(BaseModel):
    """Student profile and scheduling preferences."""
    username: str = Field(default="student", description="Account identifier")
    study_program: str = Field(default="Informatik / UZH", description="Degree program or university")
    semester: int = Field(default=3, description="Current semester")
    wake_time: str = Field(default="07:00", description="Wakeup time (HH:MM)")
    sleep_time: str = Field(default="23:00", description="Bedtime (HH:MM)")
    max_daily_study_minutes: int = Field(default=180, description="Daily cap for study sessions in minutes")
    pomodoro_minutes: int = Field(default=25, description="Focus session duration")
    calendar_ics_url: Optional[str] = Field(None, description="Subscribed university iCal/webcal feed URL")
    ankiweb_email: Optional[str] = Field(None, description="AnkiWeb email address")
    last_ankiweb_sync: Optional[str] = Field(None, description="Timestamp of last AnkiWeb sync")


class UserProfileUpdateRequest(BaseModel):
    """Request payload to update student profile settings."""
    study_program: Optional[str] = None
    semester: Optional[int] = None
    wake_time: Optional[str] = None
    sleep_time: Optional[str] = None
    max_daily_study_minutes: Optional[int] = None
    pomodoro_minutes: Optional[int] = None
    calendar_ics_url: Optional[str] = None
    ankiweb_email: Optional[str] = None


class SyncCalendarUrlRequest(BaseModel):
    """Request to import or synchronize timetable from a calendar URL (http, https, or webcal)."""
    url: str = Field(..., description="Remote iCal or webcal subscription URL")
    target_date: Optional[dt_date] = Field(None, description="Target date to filter events")
    save_to_db: bool = Field(default=True, description="Whether to persist the fetched schedule to SQLite")


class AttendanceUpdateRequest(BaseModel):
    """Payload to update whether a lecture was attended by the student."""
    event_id: int = Field(..., description="ID of the saved event")
    attended: Optional[bool] = Field(..., description="True if attended, False if skipped, None if pending")


class StudyLogCreateRequest(BaseModel):
    """Payload to log a completed study block."""
    topic_name: str = Field(..., description="Name of the topic studied")
    module_name: Optional[str] = Field(None, description="University module")
    duration_minutes: int = Field(..., description="Study duration in minutes")
    cards_reviewed: int = Field(..., description="Number of cards reviewed")
    seconds_per_card: float = Field(..., description="Average seconds spent per card")
    retention_rate: float = Field(..., description="Percentage of correct recalls (0.0 to 1.0)")
    lecture_attended: bool = Field(..., description="Whether the lecture for this topic was attended")


class AnkiWebSyncRequest(BaseModel):
    """Request to sync learning statistics from AnkiWeb."""
    email: Optional[str] = Field(None, description="AnkiWeb account email")
    password: Optional[str] = Field(None, description="AnkiWeb account password")
    api_token: Optional[str] = Field(None, description="AnkiConnect or API token")


# ============================================================================
# PHASE 1: EXAM PACING & PROGRESS TRACKING MODELS
# ============================================================================

class ExamItem(BaseModel):
    """An upcoming exam deadline."""
    id: int
    subject_name: str
    exam_date: str
    target_cards: int = 9633
    days_left: int
    notes: Optional[str] = None


class ExamCreateRequest(BaseModel):
    """Payload to create or update an exam."""
    subject_name: str = Field(..., description="Name of module or exam")
    exam_date: str = Field(..., description="Date in YYYY-MM-DD format")
    target_cards: int = Field(default=9633, description="Target card volume")
    notes: Optional[str] = None


class PacingConfigModel(BaseModel):
    """Configuration for free days and exam buffer."""
    free_weekdays: List[int] = Field(default_factory=lambda: [6], description="List of free weekdays (0=Mon, 6=Sun)")
    joker_dates: List[str] = Field(default_factory=list, description="List of specific off-dates (YYYY-MM-DD)")
    revision_buffer_days: int = Field(default=14, description="Days before exam reserved for pure revision")
    total_curriculum_cards: int = Field(default=9633, description="Total active cards in curriculum")


class PacingConfigUpdateRequest(BaseModel):
    """Payload to update pacing configuration."""
    free_weekdays: Optional[List[int]] = None
    joker_dates: Optional[List[str]] = None
    revision_buffer_days: Optional[int] = None
    total_curriculum_cards: Optional[int] = None


class DailyProgressLogItem(BaseModel):
    """Daily card review logging record."""
    log_date: str
    cards_completed: int
    minutes_spent: int = 0
    source: str = "manual"
    notes: Optional[str] = None


class ProgressLogCreateRequest(BaseModel):
    """Payload to record completed cards for a day."""
    cards_completed: int = Field(..., description="Number of cards finished today")
    minutes_spent: int = Field(default=0, description="Time spent in minutes")
    log_date: Optional[str] = Field(None, description="Date in YYYY-MM-DD format (defaults to target_date)")
    source: str = Field(default="manual", description="'manual' or 'anki_sync'")
    notes: Optional[str] = None


class ToggleJokerRequest(BaseModel):
    """Payload to toggle a specific date as rest / joker day."""
    date_str: str = Field(..., description="Date in YYYY-MM-DD format")


class ExamPacingResponse(BaseModel):
    """Complete pacing status and recommendations for the student."""
    target_date: str
    is_rest_day: bool
    rest_day_reason: Optional[str] = None
    next_exam: Optional[ExamItem] = None
    all_exams: List[ExamItem] = Field(default_factory=list)
    calendar_days_to_exam: int
    learning_days_remaining: int
    revision_buffer_days: int
    revision_start_date: str
    total_curriculum_cards: int
    total_cards_completed: int
    remaining_curriculum_cards: int
    daily_target_cards: int
    cards_completed_today: int
    cards_remaining_today: int
    completion_percentage_today: float
    overall_progress_percentage: float
    exam_readiness_score: float
    pacing_scenarios: Dict[str, int] = Field(
        default_factory=dict,
        description="Daily targets under different weekly rhythms (e.g. 7d, 6d, 5d)"
    )
    advice: str
    due_reviews_today: Optional[int] = Field(default=0, description="Fällige Wiederholungen aus Anki")
    total_daily_cards_needed: Optional[int] = Field(default=0, description="Gesamt (Neue Karten + Wiederholungen)")
    weakness_summary: Optional[str] = Field(default=None, description="Kurzzusammenfassung der Schwachstellen")


# ============================================================================
# PHASE 2: LECTURE DECISION, ANKI WEAKNESS & COMPARISON MODELS
# ============================================================================

class LectureModeRequest(BaseModel):
    """Request payload to set consumption mode for a scheduled lecture."""
    event_id: int = Field(..., description="ID of the saved event")
    mode: Optional[str] = Field(None, description="'live', 'stream_1_25', 'stream_1_5', 'stream_1_75', 'stream_2_0', 'slides_only', 'skipped'")
    consumption_mode: Optional[str] = Field(None, description="Alias for mode")
    duration_minutes: Optional[int] = Field(None, description="Duration in minutes")


class LectureModeResponse(BaseModel):
    """Response returning updated consumption mode and minutes saved."""
    event_id: int
    consumption_mode: str
    speed_factor: float
    time_saved_minutes: int
    duration_minutes: int
    lecture_attended: int


class TopicAnalyticsItem(BaseModel):
    """Detailed telemetry and weakness metrics for an Anki deck topic."""
    deck_id: int
    deck_name: str
    total_cards: int
    due_reviews_count: int
    review_count: int
    avg_ease: float
    fail_rate: float
    days_since_last_review: Optional[int] = None
    last_review_date: Optional[str] = None
    is_weakness: bool
    is_overdue: bool
    status_badge: str
    badge_color: str


class AnkiWeaknessResponse(BaseModel):
    """Response summarizing due reviews, learning cards, and topic weaknesses."""
    available: bool
    collection_path: Optional[str] = None
    due_reviews_count: int
    learning_cards_count: int
    review_cards_count: int
    new_cards_count: int
    weakness_topics: List[TopicAnalyticsItem] = Field(default_factory=list)
    overdue_topics: List[TopicAnalyticsItem] = Field(default_factory=list)
    all_topics: List[TopicAnalyticsItem] = Field(default_factory=list)
    summary: str


class ProgressComparisonResponse(BaseModel):
    """Comparative progress metrics between today, yesterday, and past 7 days."""
    target_date: str
    cards_today: int
    cards_yesterday: int
    diff_cards: int
    diff_percentage: float
    diff_label: str
    week_total_cards: int
    week_daily_average: float
    current_streak_days: int
    total_minutes_saved_today: int
    summary: str


class OlatStatusResponse(BaseModel):
    """OpenOLAT platform status, WebDAV access endpoints, and scanned slides."""
    platform: str
    url: str
    webdav_url: str
    online: bool
    status_code: Optional[int] = None
    message: str
    auth_methods: List[Dict[str, Any]] = Field(default_factory=list)
    local_slides_count: int = 0
    sample_slides: List[Dict[str, Any]] = Field(default_factory=list)
    webdav_configured: bool = True
    webdav_user: Optional[str] = "553131393539353502@uzh.ch"
    course_url: Optional[str] = "https://lms.uzh.ch/auth/RepositoryEntry/666697737/CourseNode/76022446801983"
    needs_vpn: bool = False
    vpn_instruction: Optional[str] = None


# ============================================================================
# PHASE 3: DIDACTIC CURRICULUM ROADMAP & DAILY 100-ANKI ASSIGNMENT MODELS
# ============================================================================

class CurriculumTopicSlot(BaseModel):
    """Specific portion of an Anki deck assigned on a given study day."""
    deck_name: str = Field(..., description="Full hierarchical Anki deck name")
    short_title: str = Field(..., description="Cleaned lecture/topic title")
    clean_title: Optional[str] = Field(None, description="Human-friendly topic name without raw numeric prefixes")
    lecturer: Optional[str] = Field(None, description="Identified lecturer (e.g. Manatschal, Kurt, Stockmann)")
    breadcrumb: Optional[str] = Field(None, description="Clean breadcrumb path (e.g. Blut & Immunsystem › Manatschal)")
    module_name: str = Field(..., description="Belonging curriculum module")
    cards_to_learn: int = Field(..., description="Exact number of cards to complete today from this deck")
    total_deck_cards: int = Field(..., description="Total size of this deck")
    deck_progress_pct: Optional[float] = Field(None, description="Progress within this deck")
    matched_slide_filename: Optional[str] = Field(None, description="Filename of matching lecture slide PDF")
    slide_coverage_pct: Optional[float] = Field(None, description="Slide coverage percentage")
    is_cycle_topic: bool = Field(False, description="True if topic covers biochemical cycles or cascades")
    recommended_mode: str = Field("stream_1_2", description="Recommended lecture consumption mode")
    badge_label: str = Field("Neu", description="Topic badge")
    didactic_reason: Optional[str] = Field(None, description="Medical rationale for recommended speed or skip")
    speed_factor: Optional[float] = Field(1.2, description="Recommended playback speed (0.0 for skip, 1.0, 1.2, 1.4)")
    # Synergistic Lecture-Anki fields:
    video_timestamp_guidance: Optional[str] = Field(None, description="Exact lecture video timestamps and chapters for these cards")
    video_start_time: Optional[str] = Field(None, description="Start timecode (e.g. 00:00)")
    video_end_time: Optional[str] = Field(None, description="End timecode (e.g. 54:00)")
    effective_watch_time_min: Optional[int] = Field(None, description="Effective streaming time in minutes")
    video_time_saved_min: Optional[int] = Field(None, description="Minutes saved by watching on recommended speed")
    red_thread: Optional[str] = Field(None, description="Narrative red thread explaining conceptual pre-requisites")
    cross_links: Optional[List[str]] = Field(default_factory=list, description="Clinical and physiological cross-connections")
    already_mastered_cards: Optional[int] = Field(0, description="Cards already completed in Anki")
    remaining_new_cards: Optional[int] = Field(0, description="Remaining new cards in this deck")
    concept_goal: Optional[str] = Field(None, description="Clear daily learning objective")


class DailyCurriculumAssignment(BaseModel):
    """Prescriptive daily study assignment with dynamically adjusted card quota."""
    date: str = Field(..., description="Date (YYYY-MM-DD)")
    day_of_week: str = Field(..., description="German day name (Montag, Dienstag...)")
    day_number: Optional[int] = Field(None, description="Active study day index (e.g. 1 to 97)")
    total_active_days: int = Field(97, description="Total active study days in semester")
    is_rest_day: bool = Field(False, description="True if Sunday or scheduled rest day")
    target_cards: int = Field(100, description="Final assigned new cards for today (0 on rest days)")
    base_quota: int = Field(100, description="Nominal base quota for an active study day")
    adjusted_target_cards: int = Field(100, description="Dynamically adjusted target after surplus deduction or deficit spread")
    quota_adjustment_reason: Optional[str] = Field(None, description="Reason for quota change (e.g. half surplus deducted or deficit spread)")
    surplus_deduction: int = Field(0, description="Bonus cards deducted from today due to yesterday's surplus")
    deficit_distributed: int = Field(0, description="Cards added to today due to spreading earlier deficit")
    topic_slots: List[CurriculumTopicSlot] = Field(default_factory=list, description="Subtopic breakdown for today")
    cumulative_cards_learned: int = Field(0, description="Total cumulative cards learned up to and including today")
    actual_cards_learned: int = Field(0, description="Actual real cards newly learned in curriculum so far")
    planned_cumulative_cards: int = Field(0, description="Theoretical planned cumulative cards according to schedule")
    total_curriculum_cards: int = Field(9633, description="Total cards in the 2. SJ curriculum")
    curriculum_progress_pct: float = Field(0.0, description="Percentage of entire semester curriculum completed")
    current_module: str = Field("", description="Active medical module name")
    summary: str = Field("", description="Action-oriented daily briefing")
    synergy_headline: Optional[str] = Field(None, description="Daily synergistic study headline (e.g. 'Vorlesungs-Priming -> Anki-Enkodierung')")
    recommended_study_sequence: Optional[List[str]] = Field(default_factory=list, description="Step-by-step guidance for today: 1. Vorlesung, 2. Anki, 3. Quervernetzung")
    exam_date: str = Field("2027-01-19", description="Target exam date")
    days_until_exam: int = Field(0, description="Days remaining until the exam")
    revision_buffer_days: int = Field(15, description="Free buffer days before exam after completing all 9,633 cards")


class CurriculumModuleMilestone(BaseModel):
    """Didactic block/module summary in the semester sequence."""
    module_id: int
    module_name: str
    card_count: int
    deck_count: int
    start_date: str
    end_date: str
    active_days: int
    share_pct: float


class CurriculumRoadmapResponse(BaseModel):
    """Full semester curriculum roadmap detailing all 9,633 cards across 6 modules and 97 days."""
    start_date: str
    completion_date: str
    exam_date: str
    revision_buffer_days: int
    total_cards: int
    total_active_days: int
    daily_quota: int = 100
    modules: List[CurriculumModuleMilestone] = Field(default_factory=list)
    schedule: List[DailyCurriculumAssignment] = Field(default_factory=list)


