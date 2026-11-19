import os
import json
import math
import sqlite3
import re
import time
from collections import defaultdict
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.services.anki_desktop_sync import find_local_anki_collection, clean_deck_name
from app.services.semester_config import (
    SEMESTER_START_TS,
    IGNORED_DOZENTEN,
    is_ignored_dozent,
    is_ignored_topic_entry as _is_ignored_topic_entry,
    build_anki_deck_clause,
)
from app.db.repository import get_db_connection

BACKLOG_TRIAGE_SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "cached_backlog_triage.json"
_MEM_TRIAGE_CACHE: Dict[str, Any] = {"mtime": 0.0, "ts": 0.0, "data": None}



def clean_tb_name(raw: str) -> str:
    low = raw.lower()
    if "blut" in low or "immun" in low:
        return "TB Blut & Immunsystem"
    if "herz" in low or "kreislauf" in low:
        return "TB Herz-Kreislauf"
    if "atmung" in low or "lunge" in low:
        return "TB Atmung"
    if "verdauung" in low or "ernährung" in low or "ernaehrung" in low:
        return "TB Verdauung"
    if "stoffwechsel" in low:
        return "TB Stoffwechsel"
    if "endokrin" in low:
        return "TB Endokrinologie"
    return raw.strip()


def clean_prof_name(raw: str) -> str:
    p = raw.strip()
    p = re.sub(r"^[0-9]+[\.\s_]+", "", p)
    p = p.replace("+", "").strip()
    low = p.lower()
    if "wenger" in low:
        return "Wenger"
    if "sommer" in low:
        return "Sommer"
    if "loffing" in low:
        return "Loffing"
    if "stockmann" in low:
        return "Stockmann"
    if "schneider" in low:
        return "Schneider"
    if "manatschal" in low:
        return "Manatschal"
    if "tuzlak" in low or "becher" in low:
        return "Tuzlak / Becher"
    if "kurtcuoglu" in low:
        return "Kurtcuoglu"
    if "dutzler" in low:
        return "Dutzler"
    if "lukic" in low:
        return "Lukic"
    if "rogler" in low:
        return "Rogler"
    if "wagner" in low:
        return "Wagner"
    if "emmert" in low:
        return "Emmert"
    if "hersberger" in low:
        return "Hersberger"
    if "robert" in low:
        return "Robert"
    if "jelezarov" in low:
        return "Jelezarov"
    if "hall" in low:
        return "Hall"
    if "einf" in low or "abschluss" in low:
        return "Einführung & Abschluss"
    return p


def parse_curriculum_deck(raw_name: str):
    """
    Extracts the university module (Themenblock) and lecturer (Dozent) from an Anki deck name.
    Ignores non-2. SJ decks and oral exam decks.
    """
    low = raw_name.lower()
    if ("2. sj" not in low and "hs 2021" not in low) or "mündlich" in low or "muendlich" in low:
        return None, None
    parts = [p.strip() for p in (raw_name.split("\x1f") if "\x1f" in raw_name else raw_name.split("::"))]
    tb_part = None
    prof_part = None
    for i, p in enumerate(parts):
        if p.startswith("TB ") or "themenblock" in p.lower():
            tb_part = p
            if i + 1 < len(parts):
                prof_part = parts[i + 1]
            break
    if not tb_part:
        for p in parts:
            if any(k in p.lower() for k in ["blut", "herz", "atmung", "verdauung", "stoffwechsel", "endokrin"]):
                tb_part = p
                break
    if not tb_part:
        return None, None
    tb_clean = clean_tb_name(tb_part)
    prof_clean = clean_prof_name(prof_part or "Allgemein")
    # Exclude Wenger and Sommer as requested (learned via summaries, not Anki repetitions)
    if is_ignored_dozent(prof_clean):
        return None, None
    return tb_clean, prof_clean


def _extract_real_anki_prof_prefix(raw_name: str) -> str:
    """Returns the real Anki deck hierarchy prefix up to the professor folder (using ::)."""
    parts = [p.strip() for p in (raw_name.split("\x1f") if "\x1f" in raw_name else raw_name.split("::"))]
    for i, p in enumerate(parts):
        if p.startswith("TB ") or "themenblock" in p.lower():
            if i + 1 < len(parts):
                return "::".join(parts[: i + 2])
            return "::".join(parts[: i + 1])
    return "::".join(parts[:3]) if len(parts) >= 3 else "::".join(parts)


def _extract_subdeck_short_title(raw_name: str) -> str:
    """Returns the human-readable lecture/subdeck leaf name."""
    parts = [p.strip() for p in (raw_name.split("\x1f") if "\x1f" in raw_name else raw_name.split("::"))]
    return parts[-1] if parts else raw_name


SMART_R_THRESHOLDS = (0.78, 0.80, 0.82)
SMART_UNSEEN_DAYS = 7
SMART_OVERDUE_GUARD_DAYS = 6


def _get_time_guard_r_cap(r_threshold: float) -> float:
    return round(min(0.90, float(r_threshold) + 0.05), 2)


def _build_smart_filter_suffix(r_threshold: float) -> str:
    """Builds the Anki search suffix matching Smart Focus (Vortag + weak FSRS + >=7d unseen risk)."""
    t_cap = _get_time_guard_r_cap(r_threshold)
    return (
        f"is:due (introduced:2 or prop:r<{r_threshold:.2f} "
        f"or (-rated:{SMART_UNSEEN_DAYS} prop:r<{t_cap:.2f} "
        f"(prop:lapses>=2 or prop:reps<=2 or prop:due<=-{SMART_OVERDUE_GUARD_DAYS})))"
    )


def evaluate_due_card_smart_focus(
    r_prob: float,
    is_vortag: bool,
    last_rev_ms: Optional[float],
    unseen_cutoff_ms: float,
    lapses: int,
    overdue_days: int,
    r_threshold: float,
    reps: int = 99,
):
    """
    Classifies a due card into (is_weak_fsrs, is_time_risk, is_smart_needed).
    Ensures cards unseen for >=7 days whose recall dropped below target (r < r_threshold + 0.05)
    and that either were only reviewed 1-2x so far (reps<=2), had prior lapses (lapses>=2),
    or are >=6d overdue are guarded even when flat FSRS-6 decay still estimates R >= threshold.
    """
    t_cap = _get_time_guard_r_cap(r_threshold)
    is_weak_fsrs = (not is_vortag) and (r_prob < r_threshold)
    unseen_week_plus = (last_rev_ms is None) or (last_rev_ms < unseen_cutoff_ms)
    is_time_risk = (
        (not is_vortag)
        and (not is_weak_fsrs)
        and unseen_week_plus
        and (r_prob < t_cap)
        and (lapses >= 2 or reps <= 2 or overdue_days >= SMART_OVERDUE_GUARD_DAYS)
    )
    return is_weak_fsrs, is_time_risk, (is_vortag or is_weak_fsrs or is_time_risk)


def _normalize_focus_params(focus_mode: Optional[str] = "smart", r_threshold: Optional[float] = 0.80):
    mode = "all" if str(focus_mode or "smart").strip().lower() == "all" else "smart"
    try:
        r_val = float(r_threshold if r_threshold is not None else 0.80)
    except (TypeError, ValueError):
        r_val = 0.80
    if r_val > 1.0:
        r_val = r_val / 100.0
    r_val = max(0.60, min(0.95, r_val))
    closest = min(SMART_R_THRESHOLDS, key=lambda k: abs(k - r_val))
    r_key = f"{closest:.2f}"
    return mode, r_val, r_key


