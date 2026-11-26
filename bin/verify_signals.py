"""Audit & Evidence Verification Script for `app/data/lecture_exam_signals.json`.

Checks:
  1. All referenced `source_summaries` exist and all 38 summary files are referenced.
  2. No meta-coverage notes ("Hinweis zur Transkript-Abdeckung", "Hinweis zur Quellenlage")
     leak into `exam_highlights` (must live in `coverage_note`).
  3. Evidence keyword hit-rate per bullet against the referenced summary `.md` files.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
SIGNALS_PATH = ROOT / "app" / "data" / "lecture_exam_signals.json"
SUMMARIES_DIR = ROOT / "app" / "data" / "lecture_transcripts" / "summaries"

META_PREFIXES = (
    "hinweis zur transkript-abdeckung",
    "hinweis zur quellenlage",
)


def _extract_keywords(text: str) -> List[str]:
    return sorted(set(re.findall(r"[a-zäöüß]{6,}", str(text or "").lower())))


def verify_signals(min_evidence_rate: float = 0.70) -> Dict[str, Any]:
    data = json.loads(SIGNALS_PATH.read_text(encoding="utf-8"))
    entries = data.get("entries") or []

    missing_files: List[str] = []
    meta_leaks: List[str] = []
    low_evidence: List[Dict[str, Any]] = []
    referenced = set()
    total_bullets = 0
    verified_bullets = 0

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
            if matched / len(kws) >= 0.40:
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

    all_summaries = sorted(p.name for p in SUMMARIES_DIR.glob("*.md")) if SUMMARIES_DIR.exists() else []
    unreferenced = [f for f in all_summaries if f not in referenced]
    overall_rate = round((verified_bullets / max(1, total_bullets)) * 100.0, 1)

    ok = (
        len(missing_files) == 0
        and len(meta_leaks) == 0
        and len(low_evidence) == 0
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
    }


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    report = verify_signals()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if report["ok"] else 1)
