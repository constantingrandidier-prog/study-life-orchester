import os
import json
import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.services.anki_desktop_sync import find_local_anki_collection, clean_deck_name
from app.db.repository import get_db_connection

BACKLOG_TRIAGE_SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "cached_backlog_triage.json"

import re

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


def calculate_backlog_triage(col_path=None, max_capacity: Optional[int] = 300) -> Dict[str, Any]:
    """
    Calculates intelligent workload triage aggregated at Themenblock and Dozent/Prof level.
    Evaluates:
      a) Days since last review (recency/decay risk)
      b) Deck mastery & stability (average ease & total lapses)
      c) Semester retention rate (% correct recalls)
    Provides a curated 300-card priority budget for maximum efficiency without wasting time on mastered cards.
    """
    target_path = Path(col_path) if col_path else find_local_anki_collection()
    now = datetime.now()

    is_cloud = (os.environ.get("APPDATA") is None)
    if is_cloud or not target_path or not target_path.exists():
        cached = get_cached_triage()
        if cached:
            if max_capacity:
                cached["max_capacity"] = max_capacity
                _apply_budget(cached, max_capacity)
            return cached
        if not target_path or not target_path.exists():
            return {
                "connected": False,
                "total_due_today": 0,
                "total_due_tomorrow": 0,
                "is_overloaded": False,
                "themenbloecke": [],
                "topics": [],
                "urgent_topics": [],
                "deferrable_topics": [],
                "summary_advice": "Keine Anki-Datenbank gefunden.",
            }

    from app.db.anki_db import open_anki_db_readonly
    with open_anki_db_readonly(target_path) as conn:
        cur = conn.cursor()

        crt = cur.execute("SELECT crt FROM col").fetchone()[0]
        current_day = int((now.timestamp() - crt) // 86400)
        next_day = current_day + 1
        now_ms = now.timestamp() * 1000

        raw_decks = cur.execute("SELECT id, name FROM decks").fetchall()
        deck_map = {}
        for did, dname in raw_decks:
            tb, prof = parse_curriculum_deck(dname)
            if tb:
                deck_map[did] = (tb, prof, clean_deck_name(dname))

        if not deck_map:
            return {
                "connected": True,
                "total_due_today": 0,
                "total_due_tomorrow": 0,
                "is_overloaded": False,
                "themenbloecke": [],
                "topics": [],
                "urgent_topics": [],
                "deferrable_topics": [],
                "summary_advice": "Keine relevanten 2. SJ Decks gefunden.",
            }

        placeholders = ','.join('?' * len(deck_map))
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
            SUM(c.reps) as total_reps
        FROM cards c
        WHERE c.did IN ({placeholders}) AND c.queue != -1
        GROUP BY c.did
        """
        cards_stats = cur.execute(sql_cards, [current_day, current_day, next_day, next_day] + dids).fetchall()

        sem_start_ts = int(datetime(2026, 9, 14, 0, 0, 0).timestamp() * 1000)
        sql_revs = f"""
        SELECT c.did, MAX(r.id) as last_ms, COUNT(*) as total_revs,
               SUM(CASE WHEN r.ease = 1 THEN 1 ELSE 0 END) as fail_count
        FROM revlog r
        JOIN cards c ON r.cid = c.id
        WHERE c.did IN ({placeholders}) AND r.id >= ? AND r.type != 4 AND r.ease in (1, 2, 3, 4)
        GROUP BY c.did
        """
        rev_stats = {r[0]: {"last_ms": r[1], "revs": r[2], "fails": r[3]} for r in cur.execute(sql_revs, dids + [sem_start_ts]).fetchall()}

    from collections import defaultdict
    prof_groups = defaultdict(lambda: {
        "total_cards": 0, "due_today": 0, "due_tomorrow": 0, "active_reviews": 0,
        "sum_factor": 0, "count_factor": 0, "total_lapses": 0, "total_reps": 0,
        "last_ms": 0, "total_revs": 0, "fail_count": 0, "dids": [], "deck_names": []
    })

    for r in cards_stats:
        did, total, due_now, due_tom, active, s_fac, c_fac, lapses, reps = r
        tb, prof, orig_name = deck_map[did]
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
        g["dids"].append(did)
        g["deck_names"].append(orig_name)

        r_info = rev_stats.get(did, {"last_ms": 0, "revs": 0, "fails": 0})
        if r_info["last_ms"] > g["last_ms"]:
            g["last_ms"] = r_info["last_ms"]
        g["total_revs"] += r_info["revs"]
        g["fail_count"] += r_info["fails"]

    topics = []
    total_due_today = 0
    total_due_tomorrow = 0

    for (tb, prof), g in prof_groups.items():
        if g["active_reviews"] == 0 and g["due_today"] == 0 and g["due_tomorrow"] == 0 and g["total_revs"] == 0:
            topics.append({
                "themenblock": tb,
                "dozent": prof,
                "deck_name": f"{tb} › {prof}",
                "total_cards": g["total_cards"],
                "due_today": 0,
                "due_tomorrow": 0,
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
        days_ago = round((now_ms - last_ms) / (86400 * 1000), 1) if last_ms > 0 else 999.0
        avg_ease_pct = round(g["sum_factor"] / g["count_factor"] / 10, 1) if g["count_factor"] > 0 else 250.0
        fail_rate = round((g["fail_count"] / g["total_revs"] * 100) if g["total_revs"] > 0 else 0.0, 1)
        retention_rate = round(100.0 - fail_rate, 1) if g["total_revs"] > 0 else 100.0

        # Scientific 4-pillar scoring formula:
        # User note: "der zeitpunkt ist fast schon der wichtigste faktor... weil wenn ich etwas lang nicht mehr gesehen habe werde ich es nicht so gut können"
        # 1. Recency penalty (0-45 points):
        # Starker Anstieg: nach 5 Tagen schon 25 Pkt, nach 10 Tagen 40 Pkt, ab 14 Tagen volle 45 Pkt
        if days_ago < 900:
            time_score = min(45.0, (days_ago / 12.0) * 45.0)
        else:
            time_score = 25.0 if g["active_reviews"] > 0 else 0.0

        # 2. Retention / Fail score (0-30 points):
        # 35% fail rate erreicht Maximum von 30 Punkten
        fail_score = min(30.0, (fail_rate / 35.0) * 30.0)

        # 3. Ease / stability penalty (0-15 points):
        # 250% ease = 0 pts; <= 210% ease = 15 pts (struggle cards)
        ease_penalty = min(15.0, max(0.0, (250.0 - avg_ease_pct) / 40.0 * 15.0))

        # 4. Due volume bonus (0-10 points):
        # Belohnt das Abarbeiten aufgelaufener Stapel
        volume_score = min(10.0, (max(g["due_today"], g["due_tomorrow"]) / 40.0) * 10.0)

        urgency_score = round(time_score + fail_score + ease_penalty + volume_score, 1)

        # Classification badges & actions
        if g["due_today"] > 0 and (urgency_score >= 42.0 or fail_rate >= 35.0 or days_ago >= 10.0):
            urgency_level = "KRITISCH"
            level_badge = "🚨 Höchste Priorität"
            color = "#f85149"
            action = "Sofort wiederholen: Lange nicht gesehen oder hohes Vergessensrisiko!"
        elif g["due_today"] > 0 or urgency_score >= 26.0:
            urgency_level = "HOCH"
            level_badge = "⚠️ Wiederholen"
            color = "#d29922"
            action = "Sollte heute im Repetitions-Fokus wiederholt werden."
        else:
            urgency_level = "STABIL"
            level_badge = "✅ Stabil"
            color = "#3fb950"
            action = "Kürzlich wiederholt & gut beherrscht. Kann warten."

        deck_display_name = f"{tb} › {prof}"
        # Build clean query targeting this professor's decks
        # If multiple subdecks, use wildcard or specific deck clauses
        anki_filter_query = f'deck:"*2. SJ*{tb}*{prof}*" is:due'
        anki_hard_query = f'deck:"*2. SJ*{tb}*{prof}*" is:due (prop:ease<2.3 or lapses>1)'

        topics.append({
            "themenblock": tb,
            "dozent": prof,
            "deck_name": deck_display_name,
            "total_cards": g["total_cards"],
            "due_today": g["due_today"],
            "due_tomorrow": g["due_tomorrow"],
            "active_reviews": g["active_reviews"],
            "days_since_last_review": days_ago if days_ago < 900 else None,
            "days_since_last_review_str": f"{days_ago}d" if days_ago < 900 else "Neu / nie",
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

    # Sort topics overall by urgency score descending
    topics.sort(key=lambda x: (x["due_today"] > 0, x["urgency_score"]), reverse=True)

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
            "professors": sorted(prof_list, key=lambda x: x["urgency_score"], reverse=True),
        })

    themenbloecke.sort(key=lambda x: (x["total_due_today"], max([p["urgency_score"] for p in x["professors"]] or [0])), reverse=True)

    urgent_topics = [t for t in topics if t["urgency_level"] in ("KRITISCH", "HOCH")]
    deferrable_topics = [t for t in topics if t["urgency_level"] == "STABIL"]

    is_overloaded = (total_due_today >= 500 or total_due_tomorrow >= 500)

    # Generate combined filter query for top urgent decks
    top_urgent = [t for t in topics if t["due_today"] > 0][:4] or topics[:3]
    if top_urgent:
        clauses = " or ".join([f'deck:"*2. SJ*{t["themenblock"]}*{t["dozent"]}*"' for t in top_urgent])
        urgent_combined_anki_query = f'({clauses}) is:due'
    else:
        urgent_combined_anki_query = "is:due"

    if total_due_today >= 500:
        summary_advice = f"🚨 Hohe Wiederholungslast: Heute {total_due_today} fällige Karten! Konzentriere dich strikt auf die {len(urgent_topics)} rot/orange markierten Dozenten-Decks im 300-Karten-Fokus."
    elif total_due_today > 0:
        summary_advice = f"Aktuell {total_due_today} Wiederholungen heute fällig. Priorisiere nach Fehlerquote und Tagen seit der letzten Wiederholung."
    else:
        summary_advice = "Hervorragend: Aktuell keine überfälligen Wiederholungen. Nutze den Tag für neue Vorlesungs-Karten oder morgen anstehende Repetitionen."

    result = {
        "connected": True,
        "timestamp": now.isoformat(),
        "total_due_today": total_due_today,
        "total_due_tomorrow": total_due_tomorrow,
        "is_overloaded": is_overloaded,
        "themenbloecke_count": len(themenbloecke),
        "themenbloecke": themenbloecke,
        "topics_count": len(topics),
        "topics": topics,
        "urgent_topics": urgent_topics,
        "deferrable_topics": deferrable_topics,
        "urgent_combined_anki_query": urgent_combined_anki_query,
        "summary_advice": summary_advice,
        "max_capacity": max_capacity or 300,
    }

    _apply_budget(result, max_capacity or 300)

    cache_triage(result)
    return result


def _apply_budget(result: Dict[str, Any], budget: int):
    """
    Greedy knapsack packing up to budget (e.g. 300 cards).
    Packs the most urgent decks with due cards today first.
    If today is complete or under budget, packs tomorrow's most urgent cards.
    """
    selected = []
    accumulated = 0
    deferred = []

    # Priority 1: Due cards today, sorted by urgency score descending
    today_candidates = [t for t in result.get("topics", []) if t.get("due_today", 0) > 0]
    today_candidates.sort(key=lambda x: x.get("urgency_score", 0), reverse=True)

    for t in today_candidates:
        needed = t.get("due_today", 0)
        if accumulated + needed <= budget or not selected:
            selected.append(t)
            accumulated += needed
        else:
            deferred.append(t)

    # Priority 2: If under budget, pack upcoming cards due tomorrow
    if accumulated < budget:
        tom_candidates = [t for t in result.get("topics", []) if t.get("due_tomorrow", 0) > 0 and t not in selected]
        tom_candidates.sort(key=lambda x: x.get("urgency_score", 0), reverse=True)

        for t in tom_candidates:
            needed = t.get("due_tomorrow", 0)
            if accumulated + needed <= budget or not selected:
                selected.append(t)
                accumulated += needed
            else:
                deferred.append(t)

    # Any remaining candidates
    for t in result.get("topics", []):
        if t not in selected and t not in deferred:
            deferred.append(t)

    result["budget_selected_topics"] = selected
    result["budget_deferred_topics"] = deferred
    result["budget_accumulated_cards"] = accumulated
    result["max_capacity"] = budget

    if selected:
        deck_clauses = " or ".join([f'deck:"*2. SJ*{t["themenblock"]}*{t["dozent"]}*"' for t in selected])
        result["budget_combined_anki_query"] = f'({deck_clauses}) is:due'
    else:
        result["budget_combined_anki_query"] = "is:due"

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