def _score_and_describe_topic(
    t: Dict[str, Any],
    eff_mode: str = "smart",
    eff_r_val: float = 0.80,
    eff_r_key: str = "0.80",
) -> None:
    """
    Dynamically computes undiluted FSRS recall, overdue age, urgency_score, urgency_level,
    level_badge, color, and action_recommendation for a topic under (eff_mode, eff_r_val).
    Guarantees 100% consistency whether called during fresh DB scan or cached threshold switch.
    """
    due_tot = int(t.get("due_today", 0) or 0)
    active_revs = int(t.get("active_reviews", 0) or 0)
    total_revs = int(t.get("total_reviews", 0) or 0)
    if due_tot == 0 and active_revs == 0 and int(t.get("due_tomorrow", 0) or 0) == 0 and total_revs == 0:
        return

    r_pct_label = int(round(eff_r_val * 100))
    sc_map = t.get("smart_due_counts")
    if isinstance(sc_map, dict) and sc_map:
        smart_val = int(sc_map.get(eff_r_key, t.get("smart_due_today", due_tot)) or 0)
        time_val = int(t.get("time_risk_due_counts", {}).get(eff_r_key, t.get("time_risk_due_today", 0)) or 0)
        weak_val = int(
            t.get("weak_due_counts", {}).get(
                eff_r_key,
                max(0, smart_val - int(t.get("vortag_due_today", 0) or 0) - time_val),
            )
            or 0
        )
        solid_val = max(0, due_tot - smart_val)
    else:
        smart_val = due_tot
        weak_val = due_tot
        time_val = 0
        solid_val = 0

    eff_due = smart_val if eff_mode == "smart" else due_tot
    t["smart_due_today"] = smart_val
    t["weak_due_today"] = weak_val
    t["time_risk_due_today"] = time_val
    t["solid_due_today"] = solid_val if eff_mode == "smart" else 0
    t["active_due_today"] = eff_due

    all_ret_pct = float(t.get("all_avg_retrievability_pct", t.get("avg_retrievability_pct", 100.0)) or 100.0)
    all_od_days = float(t.get("all_avg_overdue_days", t.get("avg_overdue_days", 0.0)) or 0.0)
    sm_ret_map = t.get("smart_avg_retrievability_map") or {}
    sm_od_map = t.get("smart_avg_overdue_map") or {}
    sm_un_map = t.get("smart_avg_unseen_map") or {}

    if eff_mode == "smart" and smart_val > 0:
        active_ret_pct = float(sm_ret_map.get(eff_r_key, all_ret_pct))
        active_od_days = float(sm_od_map.get(eff_r_key, all_od_days))
        active_unseen_days = float(sm_un_map.get(eff_r_key, t.get("days_since_last_review") or 0.0))
    else:
        active_ret_pct = all_ret_pct
        active_od_days = all_od_days
        active_unseen_days = float(t.get("days_since_last_review") or 0.0)

    t["avg_retrievability_pct"] = round(active_ret_pct, 1)
    t["avg_overdue_days"] = round(active_od_days, 1)

    vortag_due_cnt = int(t.get("vortag_due_today", 0) or 0)
    uncons_new_due = int(t.get("learned_yesterday_due_today", vortag_due_cnt) or 0)
    learned_yest_total = int(t.get("learned_yesterday", 0) or 0)
    # Only flag VORTAG_NEU if there are STILL unrepeated Vortag cards due right now!
    is_vortag_new = (vortag_due_cnt > 0) if eff_mode == "smart" else (due_tot > 0 and uncons_new_due > 0)
    t["is_vortag_new"] = is_vortag_new

    days_ago_val = t.get("days_since_last_review")
    days_ago = float(days_ago_val) if days_ago_val is not None else 999.0
    raw_days_ago = float(t.get("raw_days_since_last_review", days_ago if days_ago < 900 else 999.0))
    fail_rate = float(t.get("fail_rate_pct", 0.0) or 0.0)
    retention_rate = float(t.get("retention_rate_pct", 100.0) or 100.0)
    avg_ease_pct = float(t.get("avg_ease_pct", 250.0) or 250.0)
    rep_today_cnt = int(t.get("repeated_today", 0) or 0)
    rep_yest_cnt = int(t.get("repeated_yesterday", 0) or 0)

    if days_ago < 900:
        if active_od_days > 1.2:
            effective_overdue = max(days_ago, min(days_ago + 3.0, active_unseen_days * 0.55), active_od_days * 1.35)
        else:
            effective_overdue = max(raw_days_ago if raw_days_ago < 900 else days_ago, active_od_days)
        if effective_overdue <= 10.0:
            time_score = (effective_overdue / 10.0) * 22.0
        else:
            time_score = 22.0 + min(8.0, ((effective_overdue - 10.0) / 15.0) * 8.0)
    else:
        effective_overdue = 10.0
        time_score = 18.0 if active_revs > 0 else 0.0

    fail_score = min(22.0, (fail_rate / 42.0) * 22.0)
    forgetting_risk_score = min(26.0, max(0.0, (85.0 - active_ret_pct) * 2.5)) if eff_due > 0 else 0.0
    ease_penalty = min(8.0, max(0.0, (250.0 - avg_ease_pct) / 40.0 * 8.0))
    volume_score = min(14.0, (eff_due / 75.0) * 14.0)

    rotated_cooldown = (not is_vortag_new) and (rep_yest_cnt >= 20)
    t["rotated_cooldown"] = rotated_cooldown
    rotation_adjustment = -22.0 if rotated_cooldown else 0.0

    raw_urgency = time_score + fail_score + forgetting_risk_score + ease_penalty + volume_score + rotation_adjustment
    if 0 < eff_due < 10 and not is_vortag_new:
        raw_urgency *= 0.78

    if is_vortag_new:
        new_boost = min(7.9, max(vortag_due_cnt, uncons_new_due, learned_yest_total) / 15.0)
        urgency_score = round(92.0 + new_boost, 1)
        urgency_level = "VORTAG_NEU"
        level_badge = "🔥 Vortag neu gelernt"
        color = "#f85149"
        sub_sorted = sorted(t.get("yesterday_subdecks") or [], key=lambda x: x.get("new_learned", 0), reverse=True)
        sub_str = ", ".join([f"{s['new_learned']}× {s['subdeck']}" for s in sub_sorted[:3]])
        tr_txt = f" + {time_val} >7d ungesehen" if time_val > 0 else ""
        action = (
            f"Tag-1-Pflichtwiederholung: {vortag_due_cnt} Vortag-Karten + {weak_val} schwache{tr_txt} "
            f"({sub_str}) – {solid_val} solide zurückgestellt."
        )
    elif eff_mode == "smart" and due_tot > 0 and smart_val == 0:
        urgency_score = round(min(12.0, max(1.0, (90.0 - all_ret_pct) * 0.5)), 1)
        urgency_level = "STABIL"
        level_badge = "🟢 Gefestigt (0 nötig)"
        color = "#3fb950"
        action = f"Alle {due_tot} fälligen Karten sitzen stabil (Ø Recall {all_ret_pct}% ≥ {r_pct_label}%) – heute kein Fokus nötig."
    elif eff_due > 0 and (raw_urgency >= 42.0 or fail_rate >= 35.0 or effective_overdue >= 8.0 or active_ret_pct < (eff_r_val * 100.0)):
        urgency_score = round(max(15.0, min(91.0, raw_urgency)), 1)
        urgency_level = "KRITISCH"
        level_badge = "🚨 Höchste Priorität"
        color = "#f85149"
        need_non_v = (weak_val + time_val) if eff_mode == "smart" else due_tot
        if active_ret_pct < (eff_r_val * 100.0):
            action = f"Hohes Vergessensrisiko (Ø Recall {round(active_ret_pct, 1)}%): {need_non_v} gefährdete Karten gezielt festigen!"
        elif active_od_days >= 4.0:
            action = f"Sofort wiederholen: Fokus-Karten im Schnitt {round(active_od_days, 1)} Tage überfällig ({need_non_v} nötig, Retention {retention_rate}%)!"
        else:
            action = f"Sofort wiederholen: Seit {days_ago}d keine große Session ({need_non_v} gefährdet)!"
    elif eff_due > 0:
        urgency_score = round(max(8.0, min(91.0, raw_urgency)), 1)
        urgency_level = "HOCH"
        level_badge = "🔄 Rotation (Gestern gelernt)" if rotated_cooldown else "⚠️ Wiederholen"
        color = "#58a6ff" if rotated_cooldown else "#d29922"
        if rotated_cooldown:
            action = f"Gestern bereits {rep_yest_cnt} Karten wiederholt – heute rotieren zuerst länger wartende Decks nach oben."
        else:
            action = f"Steht für die rollierende Wiederholung bereit ({eff_due} nötig)."
    else:
        urgency_score = round(max(0.0, min(10.0, (time_score + fail_score) * 0.25)), 1)
        urgency_level = "STABIL"
        level_badge = "✅ Heute erledigt" if rep_today_cnt > 0 else "✅ Stabil"
        color = "#3fb950"
        action = (
            f"Heute bereits {rep_today_cnt} Karten erfolgreich wiederholt!"
            if rep_today_cnt > 0
            else "Kürzlich wiederholt & aktuell 0 Karten fällig."
        )

    if days_ago < 900:
        if active_od_days > days_ago + 1.5 and eff_due > 0:
            days_str = f"{days_ago}d (Ø {round(active_od_days, 1)}d fällig)"
        else:
            days_str = f"{days_ago}d"
    else:
        days_str = "Neu / nie"

    t["days_since_last_review_str"] = days_str
    t["urgency_score"] = urgency_score
    t["urgency_level"] = urgency_level
    t["level_badge"] = level_badge
    t["color"] = color
    t["action_recommendation"] = action


def compute_fsrs_retrievability(
    card_data_str: Optional[str],
    now_ts: float,
    queue: int = 2,
    due: int = 0,
    current_day: int = 0,
    lapses: int = 0,
    ivl: int = 0,
) -> float:
    """
    Computes exact FSRS recall probability R(t, S) in [0.0, 1.0] matching Anki's `prop:r`.
    Uses the FSRS-5/6 power-law forgetting curve:
      R(t, S) = (1 + (0.9^(-1/decay) - 1) * (t / S)) ^ (-decay)
    Falls back gracefully for SM-2 or active learning/relearning cards (queue 1/3 -> 0.50).
    """
    if card_data_str and "{" in str(card_data_str):
        try:
            dj = json.loads(card_data_str)
            s = float(dj.get("s") or 0.0)
            decay = float(dj.get("decay") or 0.5)
            lrt = dj.get("lrt")
            if s > 0.0 and lrt:
                elapsed_days = max(0.0, (now_ts - float(lrt)) / 86400.0)
                factor = (0.9 ** (-1.0 / decay)) - 1.0
                r = (1.0 + factor * (elapsed_days / s)) ** (-decay)
                return max(0.0, min(1.0, r))
        except Exception:
            pass

    if queue in (1, 3):
        return 0.50
    overdue = max(0, current_day - due) if queue == 2 else 0
    if lapses > 0 and ivl <= 3:
        return 0.72
    if ivl > 0:
        est = 0.90 * (0.9 ** (overdue / max(1.0, float(ivl))))
        return max(0.10, min(0.98, est))
    return 0.85


