"""
Service for Card-Level Deep Inspection, Micro-Yield Scoring, and Kprim Trap Detection.
Safely scans individual flashcards in local SQLite collection.anki2 or loads high-fidelity snapshot on Render.
"""

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.services.anki_desktop_sync import find_local_anki_collection
from app.services.uzh_exam_intelligence import match_professor_for_topic, calculate_uzh_exam_risk_score

CARD_YIELD_SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "cached_card_yield_stats.json"

# UZH High-Yield Medical & Clinical Syndrome Terms
HY_MEDICAL_TERMS = {
    "blutgerinnung", "hämostase", "thrombose", "faktor xa", "thrombin", "antithrombin",
    "heparin", "quick", "inr", "aptt", "thrombozyt", "von-willebrand", "fibrinogen",
    "astrup", "blutgasanalyse", "bicarbonat", "basenabweichung", "base excess",
    "azidose", "alkalose", "säure-base", "pco2", "po2", "henderson-hasselbalch",
    "hypoxie", "hif-1", "erythropoietin", "epo", "höhenanpassung", "sauerstoffbindung",
    "2,3-bpg", "hämoglobin", "bohr-effekt", "haldane-effekt", "zyanose",
    "herzentwicklung", "foramen ovale", "ductus arteriosus", "botalli", "shunts",
    "truncus arteriosus", "septum primum", "septum secundum", "herzfehler",
    "ekg", "repolarisation", "depolarisation", "sinusknoten", "av-knoten",
    "erregungsleitung", "lagetype", "arrhythmie", "aktionspotential", "refraktärzeit",
    "raas", "renin", "angiotensin", "aldosteron", "nephron", "glukagon", "insulin",
    "ketonkörper", "pfk-1", "pfk-2", "fructose-2,6-bisphosphat", "glykolyse",
    "glukoneogenese", "ags", "21-hydroxylase", "adrenogenitales syndrom", "cortisol",
    "acth", "katecholamin", "adrenalin", "noradrenalin", "pnmt", "phäochromozytom",
    "sglt2", "tubulärer transport", "diuretika", "schleifendiuretika", "furosemid",
    "immuntoleranz", "thymus", "negative selektion", "autoimmunität", "t-zell",
    "monoklonale antikörper", "somatische rekombination", "vdj", "mhc-i", "mhc-ii",
    "calcium", "phosphat", "parathormon", "calcitriol", "calcitonin", "schilddrüse",
    "t3", "t4", "tsh", "jodid", "peroxidase", "thyreoglobulin"
}

# UZH Confusable Exam Pairs (frequent point killers in Kprim)
CONFUSABLE_PAIRS = [
    {
        "pair": ("adenohypophyse", "neurohypophyse"),
        "trap": "Die Neurohypophyse produziert SELBST KEINE Hormone! Sie speichert nur ADH & Oxytocin aus dem Hypothalamus. Die Adenohypophyse synthetisiert 6 glandotrope/effektorische Hormone.",
        "warning": "Kprim-Falle: Prüfer schreiben oft 'Die Neurohypophyse synthetisiert ADH' -> FALSCH!"
    },
    {
        "pair": ("pfk-1", "pfk-2"),
        "trap": "PFK-1 ist das Schrittmacherenzym der Glykolyse (Fru-6-P -> Fru-1,6-BP). PFK-2 synthetisiert den allosterischen Aktivator Fructose-2,6-Bisphosphat unter Insulinstimulation!",
        "warning": "Kprim-Falle: Verwechslung von Schrittmacherenzym (PFK-1) und regulatorischem Enzym (PFK-2)."
    },
    {
        "pair": ("aldosteron", "adh"),
        "trap": "Aldosteron bewirkt Einbau von ENaC & Na+/K+-ATPasen (Wasser folgt osmotisch). ADH (Vasopressin) bewirkt Einbau von Aquaporin-2 (reine Wasserretention ohne primäre Natriumverschiebung!).",
        "warning": "Kprim-Falle: ADH senkt die Plasmaosmolarität, Aldosteron hält sie konstant."
    },
    {
        "pair": ("quick", "aptt"),
        "trap": "Quick / INR prüft das EXTRINSISCHE System (Faktor VII, Gewebefaktor). aPTT prüft das INTRINSISCHE System (Faktoren XII, XI, IX, VIII). Gemeinsame Endstrecke: X, V, II, I.",
        "warning": "Kprim-Falle: Cumarine/Marcoumar hemmen Vitamin-K-abhängige Faktoren (1972: X, IX, VII, II) -> Quick reagiert am schnellsten wegen kurzer HWZ von Faktor VII!"
    },
    {
        "pair": ("pneumozyt typ 1", "pneumozyt typ 2"),
        "trap": "Typ-1-Pneumozyten bedecken 95% der Alveolaroberfläche (Gasaustausch). Typ-2-Pneumozyten produzieren Surfactant (Dipalmitoylphosphatidylcholin) und teilen sich zur Regeneration!",
        "warning": "Kprim-Falle: Typ 2 ist metabolisch aktiv und Vorläuferzelle, nicht Typ 1."
    },
    {
        "pair": ("zona glomerulosa", "zona fasciculata"),
        "trap": "Glomerulosa (aussen): Aldosteron (reguliert durch Angiotensin II & K+, NICHT ACTH!). Fasciculata (mitte): Cortisol (reguliert durch ACTH). Reticularis (innen): Androgene (ACTH).",
        "warning": "Kprim-Falle: Aldosteron ist ACTH-unabhängig (wichtig bei Hypophyseninsuffizienz: Aldosteron bleibt intakt!)."
    },
    {
        "pair": ("bohr-effekt", "haldane-effekt"),
        "trap": "Bohr-Effekt: CO2 & H+ senken die O2-Affinität des Hämoglobins (Rechtsverschiebung im Gewebe). Haldane-Effekt: O2-Bindung senkt die CO2-Affinität (Freisetzung von CO2 in der Lunge).",
        "warning": "Kprim-Falle: Bohr beschreibt O2-Abgabe, Haldane beschreibt CO2-Aufnahme/Abgabe."
    },
]

