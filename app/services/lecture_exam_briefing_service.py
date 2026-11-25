"""Verified UZH 2. SJ Lecture & Exam Signal Knowledge Base (Teil 2).

Maps every active 2. SJ Anki subdeck to 100% evidence-backed exam highlights,
clinical pearls, and professor de-emphasis notes extracted from the 38
transcribed & summarized lecture recordings in `app/data/lecture_transcripts/summaries/`.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

LECTURE_EXAM_SIGNALS_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "lecture_exam_signals.json"
)
LECTURE_SUMMARIES_DIR = (
    Path(__file__).resolve().parent.parent / "data" / "lecture_transcripts" / "summaries"
)

_SIGNALS_CACHE: Dict[str, Any] = {"mtime": 0.0, "data": None}


def _normalize_match_text(text: str) -> str:
    """Normalizes deck/subdeck strings for deterministic, emoji- and punctuation-tolerant matching."""
    if not text:
        return ""
    s = str(text).lower().strip()
    # Strip common status emojis and decorative markers used in Anki deck names
    s = re.sub(r"[⚫🟢🟡🔴⚪🔵🟠🟣✅🔥🎯🛡️🔄🐢🌱]+", " ", s)
    # Normalize umlauts and Eszett consistently
    s = (
        s.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
        .replace("ss", "ss")
    )
    # Normalize common punctuation/separators to spaces
    s = re.sub(r"[/,:;_\-&+()]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _strip_leading_index(norm_text: str) -> str:
    """Removes a leading numeric prefix like '1 ' or '2 ' for clean pattern comparison."""
    return re.sub(r"^\d+\.?\s+", "", norm_text).strip()


def load_lecture_exam_signals(force_reload: bool = False) -> Dict[str, Any]:
    """Loads `app/data/lecture_exam_signals.json` with mtime-based in-memory caching."""
    if not LECTURE_EXAM_SIGNALS_PATH.exists():
        return {"version": "2.0", "total_source_summaries": 0, "entries": []}
    mtime = LECTURE_EXAM_SIGNALS_PATH.stat().st_mtime
    if not force_reload and _SIGNALS_CACHE["data"] is not None and _SIGNALS_CACHE["mtime"] == mtime:
        return _SIGNALS_CACHE["data"]
    data = json.loads(LECTURE_EXAM_SIGNALS_PATH.read_text(encoding="utf-8"))
    _SIGNALS_CACHE["mtime"] = mtime
    _SIGNALS_CACHE["data"] = data
    return data


def get_all_exam_signal_entries() -> List[Dict[str, Any]]:
    """Returns all curated lecture exam signal entries."""
    return list(load_lecture_exam_signals().get("entries") or [])


def match_subdeck_to_exam_signal(
    themenblock: str,
    dozent: str,
    subdeck: str,
    full_anki_deck: str = "",
    allow_prof_fallback: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Deterministically matches an Anki subdeck to its verified lecture exam signal entry.
    Uses longest-specific-pattern matching within `(themenblock, dozent)` so numbered
    variants (e.g. 'Trachea und Bronchien 2' vs 'Trachea und Bronchien',
    'Anatomie der Atmungsorgane II' vs 'Anatomie der Atmungsorgane') never collide.
    """
    entries = get_all_exam_signal_entries()
    if not entries:
        return None

    tb_norm = _normalize_match_text(themenblock)
    prof_norm = _normalize_match_text(dozent)
    sub_norm = _normalize_match_text(subdeck)
    sub_no_idx = _strip_leading_index(sub_norm)
    full_norm = _normalize_match_text(full_anki_deck) if full_anki_deck else sub_norm

    # Filter candidates to the same (Themenblock, Dozent) first
    same_prof_entries = [
        e for e in entries
        if _normalize_match_text(e.get("themenblock", "")) == tb_norm
        and _normalize_match_text(e.get("dozent", "")) == prof_norm
    ]
    # Also allow matching by Dozent alone if TB naming differs slightly
    candidates = same_prof_entries or [
        e for e in entries
        if _normalize_match_text(e.get("dozent", "")) == prof_norm
    ]
    if not candidates:
        return None

    best_entry: Optional[Dict[str, Any]] = None
    best_score: float = -1.0
    best_match_type: str = "unmatched"

    for entry in candidates:
        patterns = entry.get("subdeck_patterns") or []
        for pat in patterns:
            pat_norm = _normalize_match_text(pat)
            pat_no_idx = _strip_leading_index(pat_norm)
            if not pat_norm:
                continue

            score = -1.0
            mtype = "unmatched"

            # 1. Exact leaf match (highest priority)
            if sub_norm == pat_norm or (sub_no_idx and sub_no_idx == pat_no_idx):
                score = 1000.0 + len(pat_norm)
                mtype = "exact_subdeck"
            # 2. Substring match on leaf subdeck (longest pattern wins -> 'II' beats base!)
            elif pat_norm in sub_norm or (pat_no_idx and len(pat_no_idx) >= 4 and pat_no_idx in sub_no_idx):
                # Prefer closer length match to avoid 'Trachea und Bronchien' matching 'Trachea und Bronchien 2'
                matched_len = len(pat_norm) if pat_norm in sub_norm else len(pat_no_idx)
                len_penalty = abs(len(sub_no_idx) - len(pat_no_idx)) * 0.5
                score = 500.0 + matched_len * 2.0 - len_penalty
                mtype = "pattern_subdeck"
            # 3. Substring match on full Anki deck path
            elif pat_norm in full_norm:
                score = 300.0 + len(pat_norm)
                mtype = "pattern_subdeck"
            # 4. Token overlap fallback (e.g. slight spelling variation)
            else:
                p_toks = {tok for tok in pat_no_idx.split() if len(tok) >= 3}
                s_toks = {tok for tok in sub_no_idx.split() if len(tok) >= 3}
                if p_toks and s_toks:
                    overlap = len(p_toks & s_toks) / max(1, len(p_toks))
                    if overlap >= 0.65:
                        score = 150.0 + overlap * 100.0 + len(p_toks & s_toks) * 5.0
                        mtype = "token_subdeck"

            if score > best_score:
                best_score = score
                best_entry = entry
                best_match_type = mtype

    if best_entry is not None:
        out = dict(best_entry)
        out["match_type"] = best_match_type
        out["match_score"] = round(best_score, 1)
        return out

    if allow_prof_fallback and same_prof_entries:
        # Synthesize a professor-level overview from all verified lectures of this professor in this TB
        all_sources: List[str] = []
        all_dates: List[str] = []
        highlights: List[str] = []
        pearls: List[str] = []
        deemph: List[str] = []
        for e in same_prof_entries:
            for sf in e.get("source_summaries") or []:
                if sf not in all_sources:
                    all_sources.append(sf)
            for dt in e.get("lecture_dates") or []:
                if dt not in all_dates:
                    all_dates.append(dt)
            if e.get("exam_highlights"):
                highlights.append(e["exam_highlights"][0])
            if e.get("clinical_pearls"):
                pearls.append(e["clinical_pearls"][0])
            if e.get("deemphasized_notes"):
                deemph.append(e["deemphasized_notes"][0])
        return {
            "id": f"prof_fallback_{tb_norm}_{prof_norm}".replace(" ", "_"),
            "themenblock": themenblock,
            "dozent": dozent,
            "subdeck_patterns": [subdeck],
            "source_summaries": all_sources,
            "lecture_dates": sorted(all_dates),
            "exam_highlights": highlights[:3],
            "clinical_pearls": pearls[:2],
            "deemphasized_notes": deemph[:2],
            "match_type": "prof_fallback",
            "match_score": 10.0,
        }

    return None


