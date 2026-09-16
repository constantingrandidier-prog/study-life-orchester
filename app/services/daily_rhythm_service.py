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
    "klinischer kurs",
    "blockkurs",
    "skills lab",
    "tutorat",
    "tutorium",
    "pol ",
    "pol-",
    "problemorientiert",
    "absenz",
    "anwesenheitspflicht",
    "präsenzpflicht",
    "praesenzpflicht",
    "obligatorisch",
    "seziersaal",
    "mikroskopierkurs",
    "reanimation",
    "notfallkurs",
]

def is_mandatory_practical(title: str, description: str = "") -> bool:
    """Returns True if the event has mandatory in-person attendance requirements at UZH."""
    t_lower = (title or "").lower().strip()
    d_lower = (description or "").lower().strip()
    combined = f"{t_lower} {d_lower}"

    # Explicit format from UZH Moses ICS export
    if "veranstaltungsformat: praktikum" in d_lower or \
       "veranstaltungsformat: tutorat" in d_lower or \
       "veranstaltungsformat: klinischer kurs" in d_lower:
        return True

    # Explicit attendance warning in description
    if "absenz" in combined or "anwesenheitspflicht" in combined or "präsenzpflicht" in combined or "obligatorisch" in combined:
        return True

    # Introductory lecture to a course format is a lecture unless marked mandatory
    if t_lower.startswith("einführung") and "veranstaltungsformat: vorlesung" in d_lower:
        return False

    return any(k in combined for k in MANDATORY_PRACTICAL_KEYWORDS)


