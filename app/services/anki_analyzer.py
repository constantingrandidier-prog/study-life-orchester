"""Service for parsing Anki decks, analyzing topics, evaluating lecture relevance, and orchestrating study blocks."""

import csv
import io
import json
import re
import sqlite3
import tempfile
import zipfile
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Tuple

from app.models import (
    AnkiDeckSummary,
    AnkiTopic,
    CalendarEvent,
    FreeSlot,
    ManualActivity,
    RolloverItem,
    RolloverResponse,
    ScheduledStudyBlock,
    SmartScheduleResponse,
)
from app.services.time_grid import calculate_free_slots


def parse_anki_apkg_content(file_bytes: bytes, filename: str = "deck.apkg") -> AnkiDeckSummary:
    """
    Parse a native Anki .apkg package (zip file containing collection.anki2 SQLite database).
    Extracts decks, cards, notes, tags, and computes topic statistics.
    """
    cards_by_topic: Dict[str, int] = {}
    deck_name = filename.rsplit(".", 1)[0]
    total_cards = 0

    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            db_filename = None
            if "collection.anki21" in z.namelist():
                db_filename = "collection.anki21"
            elif "collection.anki2" in z.namelist():
                db_filename = "collection.anki2"

            if db_filename:
                with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
                    tmp.write(z.read(db_filename))
                    tmp_path = tmp.name

                conn = sqlite3.connect(tmp_path)
                cursor = conn.cursor()

                # Get deck names from 'col' table if available
                cursor.execute("SELECT decks FROM col LIMIT 1")
                col_row = cursor.fetchone()
                if col_row and col_row[0]:
                    try:
                        decks_meta = json.loads(col_row[0])
                        # Pick the first non-default deck name
                        for d_id, d_data in decks_meta.items():
                            d_name = d_data.get("name", "")
                            if d_name and d_name != "Default":
                                deck_name = d_name
                                break
                    except Exception:
                        pass

                # Read notes and tags
                cursor.execute("SELECT tags, flds FROM notes")
                for tags_str, flds in cursor.fetchall():
                    total_cards += 1
                    assigned_topic = None

                    # Extract tags (Anki stores tags with space delimiter: " tag1 tag2 ")
                    if tags_str and tags_str.strip():
                        tags = [t.strip() for t in tags_str.split() if t.strip()]
                        if tags:
                            # Use the most specific tag as the topic name
                            assigned_topic = tags[0].replace("::", " - ").replace("_", " ").title()

                    # Fallback: extract from first field (question text)
                    if not assigned_topic and flds:
                        first_field = flds.split("\x1f")[0]
                        # Strip html
                        clean_text = re.sub(r"<[^>]+>", "", first_field).strip()
                        if clean_text:
                            # Extract key noun phrase or first 4 words
                            words = clean_text.split()[:4]
                            assigned_topic = " ".join(words).title()

                    if not assigned_topic:
                        assigned_topic = "General Concepts"

                    cards_by_topic[assigned_topic] = cards_by_topic.get(assigned_topic, 0) + 1

                conn.close()
    except Exception as e:
        # If extraction fails (e.g. invalid zip), fall back to text parser
        return parse_anki_text_content(file_bytes.decode("utf-8", errors="ignore"), filename=filename)

    if total_cards == 0:
        return _create_default_anki_summary(deck_name)

    topics = _build_topics_from_counts(cards_by_topic)
    total_est_min = sum(t.estimated_minutes for t in topics)

    return AnkiDeckSummary(
        deck_name=deck_name,
        total_cards=total_cards,
        total_estimated_minutes=total_est_min,
        topics=topics,
    )