def validate_signals_against_transcripts() -> Dict[str, Any]:
    """
    Audits `lecture_exam_signals.json` to guarantee 100% evidence integrity:
      - Every referenced `source_summaries` file exists in `app/data/lecture_transcripts/summaries/`.
      - Every entry has required fields and non-empty `exam_highlights`.
      - No duplicate entry IDs.
    """
    data = load_lecture_exam_signals(force_reload=True)
    entries = data.get("entries") or []
    missing_files: List[Tuple[str, str]] = []
    invalid_entries: List[str] = []
    seen_ids = set()
    duplicate_ids: List[str] = []
    referenced_summaries = set()

    for e in entries:
        eid = str(e.get("id") or "")
        if not eid or eid in seen_ids:
            duplicate_ids.append(eid or "<empty>")
        seen_ids.add(eid)

        if not (
            e.get("themenblock")
            and e.get("dozent")
            and e.get("subdeck_patterns")
            and e.get("source_summaries")
            and e.get("lecture_dates")
            and e.get("exam_highlights")
        ):
            invalid_entries.append(eid)

        for sf in e.get("source_summaries") or []:
            referenced_summaries.add(sf)
            if not (LECTURE_SUMMARIES_DIR / sf).exists():
                missing_files.append((eid, sf))

    all_summary_files = sorted(p.name for p in LECTURE_SUMMARIES_DIR.glob("*.md")) if LECTURE_SUMMARIES_DIR.exists() else []
    unreferenced_summaries = [f for f in all_summary_files if f not in referenced_summaries]

    return {
        "valid": (len(missing_files) == 0 and len(invalid_entries) == 0 and len(duplicate_ids) == 0 and len(entries) > 0),
        "entry_count": len(entries),
        "total_summary_files": len(all_summary_files),
        "referenced_summary_count": len(referenced_summaries),
        "unreferenced_summaries": unreferenced_summaries,
        "missing_files": missing_files,
        "invalid_entries": invalid_entries,
        "duplicate_ids": duplicate_ids,
    }