def _get_anki_collection_mtime(target_path: Path) -> float:
    try:
        wal = target_path.with_name(target_path.name + "-wal")
        wal_m = wal.stat().st_mtime if wal.exists() else 0.0
        return max(target_path.stat().st_mtime, wal_m)
    except Exception:
        return 0.0


def calculate_backlog_triage(
    col_path=None,
    max_capacity: Optional[int] = 350,
    focus_mode: str = "smart",
    r_threshold: float = 0.80,
) -> Dict[str, Any]:
    """
    Calculates intelligent workload triage aggregated at Themenblock and Dozent/Prof level.
    Evaluates:
      1) Vortag Newly Learned Cards (Day-1 consolidation priority, directly from Anki revlog MIN(id))
      2) Per-card FSRS Retrievability R(t, S) to separate weak/forgetting-risk cards (R < threshold)
         from already solid/mastered cards (R >= threshold) so only genuinely needed cards consume budget
      3) True overdue age of currently due cards + days since last substantive review session
      4) Semester retention rate (% correct recalls) & Ease stability
      5) Daily rotation cooldown (decks repeated heavily yesterday step back so waiting decks rotate up)
    Provides a curated daily focus budget (default: 350 cards) ordered strictly from most important (#1)
    to least important, plus automatic proportional deferral across the following days.
    """
    effective_budget = int(max_capacity) if (max_capacity is not None and int(max_capacity) > 0) else 350
    eff_mode, eff_r_val, eff_r_key = _normalize_focus_params(focus_mode, r_threshold)
    target_path = Path(col_path) if col_path else find_local_anki_collection()
    now = datetime.now()

    is_cloud = (os.environ.get("APPDATA") is None)
    if is_cloud or not target_path or not target_path.exists():
        cached = get_cached_triage()
        if cached:
            cached["max_capacity"] = effective_budget
            _apply_budget(cached, effective_budget, focus_mode=eff_mode, r_threshold=eff_r_val)
            return cached
        if not target_path or not target_path.exists():
            return {
                "connected": False,
                "total_due_today": 0,
                "smart_total_due_today": 0,
                "solid_total_due_today": 0,
                "active_focus_pool_due": 0,
                "total_due_tomorrow": 0,
                "already_repeated_today": 0,
                "focus_mode": eff_mode,
                "r_threshold": eff_r_val,
                "is_overloaded": False,
                "themenbloecke": [],
                "topics": [],
                "urgent_topics": [],
                "deferrable_topics": [],
                "budget_selected_topics": [],
                "focus_plan_open": [],
                "focus_plan_completed_today": [],
                "multi_day_rollover": [],
                "summary_advice": "Keine Anki-Datenbank gefunden.",
            }

    # Fast in-memory mtime cache: avoid heavy SQLite WAL copy & revlog scan when Anki hasn't changed
    cur_mtime = _get_anki_collection_mtime(target_path)
    if (
        col_path is None
        and _MEM_TRIAGE_CACHE.get("data") is not None
        and cur_mtime > 0
        and cur_mtime == _MEM_TRIAGE_CACHE.get("mtime")
        and (time.time() - _MEM_TRIAGE_CACHE.get("ts", 0.0)) < 45.0
    ):
        cached_copy = json.loads(json.dumps(_MEM_TRIAGE_CACHE["data"]))
        cached_copy["max_capacity"] = effective_budget
        _apply_budget(cached_copy, effective_budget, focus_mode=eff_mode, r_threshold=eff_r_val)
        return cached_copy

    # Anki day rollover at 04:00 AM local time
    today_4am = now.replace(hour=4, minute=0, second=0, microsecond=0)
    if now < today_4am:
        today_4am -= timedelta(days=1)
    yesterday_4am = today_4am - timedelta(days=1)
    two_days_ago_4am = today_4am - timedelta(days=2)

    today_ms = int(today_4am.timestamp() * 1000)
    yesterday_ms = int(yesterday_4am.timestamp() * 1000)
    two_days_ms = int(two_days_ago_4am.timestamp() * 1000)
    unseen_cutoff_ms = int((today_4am - timedelta(days=SMART_UNSEEN_DAYS - 1)).timestamp() * 1000)
    now_ts = now.timestamp()
    now_ms = now_ts * 1000

    from app.db.anki_db import open_anki_db_readonly, NORM_CARDS_SQL
    with open_anki_db_readonly(target_path) as conn:
        cur = conn.cursor()

        crt = cur.execute("SELECT crt FROM col").fetchone()[0]
        crt_date = datetime.fromtimestamp(crt).date()
        current_day = (today_4am.date() - crt_date).days
        next_day = current_day + 1
        crt_anchor_sec = int(today_4am.timestamp()) - (current_day * 86400)

        raw_decks = cur.execute("SELECT id, name FROM decks").fetchall()
        deck_map = {}
        for did, dname in raw_decks:
            tb, prof = parse_curriculum_deck(dname)
            if tb:
                deck_map[did] = (
                    tb,
                    prof,
                    clean_deck_name(dname),
                    _extract_real_anki_prof_prefix(dname),
                    _extract_subdeck_short_title(dname),
                )

        if not deck_map:
            return {
                "connected": True,
                "total_due_today": 0,
                "total_due_tomorrow": 0,
                "already_repeated_today": 0,
                "is_overloaded": False,
                "themenbloecke": [],
                "topics": [],
                "urgent_topics": [],
                "deferrable_topics": [],
                "budget_selected_topics": [],
                "focus_plan_open": [],
                "focus_plan_completed_today": [],
                "multi_day_rollover": [],
                "summary_advice": "Keine relevanten 2. SJ Decks gefunden.",
            }

        placeholders = ",".join("?" * len(deck_map))
        dids = list(deck_map.keys())

        sql_cards = f"""
        SELECT 
            c.did,
            COUNT(*) as total_cards,
            SUM(CASE WHEN (c.queue = 2 AND c.due <= ?) OR c.queue = 1 OR (c.queue = 3 AND c.due <= ?) THEN 1 ELSE 0 END) as due_now,
            SUM(CASE WHEN (c.queue = 2 AND c.due = ?) OR (c.queue = 3 AND c.due = ?) THEN 1 ELSE 0 END) as due_tomorrow,
            SUM(CASE WHEN c.queue = 2 THEN 1 ELSE 0 END) as active_review_cards,
            SUM(CASE WHEN c.queue = 2 AND c.factor > 0 THEN c.factor ELSE 0 END) as sum_factor,
            SUM(CASE WHEN c.queue = 2 AND c.factor > 0 THEN 1 ELSE 0 END) as count_factor,
            SUM(c.lapses) as total_lapses,
            SUM(c.reps) as total_reps,
            SUM(CASE WHEN c.queue = 2 AND c.due <= ? THEN (? - c.due) ELSE 0 END) as sum_overdue_days
        FROM {NORM_CARDS_SQL} c
        WHERE c.did IN ({placeholders}) AND c.queue != -1
        GROUP BY c.did
        """
        cards_stats = cur.execute(
            sql_cards,
            [current_day, current_day, next_day, next_day, current_day, current_day] + dids
        ).fetchall()

        sem_start_ts = SEMESTER_START_TS
        sql_revs = f"""
        SELECT c.did, MAX(r.id) as last_ms, COUNT(*) as total_revs,
               SUM(CASE WHEN r.ease = 1 THEN 1 ELSE 0 END) as fail_count
        FROM revlog r
        JOIN {NORM_CARDS_SQL} c ON r.cid = c.id
        WHERE c.did IN ({placeholders}) AND r.id >= ? AND r.type != 4 AND r.ease in (1, 2, 3, 4)
        GROUP BY c.did
        """
        rev_stats = {
            r[0]: {"last_ms": r[1], "revs": r[2], "fails": r[3]}
            for r in cur.execute(sql_revs, dids + [sem_start_ts]).fetchall()
        }

        # Detect newly learned cards from yesterday (or 48h unconsolidated) per subdeck
        sql_new_learned = f"""
        SELECT c.did,
               SUM(CASE WHEN fr.first_rev >= ? AND fr.first_rev < ? THEN 1 ELSE 0 END) as learned_yesterday,
               SUM(CASE WHEN fr.first_rev >= ? AND fr.first_rev < ? AND ((c.queue = 2 AND c.due <= ?) OR c.queue = 1 OR (c.queue = 3 AND c.due <= ?)) THEN 1 ELSE 0 END) as learned_yest_due_now,
               SUM(CASE WHEN fr.first_rev >= ? AND fr.first_rev < ? AND c.ivl <= 1 AND ((c.queue = 2 AND c.due <= ?) OR c.queue = 1 OR (c.queue = 3 AND c.due <= ?)) THEN 1 ELSE 0 END) as learned_prev48_uncons_due
        FROM (
            SELECT cid, MIN(id) as first_rev
            FROM revlog
            GROUP BY cid
        ) fr
        JOIN {NORM_CARDS_SQL} c ON fr.cid = c.id
        WHERE c.did IN ({placeholders}) AND c.queue != -1
        GROUP BY c.did
        """
        new_learned_rows = cur.execute(
            sql_new_learned,
            [
                yesterday_ms, today_ms,
                yesterday_ms, today_ms, current_day, current_day,
                two_days_ms, yesterday_ms, current_day, current_day,
            ] + dids
        ).fetchall()
        new_learned_by_did = {
            r[0]: {
                "learned_yesterday": r[1] or 0,
                "learned_yest_due_now": r[2] or 0,
                "learned_prev48_uncons_due": r[3] or 0,
            }
            for r in new_learned_rows
        }

        # Detect daily review sessions & today's completed repetitions vs yesterday's repetitions
        sql_daily_activity = f"""
        SELECT c.did,
               CAST((r.id / 1000 - ?) / 86400 AS INT) as rev_day,
               COUNT(*) as rev_count,
               COUNT(DISTINCT CASE WHEN r.id >= ? AND fr.first_rev < ? THEN r.cid END) as rep_today_cards,
               COUNT(DISTINCT CASE WHEN r.id >= ? AND r.id < ? AND fr.first_rev < ? THEN r.cid END) as rep_yest_non_new_cards
        FROM revlog r
        JOIN {NORM_CARDS_SQL} c ON r.cid = c.id
        JOIN (
            SELECT cid, MIN(id) as first_rev
            FROM revlog
            GROUP BY cid
        ) fr ON r.cid = fr.cid
        WHERE c.did IN ({placeholders}) AND r.id >= ? AND r.type != 4
        GROUP BY c.did, rev_day
        """
        activity_rows = cur.execute(
            sql_daily_activity,
            [
                crt_anchor_sec,
                today_ms, today_ms,
                yesterday_ms, today_ms, yesterday_ms,
            ] + dids + [sem_start_ts]
        ).fetchall()

        # Per-card FSRS retrievability, Vortag & >=7d unseen time-risk inspection for Smart Efficiency Triage
        sql_due_cards_detail = f"""
        SELECT c.did, c.queue, c.due, c.ivl, c.lapses, c.reps, c.data, fr.first_rev, fr.last_rev
        FROM {NORM_CARDS_SQL} c
        LEFT JOIN (
            SELECT cid, MIN(id) as first_rev, MAX(id) as last_rev
            FROM revlog
            GROUP BY cid
        ) fr ON c.id = fr.cid
        WHERE c.did IN ({placeholders})
          AND ((c.queue = 2 AND c.due <= ?) OR c.queue = 1 OR (c.queue = 3 AND c.due <= ?))
          AND c.queue != -1
        """
        due_cards_detail_rows = cur.execute(
            sql_due_cards_detail,
            dids + [current_day, current_day],
        ).fetchall()

    prof_day_revs = defaultdict(lambda: defaultdict(int))
    prof_rep_today = defaultdict(int)
    prof_rep_yest_non_new = defaultdict(int)
    for did, rev_day, rev_cnt, rep_tod, rep_yest in activity_rows:
        tb, prof, _, _, _ = deck_map[did]
        key = (tb, prof)
        prof_day_revs[key][rev_day] += (rev_cnt or 0)
        prof_rep_today[key] += (rep_tod or 0)
        prof_rep_yest_non_new[key] += (rep_yest or 0)

    prof_smart = defaultdict(lambda: {
        "total": 0,
        "vortag_due": 0,
        "r_sum": 0.0,
        "smart": {"0.78": 0, "0.80": 0, "0.82": 0},
        "weak": {"0.78": 0, "0.80": 0, "0.82": 0},
        "time_risk": {"0.78": 0, "0.80": 0, "0.82": 0},
        "smart_r_sum": {"0.78": 0.0, "0.80": 0.0, "0.82": 0.0},
        "smart_od_sum": {"0.78": 0.0, "0.80": 0.0, "0.82": 0.0},
        "smart_unseen_sum": {"0.78": 0.0, "0.80": 0.0, "0.82": 0.0},
        "smart_unseen_cnt": {"0.78": 0, "0.80": 0, "0.82": 0},
        "subdecks": defaultdict(lambda: {"all_due": 0, "vortag_due": 0, "smart_78": 0, "smart_80": 0, "smart_82": 0}),
    })
    for did, q, due, ivl, card_lapses, card_reps, data_str, first_rev, last_rev in due_cards_detail_rows:
        tb, prof, _, _, sub_title = deck_map[did]
        key = (tb, prof)
        ps = prof_smart[key]
        r_prob = compute_fsrs_retrievability(
            data_str, now_ts, queue=q or 2, due=due or 0, current_day=current_day, lapses=card_lapses or 0, ivl=ivl or 0
        )
        is_v_card = bool(first_rev is not None and yesterday_ms <= first_rev < today_ms)
        overdue_days = max(0, current_day - (due or 0)) if (q or 2) == 2 else 0
        unseen_card_days = max(0.0, (now_ts - (float(last_rev) / 1000.0)) / 86400.0) if last_rev else None
        ps["total"] += 1
        ps["r_sum"] += r_prob
        if is_v_card:
            ps["vortag_due"] += 1
        sub_rec = ps["subdecks"][sub_title]
        sub_rec["all_due"] += 1
        if is_v_card:
            sub_rec["vortag_due"] += 1
        for thr in SMART_R_THRESHOLDS:
            tkey = f"{thr:.2f}"
            is_weak_thr, is_time_thr, is_needed_thr = evaluate_due_card_smart_focus(
                r_prob=r_prob,
                is_vortag=is_v_card,
                last_rev_ms=last_rev,
                unseen_cutoff_ms=unseen_cutoff_ms,
                lapses=card_lapses or 0,
                overdue_days=overdue_days,
                r_threshold=thr,
                reps=card_reps if card_reps is not None else 99,
            )
            if is_weak_thr:
                ps["weak"][tkey] += 1
            if is_time_thr:
                ps["time_risk"][tkey] += 1
            if is_needed_thr:
                ps["smart"][tkey] += 1
                ps["smart_r_sum"][tkey] += r_prob
                ps["smart_od_sum"][tkey] += overdue_days
                if unseen_card_days is not None:
                    ps["smart_unseen_sum"][tkey] += unseen_card_days
                    ps["smart_unseen_cnt"][tkey] += 1
                if thr == 0.78:
                    sub_rec["smart_78"] += 1
                elif thr == 0.80:
                    sub_rec["smart_80"] += 1
                elif thr == 0.82:
                    sub_rec["smart_82"] += 1

    prof_groups = defaultdict(lambda: {
        "total_cards": 0, "due_today": 0, "due_tomorrow": 0, "active_reviews": 0,
        "sum_factor": 0, "count_factor": 0, "total_lapses": 0, "total_reps": 0,
        "sum_overdue_days": 0,
        "last_ms": 0, "total_revs": 0, "fail_count": 0, "dids": [], "deck_names": [],
        "real_prefixes": set(),
        "learned_yesterday": 0, "learned_yest_due_now": 0, "learned_prev48_uncons_due": 0,
        "yesterday_subdecks": [],
    })

    for r in cards_stats:
        did, total, due_now, due_tom, active, s_fac, c_fac, lapses, reps, sum_od = r
        tb, prof, orig_name, real_prefix, subdeck_title = deck_map[did]
        key = (tb, prof)
        g = prof_groups[key]
        g["total_cards"] += (total or 0)
        g["due_today"] += (due_now or 0)
        g["due_tomorrow"] += (due_tom or 0)
        g["active_reviews"] += (active or 0)
        g["sum_factor"] += (s_fac or 0)
        g["count_factor"] += (c_fac or 0)
        g["total_lapses"] += (lapses or 0)
        g["total_reps"] += (reps or 0)
        g["sum_overdue_days"] += (sum_od or 0)
        g["dids"].append(did)
        g["deck_names"].append(orig_name)
        if real_prefix:
            g["real_prefixes"].add(real_prefix)

        r_info = rev_stats.get(did, {"last_ms": 0, "revs": 0, "fails": 0})
        if r_info["last_ms"] > g["last_ms"]:
            g["last_ms"] = r_info["last_ms"]
        g["total_revs"] += r_info["revs"]
        g["fail_count"] += r_info["fails"]

        nl_info = new_learned_by_did.get(did)
        if nl_info:
            ly = nl_info["learned_yesterday"]
            lyd = nl_info["learned_yest_due_now"]
            lp48 = nl_info["learned_prev48_uncons_due"]
            g["learned_yesterday"] += ly
            g["learned_yest_due_now"] += lyd
            g["learned_prev48_uncons_due"] += lp48
            if ly > 0 or lp48 > 0:
                g["yesterday_subdecks"].append({
                    "subdeck": subdeck_title,
                    "new_learned": ly if ly > 0 else lp48,
                    "due_now": lyd if ly > 0 else lp48,
                })

    topics = []
    total_due_today = 0
    total_due_tomorrow = 0
    total_already_repeated_today = 0

    for (tb, prof), g in prof_groups.items():
        rep_today_cnt = prof_rep_today.get((tb, prof), 0)
        rep_yest_cnt = prof_rep_yest_non_new.get((tb, prof), 0)
        total_already_repeated_today += rep_today_cnt

        real_prefixes = sorted(g["real_prefixes"])
        deck_clause = build_anki_deck_clause(real_prefixes, tb, prof)
        anki_filter_query_all = f"{deck_clause} is:due"
        smart_anki_filter_query = f"{deck_clause} {_build_smart_filter_suffix(eff_r_val)}"
        anki_filter_query = smart_anki_filter_query if eff_mode == "smart" else anki_filter_query_all
        anki_hard_query = f"{deck_clause} is:due (prop:ease<2.3 or lapses>1)"

        if g["active_reviews"] == 0 and g["due_today"] == 0 and g["due_tomorrow"] == 0 and g["total_revs"] == 0:
            topics.append({
                "themenblock": tb,
                "dozent": prof,
                "deck_name": f"{tb} › {prof}",
                "real_anki_prefixes": real_prefixes,
                "deck_clause": deck_clause,
                "total_cards": g["total_cards"],
                "due_today": 0,
                "vortag_due_today": 0,
                "smart_due_counts": {"0.78": 0, "0.80": 0, "0.82": 0},
                "weak_due_counts": {"0.78": 0, "0.80": 0, "0.82": 0},
                "time_risk_due_counts": {"0.78": 0, "0.80": 0, "0.82": 0},
                "solid_due_counts": {"0.78": 0, "0.80": 0, "0.82": 0},
                "smart_due_today": 0,
                "weak_due_today": 0,
                "time_risk_due_today": 0,
                "solid_due_today": 0,
                "all_avg_retrievability_pct": 100.0,
                "smart_avg_retrievability_map": {"0.78": 100.0, "0.80": 100.0, "0.82": 100.0},
                "avg_retrievability_pct": 100.0,
                "smart_subdecks": [],
                "due_tomorrow": 0,
                "repeated_today": 0,
                "repeated_yesterday": 0,
                "learned_yesterday": 0,
                "learned_yesterday_due_today": 0,
                "yesterday_subdecks": [],
                "is_vortag_new": False,
                "rotated_cooldown": False,
                "all_avg_overdue_days": 0.0,
                "smart_avg_overdue_map": {"0.78": 0.0, "0.80": 0.0, "0.82": 0.0},
                "smart_avg_unseen_map": {"0.78": 0.0, "0.80": 0.0, "0.82": 0.0},
                "avg_overdue_days": 0.0,
                "active_reviews": 0,
                "raw_days_since_last_review": None,
                "days_since_last_review": None,
                "days_since_last_review_str": "Noch nicht im Umlauf",
                "avg_ease_pct": 250.0,
                "fail_rate_pct": 0.0,
                "retention_rate_pct": 100.0,
                "total_fails": 0,
                "total_reviews": 0,
                "urgency_score": 0.0,
                "urgency_level": "NEU",
                "level_badge": "🌱 Noch kein Backlog",
                "color": "#8b949e",
                "action_recommendation": f"Noch nicht gestartet. {g['total_cards']} neue Karten im Lehrplan.",
                "anki_filter_query": f"{deck_clause} is:new",
                "anki_filter_query_all": f"{deck_clause} is:new",
                "smart_anki_filter_query": f"{deck_clause} is:new",
                "anki_hard_query": f"{deck_clause} is:new",
            })
            continue

        total_due_today += g["due_today"]
        total_due_tomorrow += g["due_tomorrow"]

        ps = prof_smart.get((tb, prof))
        due_cnt_total = g["due_today"]
        all_ret_pct = round((ps["r_sum"] / max(1, ps["total"])) * 100.0, 1) if (ps and ps["total"] > 0) else 100.0
        vortag_due_cnt = ps["vortag_due"] if ps else 0
        smart_counts = {
            tkey: (ps["smart"][tkey] if ps else 0)
            for tkey in ("0.78", "0.80", "0.82")
        }
        weak_counts = {
            tkey: (ps["weak"][tkey] if ps else 0)
            for tkey in ("0.78", "0.80", "0.82")
        }
        time_risk_counts = {
            tkey: (ps["time_risk"][tkey] if ps else 0)
            for tkey in ("0.78", "0.80", "0.82")
        }
        solid_counts = {
            tkey: max(0, due_cnt_total - smart_counts[tkey])
            for tkey in ("0.78", "0.80", "0.82")
        }

        last_ms = g["last_ms"]
        raw_days_ago = round((now_ms - last_ms) / (86400 * 1000), 1) if last_ms > 0 else 999.0

        # Scale substantive session threshold with actual due cards (min 2 for small decks, up to 35 for large decks)
        min_session_revs = max(2, min(35, int(round(max(g["due_today"], 4) * 0.22))))
        day_dict = prof_day_revs.get((tb, prof), {})
        subst_days = [d for d, cnt in day_dict.items() if cnt >= min_session_revs]
        if subst_days:
            last_subst_day = max(subst_days)
            subst_days_ago = max(0.0, float(current_day - last_subst_day))
            days_ago = round(max(raw_days_ago, subst_days_ago), 1) if rep_today_cnt < min_session_revs else raw_days_ago
        else:
            days_ago = raw_days_ago

        all_overdue_days = round(g["sum_overdue_days"] / g["due_today"], 1) if g["due_today"] > 0 else 0.0
        smart_ret_map = {}
        smart_od_map = {}
        smart_unseen_map = {}
        for tkey in ("0.78", "0.80", "0.82"):
            sc_n = smart_counts[tkey]
            if ps and sc_n > 0:
                smart_ret_map[tkey] = round((ps["smart_r_sum"][tkey] / sc_n) * 100.0, 1)
                smart_od_map[tkey] = round(ps["smart_od_sum"][tkey] / sc_n, 1)
                u_cnt = ps["smart_unseen_cnt"][tkey]
                smart_unseen_map[tkey] = round(ps["smart_unseen_sum"][tkey] / u_cnt, 1) if u_cnt > 0 else (days_ago if days_ago < 900 else 0.0)
            else:
                smart_ret_map[tkey] = all_ret_pct
                smart_od_map[tkey] = 0.0
                smart_unseen_map[tkey] = days_ago if days_ago < 900 else 0.0

        subdeck_list = []
        if ps:
            for sname, svals in ps["subdecks"].items():
                subdeck_list.append({
                    "subdeck": sname,
                    "all_due": svals["all_due"],
                    "vortag_due": svals["vortag_due"],
                    "smart_due_counts": {
                        "0.78": svals["smart_78"],
                        "0.80": svals["smart_80"],
                        "0.82": svals["smart_82"],
                    },
                })
            subdeck_list.sort(key=lambda x: (x["vortag_due"], x["smart_due_counts"]["0.80"], x["all_due"]), reverse=True)

        avg_ease_pct = round(g["sum_factor"] / g["count_factor"] / 10, 1) if g["count_factor"] > 0 else 250.0
        fail_rate = round((g["fail_count"] / g["total_revs"] * 100) if g["total_revs"] > 0 else 0.0, 1)
        retention_rate = round(100.0 - fail_rate, 1) if g["total_revs"] > 0 else 100.0
        learned_yest_total = g["learned_yesterday"]
        uncons_new_due = g["learned_yest_due_now"] + g["learned_prev48_uncons_due"]

        topic_entry = {
            "themenblock": tb,
            "dozent": prof,
            "deck_name": f"{tb} › {prof}",
            "real_anki_prefixes": real_prefixes,
            "deck_clause": deck_clause,
            "total_cards": g["total_cards"],
            "due_today": g["due_today"],
            "vortag_due_today": vortag_due_cnt,
            "smart_due_counts": smart_counts,
            "weak_due_counts": weak_counts,
            "time_risk_due_counts": time_risk_counts,
            "solid_due_counts": solid_counts,
            "smart_due_today": smart_counts[eff_r_key],
            "weak_due_today": weak_counts[eff_r_key],
            "time_risk_due_today": time_risk_counts[eff_r_key],
            "solid_due_today": solid_counts[eff_r_key],
            "all_avg_retrievability_pct": all_ret_pct,
            "smart_avg_retrievability_map": smart_ret_map,
            "avg_retrievability_pct": smart_ret_map[eff_r_key] if (eff_mode == "smart" and smart_counts[eff_r_key] > 0) else all_ret_pct,
            "smart_subdecks": subdeck_list,
            "due_tomorrow": g["due_tomorrow"],
            "repeated_today": rep_today_cnt,
            "repeated_yesterday": rep_yest_cnt,
            "learned_yesterday": learned_yest_total,
            "learned_yesterday_due_today": uncons_new_due,
            "yesterday_subdecks": sorted(g["yesterday_subdecks"], key=lambda x: x["new_learned"], reverse=True),
            "is_vortag_new": False,
            "rotated_cooldown": False,
            "all_avg_overdue_days": all_overdue_days,
            "smart_avg_overdue_map": smart_od_map,
            "smart_avg_unseen_map": smart_unseen_map,
            "avg_overdue_days": smart_od_map[eff_r_key] if (eff_mode == "smart" and smart_counts[eff_r_key] > 0) else all_overdue_days,
            "active_reviews": g["active_reviews"],
            "raw_days_since_last_review": raw_days_ago if raw_days_ago < 900 else None,
            "days_since_last_review": days_ago if days_ago < 900 else None,
            "days_since_last_review_str": "",
            "avg_ease_pct": avg_ease_pct,
            "fail_rate_pct": fail_rate,
            "retention_rate_pct": retention_rate,
            "total_fails": g["fail_count"],
            "total_reviews": g["total_revs"],
            "urgency_score": 0.0,
            "urgency_level": "STABIL",
            "level_badge": "",
            "color": "#3fb950",
            "action_recommendation": "",
            "anki_filter_query": anki_filter_query,
            "anki_filter_query_all": anki_filter_query_all,
            "smart_anki_filter_query": smart_anki_filter_query,
            "anki_hard_query": anki_hard_query,
        }
        _score_and_describe_topic(topic_entry, eff_mode=eff_mode, eff_r_val=eff_r_val, eff_r_key=eff_r_key)
        topics.append(topic_entry)

    # Sort topics overall: due_today > 0 first, then Vortag newly learned, then urgency_score descending
    topics.sort(
        key=lambda x: (
            x["due_today"] > 0,
            x.get("is_vortag_new", False),
            x["urgency_score"],
            x.get("avg_overdue_days", 0.0),
        ),
        reverse=True,
    )

    # Group topics hierarchically by Themenblock
    tb_map = defaultdict(list)
    for t in topics:
        tb_map[t["themenblock"]].append(t)

    themenbloecke = []
    for tb_name, prof_list in sorted(tb_map.items()):
        tb_due_today = sum(p["due_today"] for p in prof_list)
        tb_due_tom = sum(p["due_tomorrow"] for p in prof_list)
        themenbloecke.append({
            "name": tb_name,
            "total_due_today": tb_due_today,
            "total_due_tomorrow": tb_due_tom,
            "professors": sorted(
                prof_list,
                key=lambda x: (x["due_today"] > 0, x.get("is_vortag_new", False), x["urgency_score"]),
                reverse=True,
            ),
        })

    themenbloecke.sort(
        key=lambda x: (
            max([p["urgency_score"] for p in x["professors"] if p["due_today"] > 0] or [0]),
            x["total_due_today"],
        ),
        reverse=True,
    )

    urgent_topics = [t for t in topics if t["urgency_level"] in ("VORTAG_NEU", "KRITISCH", "HOCH") and t["due_today"] > 0]
    deferrable_topics = [t for t in topics if t["urgency_level"] == "STABIL" or t["due_today"] == 0]

    is_overloaded = (total_due_today >= 500 or total_due_tomorrow >= 500)

    top_urgent = [t for t in topics if t["due_today"] > 0][:4] or topics[:3]
    if top_urgent:
        urgent_clauses = []
        for t in top_urgent:
            for pfx in t.get("real_anki_prefixes", []):
                urgent_clauses.append(f'deck:"{pfx}*"')
            urgent_clauses.append(f'deck:"*2. SJ*{t["themenblock"]}*{t["dozent"]}*"')
        urgent_combined_anki_query = f"({' or '.join(dict.fromkeys(urgent_clauses))}) is:due"
    else:
        urgent_combined_anki_query = "is:due"

    result = {
        "connected": True,
        "timestamp": now.isoformat(),
        "total_due_today": total_due_today,
        "total_due_tomorrow": total_due_tomorrow,
        "already_repeated_today": total_already_repeated_today,
        "is_overloaded": is_overloaded,
        "themenbloecke_count": len(themenbloecke),
        "themenbloecke": themenbloecke,
        "topics_count": len(topics),
        "topics": topics,
        "urgent_topics": urgent_topics,
        "deferrable_topics": deferrable_topics,
        "urgent_combined_anki_query": urgent_combined_anki_query,
        "max_capacity": effective_budget,
    }

    _apply_budget(result, effective_budget, focus_mode=eff_mode, r_threshold=eff_r_val)

    if col_path is None and cur_mtime > 0:
        _MEM_TRIAGE_CACHE["mtime"] = cur_mtime
        _MEM_TRIAGE_CACHE["ts"] = time.time()
        _MEM_TRIAGE_CACHE["data"] = json.loads(json.dumps(result))

    cache_triage(result)
    return result


