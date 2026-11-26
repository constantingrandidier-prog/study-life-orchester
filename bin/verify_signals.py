"""Audit & Strict Evidence Verification Script for `app/data/lecture_exam_signals.json` (v2.0).

Checks:
  1. All referenced `source_summaries` and `ignored_dozent_summaries` exist and cover 100% of summaries.
  2. Zero meta-coverage notes ("Hinweis zur Transkript-Abdeckung", "Hinweis zur Quellenlage")
     leak into `exam_highlights` (must live in `coverage_note`).
  3. Strict keyword evidence hit-rate per bullet (>= 0.55 stem match) and per entry (>= 0.70).
  4. Strict numeric integrity check: multi-digit numbers (excluding lecture dates/date ranges)
     in `exam_highlights` and `clinical_pearls` must appear verbatim in the referenced summaries.
  5. Zero dead/unmatched signal entries against the 90 frozen golden Anki subdecks.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SIGNALS_PATH = ROOT / "app" / "data" / "lecture_exam_signals.json"
SUMMARIES_DIR = ROOT / "app" / "data" / "lecture_transcripts" / "summaries"
GOLDEN_SUBDECKS_PATH = ROOT / "tests" / "fixtures" / "triage_golden_subdecks.json"

META_PREFIXES = (
    "hinweis zur transkript-abdeckung",
    "hinweis zur quellenlage",
)


def _extract_keywords(text: str) -> List[str]:
    return sorted(set(re.findall(r"[a-zäöüß]{6,}", str(text or "").lower())))


def _strip_lecture_dates(text: str) -> str:
    # Strip date ranges like "15.–26.09.2025", "15.-26.09." and single dates "25.09.2025", "25.09."
    s = re.sub(r"\b\d{1,2}\.\s*[–\-]\s*\d{1,2}\.\d{2}\.(?:\d{2,4})?\b", " ", text)
    s = re.sub(r"\b\d{1,2}\.\d{2}\.(?:\d{2,4})?\b", " ", s)
    return s


def verify_signals(min_evidence_rate: float = 0.70, bullet_kw_threshold: float = 0.55) -> Dict[str, Any]:
    data = json.loads(SIGNALS_PATH.read_text(encoding="utf-8"))
    entries = data.get("entries") or []

    missing_files: List[str] = []
    meta_leaks: List[str] = []
    low_evidence: List[Dict[str, Any]] = []
    numeric_mismatches: List[Dict[str, Any]] = []
    referenced = set()
    total_bullets = 0
    verified_bullets = 0

    for sf in data.get("ignored_dozent_summaries") or []:
        referenced.add(sf)
        if not (SUMMARIES_DIR / sf).exists():
            missing_files.append(f"<ignored_dozent_summaries>: {sf}")

    for entry in entries:
        eid = str(entry.get("id") or "<unknown>")
        src_text_parts: List[str] = []
        for sf in entry.get("source_summaries") or []:
            referenced.add(sf)
            fp = SUMMARIES_DIR / sf
            if not fp.exists():
                missing_files.append(f"{eid}: {sf}")
            else:
                src_text_parts.append(fp.read_text(encoding="utf-8").lower())

        for hl in entry.get("exam_highlights") or []:
            hl_low = str(hl or "").strip().lower()
            if any(hl_low.startswith(p) for p in META_PREFIXES):
                meta_leaks.append(f"{eid}: {hl[:80]}")

        combined_src = "\n".join(src_text_parts)
        combined_src_compact = combined_src.replace(" ", "").replace("\u202f", "").replace("\xa0", "")

        for field in ("exam_highlights", "clinical_pearls"):
            for b in entry.get(field) or []:
                cleaned = _strip_lecture_dates(str(b or ""))
                nums = re.findall(r"\b\d{2,4}\b", cleaned)
                missing_nums = [n for n in nums if n not in combined_src_compact]
                if missing_nums:
                    numeric_mismatches.append({
                        "id": eid,
                        "field": field,
                        "missing_nums": missing_nums,
                        "bullet": str(b)[:120],
                    })

        bullets = (
            list(entry.get("exam_highlights") or [])
            + list(entry.get("clinical_pearls") or [])
            + list(entry.get("deemphasized_notes") or [])
        )
        if not bullets:
            continue

        entry_hits = 0
        for b in bullets:
            total_bullets += 1
            kws = _extract_keywords(b)
            if not kws:
                entry_hits += 1
                verified_bullets += 1
                continue
            matched = sum(1 for kw in kws if kw[:6] in combined_src)
            if matched / len(kws) >= bullet_kw_threshold:
                entry_hits += 1
                verified_bullets += 1

        rate = entry_hits / len(bullets)
        if rate < min_evidence_rate:
            low_evidence.append({
                "id": eid,
                "dozent": entry.get("dozent"),
                "rate_pct": round(rate * 100.0, 1),
                "source_summaries": entry.get("source_summaries") or [],
            })

    # Check for dead/unused entries against the 90 frozen golden Anki subdecks
    dead_entries: List[str] = []
    direct_golden_matches = 0
    total_golden = 0
    if GOLDEN_SUBDECKS_PATH.exists():
        from app.services.lecture_exam_briefing_service import match_subdeck_to_exam_signal

        golden = json.loads(GOLDEN_SUBDECKS_PATH.read_text(encoding="utf-8"))
        total_golden = len(golden)
        matched_ids = set()
        for fx in golden:
            hit = match_subdeck_to_exam_signal(
                themenblock=fx["themenblock"],
                dozent=fx["dozent"],
                subdeck=fx["subdeck"],
                full_anki_deck=fx["full_anki_deck"],
                allow_prof_fallback=True,
            )
            if hit:
                matched_ids.add(hit["id"])
                if not hit.get("is_prof_fallback"):
                    direct_golden_matches += 1
        dead_entries = [str(e.get("id")) for e in entries if e.get("id") not in matched_ids]

    all_summaries = sorted(p.name for p in SUMMARIES_DIR.glob("*.md")) if SUMMARIES_DIR.exists() else []
    unreferenced = [f for f in all_summaries if f not in referenced]
    overall_rate = round((verified_bullets / max(1, total_bullets)) * 100.0, 1)

    ok = (
        len(missing_files) == 0
        and len(meta_leaks) == 0
        and len(low_evidence) == 0
        and len(numeric_mismatches) == 0
        and len(unreferenced) == 0
        and len(dead_entries) == 0
        and len(entries) > 0
    )
    return {
        "ok": ok,
        "entry_count": len(entries),
        "total_bullets": total_bullets,
        "verified_bullets": verified_bullets,
        "overall_evidence_rate_pct": overall_rate,
        "referenced_summaries": len(referenced),
        "total_summaries": len(all_summaries),
        "unreferenced_summaries": unreferenced,
        "missing_files": missing_files,
        "meta_leaks": meta_leaks,
        "low_evidence": low_evidence,
        "numeric_mismatches": numeric_mismatches,
        "dead_entries": dead_entries,
        "golden_direct_matches": direct_golden_matches,
        "golden_total_subdecks": total_golden,
    }


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    report = verify_signals()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if report["ok"] else 1)
