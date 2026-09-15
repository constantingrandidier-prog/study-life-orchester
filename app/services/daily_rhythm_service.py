"""Service for calculating the scientific 08:30 study rhythm and identifying mandatory UZH clinical practicals."""

from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional
from app.models import CalendarEvent

MANDATORY_PRACTICAL_KEYWORDS = [
    "praktikum",
    "untersuchungskurs",
    "präparier",
    "praeparier",
    "visite",
    "testat",
    "kurs klinischer",
    "blockkurs",
    "skills lab",
]

def is_mandatory_practical(title: str, description: str = "") -> bool:
    """Returns True if the event has mandatory in-person attendance requirements at UZH."""
    combined = f"{title} {description}".lower()
    return any(k in combined for k in MANDATORY_PRACTICAL_KEYWORDS)


def tag_event_mandatory_status(event: CalendarEvent) -> CalendarEvent:
    """Tags a CalendarEvent with mandatory status, badge, and prominent violet color if applicable."""
    if is_mandatory_practical(event.title, event.description or ""):
        event.is_mandatory = True
        event.badge_label = "🏛️ OBLIGATORISCH (Präsenzpflicht)"
        event.badge_color = "#a371f7"  # Distinct bright violet for mandatory practicals
        event.recommendation = "attend"
        event.recommendation_reason = (
            "Offizielles Praktikum / Testatkurs an der UZH mit Anwesenheitspflicht vor Ort! "
            "Praktische Fertigkeiten lassen sich nicht digital durch Podcasts ersetzen."
        )
    return event


