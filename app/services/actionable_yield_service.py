"""
Service for calculating the Student's Personal Actionable Yield Index (Lern-ROI).
Identifies exactly where studying today gains the most points in UZH Modulprüfung 1 & 2.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.services.anki_deck_stats import get_detailed_deck_stats
from app.services.card_yield_engine import get_card_yield_stats

ACTIONABLE_YIELD_SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "cached_actionable_yield.json"


def calculate_actionable_deck_roi(
    deck: Dict[str, Any],
    kprim_traps_count: int = 0,
) -> Dict[str, Any]:
    """
    Calculates the exact Return on Investment (ROI) for studying a specific deck.
    Considers objective faculty importance, student's personal retention gap,
    Kprim trap density, and recency of review.
    """
    y_lvl = deck.get("yield_level")
    if not y_lvl:
        from app.services.uzh_exam_intelligence import classify_deck_yield
        y_lvl = classify_deck_yield(deck.get("anki_name", ""))["yield_level"]
    weight_map = {
        "high": 3.2,
        "medium": 1.7,
        "low": 0.5,
        "none": 0.05,
    }
    obj_weight = weight_map.get(y_lvl, 1.5)

    ret = deck.get("retention_rate")
    total_revs = deck.get("total_reviews", 0)

    # Calculate knowledge gap against safe 80% threshold
    if ret is None or total_revs == 0:
        ret_gap = 35.0  # unstudied deck represents moderate initial gap
        effective_ret = 0.0
    else:
        effective_ret = float(ret)
        ret_gap = max(0.0, 80.0 - effective_ret)

    # Kprim trap multiplier (traps destroy points under 3/4 = 0.5 Pkt rule)
    kprim_factor = 1.0 + (min(6, kprim_traps_count) * 0.12)

    # Recency decay penalty
    days_ago = deck.get("last_reviewed_days_ago")
    recency_mult = 1.0
    if days_ago is not None:
        if days_ago >= 14.0:
            recency_mult = 1.45
        elif days_ago >= 7.0:
            recency_mult = 1.25

    # Volume factor
    card_count = deck.get("card_count", 0)
    vol_factor = min(2.2, 0.6 + (card_count / 80.0))

    # Calculate raw ROI score
    raw_score = (obj_weight * (ret_gap + 5.0) * kprim_factor * recency_mult * vol_factor) / 4.2
    roi_score = min(100.0, max(0.0, round(raw_score, 1)))

    # Urgency & Status
    if y_lvl == "none":
        urgency = "none"
        urgency_label = "Keine Priorität (Reine Orga)"
        urgency_color = "#8b949e"
    elif roi_score >= 65.0:
        urgency = "critical_gap"
        urgency_label = "🚨 Höchster Punkte-Hebel (Sofort schließen!)"
        urgency_color = "#ff7b72"
    elif roi_score >= 40.0:
        urgency = "high_roi"
        urgency_label = "🔥 Hoher Klausur-ROI"
        urgency_color = "#d29922"
    elif roi_score >= 20.0:
        urgency = "medium_roi"
        urgency_label = "🟡 Reguläre Vertiefung"
        urgency_color = "#e3b341"
    else:
        urgency = "mastered"
        urgency_label = "✅ Stoff sitzt solide (Punkte gesichert)"
        urgency_color = "#3fb950"

    # Actionable advice
    if y_lvl == "high" and effective_ret < 70.0 and total_revs > 0:
        advice = f"Retention liegt bei nur {effective_ret:.1f}%. Bei Kprim droht Punktverlust. Heute 15 Min investieren!"
    elif total_revs == 0 and y_lvl == "high":
        advice = "Noch unberührtes High-Yield Deck. Erste Durcharbeitung bringt maximalen Klausurzuwachs."
    elif days_ago and days_ago > 10.0 and y_lvl in ["high", "medium"]:
        advice = f"Zuletzt vor {int(days_ago)} Tagen aktiv. Vergessenskurve abfangen, bevor Retention sinkt."
    elif effective_ret >= 80.0:
        advice = "Aktuell sicher über der Angoff-Bestehensgrenze. Keine zusätzliche Sonderzeit nötig."
    else:
        advice = "Im Standard-Rhythmus wiederholen."

    # Determine which exam this deck belongs to
    d_name_low = (deck.get("anki_name") or "").lower()
    p_topic_low = (deck.get("parent_topic") or "").lower()
    combined = d_name_low + " " + p_topic_low
    if any(k in combined for k in ["blut", "immun", "herz", "kreislauf", "atmung", "lunge"]):
        target_exam = "Modulprüfung 1 (Theorie)"
    else:
        target_exam = "Modulprüfung 2 (Theorie)"

    return {
        "deck_id": deck.get("deck_id"),
        "anki_name": deck.get("anki_name"),
        "parent_topic": deck.get("parent_topic"),
        "professor_name": deck.get("professor_name", "Dozententeam UZH"),
        "yield_level": y_lvl,
        "yield_badge": deck.get("yield_badge", "🟡 Medium-Yield"),
        "card_count": card_count,
        "due_count": deck.get("due_count", 0),
        "retention_rate": ret,
        "retention_gap": round(ret_gap, 1),
        "kprim_traps_count": kprim_traps_count,
        "last_reviewed_days_ago": days_ago,
        "roi_score": roi_score,
        "urgency": urgency,
        "urgency_label": urgency_label,
        "urgency_color": urgency_color,
        "actionable_advice": advice,
        "target_exam": target_exam,
    }


def get_ranked_actionable_yield_list() -> Dict[str, Any]:
    """
    Ranks all 120 decks by personal study ROI.
    Returns the Top 10 High-Yield Knowledge Gaps and overall ranking.
    """
    # Try snapshot fallback first if on cloud Render
    is_cloud = os.environ.get("APPDATA") is None

    deck_stats = get_detailed_deck_stats()
    all_decks = deck_stats.get("all_decks", [])

    card_stats = get_card_yield_stats()
    deck_kprim_map = card_stats.get("deck_kprim_stats", {})

    ranked_items = []
    for d in all_decks:
        did = str(d.get("deck_id", ""))
        kprim_count = deck_kprim_map.get(did, {}).get("kprim_traps_count", 0)
        roi_meta = calculate_actionable_deck_roi(d, kprim_traps_count=kprim_count)
        ranked_items.append(roi_meta)

    # Sort strictly by ROI score descending
    ranked_items.sort(key=lambda x: x["roi_score"], reverse=True)

    # Filter top actionable priorities (exclude No-Yield)
    top_actionable = [d for d in ranked_items if d["yield_level"] != "none"][:10]

    result = {
        "available": True,
        "total_decks_evaluated": len(ranked_items),
        "top_10_leverage_decks": top_actionable,
        "all_ranked_decks": ranked_items,
        "high_gap_count": len([d for d in ranked_items if d["urgency"] == "critical_gap"]),
        "safe_count": len([d for d in ranked_items if d["urgency"] == "mastered"]),
    }

    # Save cache snapshot
    try:
        ACTIONABLE_YIELD_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(ACTIONABLE_YIELD_SNAPSHOT_PATH, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return result