def verify_anki_subdeck_coverage(col_path=None) -> Dict[str, Any]:
    """
    Verifies exact subdeck matching against the real local `collection.anki2` database.
    Checks every active 2. SJ leaf deck that contains at least 1 non-suspended card.
    """
    from app.services.anki_desktop_sync import find_local_anki_collection
    from app.services.anki_backlog_triage import (
        parse_curriculum_deck,
        _extract_exact_anki_deck_path,
        _extract_subdeck_short_title,
    )
    from app.db.anki_db import open_anki_db_readonly, NORM_CARDS_SQL

    target_path = Path(col_path) if col_path else find_local_anki_collection()
    if not target_path or not target_path.exists():
        return {"connected": False, "total_leaf_decks": 0, "coverage_pct": 0.0}

    with open_anki_db_readonly(target_path) as conn:
        cur = conn.cursor()
        deck_rows = cur.execute("SELECT id, name FROM decks").fetchall()
        card_counts = dict(
            cur.execute(
                f"SELECT did, COUNT(*) FROM {NORM_CARDS_SQL} WHERE queue != -1 GROUP BY did"
            ).fetchall()
        )

    matched_exact: List[Dict[str, Any]] = []
    matched_fallback: List[Dict[str, Any]] = []
    unmatched: List[Dict[str, Any]] = []
    covered_profs = set()
    uncovered_profs = set()

    for did, raw_name in deck_rows:
        if card_counts.get(did, 0) <= 0:
            continue
        tb, prof = parse_curriculum_deck(raw_name)
        if not tb or prof == "Allgemein":
            continue
        exact_path = _extract_exact_anki_deck_path(raw_name)
        sub_title = _extract_subdeck_short_title(raw_name)
        hit = match_subdeck_to_exam_signal(
            themenblock=tb,
            dozent=prof,
            subdeck=sub_title,
            full_anki_deck=exact_path,
            allow_prof_fallback=True,
        )
        rec = {
            "themenblock": tb,
            "dozent": prof,
            "subdeck": sub_title,
            "full_anki_deck": exact_path,
            "cards": card_counts[did],
            "matched_id": hit.get("id") if hit else None,
            "match_type": hit.get("match_type") if hit else "unmatched",
        }
        if hit and hit.get("match_type") in ("exact_subdeck", "pattern_subdeck", "token_subdeck"):
            matched_exact.append(rec)
            covered_profs.add((tb, prof))
        elif hit and hit.get("match_type") == "prof_fallback":
            matched_fallback.append(rec)
            covered_profs.add((tb, prof))
        else:
            unmatched.append(rec)
            uncovered_profs.add((tb, prof))

    total = len(matched_exact) + len(matched_fallback) + len(unmatched)
    covered = len(matched_exact) + len(matched_fallback)
    return {
        "connected": True,
        "total_leaf_decks": total,
        "matched_exact_count": len(matched_exact),
        "matched_fallback_count": len(matched_fallback),
        "unmatched_count": len(unmatched),
        "exact_coverage_pct": round((len(matched_exact) / max(1, total)) * 100.0, 1),
        "total_coverage_pct": round((covered / max(1, total)) * 100.0, 1),
        "covered_professors_count": len(covered_profs),
        "uncovered_professors": sorted(uncovered_profs - covered_profs),
        "matched_fallback_decks": matched_fallback,
        "unmatched_decks": unmatched,
    }


