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


def _minutes_to_time(m: int) -> str:
    h = (m // 60) % 24
    mins = m % 60
    return f"{h:02d}:{mins:02d}"


def _parse_time_to_minutes(t_str: str) -> int:
    try:
        parts = t_str.strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return 8 * 60 + 30


def generate_daily_science_rhythm(
    target_date: Optional[date] = None,
    events: Optional[List[CalendarEvent]] = None,
    cards_due_today: int = 100,
    new_cards_target: int = 100,
    start_time_str: str = "08:30",
    lunch_duration_mins: int = 75,
    include_lecture: bool = True,
) -> Dict[str, Any]:
    """
    Generates the scientific ultradian study schedule with precise time arithmetic.
    Fully customizable: start time, lunch break duration, lecture inclusion/skip.
    Integrates today's struggle cards and precise Feierabend calculation without artificial buffers.
    """
    t_date = target_date or date.today()
    tagged_events = [tag_event_mandatory_status(ev) for ev in (events or [])]
    mandatory_events = [ev for ev in tagged_events if getattr(ev, "is_mandatory", False)]

    # Time estimates based on gross study time
    rep_gross_mins = max(30, round((cards_due_today * 36.0) / 60.0))
    new_gross_mins = max(45, round((new_cards_target * 63.0) / 60.0))

    cur_m = _parse_time_to_minutes(start_time_str)
    blocks: List[Dict[str, Any]] = []
    total_study_mins = 0
    total_pause_mins = 0

    # 1. Block 1: Morning Reps
    dur_reps = 60
    s_time = _minutes_to_time(cur_m)
    e_time = _minutes_to_time(cur_m + dur_reps)
    blocks.append({
        "id": "block_morning_reps",
        "start_time": s_time,
        "end_time": e_time,
        "duration_minutes": dur_reps,
        "title": "Block 1: Morgen-Repetitionen (~100 Karten)",
        "subtitle": "Active Recall & Elvanse-Anflutung",
        "focus_type": "active_recall",
        "icon": "🧠",
        "color": "#58a6ff",
        "badge": f"Active Recall ({dur_reps}m)",
        "description": f"Das Gehirn ist frisch. Fällige Wiederholungen (~{cards_due_today} Karten, ~{rep_gross_mins} Min. Brutto) abarbeiten. Bringt dich ohne Überforderung in den Lernflow.",
        "is_break": False,
        "is_mandatory": False,
    })
    cur_m += dur_reps
    total_study_mins += dur_reps

    # 2. Pause 1
    dur_p1 = 15
    s_time = _minutes_to_time(cur_m)
    e_time = _minutes_to_time(cur_m + dur_p1)
    blocks.append({
        "id": "pause_1",
        "start_time": s_time,
        "end_time": e_time,
        "duration_minutes": dur_p1,
        "title": "Pause 1: Diffuse Mode (Kein Bildschirm!)",
        "subtitle": "Synaptische Konsolidierung & Hydratation",
        "focus_type": "pause",
        "icon": "☕",
        "color": "#3fb950",
        "badge": "Pause (15m)",
        "description": "Zwingende Bildschirmpause: Aufstehen, Wasser trinken, Fenster öffnen. Keine Social Media!",
        "is_break": True,
        "is_mandatory": False,
    })
    cur_m += dur_p1
    total_pause_mins += dur_p1

    # 3. Block 2: Deep Encoding New Cards
    dur_new = 105
    s_time = _minutes_to_time(cur_m)
    e_time = _minutes_to_time(cur_m + dur_new)
    blocks.append({
        "id": "block_new_cards",
        "start_time": s_time,
        "end_time": e_time,
        "duration_minutes": dur_new,
        "title": "Block 2: 100 Neue Karten (Deep Encoding / Elvanse-Peak)",
        "subtitle": f"Curriculum Tagesziel ({new_cards_target} neue Karten / Vormittags-Wirkpeak)",
        "focus_type": "deep_encoding",
        "icon": "🔥",
        "color": "#d2a8ff",
        "badge": f"Deep Encoding ({dur_new}m)",
        "description": f"Absolutes Dopamin- und Konzentrationsfenster: {new_cards_target} neue Karten hochkonzentriert einprägen (~{new_gross_mins} Min. Brutto inkl. Verknüpfungen und Notizen).",
        "is_break": False,
        "is_mandatory": False,
    })
    cur_m += dur_new
    total_study_mins += dur_new

    # 4. Pause 2
    dur_p2 = 15
    s_time = _minutes_to_time(cur_m)
    e_time = _minutes_to_time(cur_m + dur_p2)
    blocks.append({
        "id": "pause_2",
        "start_time": s_time,
        "end_time": e_time,
        "duration_minutes": dur_p2,
        "title": "Pause 2: Gehirn-Reset",
        "subtitle": "Erfrischung & Bewegung",
        "focus_type": "pause",
        "icon": "🧘",
        "color": "#3fb950",
        "badge": "Pause (15m)",
        "description": "Frische Luft, Dehnen, Durchatmen vor dem nächsten Arbeitsblock.",
        "is_break": True,
        "is_mandatory": False,
    })
    cur_m += dur_p2
    total_pause_mins += dur_p2

    # 5. Optional Block 3: Lecture / Concept Stream
    if include_lecture:
        dur_lec = 60
        s_time = _minutes_to_time(cur_m)
        e_time = _minutes_to_time(cur_m + dur_lec)
        blocks.append({
            "id": "block_podcasts",
            "start_time": s_time,
            "end_time": e_time,
            "duration_minutes": dur_lec,
            "title": "Block 3: Transfer & Vormittags-Abschluss",
            "subtitle": "Skript-Abgleich / Offene Karten klären",
            "focus_type": "concept_stream",
            "icon": "📖",
            "color": "#79c0ff",
            "badge": f"Transfer ({dur_lec}m)",
            "description": "Kurzer Abgleich mit den Vorlesungsfolien oder Puffer für letzte offene Karten des Vormittags vor der Mittagspause.",
            "is_break": False,
            "is_mandatory": False,
        })
        cur_m += dur_lec
        total_study_mins += dur_lec

    # 6. Lunch Break
    dur_lunch = max(20, min(120, lunch_duration_mins))
    lunch_badge = "Mensa (75m)" if dur_lunch >= 70 else (f"Express ({dur_lunch}m)" if dur_lunch <= 35 else f"Pause ({dur_lunch}m)")
    s_time = _minutes_to_time(cur_m)
    e_time = _minutes_to_time(cur_m + dur_lunch)
    blocks.append({
        "id": "pause_lunch",
        "start_time": s_time,
        "end_time": e_time,
        "duration_minutes": dur_lunch,
        "title": f"Mittagspause & Erholung ({dur_lunch} Min.)",
        "subtitle": "Proteinreiche Mahlzeit & Kognitiver Abstand",
        "focus_type": "meal_rest",
        "icon": "🥗",
        "color": "#8b949e",
        "badge": lunch_badge,
        "description": "Proteinreiche Mahlzeit (verhindert Glukosesturz), frische Luft und vollständiger kognitiver Abstand.",
        "is_break": True,
        "is_mandatory": False,
    })
    cur_m += dur_lunch
    total_pause_mins += dur_lunch

    # 7. Afternoon Slot
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
                "color": "#a371f7",
                "badge": "🏛️ OBLIGATORISCH",
                "description": m_ev.recommendation_reason or "Offizielles Praktikum / Testatkurs an der UZH. Präsenzpflicht vor Ort!",
                "is_break": False,
                "is_mandatory": True,
            })
            # If mandatory event ends later than cur_m, update cur_m
            ev_end_m = _parse_time_to_minutes(ev_end_str)
            if ev_end_m > cur_m:
                cur_m = ev_end_m
            total_study_mins += dur
    elif include_lecture:
        dur_afternoon = 90
        s_time = _minutes_to_time(cur_m)
        e_time = _minutes_to_time(cur_m + dur_afternoon)
        blocks.append({
            "id": "block_afternoon_flex",
            "start_time": s_time,
            "end_time": e_time,
            "duration_minutes": dur_afternoon,
            "title": "Nachmittag: Podcast für MORGEN (1.2x–1.4x)",
            "subtitle": "Auditive Vorentlastung des morgigen Anki-Themas",
            "focus_type": "afternoon_flex",
            "icon": "🎧",
            "color": "#388bfd",
            "badge": f"24h-Pipeline ({dur_afternoon}m)",
            "description": "Perfekt für das Nachmittagstief: Den Podcast für morgen auf 1.2x–1.4x hören. Das Gehirn baut im Schlaf das Schema auf, damit du morgen im Elvanse-Peak durch die neuen Karten fliegst!",
            "is_break": False,
            "is_mandatory": False,
        })
        cur_m += dur_afternoon
        total_study_mins += dur_afternoon

    # 8. Evening Lapse Review with Struggle Cards Integration
    from app.services.anki_struggle_service import get_today_struggle_analysis
    struggle_data = get_today_struggle_analysis(t_date)

    dur_lapse = 30
    s_time = _minutes_to_time(cur_m)
    e_time = _minutes_to_time(cur_m + dur_lapse)
    struggle_count = struggle_data.get("total_struggles", 0)
    lapses_count = struggle_data.get("lapses_count", 0)
    hard_count = struggle_data.get("hard_count", 0)
    
    lapse_subtitle = (
        f"{struggle_count} Problemkarten heute ({lapses_count}x Nochmal, {hard_count}x Schwer)"
        if struggle_count > 0 else "Nur heute mit 'Nochmal' bewertete Karten"
    )

    blocks.append({
        "id": "block_evening_lapse",
        "start_time": s_time,
        "end_time": e_time,
        "duration_minutes": dur_lapse,
        "title": "Tagesabschluss: Mini Lapse-Review",
        "subtitle": lapse_subtitle,
        "focus_type": "lapse_cleanup",
        "icon": "🔁",
        "color": "#db6d28",
        "badge": f"Lapse-Filter ({dur_lapse}m)",
        "description": "Wissenschaftlich fundierter 15–30 Min. Abschluss: Gezieltes Durchklicken der Problemkarten des Tages schützt vor dem 'Vergessen über Nacht' (Ebbinghaus-Konsolidierung). Bei Zeitdruck direkt die 2 relevanten Dozentenfolien öffnen!",
        "is_break": False,
        "is_mandatory": False,
        "struggles_summary": struggle_data.get("summary", ""),
        "total_struggles": struggle_count,
        "anki_query": struggle_data.get("anki_query", "rated:1:1"),
        "anki_browse_url": struggle_data.get("anki_browse_url", "anki://search?q=rated:1:1"),
        "top_struggles": struggle_data.get("cards", [])[:5],
    })
    cur_m += dur_lapse
    total_study_mins += dur_lapse

    # 9. Feierabend & Evening Free (starts exactly at the end of lapse review)
    feierabend_time = _minutes_to_time(cur_m)
    dur_evening = max(60, (22 * 60) - cur_m)
    blocks.append({
        "id": "evening_free",
        "start_time": feierabend_time,
        "end_time": "22:00",
        "duration_minutes": dur_evening,
        "title": f"🎉 Feierabend ab {feierabend_time} & Sport am Abend",
        "subtitle": "Kognitive Regeneration & BDNF-Ausschüttung",
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
        "start_time": _minutes_to_time(_parse_time_to_minutes(start_time_str)),
        "lunch_duration_minutes": dur_lunch,
        "include_lecture": include_lecture,
        "feierabend_time": feierabend_time,
        "total_study_minutes": total_study_mins,
        "total_pause_minutes": total_pause_mins,
        "mandatory_events_count": len(mandatory_events),
        "blocks": blocks,
    }