def _sanitize_triage_payload(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Guarantees that Wenger and Sommer are completely removed from topics, themenbloecke,
    urgent_topics, deferrable_topics, and recomputes total_due_today / total_due_tomorrow.
    Protects against stale cache entries or older background sync daemons.
    """
    if not isinstance(result, dict):
        return result

    if "topics" in result and isinstance(result["topics"], list):
        result["topics"] = [t for t in result["topics"] if not _is_ignored_topic_entry(t)]
        result["topics_count"] = len(result["topics"])
        result["total_due_today"] = sum(t.get("due_today", 0) for t in result["topics"])
        result["total_due_tomorrow"] = sum(t.get("due_tomorrow", 0) for t in result["topics"])

    if "urgent_topics" in result and isinstance(result["urgent_topics"], list):
        result["urgent_topics"] = [t for t in result["urgent_topics"] if not _is_ignored_topic_entry(t)]

    if "deferrable_topics" in result and isinstance(result["deferrable_topics"], list):
        result["deferrable_topics"] = [t for t in result["deferrable_topics"] if not _is_ignored_topic_entry(t)]

    if "themenbloecke" in result and isinstance(result["themenbloecke"], list):
        cleaned_tbs = []
        for tb in result["themenbloecke"]:
            profs = [p for p in tb.get("professors", []) if not _is_ignored_topic_entry(p)]
            if profs:
                tb_copy = dict(tb)
                tb_copy["professors"] = profs
                tb_copy["total_due_today"] = sum(p.get("due_today", 0) for p in profs)
                tb_copy["total_due_tomorrow"] = sum(p.get("due_tomorrow", 0) for p in profs)
                cleaned_tbs.append(tb_copy)
        result["themenbloecke"] = cleaned_tbs
        result["themenbloecke_count"] = len(cleaned_tbs)

    return result


def _apply_budget(
    result: Dict[str, Any],
    budget: int,
    focus_mode: str = "smart",
    r_threshold: float = 0.80,
):
    """
    Strict priority-ordered allocation from #1 (most important) downwards:
      - First sanitizes payload to ensure Wenger & Sommer are strictly excluded.
      - In `smart` focus_mode (default): only counts & schedules cards genuinely needed today
        (`Vortag neu gelernt` OR FSRS Retrievability `R < r_threshold`), leaving already solid
        cards (`R >= r_threshold`) deferred so high-risk decks (like Emmert) aren't pushed behind!
      - In `all` focus_mode: schedules all `due_today` cards across the full backlog.
      - Vortag newly learned cards always rank at #1.
      - Packs complete professors in strict rank order until `budget` is reached.
      - Distributes remaining cards in the active pool proportionally into Day +1, Day +2, etc.
    """
    _sanitize_triage_payload(result)
    eff_mode, eff_r_val, eff_r_key = _normalize_focus_params(focus_mode, r_threshold)
    r_pct_label = int(round(eff_r_val * 100))
    budget = max(1, int(budget or 350))
    all_topics = result.get("topics", [])

    # Recompute smart vs solid counts, undiluted FSRS recall, and urgency scores dynamically for focus_mode & r_threshold
    for t in all_topics:
        _score_and_describe_topic(t, eff_mode=eff_mode, eff_r_val=eff_r_val, eff_r_key=eff_r_key)
        due_tot = int(t.get("due_today", 0) or 0)
        dclause = t.get("deck_clause")
        if dclause and due_tot > 0:
            smart_q = f"{dclause} {_build_smart_filter_suffix(eff_r_val)}"
            all_q = t.get("anki_filter_query_all") or f"{dclause} is:due"
            t["smart_anki_filter_query"] = smart_q
            t["anki_filter_query"] = smart_q if eff_mode == "smart" else all_q

    all_topics.sort(
        key=lambda x: (
            x.get("active_due_today", x.get("due_today", 0)) > 0,
            x.get("due_today", 0) > 0,
            x.get("is_vortag_new", False),
            x.get("urgency_score", 0.0),
            x.get("avg_overdue_days", 0.0),
        ),
        reverse=True,
    )

    result["urgent_topics"] = [
        t for t in all_topics
        if t.get("urgency_level") in ("VORTAG_NEU", "KRITISCH", "HOCH")
        and t.get("active_due_today", t.get("due_today", 0)) > 0
    ]
    result["deferrable_topics"] = [
        t for t in all_topics
        if t.get("urgency_level") == "STABIL"
        or t.get("active_due_today", t.get("due_today", 0)) == 0
    ]

    # Sync updated topic fields into grouped themenbloecke entries
    topic_by_key = {(t.get("themenblock"), t.get("dozent")): t for t in all_topics}
    for tb in result.get("themenbloecke", []):
        profs = tb.get("professors", [])
        for p in profs:
            src = topic_by_key.get((p.get("themenblock"), p.get("dozent")))
            if src:
                for fld in (
                    "smart_due_today", "weak_due_today", "time_risk_due_today", "solid_due_today",
                    "active_due_today", "avg_retrievability_pct", "avg_overdue_days",
                    "is_vortag_new", "rotated_cooldown", "days_since_last_review_str",
                    "urgency_score", "urgency_level", "level_badge", "color",
                    "action_recommendation", "anki_filter_query", "smart_anki_filter_query",
                ):
                    if fld in src:
                        p[fld] = src[fld]
        profs.sort(
            key=lambda x: (
                x.get("active_due_today", x.get("due_today", 0)) > 0,
                x.get("due_today", 0) > 0,
                x.get("is_vortag_new", False),
                x.get("urgency_score", 0.0),
            ),
            reverse=True,
        )
        tb["smart_total_due_today"] = sum(p.get("smart_due_today", p.get("due_today", 0)) for p in profs)

    if isinstance(result.get("themenbloecke"), list):
        result["themenbloecke"].sort(
            key=lambda x: (
                max([p.get("urgency_score", 0.0) for p in x.get("professors", []) if p.get("active_due_today", p.get("due_today", 0)) > 0] or [0.0]),
                x.get("smart_total_due_today", x.get("total_due_today", 0)),
            ),
            reverse=True,
        )

    total_due_today = sum(t.get("due_today", 0) for t in all_topics)
    smart_total_due_today = sum(t.get("smart_due_today", t.get("due_today", 0)) for t in all_topics)
    vortag_total_due_today = sum(t.get("vortag_due_today", 0) for t in all_topics)
    solid_total_due_today = max(0, total_due_today - smart_total_due_today)
    active_focus_pool_due = smart_total_due_today if eff_mode == "smart" else total_due_today

    already_repeated_today = sum(t.get("repeated_today", 0) for t in all_topics)
    total_workload_today = active_focus_pool_due + already_repeated_today

    # Strict rank order: Vortag newly learned first, then urgency_score descending, then avg_overdue_days
    today_candidates = [t for t in all_topics if t.get("active_due_today", t.get("due_today", 0)) > 0]
    today_candidates.sort(
        key=lambda x: (
            x.get("is_vortag_new", False),
            x.get("urgency_score", 0.0),
            x.get("avg_overdue_days", 0.0),
            x.get("active_due_today", 0),
        ),
        reverse=True,
    )

    completed_today_list = [
        {
            "themenblock": t["themenblock"],
            "dozent": t["dozent"],
            "deck_name": t["deck_name"],
            "repeated_today": t.get("repeated_today", 0),
            "due_remaining": t.get("active_due_today", t.get("due_today", 0)),
            "all_due_remaining": t.get("due_today", 0),
            "retention_rate_pct": t.get("retention_rate_pct", 100.0),
        }
        for t in all_topics
        if t.get("repeated_today", 0) > 0
    ]
    completed_today_list.sort(key=lambda x: x["repeated_today"], reverse=True)

    # How many cards still need to be repeated today to hit `budget`
    remaining_budget_for_today = max(0, budget - already_repeated_today)
    # For building `budget_selected_topics`, if user hasn't hit budget yet, pack `remaining_budget_for_today`;
    # if user already completed >= budget today, still compute a preview of `budget` cards so queries/tests work.
    packing_target = remaining_budget_for_today if remaining_budget_for_today > 0 else budget

    selected = []
    focus_plan_open = []
    accumulated = 0
    leftover_queue = []  # tuples of (topic_dict, remaining_active_due_cards)

    for idx, t in enumerate(today_candidates):
        pool_cnt = int(t.get("active_due_today", t.get("due_today", 0)) or 0)
        full_due_cnt = int(t.get("due_today", 0) or 0)
        vort_cnt = int(t.get("vortag_due_today", 0) or 0)
        weak_cnt = int(t.get("weak_due_today", 0) or 0)
        time_risk_cnt = int(t.get("time_risk_due_today", 0) or 0)
        solid_cnt = int(t.get("solid_due_today", 0) or 0)
        if pool_cnt <= 0:
            continue

        if accumulated < packing_target:
            room_left = packing_target - accumulated
            if pool_cnt <= room_left:
                assigned = pool_cnt
                is_partial = False
                rem_after = 0
            else:
                assigned = room_left
                is_partial = True
                rem_after = pool_cnt - assigned

            plan_entry = dict(t)
            plan_entry["rank"] = len(selected) + 1
            plan_entry["assigned_cards"] = assigned
            plan_entry["active_due_today"] = pool_cnt
            plan_entry["is_partial"] = is_partial
            plan_entry["deferred_from_deck"] = rem_after

            if eff_mode == "smart":
                parts_lbl = []
                if vort_cnt > 0:
                    parts_lbl.append(f"{vort_cnt} Vortag-Neu")
                if weak_cnt > 0:
                    parts_lbl.append(f"{weak_cnt} schwach (R<{r_pct_label}%)")
                if time_risk_cnt > 0:
                    parts_lbl.append(f"{time_risk_cnt} >7d ungesehen")
                mix_desc = " + ".join(parts_lbl) if parts_lbl else f"{pool_cnt} gefährdet"
                skip_note = f" • {solid_cnt} gefestigte übersprungen" if solid_cnt > 0 else ""
                if is_partial:
                    plan_entry["focus_instruction"] = f"Davon {assigned} von {pool_cnt} nötigen Karten ({mix_desc}{skip_note})"
                else:
                    plan_entry["focus_instruction"] = f"Nur {assigned} nötige Karten ({mix_desc}{skip_note})"
            else:
                if is_partial:
                    plan_entry["focus_instruction"] = f"Davon {assigned} von {full_due_cnt} Karten machen (Rest {rem_after} automatisch auf morgen verschoben)"
                else:
                    plan_entry["focus_instruction"] = f"Komplett wiederholen ({assigned} Karten)"

            selected.append(plan_entry)
            if remaining_budget_for_today > 0:
                focus_plan_open.append(plan_entry)
            accumulated += assigned

            if rem_after > 0:
                leftover_queue.append((t, rem_after))
        else:
            leftover_queue.append((t, pool_cnt))

    # If today had fewer active due cards than packing_target and total_due_today == 0, preview tomorrow
    if accumulated < packing_target and active_focus_pool_due == 0 and total_due_today == 0:
        tom_candidates = [t for t in all_topics if t.get("due_tomorrow", 0) > 0 and t not in selected]
        tom_candidates.sort(key=lambda x: x.get("urgency_score", 0.0), reverse=True)
        for t in tom_candidates:
            needed = t.get("due_tomorrow", 0)
            if accumulated < packing_target:
                assigned = min(needed, packing_target - accumulated)
                plan_entry = dict(t)
                plan_entry["rank"] = len(selected) + 1
                plan_entry["assigned_cards"] = assigned
                plan_entry["is_partial"] = assigned < needed
                plan_entry["deferred_from_deck"] = needed - assigned
                plan_entry["focus_instruction"] = f"Vorschau morgen ({assigned} Karten)"
                selected.append(plan_entry)
                accumulated += assigned

    # Build multi-day proportional rollover schedule for remaining active pool cards
    multi_day_rollover = []
    day_Labels = ["Morgen (Tag +1)", "Übermorgen (Tag +2)", "In 3 Tagen (Tag +3)", "In 4 Tagen (Tag +4)", "Folgetage"]
    queue_idx = 0
    day_bucket_idx = 0
    current_rem_in_item = leftover_queue[0][1] if leftover_queue else 0

    while queue_idx < len(leftover_queue) and day_bucket_idx < len(day_Labels):
        bucket_cap = budget
        bucket_cards = 0
        bucket_decks = []

        while queue_idx < len(leftover_queue) and bucket_cards < bucket_cap:
            topic_obj, _ = leftover_queue[queue_idx]
            take = min(current_rem_in_item, bucket_cap - bucket_cards)
            bucket_cards += take
            bucket_decks.append({
                "themenblock": topic_obj["themenblock"],
                "dozent": topic_obj["dozent"],
                "deck_name": topic_obj["deck_name"],
                "cards": take,
                "total_due_in_deck": topic_obj.get("active_due_today", topic_obj["due_today"]),
                "urgency_score": topic_obj["urgency_score"],
            })
            current_rem_in_item -= take
            if current_rem_in_item <= 0:
                queue_idx += 1
                if queue_idx < len(leftover_queue):
                    current_rem_in_item = leftover_queue[queue_idx][1]

        if bucket_cards > 0:
            multi_day_rollover.append({
                "day_label": day_Labels[day_bucket_idx],
                "day_offset": day_bucket_idx + 1,
                "planned_cards": bucket_cards,
                "decks": bucket_decks,
            })
            day_bucket_idx += 1

    deferred_topics = [t for (t, _) in leftover_queue]
    effective_today_target = min(budget, total_workload_today) if total_workload_today > 0 else 0
    coverage_pct = round(min(100.0, (effective_today_target / max(1, total_workload_today)) * 100.0), 1)
    if remaining_budget_for_today > 0:
        deferred_cards_count = max(0, active_focus_pool_due - sum(x["assigned_cards"] for x in focus_plan_open))
    else:
        deferred_cards_count = active_focus_pool_due

    if active_focus_pool_due > 0:
        days_to_clear_backlog = (1 if len(focus_plan_open) > 0 else 0) + len(multi_day_rollover)
    else:
        days_to_clear_backlog = 0

    result["focus_mode"] = eff_mode
    result["r_threshold"] = eff_r_val
    result["smart_total_due_today"] = smart_total_due_today
    result["vortag_total_due_today"] = vortag_total_due_today
    result["solid_total_due_today"] = solid_total_due_today
    result["total_solid_skipped_today"] = solid_total_due_today if eff_mode == "smart" else 0
    result["active_focus_pool_due"] = active_focus_pool_due
    result["budget_selected_topics"] = selected
    result["focus_plan_open"] = focus_plan_open
    result["focus_plan_completed_today"] = completed_today_list
    result["budget_deferred_topics"] = deferred_topics
    result["budget_accumulated_cards"] = accumulated
    result["already_repeated_today"] = already_repeated_today
    result["remaining_budget_today"] = remaining_budget_for_today
    result["effective_today_target"] = effective_today_target
    result["coverage_pct"] = coverage_pct
    result["deferred_cards_count"] = deferred_cards_count
    result["days_to_clear_backlog"] = days_to_clear_backlog
    result["multi_day_rollover"] = multi_day_rollover
    result["max_capacity"] = budget

    rollover_days_txt = "am nächsten Tag" if len(multi_day_rollover) == 1 else f"in den nächsten {len(multi_day_rollover)} Tagen"
    if eff_mode == "smart":
        if active_focus_pool_due > budget:
            result["summary_advice"] = (
                f"🎯 Effizienz-Fokus (R < {r_pct_label}% / >7d ungesehen): Von {total_due_today} fälligen Karten brauchen nur {smart_total_due_today} "
                f"heute Aufmerksamkeit ({solid_total_due_today} gefestigte übersprungen). Davon machst du {effective_today_target} heute ({coverage_pct}%), "
                f"restliche {deferred_cards_count} rotieren {rollover_days_txt}!"
            )
        elif active_focus_pool_due > 0:
            result["summary_advice"] = (
                f"🎯 Effizienz-Fokus (R < {r_pct_label}% / >7d ungesehen): Alle {smart_total_due_today} wirklich nötigen Karten "
                f"({vortag_total_due_today} Vortag + {max(0, smart_total_due_today - vortag_total_due_today)} gefährdet) passen komplett heute! "
                f"{solid_total_due_today} gefestigte Karten automatisch entlastet."
            )
        elif total_due_today > 0:
            result["summary_advice"] = (
                f"🎉 Alle {total_due_today} offenen Karten sitzen stabil (R ≥ {r_pct_label}%). Du kannst bei Bedarf auf 'Alle Fälligen' umschalten."
            )
        else:
            result["summary_advice"] = "🎉 Hervorragend: Aktuell keine offenen Wiederholungen für heute!"
    else:
        rollover_all_txt = "auf morgen" if len(multi_day_rollover) == 1 else f"auf die nächsten {len(multi_day_rollover)} Tage"
        if total_due_today > budget:
            result["summary_advice"] = (
                f"📚 Alle Fälligen aktiv: Du machst heute gezielt {effective_today_target} von {total_workload_today} fälligen Karten ({coverage_pct}%). "
                f"Die übrigen {deferred_cards_count} Karten ({round(100.0 - coverage_pct, 1)}%) werden automatisch {rollover_all_txt} verschoben!"
            )
        elif total_due_today > 0:
            result["summary_advice"] = (
                f"✅ Alle {total_due_today} fälligen Karten passen heute komplett in dein {budget}er Fokus-Budget (100% Abdeckung)."
            )
        else:
            result["summary_advice"] = "🎉 Hervorragend: Aktuell keine offenen Wiederholungen für heute!"

    if selected:
        clauses = []
        for t in selected:
            for pfx in t.get("real_anki_prefixes", []):
                clauses.append(f'deck:"{pfx}*"')
            clauses.append(f'deck:"*2. SJ*{t["themenblock"]}*{t["dozent"]}*"')
        deck_union = " or ".join(dict.fromkeys(clauses))
        result["budget_combined_anki_query_all"] = f"({deck_union}) is:due"
        if eff_mode == "smart":
            smart_suffix = _build_smart_filter_suffix(eff_r_val)
            result["budget_combined_anki_query"] = f"({deck_union}) {smart_suffix}"
            top4_clauses = []
            for t in selected[:4]:
                for pfx in t.get("real_anki_prefixes", []):
                    top4_clauses.append(f'deck:"{pfx}*"')
                top4_clauses.append(f'deck:"*2. SJ*{t["themenblock"]}*{t["dozent"]}*"')
            result["urgent_combined_anki_query"] = f"({' or '.join(dict.fromkeys(top4_clauses))}) {smart_suffix}"
        else:
            result["budget_combined_anki_query"] = result["budget_combined_anki_query_all"]
    else:
        result["budget_combined_anki_query_all"] = "is:due"
        result["budget_combined_anki_query"] = "is:due"


def cache_triage(data: Dict[str, Any]):
    if not isinstance(data, dict):
        return
    _sanitize_triage_payload(data)

    # Protect against legacy in-memory sync daemons overwriting v2.3 undiluted FSRS schema
    topics = data.get("topics", [])
    is_legacy_payload = bool(topics) and (
        "is_vortag_new" not in topics[0]
        or "smart_due_counts" not in topics[0]
        or "time_risk_due_counts" not in topics[0]
        or "smart_avg_retrievability_map" not in topics[0]
    )
    if is_legacy_payload:
        try:
            if BACKLOG_TRIAGE_SNAPSHOT_PATH.exists():
                snap = json.loads(BACKLOG_TRIAGE_SNAPSHOT_PATH.read_text(encoding="utf-8"))
                snap_topics = snap.get("topics", [])
                if snap_topics and "smart_avg_retrievability_map" in snap_topics[0]:
                    data = snap
                    _sanitize_triage_payload(data)
        except Exception:
            pass
        _apply_budget(
            data,
            data.get("max_capacity") or 350,
            focus_mode=data.get("focus_mode") or "smart",
            r_threshold=data.get("r_threshold") or 0.80,
        )
    elif "focus_plan_open" not in data:
        _apply_budget(
            data,
            data.get("max_capacity") or 350,
            focus_mode=data.get("focus_mode") or "smart",
            r_threshold=data.get("r_threshold") or 0.80,
        )

    json_str = json.dumps(data, ensure_ascii=False)
    # 1. DB Cache
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS anki_backlog_triage_cache (id INTEGER PRIMARY KEY CHECK (id = 1), data_json TEXT NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
            cur.execute("INSERT INTO anki_backlog_triage_cache (id, data_json, updated_at) VALUES (1, ?, CURRENT_TIMESTAMP) ON CONFLICT(id) DO UPDATE SET data_json = excluded.data_json, updated_at = CURRENT_TIMESTAMP;", (json_str,))
    except Exception:
        pass

    # 2. File-system snapshot (deployed to Render)
    try:
        BACKLOG_TRIAGE_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        BACKLOG_TRIAGE_SNAPSHOT_PATH.write_text(json_str, encoding="utf-8")
    except Exception:
        pass


def get_cached_triage() -> Optional[Dict[str, Any]]:
    snap_data = None
    try:
        if BACKLOG_TRIAGE_SNAPSHOT_PATH.exists():
            content = BACKLOG_TRIAGE_SNAPSHOT_PATH.read_text(encoding="utf-8")
            if content.strip():
                snap_data = json.loads(content)
    except Exception:
        snap_data = None

    db_data = None
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS anki_backlog_triage_cache (id INTEGER PRIMARY KEY CHECK (id = 1), data_json TEXT NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
            row = cur.execute("SELECT data_json FROM anki_backlog_triage_cache WHERE id = 1").fetchone()
            if row and row[0]:
                db_data = json.loads(row[0])
    except Exception:
        db_data = None

    def _schema_rank(payload: Dict[str, Any]) -> int:
        tps = payload.get("topics", [])
        if not tps:
            return 0
        t0 = tps[0]
        if "smart_avg_retrievability_map" in t0:
            return 4
        if "time_risk_due_counts" in t0:
            return 3
        if "smart_due_counts" in t0:
            return 2
        if "is_vortag_new" in t0:
            return 1
        return 0

    chosen = db_data or snap_data
    if db_data and snap_data:
        if _schema_rank(snap_data) > _schema_rank(db_data):
            chosen = snap_data

    if chosen:
        _sanitize_triage_payload(chosen)
    return chosen