def parse_anki_text_content(text: str, filename: str = "notes.txt") -> AnkiDeckSummary:
    """
    Parse a text, CSV, or TSV exported Anki deck.
    """
    cards_by_topic: Dict[str, int] = {}
    lines = text.strip().splitlines()
    total_cards = 0
    deck_name = filename.rsplit(".", 1)[0]

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split("\t") if "\t" in line else line.split(";")
        if len(parts) >= 1:
            total_cards += 1
            topic = "General Knowledge"

            # Check if last column has tags
            if len(parts) >= 3 and parts[-1].strip():
                tag_candidate = parts[-1].strip()
                topic = tag_candidate.split()[0].replace("::", " - ").replace("_", " ").title()
            else:
                # Infer from first question column
                clean_q = re.sub(r"<[^>]+>", "", parts[0]).strip()
                words = clean_q.split()[:3]
                if words:
                    topic = " ".join(words).title()

            cards_by_topic[topic] = cards_by_topic.get(topic, 0) + 1

    if total_cards == 0:
        return _create_default_anki_summary(deck_name)

    topics = _build_topics_from_counts(cards_by_topic)
    total_est_min = sum(t.estimated_minutes for t in topics)

    return AnkiDeckSummary(
        deck_name=deck_name,
        total_cards=total_cards,
        total_estimated_minutes=total_est_min,
        topics=topics,
    )


def _detect_cluster(topic_name: str) -> str:
    """Classify a topic into a cohesive thematic knowledge cluster to bundle related concepts."""
    lower = topic_name.lower()
    # Medicine & Life Sciences
    if any(k in lower for k in ["anatomie", "gelenk", "knochen", "muskel", "skelett", "extremit", "wirbel", "schulter", "fuss", "knie"]):
        return "Anatomie & Bewegungsapparat"
    if any(k in lower for k in ["chemie", "organisch", "anorganisch", "carbonyl", "carbonsäure", "glykolyse", "citratzyklus", "stoffwechsel"]):
        return "Chemie & Stoffwechsel"
    if any(k in lower for k in ["mzb", "makromolek", "protein", "dna", "rna", "transkription", "translation", "zellzyklus"]):
        return "Molekulare Zellbiologie & Genetik"
    if any(k in lower for k in ["embryo", "gewebe", "epithel", "drüse", "morphologie", "slomianka", "lienkamp", "histologie"]):
        return "Embryologie & Zellbiologie"
    if any(k in lower for k in ["blut", "erythro", "leuko", "myelo", "hämo", "immun", "thrombo"]):
        return "Hämatologie & Immunologie"
    if any(k in lower for k in ["psycho", "medizin", "ethik", "wissenschaftstheorie", "biostatistik"]):
        return "Medizinische Grundlagen & Psychosoziales"
    if any(k in lower for k in ["neuro", "synapse", "übertragung", "gehirn", "helmchen", "signal"]):
        return "Neurowissenschaften & Neurobiologie"

    # Computer Science & Mathematics
    if any(k in lower for k in ["algorithm", "graph", "tree", "sort", "complexity", "dynamic", "data structure"]):
        return "Theoretische Informatik & Algorithmen"
    if any(k in lower for k in ["system", "concurrency", "operating", "thread", "process", "memory", "cache", "kernel"]):
        return "Systemnahe Programmierung & OS"
    if any(k in lower for k in ["intelligence", "deep learning", "neural", "attention", "transformer", "model", "ai", "machine"]):
        return "Künstliche Intelligenz & Data Science"
    if any(k in lower for k in ["pattern", "software", "agile", "architecture", "testing", "refactor", "design"]):
        return "Software Engineering & Entwurf"
    if any(k in lower for k in ["math", "calculus", "linear", "matrix", "vector", "probability"]):
        return "Mathematik & Formale Grundlagen"
    return "Allgemeines Fachwissen"


def _build_topics_from_counts(cards_by_topic: Dict[str, int]) -> List[AnkiTopic]:
    """Helper to convert topic frequency into AnkiTopic models with thematic clustering."""
    topics: List[AnkiTopic] = []
    # Sort by card volume
    sorted_items = sorted(cards_by_topic.items(), key=lambda x: x[1], reverse=True)

    for topic_name, count in sorted_items[:8]:  # Keep top 8 topics
        # Estimate: ~35 seconds per card (~1.7 cards/min)
        est_minutes = max(10, int(count * 0.6))
        # Estimate difficulty based on card density
        diff = min(5.0, max(1.5, round(2.0 + (count / 30.0), 1)))
        cluster = _detect_cluster(topic_name)

        topics.append(
            AnkiTopic(
                name=topic_name,
                cluster_name=cluster,
                card_count=count,
                estimated_minutes=est_minutes,
                difficulty_score=diff,
                urgency="high" if count > 40 else ("medium" if count > 15 else "normal"),
            )
        )
    return topics