def _dedupe_bullets_round_robin(
    per_subdeck_lists: List[List[str]],
    max_items: int,
) -> List[str]:
    """
    Collects concise, deduplicated bullets round-robin across a professor's today subdecks
    so every selected subdeck gets represented within the compact scannable cap.
    """
    out: List[str] = []
    seen = set()
    if not per_subdeck_lists or max_items <= 0:
        return out
    max_depth = max((len(lst) for lst in per_subdeck_lists), default=0)
    for depth in range(max_depth):
        for lst in per_subdeck_lists:
            if depth < len(lst):
                bullet = str(lst[depth] or "").strip()
                key = bullet.lower()
                if bullet and key not in seen:
                    seen.add(key)
                    out.append(bullet)
                    if len(out) >= max_items:
                        return out
    return out


def build_daily_triage_prof_briefing(
    selected_subdecks: List[Dict[str, Any]],
    max_capacity: int = 350,
    focus_mode: str = "smart",
    r_threshold: float = 0.80,
) -> Dict[str, Any]:
    """
    Teil 3 — Dynamic Daily Professor Exam Briefing.

    Synthesizes a compact, scannable daily exam review exclusively for the subdecks
    currently selected in today's triage package (`selected_subdecks`), preserving
    the exact `#1, #2, #3 ...` working order.
    Recalculates live whenever today's due cards change or the user adjusts `max_capacity`
    (e.g., 350 -> 500 -> 700 -> All), both locally and on Render / iPad.
    """
    from datetime import date

    if not selected_subdecks:
        return {
            "generated_for_date": date.today().isoformat(),
            "max_capacity": int(max_capacity or 350),
            "focus_mode": str(focus_mode or "smart"),
            "r_threshold": float(r_threshold or 0.80),
            "total_briefing_cards": 0,
            "total_subdecks_covered": 0,
            "total_topics_count": 0,
            "headline": "🎙️ Heutiges Prof-Prüfungs-Briefing: Aktuell keine offenen Triage-Themen",
            "items": [],
        }

    # Group selected subdecks by (themenblock, dozent) while preserving exact first-appearance order!
    grouped_order: List[Tuple[str, str]] = []
    grouped_sds: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for sd in selected_subdecks:
        tb = str(sd.get("themenblock") or "").strip()
        prof = str(sd.get("dozent") or "").strip()
        if not tb or not prof:
            continue
        key = (tb, prof)
        if key not in grouped_sds:
            grouped_order.append(key)
            grouped_sds[key] = []
        grouped_sds[key].append(sd)

    items: List[Dict[str, Any]] = []
    total_cards = 0
    total_subdecks = 0

    for rank_idx, (tb, prof) in enumerate(grouped_order, start=1):
        sds = grouped_sds[(tb, prof)]
        prof_assigned_cards = sum(int(s.get("assigned_cards", s.get("active_due", 0)) or 0) for s in sds)
        total_cards += prof_assigned_cards
        total_subdecks += len(sds)

        # Highest priority zone among this professor's selected subdecks today (first item is highest)
        lead_sd = sds[0]
        lead_zone = str(lead_sd.get("zone") or "C")
        lead_zone_badge = str(lead_sd.get("zone_badge") or "🔄 C Rotation")

        subdeck_briefings: List[Dict[str, Any]] = []
        hl_lists: List[List[str]] = []
        pearl_lists: List[List[str]] = []
        deemph_lists: List[List[str]] = []
        all_dates: List[str] = []
        all_sources: List[str] = []

        for sd in sds:
            sub_name = str(sd.get("subdeck") or "").strip()
            full_deck = str(sd.get("full_anki_deck") or "").strip()
            sig = match_subdeck_to_exam_signal(
                themenblock=tb,
                dozent=prof,
                subdeck=sub_name,
                full_anki_deck=full_deck,
                allow_prof_fallback=True,
            )
            sd_hl = list(sig.get("exam_highlights") or []) if sig else []
            sd_pearls = list(sig.get("clinical_pearls") or []) if sig else []
            sd_deemph = list(sig.get("deemphasized_notes") or []) if sig else []
            sd_dates = list(sig.get("lecture_dates") or []) if sig else []
            sd_sources = list(sig.get("source_summaries") or []) if sig else []

            if sd_hl:
                hl_lists.append(sd_hl)
            if sd_pearls:
                pearl_lists.append(sd_pearls)
            if sd_deemph:
                deemph_lists.append(sd_deemph)
            for dt in sd_dates:
                if dt not in all_dates:
                    all_dates.append(dt)
            for sf in sd_sources:
                if sf not in all_sources:
                    all_sources.append(sf)

            subdeck_briefings.append({
                "rank": int(sd.get("rank", 0) or 0),
                "subdeck": sub_name,
                "full_anki_deck": full_deck,
                "assigned_cards": int(sd.get("assigned_cards", sd.get("active_due", 0)) or 0),
                "active_due": int(sd.get("active_due", 0) or 0),
                "zone": str(sd.get("zone") or "C"),
                "zone_badge": str(sd.get("zone_badge") or "🔄 C Rotation"),
                "match_type": sig.get("match_type", "unmatched") if sig else "unmatched",
                "signal_id": sig.get("id") if sig else None,
                "lecture_dates": sorted(sd_dates),
                "source_summaries": sd_sources,
                "exam_highlights": sd_hl,
                "clinical_pearls": sd_pearls,
                "deemphasized_notes": sd_deemph,
            })

        # Compact top-level summary for fast scanning (2-4 highlights, 2-3 pearls, 0-2 calm de-emphasis notes)
        agg_highlights = _dedupe_bullets_round_robin(hl_lists, max_items=4)
        agg_pearls = _dedupe_bullets_round_robin(pearl_lists, max_items=3)
        agg_deemph = _dedupe_bullets_round_robin(deemph_lists, max_items=2)

        sub_lbl = f"{len(sds)} Vorlesung" if len(sds) == 1 else f"{len(sds)} Vorlesungen"
        items.append({
            "rank": rank_idx,
            "themenblock": tb,
            "dozent": prof,
            "deck_name": f"{tb} › {prof}",
            "zone": lead_zone,
            "zone_badge": lead_zone_badge,
            "assigned_cards": prof_assigned_cards,
            "subdeck_count": len(sds),
            "header_summary": f"{prof_assigned_cards} Karten ({sub_lbl}) – {lead_zone_badge}",
            "lecture_dates": sorted(all_dates),
            "source_summaries": all_sources,
            "exam_highlights": agg_highlights,
            "clinical_pearls": agg_pearls,
            "deemphasized_notes": agg_deemph,
            "subdecks": subdeck_briefings,
        })

    return {
        "generated_for_date": date.today().isoformat(),
        "max_capacity": int(max_capacity or 350),
        "focus_mode": str(focus_mode or "smart"),
        "r_threshold": float(r_threshold or 0.80),
        "total_briefing_cards": total_cards,
        "total_subdecks_covered": total_subdecks,
        "total_topics_count": len(items),
        "headline": f"🎙️ Heutiges Prof-Prüfungs-Briefing ({total_subdecks} Vorlesungen • {total_cards} Karten)",
        "items": items,
    }