# Negation and exclusivity triggers typical for trick questions
NEGATION_TRIGGERS = [
    r"\bausschliesslich\b", r"\bausschließlich\b", r"\bnie\b", r"\bnur\b",
    r"\bimmer\b", r"\bausnahmslos\b", r"\bkein\b", r"\bkeine\b", r"\bkeinerlei\b",
    r"\bnicht\b", r"\bausser\b", r"\baußer\b", r"\balle\b"
]

# Directional/causal regulators
DIRECTIONAL_TRIGGERS = [
    r"\bhemmt\b", r"\baktiviert\b", r"\breziprok\b", r"\berhöht\b", r"\bsenkt\b",
    r"\bdilatiert\b", r"\bkonstrihiert\b", r"\bfördert\b", r"\bunterdrückt\b",
    r"\binduziert\b", r"\bsteigert\b"
]


def clean_html_card_text(text: str) -> str:
    """Strips HTML tags, cloze brackets, non-breaking spaces and normalizes text."""
    if not text:
        return ""
    # Strip Anki Cloze {{c1::answer::hint}} -> answer
    text = re.sub(r"\{\{c\d+::(.*?)(?:::.*?)?\}\}", r"\1", text)
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Strip HTML entities
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    # Fix common UTF8 glitches
    reps = {
        "Einf\ufffdhrung": "Einführung",
        "Zellul\ufffdre": "Zelluläre",
        "Immunit\ufffdt": "Immunität",
        "Gef\ufffdss": "Gefäss",
        "Atmosph\ufffdre": "Atmosphäre",
        "H\ufffdmostase": "Hämostase",
    }
    for k, v in reps.items():
        text = text.replace(k, v)
    return " ".join(text.split()).strip()


