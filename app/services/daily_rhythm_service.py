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
        event.badge_label = "OBLIGATORISCH (Präsenzpflicht)"
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
    anki_first_review_time: Optional[str] = None,
    inserted_blocks: Optional[List[Dict[str, Any]]] = None,
    split_blocks: Optional[Dict[str, Any]] = None,
    is_manual_start: bool = False,
) -> Dict[str, Any]:
    """
    Generates the scientific ultradian study schedule with precise time arithmetic.
    Fully customizable: start time, lunch break duration, lecture inclusion/skip.
    Integrates today's struggle cards, morning Anki focus, and afternoon lecture priming for tomorrow.
    Supports dynamic block deletion and intelligent scheduling of postponed tasks from previous days.
    Supports inserting custom breaks and splitting long marathon study blocks into 1h intervals.
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

    custom_durations = {}
    completed_set = set()
    custom_blocks = {}
    if inserted_blocks is None:
        inserted_blocks = []
    if split_blocks is None:
        split_blocks = {}
    interrupted_blocks = {}
    try:
        from app.db.repository import get_rhythm_actions_for_date
        db_actions = get_rhythm_actions_for_date(date_iso)
        if not removed_block_ids:
            removed_set.update(db_actions.get("removed_block_ids", []))
        completed_set.update(db_actions.get("completed_block_ids", []))
        custom_blocks = db_actions.get("custom_blocks", {})
        if postponed_blocks is None:
            active_postponed.extend(db_actions.get("postponed_blocks", []))
        if not custom_block_order:
            custom_block_order = db_actions.get("custom_order", [])
        custom_durations = db_actions.get("custom_durations", {})
        if not inserted_blocks:
            inserted_blocks = list(db_actions.get("inserted_blocks", []))
        if not split_blocks:
            split_blocks = dict(db_actions.get("split_blocks", {}))
        interrupted_blocks = dict(db_actions.get("interrupted_blocks", {}))
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
    # 50s per review card (realistic, was 36s which was too optimistic)
    SECS_PER_REVIEW = 50.0
    SECS_PER_NEW = 63.0
    rep_gross_mins = max(30, round((cards_due_today * SECS_PER_REVIEW) / 60.0))
    new_gross_mins = max(45, round((new_cards_target * SECS_PER_NEW) / 60.0))

    now = datetime.now()
    is_today_date = (t_date == now.date())
    now_minutes = now.hour * 60 + now.minute if is_today_date else 0

    # Automatic Anki & Start-Time Determination:
    # 1. If user explicitly provided a manual start time (is_manual_start=True), strictly respect user input!
    # 2. If real Anki reviews exist for this date (today or past), automatically adopt the exact time of the first Anki review!
    # 3. Otherwise, use the planned start time (start_time_str or default "08:30").
    # NOTE: Never dynamically shift the schedule forward minute-by-minute to `now` without user initiation.
    used_anki_start = False

    if is_manual_start and start_time_str:
        effective_start_str = start_time_str
        used_anki_start = False
    elif t_date <= now.date() and anki_first_review_time:
        effective_start_str = anki_first_review_time
        used_anki_start = True
    elif start_time_str:
        effective_start_str = start_time_str
        used_anki_start = False
    else:
        effective_start_str = "08:30"
        used_anki_start = False

    cur_m = _parse_time_to_minutes(effective_start_str)
    blocks: List[Dict[str, Any]] = []
    total_study_mins = 0
    total_pause_mins = 0

    def add_block_if_active(b_dict: Dict[str, Any]) -> bool:
        nonlocal cur_m, total_study_mins, total_pause_mins
        bid = b_dict.get("id")
        if bid and bid in removed_set:
            return False

        if bid and split_blocks and bid in split_blocks:
            split_info = split_blocks[bid]
            sub_list = split_info.get("sub_blocks", []) if isinstance(split_info, dict) else split_info
            if sub_list:
                for sub in sub_list:
                    sub_copy = dict(sub)
                    add_block_if_active(sub_copy)
                return True

        if bid and custom_durations and bid in custom_durations:
            try:
                b_dict["duration_minutes"] = int(custom_durations[bid])
                if "badge" in b_dict and isinstance(b_dict["badge"], str) and "(" in b_dict["badge"] and "m)" in b_dict["badge"]:
                    import re
                    b_dict["badge"] = re.sub(r'\(\d+m\)', f'({b_dict["duration_minutes"]}m)', b_dict["badge"])
            except Exception:
                pass
        if bid and bid in custom_blocks:
            b_dict.update(custom_blocks[bid])
        is_done = bid and (bid in completed_set or b_dict.get("is_completed"))
        if is_done:
            b_dict["is_completed"] = True

        dur = b_dict.get("duration_minutes", 30)

        # DYNAMIC TIME ADJUSTMENT: if today, incomplete, and current time has passed
        # the scheduled end of this block, shift start to current time (plan catches up live)
        if is_today_date and not is_done and not b_dict.get("is_break") and now_minutes > cur_m:
            cur_m = now_minutes

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

    # 1. Block 1: Morning Reps (dynamisch an tatsächliche Anki-Last angepasst)

    if is_today_date:
        # Dynamisch für heute: 50s pro Karte, gerundet auf 15-Minuten-Raster (mindestens 30m, maximal 240m)
        calc_reps_mins = max(30, min(240, round((cards_due_today * SECS_PER_REVIEW) / 60.0)))
        dur_reps = int(round(calc_reps_mins / 15.0) * 15)
        is_reps_completed = (cards_due_today == 0)
        reps_title = f"Block 1: Morgen-Repetitionen ({cards_due_today} Karten)" if cards_due_today > 0 else "Block 1: Morgen-Repetitionen (Erledigt)"
        reps_subtitle = f"{cards_due_today} fällig · ~{calc_reps_mins} Min. benötigt"
    else:
        # Für zukünftige Tage: niemals vorab als 'Erledigt' markieren! Volle Zeit einplanen.
        effective_due = cards_due_today if cards_due_today > 0 else 100
        calc_reps_mins = max(30, min(240, round((effective_due * SECS_PER_REVIEW) / 60.0)))
        dur_reps = int(round(calc_reps_mins / 15.0) * 15)
        is_reps_completed = False
        reps_title = f"Block 1: Morgen-Repetitionen ({effective_due} Karten)"
        reps_subtitle = f"{effective_due} fällig · ~{calc_reps_mins} Min. eingeplant"

    reps_badge = f"Active Recall ({dur_reps}m)"
    reps_desc = f"Fällige Wiederholungen ({cards_due_today} Karten, ~{calc_reps_mins} Min. Brutto) abarbeiten. Plan passt sich automatisch an deinen Lernfortschritt an."

    add_block_if_active({
        "id": "block_morning_reps",
        "duration_minutes": dur_reps,
        "title": reps_title,
        "subtitle": reps_subtitle,
        "focus_type": "active_recall",
        "icon": "",
        "color": "#58a6ff",
        "badge": reps_badge,
        "description": reps_desc,
        "is_break": False,
        "is_mandatory": False,
        "is_completed": is_reps_completed,
        "cards_due": cards_due_today,
    })

    # 2. Pause 1
    dur_p1 = 15
    add_block_if_active({
        "id": "pause_1",
        "duration_minutes": dur_p1,
        "title": "Pause 1: Diffuse Mode (Kein Bildschirm!)",
        "subtitle": "Synaptische Konsolidierung & Hydratation",
        "focus_type": "pause",
        "icon": "",
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
        "icon": "",
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
        "icon": "",
        "color": "#3fb950",
        "badge": "Pause (15m)",
        "description": "Frische Luft, Dehnen, Durchatmen vor dem nächsten Arbeitsblock.",
        "is_break": True,
        "is_mandatory": False,
    })

    # 5. Optional Block 3: Lecture / Concept Stream
    if include_lecture:
        dur_lec = 60
        today_primary = today_slots[0] if today_slots else {}
        b3_sub = f"Skript-Abgleich ({today_primary.get('clean_title') or today_primary.get('short_title', 'Thema')}) / Offene Karten" if today_slots else "Skript-Abgleich / Offene Karten klären"
        add_block_if_active({
            "id": "block_podcasts",
            "duration_minutes": dur_lec,
            "title": "Block 3: Transfer & Vormittags-Abschluss",
            "subtitle": b3_sub,
            "focus_type": "concept_stream",
            "icon": "",
            "color": "#79c0ff",
            "badge": f"Transfer ({dur_lec}m)",
            "description": "Kurzer Abgleich mit den Vorlesungsfolien oder Puffer für letzte offene Karten des Vormittags vor der Mittagspause.",
            "is_break": False,
            "is_mandatory": False,
            "podcast_folder_name": today_primary.get("podcast_folder_name"),
            "preferred_video_file": today_primary.get("preferred_video_file"),
            "slide_filename": today_primary.get("matched_slide_filename"),
            "slide_rel_path": today_primary.get("slide_relative_path"),
            "local_podcast_file_path": today_primary.get("local_podcast_file_path"),
            "local_podcast_folder_path": today_primary.get("local_podcast_folder_path"),
            "local_slide_file_path": today_primary.get("local_slide_file_path"),
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
        "icon": "",
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
            "local_podcast_folder_path": p.get("local_podcast_folder_path") or (f"C:\\Users\\Constantin Grandidie\\OneDrive - Universität Zürich UZH\\Desktop\\UNI sem app\\Podcasts\\{p.get('podcast_folder_name')}" if p.get("podcast_folder_name") else None),
            "local_slide_file_path": p.get("local_slide_file_path") or (f"C:\\Users\\Constantin Grandidie\\OneDrive - Universität Zürich UZH\\Desktop\\UNI sem app\\{p.get('slide_rel_path').replace('/', chr(92))}" if p.get("slide_rel_path") else None),
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
            tom_m_warning = f" • Morgen {m_time} Uhr: {first_m.title} (Präsenzpflicht!)"

        title_text = f"Nachmittag: Vorlesung für MORGEN sichten – {tom_title}"
        subtitle_text = f"{tom_lec} • Bereitet {tom_cards} Anki-Karten für morgen vor{tom_m_warning}"
        desc_text = f"Auditive Vorentlastung für morgen: Vorlesung '{tom_title}'{' (' + tom_date + ')' if tom_date else ''} auf {tom_speed}x sichten{' (' + tom_timecode + ')' if tom_timecode else ''}. Bereitet die morgigen {tom_cards} neuen Karten vor ({tom_topics}). Das Gehirn baut im Schlaf das Schema auf!"
        if tomorrow_mandatory:
            desc_text += f" Wichtig: Morgen ab {tomorrow_mandatory[0].start_time.strftime('%H:%M')} Uhr findet das obligatorische '{tomorrow_mandatory[0].title}' vor Ort statt."

        add_block_if_active({
            "id": "block_afternoon_flex",
            "duration_minutes": dur_afternoon,
            "title": title_text,
            "subtitle": subtitle_text,
            "focus_type": "afternoon_flex",
            "icon": "",
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
            "preferred_video_file": tomorrow_data.get("preferred_video_file"),
            "slide_filename": tomorrow_data.get("slide_filename"),
            "slide_rel_path": tomorrow_data.get("slide_rel_path"),
            "local_podcast_folder_path": f"C:\\Users\\Constantin Grandidie\\OneDrive - Universität Zürich UZH\\Desktop\\UNI sem app\\Podcasts\\{tomorrow_data.get('podcast_folder_name')}" if tomorrow_data.get("podcast_folder_name") else None,
            "local_podcast_file_path": f"C:\\Users\\Constantin Grandidie\\OneDrive - Universität Zürich UZH\\Desktop\\UNI sem app\\Podcasts\\{tomorrow_data.get('podcast_folder_name')}\\{tomorrow_data.get('preferred_video_file')}" if (tomorrow_data.get("podcast_folder_name") and tomorrow_data.get("preferred_video_file")) else None,
            "local_slide_file_path": f"C:\\Users\\Constantin Grandidie\\OneDrive - Universität Zürich UZH\\Desktop\\UNI sem app\\{tomorrow_data.get('slide_rel_path').replace('/', chr(92))}" if tomorrow_data.get("slide_rel_path") else None,
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
                "title": f"Puffer, Vorbereitung & Wegzeit ({loc_label})",
                "subtitle": f"Kognitive Erholung & Transfer zum Kursort • {dur_label}",
                "focus_type": "pause",
                "icon": "",
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
            "title": f"{m_ev.title}",
            "subtitle": f"UZH Vor-Ort Präsenzpflicht{loc_text}",
            "focus_type": "mandatory_in_person",
            "icon": "",
            "color": "#a371f7",
            "badge": "OBLIGATORISCH (Präsenzpflicht)",
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
        "icon": "",
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

    # 10b. Inserted Custom Blocks (e.g. ad-hoc pauses inserted via "+ Pause" or "Pause jetzt machen")
    if inserted_blocks:
        for ins in inserted_blocks:
            ins_id = ins.get("id")
            if ins_id and not any(b.get("id") == ins_id for b in blocks):
                add_block_if_active(dict(ins))

    # 11. Feierabend & Evening Free (starts exactly at the end of scheduled work)
    feierabend_time = _minutes_to_time(cur_m)
    dur_evening = max(60, (22 * 60) - cur_m)
    blocks.append({
        "id": "evening_free",
        "start_time": feierabend_time,
        "end_time": "22:00",
        "duration_minutes": dur_evening,
        "title": f"Feierabend ab {feierabend_time} & Sport am Abend",
        "subtitle": "Kognitive Regeneration & BDNF-Ausschüttung",
        "focus_type": "evening_free",
        "icon": "",
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
        c_m = _parse_time_to_minutes(effective_start_str)
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
                if custom_durations and b.get("id") in custom_durations:
                    try:
                        dur = int(custom_durations[b["id"]])
                        b["duration_minutes"] = dur
                    except Exception:
                        pass
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
            free_block["title"] = f"Feierabend ab {feierabend_time} & Sport am Abend"

        blocks = ordered_blocks
        total_study_mins = calc_study
        total_pause_mins = calc_pause
    else:
        # Sort all blocks chronologically by their start time
        blocks.sort(key=lambda b: _parse_time_to_minutes(b.get("start_time", "08:30")))

    # Apply interruptions, custom block overrides, and completed status to all final blocks
    for b in blocks:
        bid = b.get("id")
        if bid and bid in interrupted_blocks:
            b["interruptions"] = interrupted_blocks[bid]
        if bid and bid in custom_blocks:
            b.update(custom_blocks[bid])
        if bid and (bid in completed_set or b.get("is_completed")):
            b["is_completed"] = True

    # If any blocks have interruptions, recalculate sequential timings and feierabend
    has_any_interruptions = any(b.get("interruptions") for b in blocks)
    if has_any_interruptions:
        cur_calc_m = _parse_time_to_minutes(effective_start_str)
        study_sum = 0
        pause_sum = 0
        for b in blocks:
            if b.get("id") == "evening_free":
                continue
            if b.get("is_mandatory") and b.get("start_time") and b.get("end_time"):
                m_start_m = _parse_time_to_minutes(b["start_time"])
                m_end_m = _parse_time_to_minutes(b["end_time"])
                cur_calc_m = max(cur_calc_m, m_end_m)
                study_sum += b.get("duration_minutes", m_end_m - m_start_m)
            else:
                dur = b.get("duration_minutes", 45)
                inter_p = sum(item.get("duration_minutes", 0) for item in b.get("interruptions", []))
                tot_span = dur + inter_p
                b["start_time"] = _minutes_to_time(cur_calc_m)
                cur_calc_m += tot_span
                b["end_time"] = _minutes_to_time(cur_calc_m)
                if b.get("is_break"):
                    pause_sum += tot_span
                else:
                    study_sum += dur
                    pause_sum += inter_p

        feierabend_time = _minutes_to_time(cur_calc_m)
        free_block = next((b for b in blocks if b.get("id") == "evening_free"), None)
        if free_block:
            free_block["start_time"] = feierabend_time
            free_block["duration_minutes"] = max(60, (22 * 60) - cur_calc_m)
            free_block["title"] = f"Feierabend ab {feierabend_time} & Sport am Abend"
        total_study_mins = study_sum
        total_pause_mins = pause_sum

    return {
        "date": t_date.isoformat(),
        "start_time": _minutes_to_time(_parse_time_to_minutes(effective_start_str)),
        "configured_start_time": start_time_str,
        "anki_first_review_time": anki_first_review_time,
        "used_anki_start": used_anki_start,
        "is_live_catching_up": False,
        "lunch_duration_minutes": dur_lunch,
        "include_lecture": include_lecture,
        "feierabend_time": feierabend_time,
        "total_study_minutes": total_study_mins,
        "total_pause_minutes": total_pause_mins,
        "mandatory_events_count": len(mandatory_events),
        "completed_blocks_count": sum(1 for b in blocks if b.get("is_completed", False)),
        "removed_blocks_count": len(removed_set),
        "postponed_blocks_count": len(active_postponed),
        "custom_order": custom_block_order or [],
        "custom_durations": custom_durations,
        "inserted_blocks": inserted_blocks or [],
        "split_blocks": split_blocks or {},
        "interrupted_blocks": interrupted_blocks or {},
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