def _create_default_anki_summary(deck_name: str) -> AnkiDeckSummary:
    """Fallback sample topics grouped into coherent clusters for university student."""
    sample_topics = [
        AnkiTopic(
            name="Graph Algorithms & Dynamic Programming",
            cluster_name="Theoretische Informatik & Algorithmen",
            card_count=48,
            estimated_minutes=30,
            difficulty_score=4.2,
            urgency="high",
        ),
        AnkiTopic(
            name="Operating Systems & Concurrency",
            cluster_name="Systemnahe Programmierung & OS",
            card_count=35,
            estimated_minutes=25,
            difficulty_score=3.8,
            urgency="high",
        ),
        AnkiTopic(
            name="Deep Learning & Attention Mechanisms",
            cluster_name="Künstliche Intelligenz & Data Science",
            card_count=28,
            estimated_minutes=20,
            difficulty_score=3.5,
            urgency="medium",
        ),
        AnkiTopic(
            name="Software Design Patterns (GoF)",
            cluster_name="Software Engineering & Entwurf",
            card_count=22,
            estimated_minutes=15,
            difficulty_score=2.6,
            urgency="normal",
        ),
    ]
    return AnkiDeckSummary(
        deck_name=deck_name or "Informatik & Algorithmen Semester 3",
        total_cards=sum(t.card_count for t in sample_topics),
        total_estimated_minutes=sum(t.estimated_minutes for t in sample_topics),
        topics=sample_topics,
    )



def match_topics_with_lectures(
    topics: List[AnkiTopic],
    events: List[CalendarEvent],
) -> List[AnkiTopic]:
    """
    Evaluate how strongly each Anki topic correlates with scheduled lectures/seminars.
    Assigns relevance score (0.0 - 1.0) and descriptive educational advice.
    """
    keyword_map = {
        "anatomie": ["anatomie", "gelenk", "knochen", "muskel", "schulter", "fuss", "knie", "extremit", "wirbel", "bänder"],
        "blut": ["blut", "erythro", "leuko", "myelo", "hämo", "immun", "plasma"],
        "chemie": ["chemie", "organisch", "anorganisch", "stoffwechsel", "glykolyse", "citrat", "makromolek"],
        "embryo": ["embryo", "gewebe", "epithel", "histologie", "zell"],
        "algorithm": ["graph", "tree", "sort", "complexity", "dynamic", "data structure"],
        "system": ["concurrency", "process", "thread", "memory", "operating", "architecture", "cache"],
        "intelligence": ["neural", "learning", "attention", "transformer", "model", "ai", "deep"],
        "software": ["pattern", "agile", "architecture", "testing", "refactor", "code"],
        "math": ["calculus", "linear", "matrix", "vector", "probability"],
    }

    updated_topics: List[AnkiTopic] = []

    for topic in topics:
        topic_lower = topic.name.lower()
        best_match_event: Optional[CalendarEvent] = None
        best_score = 0.0

        for event in events:
            ev_title = event.title.lower()
            ev_desc = (event.description or "").lower()
            combined_event_text = f"{ev_title} {ev_desc}"

            # Direct word overlap
            topic_words = set(re.findall(r"\w{4,}", topic_lower))
            event_words = set(re.findall(r"\w{4,}", combined_event_text))
            common = topic_words.intersection(event_words)

            score = 0.0
            if common:
                score = min(0.95, 0.4 + 0.2 * len(common))

            # Synonyms / semantic category overlap
            for category, keywords in keyword_map.items():
                if category in combined_event_text:
                    for kw in keywords:
                        if kw in topic_lower:
                            score = max(score, 0.85)

            if score > best_score:
                best_score = score
                best_match_event = event

        # Format pedagogical relevance explanation
        if best_match_event and best_score >= 0.5:
            reason = (
                f"Hohe Prüfungs- und Vorlesungsrelevanz für '{best_match_event.title}'. "
                f"Eine gezielte Wiederholung festigt das Verständnis des heutigen Stoffs nachhaltig."
            )
            matched_title = best_match_event.title
            urgency = "high"
        else:
            best_score = max(0.2, best_score)
            reason = "Reguläre Wissensfestigung nach Spaced-Repetition-Intervall."
            matched_title = None
            urgency = topic.urgency

        updated_topics.append(
            AnkiTopic(
                name=topic.name,
                cluster_name=topic.cluster_name,
                card_count=topic.card_count,
                estimated_minutes=topic.estimated_minutes,
                difficulty_score=topic.difficulty_score,
                matched_lecture=matched_title,
                relevance_score=round(best_score, 2),
                relevance_reason=reason,
                urgency=urgency,
            )
        )

    # Sort topics so high-relevance & high-urgency come first, keeping clusters grouped
    updated_topics.sort(key=lambda t: (t.relevance_score, t.cluster_name, t.card_count), reverse=True)
    return updated_topics


