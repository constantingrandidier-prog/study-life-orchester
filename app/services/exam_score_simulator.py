"""
Service for simulating UZH Modulprüfung 1 & 2 exam scores based on active Anki retention.
Applies official faculty weights, ECTS scaling, and the 60% Angoff pass threshold.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.services.anki_deck_stats import get_detailed_deck_stats

EXAM_SIMULATOR_SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "cached_exam_simulation.json"

# Official UZH Examination Structure & Topic Weights
MP1_CONFIG = {
    "name": "Modulprüfung 1 (Theorie)",
    "date": "Dienstag, 19. Januar 2027",
    "ects": 14,
    "duration_min": 150,
    "angoff_cutoff": 60.0,
    "safety_target": 75.0,
    "topics": [
        {
            "id": "blut_immun",
            "name": "1. Blut & Immunsystem",
            "weight": 0.28,
            "keywords": ["blut", "immun", "hämat", "gerinnung", "manatschal", "tuzlak", "stockmann"],
        },
        {
            "id": "herz_kreislauf",
            "name": "2. Herz-Kreislauf",
            "weight": 0.42,
            "keywords": ["herz", "kreislauf", "ekg", "sommer", "kurtcuoglu", "gefäss"],
        },
        {
            "id": "atmung",
            "name": "3. Atmung & Lunge",
            "weight": 0.30,
            "keywords": ["atmung", "lunge", "wenger", "hypoxie", "respir", "asthma"],
        },
    ],
}

MP2_CONFIG = {
    "name": "Modulprüfung 2 (Theorie)",
    "date": "Donnerstag, 21. Januar 2027",
    "ects": 16,
    "duration_min": 150,
    "angoff_cutoff": 60.0,
    "safety_target": 75.0,
    "topics": [
        {
            "id": "verdauung",
            "name": "4. Verdauung",
            "weight": 0.32,
            "keywords": ["verdauung", "magen", "darm", "leber", "pankreas", "wagner", "gastro"],
        },
        {
            "id": "stoffwechsel",
            "name": "5. Stoffwechsel",
            "weight": 0.34,
            "keywords": ["stoffwechsel", "emmert", "glykol", "insulin", "glukagon", "biochemie"],
        },
        {
            "id": "endokrinologie",
            "name": "6. Endokrinologie",
            "weight": 0.34,
            "keywords": ["endokrin", "hormon", "hall", "sokolowska", "steroid", "neben", "ags"],
        },
    ],
}


def compute_exam_simulation(exam_config: Dict[str, Any], all_decks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes weighted exam score simulation for one Modulprüfung."""
    topic_scores = []
    total_predicted = 0.0

    for top in exam_config["topics"]:
        kws = top["keywords"]
        matched_decks = [
            d for d in all_decks
            if any(k in (d.get("anki_name") or "").lower() for k in kws)
            or any(k in (d.get("parent_topic") or "").lower() for k in kws)
        ]

        # Calculate weighted retention for this topic
        studied_decks = [d for d in matched_decks if d.get("retention_rate") is not None and d.get("total_reviews", 0) > 0]
        if studied_decks:
            # Weighted by card count
            total_cards = sum(d.get("card_count", 0) for d in studied_decks)
            if total_cards > 0:
                topic_ret = sum(float(d["retention_rate"]) * d.get("card_count", 0) for d in studied_decks) / total_cards
            else:
                topic_ret = sum(float(d["retention_rate"]) for d in studied_decks) / len(studied_decks)
        else:
            # Baseline expectation for unreviewed decks under Angoff guessing baseline
            topic_ret = 48.0

        topic_ret = round(topic_ret, 1)
        contribution = round(topic_ret * top["weight"], 1)
        total_predicted += contribution

        # Status of this topic
        if topic_ret >= 80.0:
            top_status = "safe"
            top_color = "#3fb950"
        elif topic_ret >= 65.0:
            top_status = "moderate"
            top_color = "#d29922"
        else:
            top_status = "critical"
            top_color = "#ff7b72"

        # Find weakest high-yield deck in this topic
        hy_weak = [
            d for d in matched_decks
            if d.get("yield_level") == "high"
        ]
        hy_weak.sort(key=lambda d: float(d.get("retention_rate") or 0.0))
        top_weakest_deck = hy_weak[0]["anki_name"] if hy_weak else (matched_decks[0]["anki_name"] if matched_decks else None)

        topic_scores.append({
            "topic_id": top["id"],
            "topic_name": top["name"],
            "weight_pct": int(top["weight"] * 100),
            "retention_rate": topic_ret,
            "contribution_points": contribution,
            "status": top_status,
            "status_color": top_color,
            "matched_decks_count": len(matched_decks),
            "weakest_deck": top_weakest_deck,
        })

    predicted_score = round(total_predicted, 1)
    cutoff = exam_config["angoff_cutoff"]
    safety_target = exam_config["safety_target"]
    safety_margin = round(predicted_score - cutoff, 1)

    if predicted_score >= safety_target:
        pass_status = "safe_pass"
        status_label = "✅ Sicherer Bestehensbereich (Solider Puffer)"
        status_color = "#3fb950"
    elif predicted_score >= cutoff:
        pass_status = "borderline_pass"
        status_label = "⚠️ Knapp im Bestehensbereich (Gefahr bei Kprim-Fallen!)"
        status_color = "#d29922"
    else:
        pass_status = "fail_risk"
        status_label = "🚨 Unter der Bestehensgrenze (Sofortiger Fokus nötig!)"
        status_color = "#ff7b72"

    return {
        "exam_name": exam_config["name"],
        "date": exam_config["date"],
        "ects": exam_config["ects"],
        "duration_min": exam_config["duration_min"],
        "angoff_cutoff": cutoff,
        "safety_target": safety_target,
        "predicted_score": predicted_score,
        "safety_margin": safety_margin,
        "safety_margin_text": f"+{safety_margin}% Puffer" if safety_margin >= 0 else f"{safety_margin}% Lücke",
        "pass_status": pass_status,
        "status_label": status_label,
        "status_color": status_color,
        "topic_breakdown": topic_scores,
    }


def get_full_exam_simulation() -> Dict[str, Any]:
    """Computes live exam simulation for both Modulprüfung 1 and Modulprüfung 2."""
    deck_stats = get_detailed_deck_stats()
    all_decks = deck_stats.get("all_decks", [])

    mp1_res = compute_exam_simulation(MP1_CONFIG, all_decks)
    mp2_res = compute_exam_simulation(MP2_CONFIG, all_decks)

    # Combined overall readiness
    avg_predicted = round((mp1_res["predicted_score"] + mp2_res["predicted_score"]) / 2.0, 1)
    overall_safe = (mp1_res["pass_status"] == "safe_pass" and mp2_res["pass_status"] == "safe_pass")

    result = {
        "available": True,
        "average_predicted_score": avg_predicted,
        "overall_safe": overall_safe,
        "modulpruefung_1": mp1_res,
        "modulpruefung_2": mp2_res,
        "total_ects": 30,
        "summary_recommendation": (
            "Beide Modulprüfungen liegen im sicheren Pufferbereich."
            if overall_safe else
            f"Fokus auf die schwächere Modulprüfung legen (MP1: {mp1_res['predicted_score']}% vs MP2: {mp2_res['predicted_score']}%)."
        ),
    }

    # Save cache snapshot
    try:
        EXAM_SIMULATOR_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(EXAM_SIMULATOR_SNAPSHOT_PATH, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return result