def analyze_card_content(
    front: str,
    back: str = "",
    extra: str = "",
    deck_name: str = "",
    prof_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Deep content inspection of an individual Anki flashcard.
    Calculates yield score, Kprim risk, negation trap detection, and specific exam warnings.
    """
    full_text = f"{clean_html_card_text(front)} {clean_html_card_text(back)} {clean_html_card_text(extra)}".lower()
    front_clean = clean_html_card_text(front)
    back_clean = clean_html_card_text(back)

    # 1. Detect Confusable Pairs (highest Kprim trap density)
    confusable_match = None
    for cp in CONFUSABLE_PAIRS:
        term_a, term_b = cp["pair"]
        if term_a in full_text and term_b in full_text:
            confusable_match = cp
            break

    # 2. Detect Negation and Exclusivity Triggers
    negation_hits = []
    for pat in NEGATION_TRIGGERS:
        found = re.findall(pat, full_text)
        if found:
            negation_hits.extend(found)

    # 3. Detect Directional Regulation Triggers
    directional_hits = []
    for pat in DIRECTIONAL_TRIGGERS:
        found = re.findall(pat, full_text)
        if found:
            directional_hits.extend(found)

    # 4. Count High-Yield Medical Terms
    hy_hits = [t for t in HY_MEDICAL_TERMS if t in full_text]

    # Calculate Micro-Yield Score (0 - 100)
    base_yield = 40.0
    base_yield += min(45.0, len(hy_hits) * 9.0)
    if confusable_match:
        base_yield += 15.0
    if len(directional_hits) >= 2:
        base_yield += 10.0
    if prof_info and prof_info.get("uzh_importance", "").startswith("Sehr hoch"):
        base_yield += 10.0

    # Low-Yield penalties
    if any(k in full_text for k in ["versuch", "pipettieren", "photometer", "sds-page", "spurenelement"]):
        base_yield = max(15.0, base_yield - 35.0)
    if any(k in full_text for k in ["organisatorisch", "vorbesprechung", "semesterüberblick"]):
        base_yield = 5.0

    card_yield_score = min(100.0, round(base_yield, 1))

    # Kprim Trap Classification
    is_kprim_trap = False
    trap_type = "none"
    trap_label = "Standardkarte"
    trap_warning = None

    if confusable_match:
        is_kprim_trap = True
        trap_type = "confusable_pair"
        trap_label = f"Kprim-Verwechslungsfalle: {confusable_match['pair'][0].capitalize()} vs. {confusable_match['pair'][1].capitalize()}"
        trap_warning = confusable_match["warning"]
    elif len(negation_hits) >= 2 or (len(negation_hits) >= 1 and len(directional_hits) >= 1):
        is_kprim_trap = True
        trap_type = "negation_directional"
        trap_label = "Kprim-Logikfalle: Verneinung & Richtungswechsel"
        trap_warning = "Achtung bei Kprim: Formulierungen wie 'hemmt nicht' oder 'ausschliesslich' werden von UZH-Dozenten gerne für Fangentscheidungen genutzt."
    elif len(directional_hits) >= 2:
        is_kprim_trap = True
        trap_type = "causal_chain"
        trap_label = "Kprim-Kausalkette: Reziproke Regulation"
        trap_warning = "Prüfe genau: Welches Hormon/Enzym stimuliert und welches hemmt? Bei Kprim führen getauschte Pfeilrichtungen zu Punktverlust."
    elif card_yield_score >= 80.0:
        is_kprim_trap = True
        trap_type = "high_yield_core"
        trap_label = "Zentraler Klausur-Hotspot"
        trap_warning = "Klassischer Prüfungsstoff. Hier muss die Definition bis ins kleinste Detail sitzen."

    # Card Type Classification
    if is_kprim_trap:
        card_type = "kprim_mechanism"
    elif any(k in full_text for k in ["versuch", "labor", "pipette"]):
        card_type = "practical_lab"
    elif any(k in full_text for k in ["normwert", "grenzwert", "wert", "referenz", "mmhg", "g/dl"]):
        card_type = "reference_values"
    else:
        card_type = "type_a_fact"

    return {
        "card_yield_score": card_yield_score,
        "is_kprim_trap": is_kprim_trap,
        "trap_type": trap_type,
        "trap_label": trap_label,
        "trap_warning": trap_warning,
        "card_type": card_type,
        "hy_terms_detected": hy_hits[:6],
        "negation_count": len(negation_hits),
        "directional_count": len(directional_hits),
        "front_snippet": front_clean[:120],
        "back_snippet": back_clean[:140],
    }


def scan_all_cards_in_collection(col_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Scans all 9'600+ cards and notes in collection.anki2 with safe immutable connection.
    Builds deck-level Kprim summaries and the Top 25 UZH Exam Pitfall Cards.
    """
    target_path = Path(col_path) if col_path else find_local_anki_collection()

    # If no local collection exists (e.g. deployed on Render), load the snapshot
    if not target_path or not target_path.exists():
        if CARD_YIELD_SNAPSHOT_PATH.exists():
            try:
                with open(CARD_YIELD_SNAPSHOT_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "available": False,
            "total_cards_scanned": 0,
            "total_kprim_traps": 0,
            "top_25_todesfallen": [],
            "deck_kprim_stats": {},
            "message": "Keine Anki-Sammlung gefunden und kein Snapshot vorhanden."
        }

    uri = f"file:///{target_path.as_posix()}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    cur = conn.cursor()

    # 1. Fetch decks map
    decks_map = {}
    for did, dname in cur.execute("SELECT id, name FROM decks").fetchall():
        clean = dname.replace(chr(31), " :: ")
        clean = clean.replace("2. SJ - 1 :: ", "").replace("1year :: ", "").strip()
        decks_map[did] = clean

    # 2. Query all cards with their note fields
    sql = """
        SELECT c.id, c.nid, c.did, n.sfld, n.flds, c.reps, c.lapses, c.ivl, c.queue
        FROM cards c
        JOIN notes n ON c.nid = n.id
    """
    rows = cur.execute(sql).fetchall()
    conn.close()

    total_cards = len(rows)
    all_inspected_cards = []
    deck_card_stats: Dict[int, Dict[str, Any]] = {}

    for r in rows:
        cid, nid, did, sfld, flds_str, reps, lapses, ivl, queue = r
        dname = decks_map.get(did, "Unbekanntes Deck")

        parts = flds_str.split(chr(31))
        front = parts[0] if len(parts) > 0 else sfld
        back = parts[1] if len(parts) > 1 else ""
        extra = parts[2] if len(parts) > 2 else ""

        prof_info = match_professor_for_topic(dname, front, dname)
        analysis = analyze_card_content(front, back, extra, dname, prof_info)

        card_entry = {
            "card_id": cid,
            "note_id": nid,
            "deck_id": did,
            "deck_name": dname,
            "professor_name": prof_info["name"] if prof_info else "Dozententeam UZH",
            "professor_institute": prof_info["institute"] if prof_info else "Medizinische Fakultät UZH",
            "reps": reps,
            "lapses": lapses,
            "interval_days": ivl,
            "card_yield_score": analysis["card_yield_score"],
            "is_kprim_trap": analysis["is_kprim_trap"],
            "trap_type": analysis["trap_type"],
            "trap_label": analysis["trap_label"],
            "trap_warning": analysis["trap_warning"],
            "card_type": analysis["card_type"],
            "front_snippet": analysis["front_snippet"],
            "back_snippet": analysis["back_snippet"],
            "hy_terms_detected": analysis["hy_terms_detected"],
        }
        all_inspected_cards.append(card_entry)

        # Aggregate by deck
        if did not in deck_card_stats:
            deck_card_stats[did] = {
                "deck_id": did,
                "deck_name": dname,
                "total_cards": 0,
                "high_yield_cards_count": 0,
                "kprim_traps_count": 0,
                "confusable_pairs_count": 0,
                "avg_card_yield_score": 0.0,
                "sample_kprim_traps": [],
            }
        ds = deck_card_stats[did]
        ds["total_cards"] += 1
        if analysis["card_yield_score"] >= 70.0:
            ds["high_yield_cards_count"] += 1
        if analysis["is_kprim_trap"]:
            ds["kprim_traps_count"] += 1
            if len(ds["sample_kprim_traps"]) < 4:
                ds["sample_kprim_traps"].append(card_entry)
        if analysis["trap_type"] == "confusable_pair":
            ds["confusable_pairs_count"] += 1

    # Calculate deck averages
    for did, ds in deck_card_stats.items():
        deck_cards = [c for c in all_inspected_cards if c["deck_id"] == did]
        if deck_cards:
            ds["avg_card_yield_score"] = round(sum(c["card_yield_score"] for c in deck_cards) / len(deck_cards), 1)

    # Top 25 UZH Kprim-Todesfallen
    # Rank by: (is_kprim_trap True, card_yield_score descending, lapses descending)
    trap_cards = [c for c in all_inspected_cards if c["is_kprim_trap"]]
    trap_cards.sort(key=lambda c: (
        2 if c["trap_type"] == "confusable_pair" else (1 if c["trap_type"] == "negation_directional" else 0),
        c["card_yield_score"],
        c["lapses"]
    ), reverse=True)

    top_25_traps = trap_cards[:25]

    result = {
        "available": True,
        "total_cards_scanned": total_cards,
        "total_kprim_traps": len(trap_cards),
        "kprim_trap_percentage": round(len(trap_cards) / max(1, total_cards) * 100, 1),
        "top_25_todesfallen": top_25_traps,
        "deck_kprim_stats": {str(k): v for k, v in deck_card_stats.items()},
        "updated_at": Path(target_path).stat().st_mtime if target_path.exists() else 0,
    }

    # Save cache snapshot
    try:
        CARD_YIELD_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CARD_YIELD_SNAPSHOT_PATH, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return result


def get_card_yield_stats() -> Dict[str, Any]:
    """Reads card yield stats from local collection or fallback snapshot."""
    if CARD_YIELD_SNAPSHOT_PATH.exists():
        try:
            with open(CARD_YIELD_SNAPSHOT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return scan_all_cards_in_collection()