def generate_daily_science_rhythm(
    target_date: Optional[date] = None,
    events: Optional[List[CalendarEvent]] = None,
    cards_due_today: int = 100,
    new_cards_target: int = 100,
) -> Dict[str, Any]:
    """
    Generates the scientific ultradian study schedule starting precisely at 08:30 AM.
    Optimized for memorization (Active Recall -> Pause -> Deep Encoding -> Pause -> Concept Stream).
    """
    t_date = target_date or date.today()
    tagged_events = [tag_event_mandatory_status(ev) for ev in (events or [])]

    # Check for mandatory events on this day
    mandatory_events = [ev for ev in tagged_events if getattr(ev, "is_mandatory", False)]

    # Time estimates based on real-world gross study time (1h / 100 reps, ~1h45 / 100 new cards)
    rep_gross_mins = max(30, round((cards_due_today * 36.0) / 60.0))
    new_gross_mins = max(45, round((new_cards_target * 63.0) / 60.0))

    # Base schedule blocks starting at 08:30
    blocks = [
        {
            "id": "block_morning_reps",
            "start_time": "08:30",
            "end_time": "09:30",
            "duration_minutes": 60,
            "title": "Block 1: Morgen-Repetitionen (~100 Karten)",
            "subtitle": "Active Recall & Elvanse-Anflutung",
            "focus_type": "active_recall",
            "icon": "🧠",
            "color": "#58a6ff",
            "badge": "Active Recall (60m)",
            "description": f"Das Gehirn ist frisch. Fällige Wiederholungen (~{cards_due_today} Karten, ~{rep_gross_mins} Min. Brutto) abarbeiten. Bringt dich ohne Überforderung in den Lernflow.",
            "is_break": False,
            "is_mandatory": False,
        },
        {
            "id": "pause_1",
            "start_time": "09:30",
            "end_time": "09:45",
            "duration_minutes": 15,
            "title": "Pause 1: Diffuse Mode (Kein Bildschirm!)",
            "subtitle": "Synaptische Konsolidierung & Hydratation",
            "focus_type": "pause",
            "icon": "☕",
            "color": "#3fb950",
            "badge": "Pause (15m)",
            "description": "Zwingende Bildschirmpause: Aufstehen, Wasser trinken, Fenster öffnen. Keine Social Media!",
            "is_break": True,
            "is_mandatory": False,
        },
        {
            "id": "block_new_cards",
            "start_time": "09:45",
            "end_time": "11:30",
            "duration_minutes": 105,
            "title": "Block 2: 100 Neue Karten (Deep Encoding / Elvanse-Peak)",
            "subtitle": f"Curriculum Tagesziel ({new_cards_target} neue Karten / Vormittags-Wirkpeak)",
            "focus_type": "deep_encoding",
            "icon": "🔥",
            "color": "#d2a8ff",
            "badge": "Deep Encoding (105m)",
            "description": f"Absolutes Dopamin- und Konzentrationsfenster: {new_cards_target} neue Karten hochkonzentriert einprägen (~{new_gross_mins} Min. Brutto inkl. Verknüpfungen und Notizen).",
            "is_break": False,
            "is_mandatory": False,
        },
        {
            "id": "pause_2",
            "start_time": "11:30",
            "end_time": "11:45",
            "duration_minutes": 15,
            "title": "Pause 2: Gehirn-Reset",
            "subtitle": "Erfrischung & Bewegung",
            "focus_type": "pause",
            "icon": "🧘",
            "color": "#3fb950",
            "badge": "Pause (15m)",
            "description": "Frische Luft, Dehnen, Durchatmen vor den Vorlesungs-Konzepten.",
            "is_break": True,
            "is_mandatory": False,
        },
        {
            "id": "block_podcasts",
            "start_time": "11:45",
            "end_time": "12:45",
            "duration_minutes": 60,
            "title": "Block 3: Transfer & Vormittags-Abschluss",
            "subtitle": "Skript-Abgleich / Offene Karten klären",
            "focus_type": "concept_stream",
            "icon": "📖",
            "color": "#79c0ff",
            "badge": "Vormittags-Abschluss (60m)",
            "description": "Kurzer Abgleich mit den Vorlesungsfolien oder Puffer für letzte offene Karten des Vormittags vor der Mittagspause.",
            "is_break": False,
            "is_mandatory": False,
        },
        {
            "id": "pause_lunch",
            "start_time": "12:45",
            "end_time": "14:00",
            "duration_minutes": 75,
            "title": "Mittagspause & Erholung",
            "subtitle": "Mensa & Proteinreiche Mahlzeit",
            "focus_type": "meal_rest",
            "icon": "🥗",
            "color": "#8b949e",
            "badge": "Mensa (75m)",
            "description": "Proteinreiche Mahlzeit (verhindert Glukosesturz), frische Luft und vollständiger kognitiver Abstand.",
            "is_break": True,
            "is_mandatory": False,
        },
    ]

    # Afternoon slot: integrate mandatory events if scheduled, or flexible study
    if mandatory_events:
        for m_ev in mandatory_events:
            ev_start_str = m_ev.start_time.strftime("%H:%M")
            ev_end_str = m_ev.end_time.strftime("%H:%M")
            dur = int((m_ev.end_time - m_ev.start_time).total_seconds() / 60)
            blocks.append({
                "id": f"mandatory_event_{m_ev.id or 0}",
                "start_time": ev_start_str,
                "end_time": ev_end_str,
                "duration_minutes": dur,
                "title": f"🏛️ {m_ev.title}",
                "subtitle": "UZH Vor-Ort Präsenzpflicht",
                "focus_type": "mandatory_in_person",
                "icon": "🔒",
                "color": "#a371f7",  # Bold purple
                "badge": "🏛️ OBLIGATORISCH",
                "description": m_ev.recommendation_reason or "Offizielles Praktikum / Testatkurs an der UZH. Präsenzpflicht vor Ort!",
                "is_break": False,
                "is_mandatory": True,
            })
    else:
        blocks.append({
            "id": "block_afternoon_flex",
            "start_time": "14:00",
            "end_time": "17:00",
            "duration_minutes": 180,
            "title": "Nachmittag: Praktika ODER Podcast für MORGEN (1.2x–1.4x)",
            "subtitle": "Pflicht-Praktikum oder Vorbereitung des morgigen Anki-Themas",
            "focus_type": "afternoon_flex",
            "icon": "🎧",
            "color": "#388bfd",
            "badge": "24h-Pipeline (180m)",
            "description": "Perfekt für das Nachmittagstief: Pflichtpraktika absolvieren ODER den Podcast für morgen auf 1.2x–1.4x hören. Das Gehirn baut im Schlaf das Schema auf, damit du morgen im Elvanse-Peak durch die neuen Karten fliegst!",
            "is_break": False,
            "is_mandatory": False,
        })

    # Evening review before sport
    blocks.append({
        "id": "block_evening_lapse",
        "start_time": "17:00",
        "end_time": "17:30",
        "duration_minutes": 30,
        "title": "Tagesabschluss: Mini Lapse-Review",
        "subtitle": "Nur heute mit 'Nochmal' bewertete Karten",
        "focus_type": "lapse_cleanup",
        "icon": "🔁",
        "color": "#db6d28",
        "badge": "Lapse-Filter (30m)",
        "description": "Kurzer Durchklick der Problemkarten des Tages. Schützt vor dem 'Vergessen über Nacht'.",
        "is_break": False,
        "is_mandatory": False,
    })

    blocks.append({
        "id": "evening_free",
        "start_time": "17:30",
        "end_time": "22:00",
        "duration_minutes": 270,
        "title": "Feierabend & Sport am Abend",
        "subtitle": "Kognitive Regeneration & BDNF",
        "focus_type": "evening_free",
        "icon": "🏃",
        "color": "#238636",
        "badge": "Sport & Freizeit",
        "description": "Keine Lernzeiten mehr! Sport am Abend schüttet BDNF aus, puffert den Elvanse-Rebound ab und verankert das Gelernte in der Nacht.",
        "is_break": True,
        "is_mandatory": False,
    })

    return {
        "date": t_date.isoformat(),
        "start_time": "08:30",
        "total_study_minutes": 60 + 105 + 60 + 30,
        "total_pause_minutes": 15 + 15 + 75,
        "mandatory_events_count": len(mandatory_events),
        "blocks": blocks,
    }
