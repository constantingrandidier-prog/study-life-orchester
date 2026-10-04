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
    """
    Computes weighted exam score simulation for one Modulprüfung.
    Realistic medical examination model:
    - Factors in curriculum coverage (how many cards were actually studied).
    - Unstudied material is evaluated at standard Type-A / Kprim guessing baseline (20.0%).
    - Studied material is evaluated at the student's actual retention rate.
    - Also calculates potential score (if 100% of material is studied at current retention).
    """
    topic_scores = []
    total_cards_exam = 0
    studied_cards_exam = 0
    total_predicted = 0.0
    total_potential = 0.0

    for top in exam_config["topics"]:
        from app.services.uzh_exam_intelligence import get_deck_exam_topic
        matched_decks = [
            d for d in all_decks
            if get_deck_exam_topic(d.get("anki_name") or "", d.get("parent_topic"))["topic_id"] == top["id"]
        ]

        total_cards = sum(d.get("card_count", 0) for d in matched_decks)
        studied_decks = [d for d in matched_decks if d.get("retention_rate") is not None and d.get("total_reviews", 0) > 0]
        studied_cards = sum(d.get("card_count", 0) for d in studied_decks)

        total_cards_exam += total_cards
        studied_cards_exam += studied_cards

        coverage_ratio = (studied_cards / total_cards) if total_cards > 0 else 0.0
        coverage_pct = round(coverage_ratio * 100.0, 1)

        if studied_cards > 0:
            ret_studied = sum(float(d["retention_rate"]) * d.get("card_count", 0) for d in studied_decks) / studied_cards
        else:
            ret_studied = 0.0

        # Realistic expected score:
        # Studied part: coverage_ratio * ret_studied
        # Unstudied part: (1.0 - coverage_ratio) * 20.0 (guessing baseline on MC/Kprim)
        real_score = (coverage_ratio * ret_studied) + ((1.0 - coverage_ratio) * 20.0) if total_cards > 0 else 20.0
        potential_score = ret_studied if studied_cards > 0 else 80.0

        real_score = round(real_score, 1)
        potential_score = round(potential_score, 1)
        contribution = round(real_score * top["weight"], 1)
        total_predicted += contribution
        total_potential += round(potential_score * top["weight"], 1)

        # Status of this topic
        if real_score >= 60.0:
            top_status = "safe"
            top_color = "#3fb950"
        elif coverage_pct > 0.0:
            top_status = "in_progress"
            top_color = "#d29922" if real_score >= 35.0 else "#ff7b72"
        else:
            top_status = "unstarted"
            top_color = "#8b949e"

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
            "total_cards": total_cards,
            "studied_cards": studied_cards,
            "coverage_pct": coverage_pct,
            "retention_rate": round(ret_studied, 1),
            "real_score": real_score,
            "potential_score": potential_score,
            "contribution_points": contribution,
            "status": top_status,
            "status_color": top_color,
            "matched_decks_count": len(matched_decks),
            "weakest_deck": top_weakest_deck,
        })

    predicted_score = round(total_predicted, 1)
    potential_score = round(total_potential, 1)
    exam_coverage_pct = round((studied_cards_exam / total_cards_exam * 100.0) if total_cards_exam > 0 else 0.0, 1)
    cutoff = exam_config["angoff_cutoff"]
    safety_target = exam_config["safety_target"]
    safety_margin = round(predicted_score - cutoff, 1)

    if studied_cards_exam == 0:
        pass_status = "unstarted"
        status_label = "⚪ Noch unberührt (0% gelernt)"
        status_color = "#8b949e"
    elif predicted_score >= safety_target:
        pass_status = "safe_pass"
        status_label = "✅ Sicherer Bestehensbereich (Solider Puffer)"
        status_color = "#3fb950"
    elif predicted_score >= cutoff:
        pass_status = "borderline_pass"
        status_label = "⚠️ Knapp im Bestehensbereich (Gefahr bei Kprim-Fallen!)"
        status_color = "#d29922"
    else:
        pass_status = "in_progress"
        status_label = f"⏳ In Erarbeitung ({exam_coverage_pct}% Stoff gelernt)"
        status_color = "#ff7b72"

    return {
        "exam_name": exam_config["name"],
        "date": exam_config["date"],
        "ects": exam_config["ects"],
        "duration_min": exam_config["duration_min"],
        "angoff_cutoff": cutoff,
        "safety_target": safety_target,
        "predicted_score": predicted_score,
        "potential_score": potential_score,
        "coverage_pct": exam_coverage_pct,
        "studied_cards": studied_cards_exam,
        "total_cards": total_cards_exam,
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