def orchestrate_study_plan(
    events: List[CalendarEvent],
    manual_activities: List[ManualActivity],
    anki_topics: List[AnkiTopic],
    target_date: Optional[date] = None,
    day_start_hour: int = 7,
    day_end_hour: int = 23,
) -> SmartScheduleResponse:
    """
    Intelligently schedule Anki study sessions into available free time slots.
    Prioritizes cohesive topic clusters to avoid random jumping between unrelated subjects.
    """
    if target_date is None:
        target_date = events[0].start_time.date() if events else date.today()

    # Match topics with lectures first and assign clusters
    analyzed_topics = match_topics_with_lectures(anki_topics, events)

    # Combine fixed events and manual activities to compute true available free slots
    combined_fixed: List[CalendarEvent] = list(events)
    for act in manual_activities:
        combined_fixed.append(
            CalendarEvent(
                title=f"Aktivität: {act.title}",
                start_time=act.start_time,
                end_time=act.end_time,
                location=act.category.upper(),
                description=act.notes or f"Manuell geplante Aktivität ({act.category})",
            )
        )

    # Calculate free slots
    free_slots = calculate_free_slots(
        events=combined_fixed,
        target_date=target_date,
        day_start_hour=day_start_hour,
        day_end_hour=day_end_hour,
    )

    scheduled_sessions: List[ScheduledStudyBlock] = []
    remaining_slots: List[FreeSlot] = []
    recommendations: List[str] = []

    # Allocate prioritized topics into suitable free slots, keeping coherent clusters together
    topic_queue = list(analyzed_topics)

    for slot in free_slots:
        slot_start = slot.start_time
        slot_end = slot.end_time
        slot_duration = slot.duration_minutes

        # If slot is too short for a focused session (< 20 mins), keep it free for a quick break
        if slot_duration < 20 or not topic_queue:
            remaining_slots.append(slot)
            continue

        # Check if this slot precedes a relevant lecture
        chosen_topic_idx = None
        for i, t in enumerate(topic_queue):
            if t.matched_lecture:
                for ev in events:
                    if ev.title == t.matched_lecture and ev.start_time >= slot_end:
                        chosen_topic_idx = i
                        break
            if chosen_topic_idx is not None:
                break

        if chosen_topic_idx is None:
            # Pick from the current primary cluster to maintain contextual flow
            chosen_topic_idx = 0

        topic = topic_queue.pop(chosen_topic_idx)

        # Determine study block length (capped to min(topic estimated minutes, slot duration))
        study_duration = min(topic.estimated_minutes, slot_duration)
        study_end = slot_start + timedelta(minutes=study_duration)

        cards_target = min(topic.card_count, max(10, int(study_duration * 1.5)))

        reason = (
            f"Vorbereitung für '{topic.matched_lecture}'"
            if topic.matched_lecture
            else f"Fokus-Block: {cards_target} Karten wiederholen ({topic.name})"
        )

        scheduled_sessions.append(
            ScheduledStudyBlock(
                topic_name=topic.name,
                cluster_name=topic.cluster_name,
                start_time=slot_start,
                end_time=study_end,
                duration_minutes=study_duration,
                cards_to_review=cards_target,
                reason=reason,
            )
        )

        # If significant time remains in this slot (>= 15 mins), keep remainder as free
        remainder_duration = int((slot_end - study_end).total_seconds() / 60)
        if remainder_duration >= 15:
            remaining_slots.append(
                FreeSlot(
                    start_time=study_end,
                    end_time=slot_end,
                    duration_minutes=remainder_duration,
                )
            )

    # Generate pedagogical insights & recommendations
    if scheduled_sessions:
        total_study = sum(s.duration_minutes for s in scheduled_sessions)
        primary_cluster = scheduled_sessions[0].cluster_name or "Fachwissen"
        recommendations.append(
            f"🎯 Heute sind {len(scheduled_sessions)} zusammenhängende Lerneinheiten ({total_study} Minuten) eingeplant. Schwerpunkt: '{primary_cluster}'."
        )

    for topic in analyzed_topics[:2]:
        if topic.matched_lecture:
            recommendations.append(
                f"⭐ Wichtig: Das Thema '{topic.name}' korreliert stark mit '{topic.matched_lecture}'. Wiederhole die Karten vor Vorlesungsbeginn!"
            )

    if not remaining_slots:
        recommendations.append("ℹ️ Dein Tag ist dicht getaktet. Achte auf kurze 5-minütige Bildschirmpausen.")
    else:
        longest_free = max(s.duration_minutes for s in remaining_slots)
        recommendations.append(
            f"☕ Du hast noch {len(remaining_slots)} freie Zeitfenster (längster Block: {longest_free} Min) für Erholung, Mahlzeiten oder Sport."
        )

    return SmartScheduleResponse(
        date=target_date,
        fixed_events=events,
        manual_activities=manual_activities,
        study_sessions=scheduled_sessions,
        remaining_free_slots=remaining_slots,
        recommendations=recommendations,
    )