def tag_event_mandatory_status(event: CalendarEvent) -> CalendarEvent:
    """Tags a CalendarEvent with mandatory status, badge, and prominent violet color if applicable."""
    if is_mandatory_practical(event.title, event.description or ""):
        event.is_mandatory = True
        event.badge_label = "🏛️ OBLIGATORISCH (Präsenzpflicht)"
        event.badge_color = "#a371f7"  # Distinct bright violet for mandatory practicals
        event.recommendation = "attend"
        event.recommendation_reason = (
            "Offizielles Praktikum / Tutorat an der UZH mit Anwesenheitspflicht vor Ort! "
            "Praktische Fertigkeiten und Testate lassen sich nicht digital durch Podcasts ersetzen."
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
    curriculum_assignment: Optional[Dict[str, Any]] = None,
    removed_block_ids: Optional[List[str]] = None,
    postponed_blocks: Optional[List[Dict[str, Any]]] = None,
    custom_block_order: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generates the scientific ultradian study schedule with precise time arithmetic.
    Fully customizable: start time, lunch break duration, lecture inclusion/skip.
    Integrates today's struggle cards, morning Anki focus, and afternoon lecture priming for tomorrow.
    Supports dynamic block deletion and intelligent scheduling of postponed tasks from previous days.
    """
    t_date = target_date or date.today()
    date_iso = t_date.isoformat()

    if events is None:
        try:
            from app.db.repository import get_saved_events
            raw_evs = get_saved_events(t_date)
            events = [CalendarEvent(**e) for e in raw_evs]
        except Exception:
            events = []

    tagged_events = [tag_event_mandatory_status(ev) for ev in (events or [])]
    mandatory_events = [ev for ev in tagged_events if getattr(ev, "is_mandatory", False)]

    # Look up tomorrow's calendar for upcoming mandatory practicals/tutorats
    next_date = t_date + timedelta(days=1)
    tomorrow_mandatory = []
    try:
        from app.db.repository import get_saved_events
        tom_raw = get_saved_events(next_date)
        for e in tom_raw:
            c_ev = CalendarEvent(**e)
            if is_mandatory_practical(c_ev.title, c_ev.description or ""):
                tomorrow_mandatory.append(tag_event_mandatory_status(c_ev))
    except Exception:
        pass

    # Load persistent removed and postponed actions if not explicitly passed
    removed_set = set(removed_block_ids or [])
    active_postponed = list(postponed_blocks if postponed_blocks is not None else [])

    try:
        from app.db.repository import get_rhythm_actions_for_date
        db_actions = get_rhythm_actions_for_date(date_iso)
        if not removed_block_ids:
            removed_set.update(db_actions.get("removed_block_ids", []))
        if postponed_blocks is None:
            active_postponed.extend(db_actions.get("postponed_blocks", []))
        if not custom_block_order:
            custom_block_order = db_actions.get("custom_order", [])
    except Exception:
        pass

    if curriculum_assignment is None:
        try:
            from app.services.curriculum_roadmap_service import get_daily_curriculum_assignment
            curriculum_assignment = get_daily_curriculum_assignment(target_date=t_date)
        except Exception:
            curriculum_assignment = None

    if curriculum_assignment:
        new_cards_target = curriculum_assignment.get("adjusted_target_cards", new_cards_target or 101)
        today_slots = curriculum_assignment.get("topic_slots", [])
        slot_summary = " + ".join(f"{s['cards_to_learn']}× {s.get('clean_title') or s['short_title']}" for s in today_slots) if today_slots else f"{new_cards_target} neue Karten"
        tomorrow_data = curriculum_assignment.get("tomorrow_preview") or {}
    else:
        today_slots = []
        slot_summary = f"{new_cards_target} neue Karten"
        tomorrow_data = {}

    # Time estimates based on gross study time
    rep_gross_mins = max(30, round((cards_due_today * 36.0) / 60.0))
    new_gross_mins = max(45, round((new_cards_target * 63.0) / 60.0))

    cur_m = _parse_time_to_minutes(start_time_str)
    blocks: List[Dict[str, Any]] = []
    total_study_mins = 0
    total_pause_mins = 0

    def add_block_if_active(b_dict: Dict[str, Any]) -> bool:
        nonlocal cur_m, total_study_mins, total_pause_mins
        bid = b_dict.get("id")
        if bid and bid in removed_set:
            return False
        dur = b_dict.get("duration_minutes", 30)
        s_time = _minutes_to_time(cur_m)
        e_time = _minutes_to_time(cur_m + dur)
        b_dict["start_time"] = s_time
        b_dict["end_time"] = e_time
        cur_m += dur
        if b_dict.get("is_break"):
            total_pause_mins += dur
        else:
            total_study_mins += dur
        blocks.append(b_dict)
        return True

    # 1. Block 1: Morning Reps
    dur_reps = 60
    add_block_if_active({
        "id": "block_morning_reps",
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

    # 2. Pause 1
    dur_p1 = 15
    add_block_if_active({
        "id": "pause_1",
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

    # 3. Block 2: Deep Encoding New Cards (Curriculum Today)
    dur_new = 105
    add_block_if_active({
        "id": "block_new_cards",
        "duration_minutes": dur_new,
        "title": f"Block 2: {new_cards_target} Neue Karten HEUTE (Deep Encoding)",
        "subtitle": f"{slot_summary} • Vormittags-Fokus",
        "focus_type": "deep_encoding",
        "icon": "🔥",
        "color": "#d2a8ff",
        "badge": f"Deep Encoding ({dur_new}m)",
        "description": f"Absolutes Dopamin- und Konzentrationsfenster: Exakt {new_cards_target} neue Karten für HEUTE hochkonzentriert einprägen ({slot_summary}). Vorlesung wurde bereits gestern Nachmittag geprimed!",
        "is_break": False,
        "is_mandatory": False,
        "target_cards": new_cards_target,
        "topic_slots": today_slots,
        "today_summary": slot_summary,
    })

    # 4. Pause 2
    dur_p2 = 15
    add_block_if_active({
        "id": "pause_2",
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

    # 5. Optional Block 3: Lecture / Concept Stream
    if include_lecture:
        dur_lec = 60
        add_block_if_active({
            "id": "block_podcasts",
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

    # 6. Lunch Break
    dur_lunch = max(20, min(120, lunch_duration_mins))
    lunch_badge = "Mensa (75m)" if dur_lunch >= 70 else (f"Express ({dur_lunch}m)" if dur_lunch <= 35 else f"Pause ({dur_lunch}m)")
    add_block_if_active({
        "id": "pause_lunch",
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

    # 7. Postponed Tasks Injection (Scientific Slot: 14:00 Post-Lunch Auditory Prime Window)
    for p in active_postponed:
        p_id = p.get("id") or "postponed_task"
        p_title = p.get("title") or "Verschobener Schritt"
        p_dur = min(90, max(30, int(p.get("duration_minutes", 75) or 75)))
        p_from = p.get("_postponed_from") or p.get("postponed_from") or "gestern"

        clean_title = p_title.replace("Nachmittag: ", "").replace("[Nachhol-Block] ", "").strip()

        add_block_if_active({
            "id": f"postponed_{p_id}",
            "original_id": p_id,
            "duration_minutes": p_dur,
            "title": f"⏩ [Nachhol-Block] {clean_title}",
            "subtitle": f"Von {p_from} verschoben • Neuro-optimal: Nachmittags-Fokus (14:00)",
            "focus_type": "postponed_catchup",
            "icon": "⏩",
            "color": "#f59f00",
            "badge": "⏩ Von gestern verschoben (Optimal eingetaktet)",
            "description": (
                f"Wissenschaftlich optimal nach der Mittagspause eingetaktet: Dein Arbeitsgedächtnis "
                f"ist jetzt ideal aufnahmefähig für die auditive Vorentlastung dieser verschobenen Vorlesung. "
                f"{p.get('description') or ''}"
            ),
            "is_break": False,
            "is_mandatory": False,
            "is_postponed": True,
            "postponed_from": p_from,
            "vam_url": p.get("vam_url"),
            "podcast_folder_name": p.get("podcast_folder_name"),
            "slide_filename": p.get("slide_filename"),
            "slide_rel_path": p.get("slide_rel_path"),
            "tomorrow_lecture_title": p.get("tomorrow_lecture_title") or clean_title,
        })

    # 8. Afternoon Lecture Priming (24h-Pipeline for Tomorrow)
    has_afternoon_mandatory_conflict = any(
        m for m in mandatory_events
        if _parse_time_to_minutes(m.start_time.strftime("%H:%M")) < (15 * 60 + 30)
        and _parse_time_to_minutes(m.end_time.strftime("%H:%M")) > (14 * 60)
    )

    if include_lecture and not has_afternoon_mandatory_conflict:
        dur_afternoon = 90
        tom_title = tomorrow_data.get("primary_lecture_title") or "Vorlesung für MORGEN"
        tom_lec = tomorrow_data.get("primary_lecturer") or "Dozententeam"
        tom_date = tomorrow_data.get("primary_lecture_date")
        tom_cards = tomorrow_data.get("target_cards", 101)
        tom_topics = tomorrow_data.get("topics_summary") or "morgige Anki-Karten"
        tom_speed = tomorrow_data.get("primary_speed_factor", 1.2)
        tom_timecode = tomorrow_data.get("primary_timecode_guidance")

        tom_m_warning = ""
        if tomorrow_mandatory:
            first_m = tomorrow_mandatory[0]
            m_time = first_m.start_time.strftime("%H:%M")
            tom_m_warning = f" • ⚠️ Morgen {m_time} Uhr: 🏛️ {first_m.title} (Präsenzpflicht!)"

        title_text = f"Nachmittag: Vorlesung für MORGEN sichten – {tom_title}"
        subtitle_text = f"👨‍🏫 {tom_lec} • Bereitet {tom_cards} Anki-Karten für morgen vor{tom_m_warning}"
        desc_text = f"Auditive Vorentlastung für morgen: Vorlesung '{tom_title}'{' (' + tom_date + ')' if tom_date else ''} auf {tom_speed}x sichten{' (' + tom_timecode + ')' if tom_timecode else ''}. Bereitet die morgigen {tom_cards} neuen Karten vor ({tom_topics}). Das Gehirn baut im Schlaf das Schema auf!"
        if tomorrow_mandatory:
            desc_text += f" Wichtig: Morgen ab {tomorrow_mandatory[0].start_time.strftime('%H:%M')} Uhr findet das obligatorische '{tomorrow_mandatory[0].title}' vor Ort statt."

        add_block_if_active({
            "id": "block_afternoon_flex",
            "duration_minutes": dur_afternoon,
            "title": title_text,
            "subtitle": subtitle_text,
            "focus_type": "afternoon_flex",
            "icon": "🎧",
            "color": "#388bfd",
            "badge": f"24h-Pipeline ({dur_afternoon}m)",
            "description": desc_text,
            "is_break": False,
            "is_mandatory": False,
            "tomorrow_preview": tomorrow_data,
            "tomorrow_cards": tom_cards,
            "tomorrow_topics": tom_topics,
            "tomorrow_lecture_title": tom_title,
            "tomorrow_lecture_date": tom_date,
            "tomorrow_lecturer": tom_lec,
            "vam_url": tomorrow_data.get("lecture_url"),
            "podcast_folder_name": tomorrow_data.get("podcast_folder_name"),
            "slide_filename": tomorrow_data.get("slide_filename"),
            "slide_rel_path": tomorrow_data.get("slide_rel_path"),
        })

    # 9. Fixed Mandatory In-Person Sessions (Praktika, Tutorate, Testate, Klinische Kurse)
    sorted_mandatory = sorted(mandatory_events, key=lambda ev: ev.start_time)
    for m_ev in sorted_mandatory:
        ev_start_str = m_ev.start_time.strftime("%H:%M")
        ev_end_str = m_ev.end_time.strftime("%H:%M")
        ev_start_m = _parse_time_to_minutes(ev_start_str)
        ev_end_m = _parse_time_to_minutes(ev_end_str)
        dur = max(15, ev_end_m - ev_start_m)

        # If there is a noticeable gap between study work and this mandatory session, insert a buffer/commute block
        if ev_start_m > cur_m and (ev_start_m - cur_m) >= 25:
            gap_dur = ev_start_m - cur_m
            gap_h = gap_dur // 60
            gap_rem = gap_dur % 60
            dur_label = f"{gap_h}h {gap_rem}m" if gap_h > 0 else f"{gap_rem}m"
            loc_label = (m_ev.location or "Campus Irchel").split(",")[0].strip()

            blocks.append({
                "id": f"buffer_commute_{m_ev.id or 0}",
                "start_time": _minutes_to_time(cur_m),
                "end_time": _minutes_to_time(ev_start_m),
                "duration_minutes": gap_dur,
                "title": f"🚶 Puffer, Vorbereitung & Wegzeit ({loc_label})",
                "subtitle": f"Kognitive Erholung & Transfer zum Kursort • {dur_label}",
                "focus_type": "pause",
                "icon": "🚶",
                "color": "#3fb950",
                "badge": f"Puffer ({dur_label})",
                "description": f"Freie Zeit für Erholung, Snack, Durchatmen und rechtzeitigen Transfer zum Kursort ({m_ev.location or 'UZH'}).",
                "is_break": True,
                "is_mandatory": False,
            })
            total_pause_mins += gap_dur
            cur_m = ev_start_m

        loc_text = f" • {m_ev.location}" if m_ev.location else ""
        desc_full = (m_ev.description or m_ev.recommendation_reason or "Offizielles Praktikum / Tutorat an der UZH mit Anwesenheitspflicht vor Ort!").strip()

        blocks.append({
            "id": f"mandatory_event_{m_ev.id or 0}",
            "start_time": ev_start_str,
            "end_time": ev_end_str,
            "duration_minutes": dur,
            "title": f"🏛️ {m_ev.title}",
            "subtitle": f"UZH Vor-Ort Präsenzpflicht{loc_text}",
            "focus_type": "mandatory_in_person",
            "icon": "🏛️",
            "color": "#a371f7",
            "badge": "🏛️ OBLIGATORISCH (Präsenzpflicht)",
            "description": desc_full,
            "is_break": False,
            "is_mandatory": True,
            "location": m_ev.location,
        })
        total_study_mins += dur
        cur_m = max(cur_m, ev_end_m)

    # 10. Evening Lapse Review with Struggle Cards Integration
    from app.services.anki_struggle_service import get_today_struggle_analysis
    struggle_data = get_today_struggle_analysis(t_date)

    dur_lapse = 30
    struggle_count = struggle_data.get("total_struggles", 0)
    lapses_count = struggle_data.get("lapses_count", 0)
    hard_count = struggle_data.get("hard_count", 0)

    lapse_subtitle = (
        f"{struggle_count} Problemkarten heute ({lapses_count}x Nochmal, {hard_count}x Schwer)"
        if struggle_count > 0 else "Nur heute mit 'Nochmal' bewertete Karten"
    )

    s_lapse = _minutes_to_time(cur_m)
    e_lapse = _minutes_to_time(cur_m + dur_lapse)
    blocks.append({
        "id": "block_evening_lapse",
        "start_time": s_lapse,
        "end_time": e_lapse,
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
    total_study_mins += dur_lapse
    cur_m += dur_lapse

    # 11. Feierabend & Evening Free (starts exactly at the end of scheduled work)
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

    if custom_block_order and len(custom_block_order) > 0:
        block_map = {b["id"]: b for b in blocks}
        ordered_blocks = []
        for bid in custom_block_order:
            if bid in block_map:
                ordered_blocks.append(block_map.pop(bid))
        # Add any remaining blocks
        for b in block_map.values():
            ordered_blocks.append(b)

        # Keep evening_free at the very end
        free_block = next((b for b in ordered_blocks if b["id"] == "evening_free"), None)
        if free_block:
            ordered_blocks.remove(free_block)
            ordered_blocks.append(free_block)

        # Recalculate sequential start and end times
        c_m = _parse_time_to_minutes(start_time_str)
        calc_study = 0
        calc_pause = 0
        for b in ordered_blocks:
            if b["id"] == "evening_free":
                continue
            if b.get("is_mandatory") and b.get("start_time") and b.get("end_time"):
                m_start_m = _parse_time_to_minutes(b["start_time"])
                m_end_m = _parse_time_to_minutes(b["end_time"])
                c_m = max(c_m, m_end_m)
                calc_study += b.get("duration_minutes", m_end_m - m_start_m)
            else:
                dur = b.get("duration_minutes", 45)
                b["start_time"] = _minutes_to_time(c_m)
                c_m += dur
                b["end_time"] = _minutes_to_time(c_m)
                if b.get("is_break"):
                    calc_pause += dur
                else:
                    calc_study += dur

        feierabend_time = _minutes_to_time(c_m)
        if free_block:
            free_block["start_time"] = feierabend_time
            free_block["duration_minutes"] = max(60, (22 * 60) - c_m)
            free_block["title"] = f"🎉 Feierabend ab {feierabend_time} & Sport am Abend"

        blocks = ordered_blocks
        total_study_mins = calc_study
        total_pause_mins = calc_pause
    else:
        # Sort all blocks chronologically by their start time
        blocks.sort(key=lambda b: _parse_time_to_minutes(b.get("start_time", "08:30")))

    return {
        "date": t_date.isoformat(),
        "start_time": _minutes_to_time(_parse_time_to_minutes(start_time_str)),
        "lunch_duration_minutes": dur_lunch,
        "include_lecture": include_lecture,
        "feierabend_time": feierabend_time,
        "total_study_minutes": total_study_mins,
        "total_pause_minutes": total_pause_mins,
        "mandatory_events_count": len(mandatory_events),
        "removed_blocks_count": len(removed_set),
        "postponed_blocks_count": len(active_postponed),
        "custom_order": custom_block_order or [],
        "blocks": blocks,
        "mandatory_events": [
            {
                "title": m.title,
                "start_time": m.start_time.strftime("%H:%M"),
                "end_time": m.end_time.strftime("%H:%M"),
                "location": m.location,
                "description": m.description,
            }
            for m in mandatory_events
        ],
        "tomorrow_mandatory_events": [
            {
                "title": m.title,
                "start_time": m.start_time.strftime("%H:%M"),
                "end_time": m.end_time.strftime("%H:%M"),
                "location": m.location,
                "description": m.description,
            }
            for m in tomorrow_mandatory
        ],
    }
