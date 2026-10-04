"""
Service for matching UZH Lecture Slides (from OpenOLAT / VAM / OneDrive)
to Anki topics, decks, and professor exam preferences.
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.services.olat_connector import scan_local_uzh_slides
from app.services.uzh_exam_intelligence import UZH_PROFESSORS, match_professor_for_topic

SLIDE_MATCH_SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "cached_slide_matches.json"

# High-priority lecture emphasis signals used by UZH professors
EMPHASIS_FLAGS = [
    r"\bcave\b", r"\bklausurrelevant\b", r"\bprüfungsrelevant\b", r"\bprüfungsstoff\b",
    r"\bkprim\b", r"\bmerke\b", r"\bwichtig\b", r"\bprüfungsbeispiel\b",
    r"\bschema\b", r"\breferenzbereich\b", r"\bformel\b"
]


def extract_lecture_metadata(filename: str, path_str: str) -> Dict[str, Any]:
    """Extracts topic, professor, and lecture number from slide PDF name and path."""
    clean_fn = filename.lower().replace(".pdf", "")
    full = (path_str + " " + filename).lower()

    # Determine topic cluster
    cluster = "Allgemein"
    if any(k in full for k in ["blut", "immun", "hämat", "thromb", "gerinnung"]):
        cluster = "TB Blut & Immunsystem"
    elif any(k in full for k in ["herz", "kreislauf", "ekg", "gefäss", "kardio"]):
        cluster = "TB Herz-Kreislauf"
    elif any(k in full for k in ["atmung", "lunge", "ventil", "sauerstoff", "respir"]):
        cluster = "TB Atmung"
    elif any(k in full for k in ["verdauung", "magen", "darm", "leber", "pankreas", "gastro"]):
        cluster = "TB Verdauung"
    elif any(k in full for k in ["stoffwechsel", "glykol", "insulin", "biochem"]):
        cluster = "TB Stoffwechsel"
    elif any(k in full for k in ["endokrin", "hormon", "hypophys", "steroid", "neben"]):
        cluster = "TB Endokrinologie"
    elif any(k in full for k in ["niere", "renin", "tubul"]):
        cluster = "TB Niere"

    # Professor match
    matched_prof = None
    for p_id, p in UZH_PROFESSORS.items():
        if any(kw in full for kw in p["keywords"]):
            matched_prof = p["name"]
            break

    # Emphasis cues
    emphasis_cues = []
    for pat in EMPHASIS_FLAGS:
        if re.search(pat, full):
            emphasis_cues.append(pat.replace(r"\b", ""))

    return {
        "cluster": cluster,
        "professor": matched_prof,
        "is_high_emphasis": len(emphasis_cues) > 0,
        "emphasis_cues": emphasis_cues,
    }


def build_slide_cross_match_index(base_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Scans discovered lecture slides and builds a cross-reference index to Anki topics and decks.
    """
    discovered_files = scan_local_uzh_slides(base_path=base_path)

    # If no local files found (e.g. running on cloud Render), load cached snapshot
    if not discovered_files and SLIDE_MATCH_SNAPSHOT_PATH.exists():
        try:
            with open(SLIDE_MATCH_SNAPSHOT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    indexed_slides = []
    cluster_counts: Dict[str, int] = {}
    high_emphasis_count = 0

    for f in discovered_files:
        meta = extract_lecture_metadata(f["filename"], f["relative_path"])
        entry = {
            "filename": f["filename"],
            "relative_path": f["relative_path"],
            "cluster": meta["cluster"],
            "professor": meta["professor"],
            "is_high_emphasis": meta["is_high_emphasis"],
            "emphasis_cues": meta["emphasis_cues"],
            "modified": f.get("modified"),
            "size_kb": f.get("size_kb"),
        }
        indexed_slides.append(entry)
        cluster_counts[meta["cluster"]] = cluster_counts.get(meta["cluster"], 0) + 1
        if meta["is_high_emphasis"]:
            high_emphasis_count += 1

    result = {
        "available": True,
        "total_slides_indexed": len(indexed_slides),
        "high_emphasis_slides_count": high_emphasis_count,
        "cluster_distribution": cluster_counts,
        "slides": indexed_slides[:50],  # sample
        "cross_match_summary": f"{len(indexed_slides)} Vorlesungsfolien erfolgreich mit 2. SJ Anki-Themen synchronisiert.",
    }

    # Save cache snapshot
    try:
        SLIDE_MATCH_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SLIDE_MATCH_SNAPSHOT_PATH, "w", encoding="utf-8") as out:
            json.dump(result, out, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return result


def get_slide_cross_match_stats() -> Dict[str, Any]:
    """Returns cached slide matches or builds fresh index."""
    if SLIDE_MATCH_SNAPSHOT_PATH.exists():
        try:
            with open(SLIDE_MATCH_SNAPSHOT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return build_slide_cross_match_index()
