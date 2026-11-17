import os
import json
import sqlite3
import re
from collections import defaultdict
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.services.anki_desktop_sync import find_local_anki_collection, clean_deck_name
from app.db.repository import get_db_connection

BACKLOG_TRIAGE_SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "cached_backlog_triage.json"


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
    return clean_tb_name(tb_part), clean_prof_name(prof_part or "Allgemein")


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


def calculate_backlog_triage(col_path=None, max_capacity: Optional[int] = 350) -> Dict[str, Any]:
    """
    Calculates intelligent workload triage aggregated at Themenblock and Dozent/Prof level.
    Evaluates:
      1) Vortag Newly Learned Cards (Day-1 consolidation priority, directly from Anki revlog MIN(id))
      2) True overdue age of currently due cards + days since last substantive review session (>=10 reviews)
      3) Semester retention rate (% correct recalls) & Ease stability
      4) Daily rotation cooldown (decks repeated heavily yesterday step back so waiting decks rotate up)
    Provides a curated daily focus budget (default: 350 cards) ordered strictly from most important (#1)
    to least important, plus automatic proportional deferral across the following days.
    """
    effective_budget = int(max_capacity) if (max_capacity is not None and int(max_capacity) > 0) else 350
    target_path = Path(col_path) if col_path else find_local_anki_collection()
    now = datetime.now()

    is_cloud = (os.environ.get("APPDATA") is None)
    if is_cloud or not target_path or not target_path.exists():
        cached = get_cached_triage()
        if cached:
            cached["max_capacity"] = effective_budget
            _apply_budget(cached, effective_budget)
            return cached
        if not target_path or not target_path.exists():
            return {
                "connected": False,
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
                "summary_advice": "Keine Anki-Datenbank gefunden.",
            }

    # Anki day rollover at 04:00 AM local time
    today_4am = now.replace(hour=4, minute=0, second=0, microsecond=0)
    if now < today_4am:
        today_4am -= timedelta(days=1)
    yesterday_4am = today_4am - timedelta(days=1)
    two_days_ago_4am = today_4am - timedelta(days=2)

    today_ms = int(today_4am.timestamp() * 1000)
    yesterday_ms = int(yesterday_4am.timestamp() * 1000)
    two_days_ms = int(two_days_ago_4am.timestamp() * 1000)
    now_ms = now.timestamp() * 1000

    from app.db.anki_db import open_anki_db_readonly
    with open_anki_db_readonly(target_path) as conn:
        cur = conn.cursor()

        crt = cur.execute("SELECT crt FROM col").fetchone()[0]
        current_day = int((now.timestamp() - crt) // 86400)
        next_day = current_day + 1

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
        FROM cards c
        WHERE c.did IN ({placeholders}) AND c.queue != -1
        GROUP BY c.did
        """
        cards_stats = cur.execute(
            sql_cards,
            [current_day, current_day, next_day, next_day, current_day, current_day] + dids
        ).fetchall()

        sem_start_ts = int(datetime(2026, 9, 14, 0, 0, 0).timestamp() * 1000)
        sql_revs = f"""
        SELECT c.did, MAX(r.id) as last_ms, COUNT(*) as total_revs,
               SUM(CASE WHEN r.ease = 1 THEN 1 ELSE 0 END) as fail_count
        FROM revlog r
        JOIN cards c ON r.cid = c.id
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
        JOIN cards c ON fr.cid = c.id
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
        JOIN cards c ON r.cid = c.id
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
                crt,
                today_ms, today_ms,
                yesterday_ms, today_ms, yesterday_ms,
            ] + dids + [sem_start_ts]
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
        exact_clauses = [f'deck:"{pfx}*"' for pfx in real_prefixes]
        fallback_clause = f'deck:"*2. SJ*{tb}*{prof}*"'
        if exact_clauses:
            combined_deck_clause = " or ".join(exact_clauses + [fallback_clause])
            anki_filter_query = f"({combined_deck_clause}) is:due"
            anki_hard_query = f"({combined_deck_clause}) is:due (prop:ease<2.3 or lapses>1)"
        else:
            anki_filter_query = f"{fallback_clause} is:due"
            anki_hard_query = f"{fallback_clause} is:due (prop:ease<2.3 or lapses>1)"

        if g["active_reviews"] == 0 and g["due_today"] == 0 and g["due_tomorrow"] == 0 and g["total_revs"] == 0:
            topics.append({
                "themenblock": tb,
                "dozent": prof,
                "deck_name": f"{tb} › {prof}",
                "total_cards": g["total_cards"],
                "due_today": 0,
                "due_tomorrow": 0,
                "repeated_today": 0,
                "repeated_yesterday": 0,
                "learned_yesterday": 0,
                "learned_yesterday_due_today": 0,
                "yesterday_subdecks": [],
                "is_vortag_new": False,
                "rotated_cooldown": False,
                "avg_overdue_days": 0.0,
                "active_reviews": 0,
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
                "anki_filter_query": f'deck:"*2. SJ*{tb}*{prof}*" is:new',
                "anki_hard_query": f'deck:"*2. SJ*{tb}*{prof}*" is:new',
            })
            continue

        total_due_today += g["due_today"]
        total_due_tomorrow += g["due_tomorrow"]

        last_ms = g["last_ms"]
        raw_days_ago = round((now_ms - last_ms) / (86400 * 1000), 1) if last_ms > 0 else 999.0

        # Calculate days since last substantive review session
        # Scales threshold with deck size (3 cards for tiny decks, 10 cards for normal/large decks)
        min_session_revs = max(3, min(10, int(max(g["active_reviews"], g["due_today"]) * 0.25)))
        day_dict = prof_day_revs.get((tb, prof), {})
        subst_days = [d for d, cnt in day_dict.items() if cnt >= min_session_revs]
        if subst_days:
            last_subst_day = max(subst_days)
            subst_days_ago = max(0.0, float(current_day - last_subst_day))
            days_ago = round(max(raw_days_ago, subst_days_ago), 1) if rep_today_cnt < min_session_revs else raw_days_ago
        else:
            days_ago = raw_days_ago

        avg_overdue_days = round(g["sum_overdue_days"] / g["due_today"], 1) if g["due_today"] > 0 else 0.0
        avg_ease_pct = round(g["sum_factor"] / g["count_factor"] / 10, 1) if g["count_factor"] > 0 else 250.0
        fail_rate = round((g["fail_count"] / g["total_revs"] * 100) if g["total_revs"] > 0 else 0.0, 1)
        retention_rate = round(100.0 - fail_rate, 1) if g["total_revs"] > 0 else 100.0

        learned_yest_total = g["learned_yesterday"]
        uncons_new_due = g["learned_yest_due_now"] + g["learned_prev48_uncons_due"]
        is_vortag_new = (g["due_today"] > 0) and (learned_yest_total > 0 or uncons_new_due > 0)

        # Effective overdue metric combines session recency and actual due-card age
        effective_overdue = max(days_ago if days_ago < 900 else 10.0, avg_overdue_days)

        # 1. Time / Overdue score (0-48 points):
        # Differentiates cleanly between 5d, 11d, 15d, and 29d neglect
        if days_ago < 900:
            if effective_overdue <= 10.0:
                time_score = (effective_overdue / 10.0) * 34.0
            else:
                time_score = 34.0 + min(14.0, ((effective_overdue - 10.0) / 20.0) * 14.0)
        else:
            time_score = 25.0 if g["active_reviews"] > 0 else 0.0

        # 2. Retention / Fail score (0-28 points):
        # Differentiates between 30% fail rate (70% ret) and 54% fail rate (46% ret)
        fail_score = min(28.0, (fail_rate / 50.0) * 28.0)

        # 3. Ease / stability penalty (0-12 points)
        ease_penalty = min(12.0, max(0.0, (250.0 - avg_ease_pct) / 40.0 * 12.0))

        # 4. Due volume bonus (0-10 points)
        volume_score = min(10.0, (max(g["due_today"], g["due_tomorrow"]) / 60.0) * 10.0)

        # 5. Daily Rotation Cooldown:
        # If this professor was already heavily repeated yesterday (>= 20 non-new reviews)
        # and has NO newly learned cards from yesterday, step back today so waiting decks rotate up!
        rotated_cooldown = (not is_vortag_new) and (rep_yest_cnt >= 20 or (days_ago <= 1.2 and avg_overdue_days < 1.5))
        rotation_adjustment = -22.0 if rotated_cooldown else 0.0

        if is_vortag_new:
            # Tier 1 Top Priority: Newly learned cards from yesterday MUST be consolidated first!
            new_boost = min(7.9, max(learned_yest_total, uncons_new_due) / 15.0)
            urgency_score = round(92.0 + new_boost, 1)
            urgency_level = "VORTAG_NEU"
            level_badge = "🔥 Vortag neu gelernt"
            color = "#f85149"
            sub_sorted = sorted(g["yesterday_subdecks"], key=lambda x: x["new_learned"], reverse=True)
            sub_str = ", ".join([f"{s['new_learned']}× {s['subdeck']}" for s in sub_sorted[:3]])
            action = (
                f"Tag-1-Pflichtwiederholung: Gestern {max(learned_yest_total, uncons_new_due)} Karten neu gelernt "
                f"({sub_str}) – heute zuerst festigen!"
            )
        elif g["due_today"] > 0 and (
            (time_score + fail_score + ease_penalty + volume_score + rotation_adjustment) >= 42.0
            or fail_rate >= 35.0
            or effective_overdue >= 8.0
        ):
            urgency_score = round(max(15.0, min(91.0, time_score + fail_score + ease_penalty + volume_score + rotation_adjustment)), 1)
            urgency_level = "KRITISCH"
            level_badge = "🚨 Höchste Priorität"
            color = "#f85149"
            if avg_overdue_days >= 5.0:
                action = f"Sofort wiederholen: Karten im Schnitt {avg_overdue_days} Tage überfällig (Retention {retention_rate}%)!"
            else:
                action = f"Sofort wiederholen: Seit {days_ago}d keine große Session oder hohes Vergessensrisiko!"
        elif g["due_today"] > 0:
            urgency_score = round(max(8.0, min(91.0, time_score + fail_score + ease_penalty + volume_score + rotation_adjustment)), 1)
            urgency_level = "HOCH"
            level_badge = "🔄 Rotation (Gestern gelernt)" if rotated_cooldown else "⚠️ Wiederholen"
            color = "#58a6ff" if rotated_cooldown else "#d29922"
            if rotated_cooldown:
                action = f"Gestern bereits {rep_yest_cnt} Karten wiederholt – heute rotieren zuerst länger wartende Decks nach oben."
            else:
                action = "Steht für die rollierende Wiederholung bereit."
        else:
            urgency_score = round(max(0.0, time_score + fail_score + ease_penalty), 1)
            urgency_level = "STABIL"
            level_badge = "✅ Heute erledigt" if rep_today_cnt > 0 else "✅ Stabil"
            color = "#3fb950"
            action = (
                f"Heute bereits {rep_today_cnt} Karten erfolgreich wiederholt!"
                if rep_today_cnt > 0
                else "Kürzlich wiederholt & aktuell 0 Karten fällig."
            )

        if days_ago < 900:
            if avg_overdue_days > days_ago + 2.0 and g["due_today"] > 0:
                days_str = f"{days_ago}d (Ø {avg_overdue_days}d fällig)"
            else:
                days_str = f"{days_ago}d"
        else:
            days_str = "Neu / nie"

        topics.append({
            "themenblock": tb,
            "dozent": prof,
            "deck_name": f"{tb} › {prof}",
            "total_cards": g["total_cards"],
            "due_today": g["due_today"],
            "due_tomorrow": g["due_tomorrow"],
            "repeated_today": rep_today_cnt,
            "repeated_yesterday": rep_yest_cnt,
            "learned_yesterday": learned_yest_total,
            "learned_yesterday_due_today": uncons_new_due,
            "yesterday_subdecks": sorted(g["yesterday_subdecks"], key=lambda x: x["new_learned"], reverse=True),
            "is_vortag_new": is_vortag_new,
            "rotated_cooldown": rotated_cooldown,
            "avg_overdue_days": avg_overdue_days,
            "active_reviews": g["active_reviews"],
            "days_since_last_review": days_ago if days_ago < 900 else None,
            "days_since_last_review_str": days_str,
            "avg_ease_pct": avg_ease_pct,
            "fail_rate_pct": fail_rate,
            "retention_rate_pct": retention_rate,
            "total_fails": g["fail_count"],
            "total_reviews": g["total_revs"],
            "urgency_score": urgency_score,
            "urgency_level": urgency_level,
            "level_badge": level_badge,
            "color": color,
            "action_recommendation": action,
            "anki_filter_query": anki_filter_query,
            "anki_hard_query": anki_hard_query,
        })

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
        clauses = " or ".join([f'deck:"*2. SJ*{t["themenblock"]}*{t["dozent"]}*"' for t in top_urgent])
        urgent_combined_anki_query = f"({clauses}) is:due"
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

    _apply_budget(result, effective_budget)

    cache_triage(result)
    return result