def redistribute_uncompleted_cards(
    uncompleted_topics: List[AnkiTopic],
    target_date: Optional[date] = None,
    days_ahead: int = 3,
) -> RolloverResponse:
    """
    Intelligently redistribute uncompleted study goals across subsequent days.
    Batches coherent cluster cards together to preserve cognitive context.
    """
    if target_date is None:
        target_date = date.today()

    total_uncompleted = sum(t.card_count for t in uncompleted_topics)
    if total_uncompleted == 0:
        return RolloverResponse(
            message="Keine unerledigten Lernziele vorhanden.",
            total_uncompleted_cards=0,
            redistribution=[],
            advice="Hervorragend! Du bist heute perfekt im Zeitplan.",
        )

    # Group uncompleted by cluster
    clusters: Dict[str, List[AnkiTopic]] = {}
    for t in uncompleted_topics:
        c_name = t.cluster_name or "Allgemeines Fachwissen"
        clusters.setdefault(c_name, []).append(t)

    redistribution: List[RolloverItem] = []
    current_day = 1

    for c_name, c_topics in clusters.items():
        for topic in c_topics:
            cards_left = topic.card_count
            batch_size = max(15, cards_left // min(days_ahead, 2)) if cards_left > 20 else cards_left

            while cards_left > 0:
                batch = min(cards_left, batch_size)
                assigned_date = target_date + timedelta(days=current_day)
                est_min = max(10, int(batch * 0.6))

                redistribution.append(
                    RolloverItem(
                        day_offset=current_day,
                        target_date=assigned_date,
                        topic_name=topic.name,
                        cluster_name=c_name,
                        cards_count=batch,
                        estimated_minutes=est_min,
                    )
                )
                cards_left -= batch
                current_day = (current_day % days_ahead) + 1

    redistribution.sort(key=lambda x: (x.target_date, x.cluster_name))

    tomorrow_cards = sum(r.cards_count for r in redistribution if r.day_offset == 1)
    primary_cluster = list(clusters.keys())[0]
    advice = (
        f"Kein Stress! Deine {total_uncompleted} offenen Karten wurden so auf die nächsten {days_ahead} Tage aufgeteilt, "
        f"dass zusammenhängende Stoffe (wie '{primary_cluster}') gebündelt bleiben. "
        f"Morgen stehen dafür schonende +{tomorrow_cards} Karten an."
    )

    return RolloverResponse(
        message=f"{total_uncompleted} Karten erfolgreich auf {days_ahead} Tage umverteilt",
        total_uncompleted_cards=total_uncompleted,
        redistribution=redistribution,
        advice=advice,
    )

