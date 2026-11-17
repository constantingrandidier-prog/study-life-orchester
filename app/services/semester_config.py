"""Centralized Semester & Curriculum Configuration for StudyLife Orchestrator.

Single source of truth for:
- Semester timeline constants (Start Date, Exam Date, Revision Buffer)
- Excluded / ignored lecturers (e.g., Wenger & Sommer, studied via summaries instead of Anki repetitions)
- Real Anki deck query construction and professor/module filtering helpers
"""

from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# Semester & Exam Timeline (Single Source of Truth)
SEMESTER_START_DATE = date(2026, 9, 14)
SEMESTER_START_TS = int(datetime(2026, 9, 14, 0, 0, 0).timestamp() * 1000)
TARGET_EXAM_DATE = date(2027, 1, 19)
DEFAULT_REVISION_BUFFER_DAYS = 14
DEFAULT_DAILY_REP_BUDGET = 350

# Lecturers excluded from Anki repetition triage & due counts (studied via summaries)
# Note: Schneider subdecks in TB Blut/Immunsystem that mention "/ Wenger" in their subdeck title
# belong to Prof. Schneider and remain included!
IGNORED_DOZENTEN: Set[str] = {"wenger", "sommer"}

# Specific Anki deck path substrings that identify ignored professor decks in raw SQL/strings
IGNORED_DECK_PATH_PATTERNS: Tuple[str, ...] = (
    "atmung_physiologie_wenger",
    "::sommer",
    ":: sommer",
    "\x1fsommer",
    "4 sommer",
    "/ sommer",
    "wenger ::",
)


def is_ignored_dozent(prof_name: Optional[str]) -> bool:
    """Return True if the normalized lecturer name is in the ignored set."""
    if not prof_name:
        return False
    low = str(prof_name).strip().lower()
    if low in IGNORED_DOZENTEN:
        return True
    return any(ig in low for ig in IGNORED_DOZENTEN)


def is_ignored_deck_name(raw_or_clean_deck_name: Optional[str]) -> bool:
    """
    Return True if an Anki deck name belongs to an ignored professor (Wenger in TB Atmung, or Sommer).
    Carefully preserves TB Blut/Immunsystem :: Schneider :: ... / Wenger subdecks.
    """
    if not raw_or_clean_deck_name:
        return False
    low = str(raw_or_clean_deck_name).lower()
    if "schneider" in low:
        return False
    return any(pat in low for pat in IGNORED_DECK_PATH_PATTERNS)


def is_ignored_topic_entry(entry: Dict[str, Any]) -> bool:
    """Return True if a topic/professor dictionary entry belongs to an ignored lecturer."""
    if not isinstance(entry, dict):
        return False
    doz = str(entry.get("dozent", "")).strip().lower()
    dname = str(entry.get("deck_name", "")).strip().lower()
    if is_ignored_dozent(doz):
        return True
    if "› wenger" in dname or "› sommer" in dname:
        return True
    if is_ignored_deck_name(dname):
        return True
    return False


def build_anki_deck_clause(
    real_prefixes: Iterable[str],
    tb_clean: str,
    prof_clean: str,
) -> str:
    """
    Builds a 100% accurate Anki search deck clause combining the exact Anki deck path prefixes
    (which always match in Anki, even when TB or professor names have special chars like '/', '&', '+')
    and a wildcard fallback.
    """
    clauses: List[str] = []
    for pfx in sorted(set(p for p in (real_prefixes or []) if p)):
        clauses.append(f'deck:"{pfx}*"')
    fallback = f'deck:"*2. SJ*{tb_clean}*{prof_clean}*"'
    if fallback not in clauses:
        clauses.append(fallback)
    if len(clauses) == 1:
        return clauses[0]
    return f"({' or '.join(clauses)})"