def _apply_budget(result: Dict[str, Any], budget: int):
    """
    Strict priority-ordered allocation from #1 (most important) downwards without skipping professors:
      - Vortag newly learned cards always rank at #1.
      - Packs complete professors in strict rank order until the boundary professor reaches `budget`.
      - The boundary professor gets the exact remaining card count (`assigned_cards` of `due_today`)
        so the daily focus box always totals exactly `budget` (e.g. 350 cards).
      - Automatically distributes all remaining due cards proportionally into Day +1 (Morgen),
        Day +2 (Übermorgen), etc.
    """
    budget = max(1, int(budget or 350))
    all_topics = result.get("topics", [])
    total_due_today = sum(t.get("due_today", 0) for t in all_topics)
    already_repeated_today = sum(t.get("repeated_today", 0) for t in all_topics)
    total_workload_today = total_due_today + already_repeated_today

    # Strict rank order: Vortag newly learned first, then urgency_score descending, then avg_overdue_days
    today_candidates = [t for t in all_topics if t.get("due_today", 0) > 0]
    today_candidates.sort(
        key=lambda x: (
            x.get("is_vortag_new", False),
            x.get("urgency_score", 0.0),
            x.get("avg_overdue_days", 0.0),
            x.get("due_today", 0),
        ),
        reverse=True,
    )

    completed_today_list = [
        {
            "themenblock": t["themenblock"],
            "dozent": t["dozent"],
            "deck_name": t["deck_name"],
            "repeated_today": t.get("repeated_today", 0),
            "due_remaining": t.get("due_today", 0),
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
    leftover_queue = []  # tuples of (topic_dict, remaining_due_cards)

    for idx, t in enumerate(today_candidates):
        due_cnt = t.get("due_today", 0)
        if due_cnt <= 0:
            continue

        if accumulated < packing_target:
            room_left = packing_target - accumulated
            if due_cnt <= room_left:
                assigned = due_cnt
                is_partial = False
                rem_after = 0
            else:
                assigned = room_left
                is_partial = True
                rem_after = due_cnt - assigned

            plan_entry = dict(t)
            plan_entry["rank"] = len(selected) + 1
            plan_entry["assigned_cards"] = assigned
            plan_entry["is_partial"] = is_partial
            plan_entry["deferred_from_deck"] = rem_after
            if is_partial:
                plan_entry["focus_instruction"] = f"Davon {assigned} von {due_cnt} Karten machen (Rest {rem_after} automatisch auf morgen verschoben)"
            else:
                plan_entry["focus_instruction"] = f"Komplett wiederholen ({assigned} Karten)"

            selected.append(plan_entry)
            if remaining_budget_for_today > 0:
                focus_plan_open.append(plan_entry)
            accumulated += assigned

            if rem_after > 0:
                leftover_queue.append((t, rem_after))
        else:
            leftover_queue.append((t, due_cnt))

    # If today had fewer due cards than packing_target, optionally include tomorrow's due cards
    if accumulated < packing_target and total_due_today == 0:
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

    # Build multi-day proportional rollover schedule for all remaining cards
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
                "total_due_in_deck": topic_obj["due_today"],
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
    deferred_cards_count = max(0, total_due_today - len(focus_plan_open) and (total_due_today - sum(x["assigned_cards"] for x in focus_plan_open)))
    if remaining_budget_for_today > 0:
        deferred_cards_count = max(0, total_due_today - sum(x["assigned_cards"] for x in focus_plan_open))
    else:
        deferred_cards_count = total_due_today

    days_to_clear_backlog = math.ceil(total_due_today / max(1, budget)) if total_due_today > 0 else 0

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

    if total_due_today > budget:
        result["summary_advice"] = (
            f"🎯 Prozentuale Tages-Anpassung aktiv: Du machst heute gezielt {effective_today_target} von {total_workload_today} fälligen Karten ({coverage_pct}%). "
            f"Die übrigen {deferred_cards_count} Karten ({round(100.0 - coverage_pct, 1)}%) werden automatisch auf die nächsten {len(multi_day_rollover)} Tage verschoben!"
        )
    elif total_due_today > 0:
        result["summary_advice"] = (
            f"✅ Alle {total_due_today} fälligen Karten passen heute komplett in dein {budget}er Fokus-Budget (100% Abdeckung)."
        )
    else:
        result["summary_advice"] = (
            "🎉 Hervorragend: Aktuell keine offenen Wiederholungen für heute!"
        )

    if selected:
        clauses = []
        for t in selected:
            clauses.append(f'deck:"*2. SJ*{t["themenblock"]}*{t["dozent"]}*"')
        result["budget_combined_anki_query"] = f'({" or ".join(clauses)}) is:due'
    else:
        result["budget_combined_anki_query"] = "is:due"


import math


def cache_triage(data: Dict[str, Any]):
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
    # 1. Try DB first
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS anki_backlog_triage_cache (id INTEGER PRIMARY KEY CHECK (id = 1), data_json TEXT NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
            row = cur.execute("SELECT data_json FROM anki_backlog_triage_cache WHERE id = 1").fetchone()
            if row and row[0]:
                return json.loads(row[0])
    except Exception:
        pass

    # 2. Fall back to JSON snapshot file
    try:
        if BACKLOG_TRIAGE_SNAPSHOT_PATH.exists():
            content = BACKLOG_TRIAGE_SNAPSHOT_PATH.read_text(encoding="utf-8")
            if content.strip():
                return json.loads(content)
    except Exception:
        pass

    return None
