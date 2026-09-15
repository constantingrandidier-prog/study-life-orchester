import os
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import pypdf
except ImportError:
    pypdf = None

from app.db.database import get_db_connection

_SLIDE_OVERLAP_CACHE: Dict[str, Dict[str, Any]] = {}

SYNONYMS_MAP = {
    "hämoglobin": ["hamoglobin", "myoglobin"],
    "myoglobin": ["hamoglobin", "myoglobin"],
    "erythrozyten": ["hamoglobin", "erythropoiese", "blutgerinnung"],
    "leukozyten": ["immunsystem", "b zell", "antikorper"],
    "myelopoiese": ["blutgerinnung", "erythropoiese", "komplementsystem"],
    "blutgerinnung": ["blutgerinnung"],
    "thrombozyten": ["blutgerinnung"],
    "hämostase": ["blutgerinnung"],
    "komplementsystem": ["komplementsystem"],
    "säure-basen": ["saure-base", "co2-transport"],
    "co2": ["co2-transport", "saure-base"],
    "atmung": ["lungen", "zwerch"],
    "lunge": ["lungen", "zwerch"],
    "herz": ["herzgefaess", "herz"],
    "herzentwicklung": ["herzgefaess"],
    "pankreas": ["pankreas", "insulin", "glucagon"],
    "insulin": ["pankreas", "insulin", "glucagon"],
    "glukagon": ["pankreas", "insulin", "glucagon"],
    "magen": ["magen", "oesophagus"],
    "oesophagus": ["oesophagus", "magen"],
    "darm": ["dickdarm", "duenndarm"],
    "rektum": ["dickdarm", "rektum"],
    "leber": ["leber", "leberspezifisch"],
    "gallenblase": ["leber", "gallenblase"],
    "mundhöhle": ["mundhohle", "kauapparat", "zahne"],
    "kauapparat": ["mundhohle", "kauapparat", "zahne"],
    "zähne": ["mundhohle", "kauapparat", "zahne"],
    "untersuchungskurs": ["klin-untersuchungskurs", "untersuchungskurs"],
    "hormone": ["hormone", "endokrin", "hypothalam"],
    "hypophyse": ["hypothalamische", "hypophysare", "hypothalamus"],
    "schilddrüse": ["schilddruse", "thyroid"],
    "nebenniere": ["nebenniere", "steroidhormone", "adrenals"],
    "katecholamine": ["katecholamine"],
    "kohlenhydrat": ["kohlenhydratstoffwechsels", "kh stw"],
    "immunsystem": ["immunsystem", "autoimmunitat", "immuntoleranz"],
    "antikörper": ["antikorper", "immunsystem"],
    "b-zell": ["b zell"],
}

SPEED_FACTORS = {
    "live": 1.0,
    "stream_1_25": 1.25,
    "stream_1_5": 1.5,
    "stream_1_75": 1.75,
    "stream_2_0": 2.0,
    "slides_only": 0.0,
    "skipped": 0.0,
}


def calculate_mode_time_savings(total_minutes: int, mode: str) -> Dict[str, Any]:
    """Calculate actual minutes spent and minutes saved for a specific consumption mode."""
    if mode == "skipped":
        spent = 0
        saved = total_minutes
    elif mode == "slides_only":
        spent = min(20, total_minutes)
        saved = max(0, total_minutes - spent)
    elif mode in SPEED_FACTORS and SPEED_FACTORS[mode] > 0:
        factor = SPEED_FACTORS[mode]
        spent = max(1, round(total_minutes / factor))
        saved = max(0, total_minutes - spent)
    else:
        spent = total_minutes
        saved = 0

    return {
        "mode": mode,
        "speed_factor": SPEED_FACTORS.get(mode, 1.0),
        "duration_minutes": spent,
        "time_saved_minutes": saved,
    }


_ALL_LOCAL_SLIDES: Optional[List[Path]] = None


def get_local_slide_files() -> List[Path]:
    """Find all lecture slide PDFs in UNI sem app and OneDrive (cached)."""
    global _ALL_LOCAL_SLIDES
    if _ALL_LOCAL_SLIDES is not None:
        return _ALL_LOCAL_SLIDES

    candidates = [
        Path(r"C:\Users\Constantin Grandidie\OneDrive - Universität Zürich UZH\Desktop\UNI sem app"),
    ]
    files: List[Path] = []
    for c in candidates:
        if c.exists():
            files.extend(list(c.rglob("*.pdf")))

    # Fallback to alles/Studium only if no files found
    if not files:
        studium = Path(r"C:\Users\Constantin Grandidie\OneDrive - Universität Zürich UZH\alles\Studium")
        if studium.exists():
            files.extend(list(studium.rglob("*.pdf")))

    _ALL_LOCAL_SLIDES = files
    return _ALL_LOCAL_SLIDES


def find_matching_slide_for_lecture(title: str, module_name: str = "") -> Optional[Path]:
    """Find the best-matching local slide PDF for a given lecture title."""
    slides = get_local_slide_files()
    if not slides:
        return None

    combined = f"{title} {module_name}".lower()

    # 1. Check synonym mappings
    for key, targets in SYNONYMS_MAP.items():
        if key in combined:
            for t in targets:
                for s in slides:
                    if t in s.stem.lower():
                        return s

    # 2. Check direct word stems in filename
    title_clean = re.sub(r'[^a-zA-Z0-9äöüÄÖÜ]', ' ', combined)
    tokens = [w for w in title_clean.split() if len(w) >= 5 and w not in {'einführung', 'überblick', 'vorlesung', 'allgemein'}]
    for s in slides:
        s_stem = s.stem.lower()
        if any(tok in s_stem for tok in tokens):
            return s

    return None


def compute_pdf_anki_overlap(pdf_path: Path) -> Optional[Dict[str, Any]]:
    """Extract medical terms from PDF and compute overlap with local Anki collection."""
    path_key = str(pdf_path)
    if path_key in _SLIDE_OVERLAP_CACHE:
        return _SLIDE_OVERLAP_CACHE[path_key]

    if not pypdf or not pdf_path.exists():
        return None

    try:
        reader = pypdf.PdfReader(str(pdf_path))
        num_pages = len(reader.pages)
        full_text = ""
        for page in reader.pages[:30]:
            full_text += (page.extract_text() or "") + " "

        words = set(re.findall(r'[A-Za-zÄÖÜäöüéèà]{5,}', full_text))
        filler = {'dieser', 'werden', 'welche', 'diese', 'durch', 'kann', 'eine', 'einer', 'einen', 'oder', 'nach', 'über', 'unter', 'sowie', 'auch', 'dass', 'wenn', 'beim', 'sich'}
        med_words = [w for w in words if w.lower() not in filler]

        anki_db = Path(os.environ.get("APPDATA", "")) / "Anki2" / "Benutzer 1" / "collection.anki2"
        if not anki_db.exists():
            return None

        uri = f"file:///{anki_db.as_posix()}?mode=ro&immutable=1"
        sample_words = med_words[:25]
        with sqlite3.connect(uri, uri=True) as conn:
            for w in sample_words:
                c = conn.execute("SELECT count(*) FROM notes WHERE flds LIKE ? LIMIT 1", (f"%{w}%",)).fetchone()[0]
                if c > 0:
                    matches.append(w)

        overlap_pct = round((len(matches) / max(1, len(sample_words))) * 100, 1)
        res = {
            "matched": True,
            "pdf_name": pdf_path.name,
            "pdf_path": str(pdf_path),
            "pages_count": num_pages,
            "terms_count": len(med_words),
            "anki_matches_count": len(matches),
            "overlap_pct": overlap_pct,
            "sample_matches": matches[:8],
        }
        _SLIDE_OVERLAP_CACHE[path_key] = res
        return res
    except Exception:
        return None


def evaluate_lecture_value(
    title: str,
    module_name: str,
    duration_minutes: int = 90,
    anki_fail_rate: Optional[float] = None,
    anki_cards_count: int = 0,
) -> Dict[str, Any]:
    """
    Evaluate whether attending a lecture in person is worthwhile or if streaming/skipping is superior.
    Cross-checks with real UZH lecture slide PDFs and Anki retention history.
    """
    title_lower = title.lower()
    module_lower = (module_name or "").lower()
    combined = f"{title_lower} {module_lower}"

    matched_slide_filename = None
    slide_coverage_pct = None

    # Try matching real lecture slides from UNI sem app
    matching_pdf = find_matching_slide_for_lecture(title, module_name)
    pdf_eval = compute_pdf_anki_overlap(matching_pdf) if matching_pdf else None

    if pdf_eval:
        matched_slide_filename = pdf_eval["pdf_name"]
        slide_coverage_pct = pdf_eval["overlap_pct"]

    # 1. Mandatory In-Person Course / Clinical Skills with attendance testat
    mandatory_in_person_keywords = [
        "praktikum", "untersuchungskurs", "präparier", "praeparier", "visite", "kurs klinischer", "testat"
    ]

    # 2. High-complexity physiological "Killer-Concepts" -> 1.5x Focus Stream (Never 2.0x, diagram intensive)
    focus_concepts_keywords = [
        "herzmechanik", "druck-volumen", "pv-loop", "wiggers", "frank-starling", "laplace",
        "erregungsleitung", "aktionspotenzial", "ekg", "rhythmusstörung", "arrhythmi", "antiarrhythmika",
        "atemmechanik", "compliance", "resistance", "ventilation", "perfusion", "gasaustausch", "alveolär",
        "säure-base", "saure-base", "henderson", "astrup", "bikarbonat", "azidose", "alkalose",
        "blutgerinnung", "hämostase", "haemostase", "thrombose", "gerinnung", "kaskade", "fibrinolyse", "antikoagulan",
        "raas", "renin", "angiotensin", "aldosteron", "barorezeptor", "blutdruckregulation", "kreislaufregulation"
    ]

    # 3. Factual / nomenclature / histology / tables -> 0x SKIP completely (100% Anki & Skim Slides)
    pure_factual_keywords = [
        "histologie", "mikroskop", "wandschicht", "zellmorphologie", "myelopoiese", "erythropoiese",
        "vitamin", "spurenelement", "mineralstoff", "kauapparat", "zahn", "zahne", "gaumen", "mundhöhle", "mundhohle",
        "anatomie oesophagus", "anatomie magen", "anatomie dickdarm", "anatomie duenndarm", "anatomie leber",
        "anatomie rektum", "anatomie trachea", "nomenklatur", "definition", "repetition", "stoffchemie"
    ]

    # 4. Overview / Descriptive / Developmental / Endocrine -> 2.0x High-Speed Stream
    # All remaining lectures benefit from 2.0x speed for red thread and lecturer emphasis without wasting time

    if any(k in combined for k in mandatory_in_person_keywords):
        recommendation = "attend"
        recommended_mode = "live"
        badge_label = "🏛️ OBLIGATORISCH (Präsenzpflicht)"
        badge_color = "#a371f7"  # Distinct bright violet for mandatory UZH practicals
        reason = (
            "Offizielles Praktikum / Testatkurs an der UZH. Hier gilt Anwesenheitspflicht vor Ort! "
            "Praktische Fertigkeiten (Untersuchung, Perkussion, Palpation, Präparation) lassen sich nicht digital ersetzen."
        )

    elif anki_fail_rate is not None and anki_fail_rate >= 40.0:
        recommendation = "stream"
        recommended_mode = "stream_1_5"
        badge_label = f"🟠 Hohe Fehlerquote {anki_fail_rate:.0f}% (1.5x Focus Stream)"
        badge_color = "#db6d28"
        reason = (
            f"Deine Anki-Statistik zeigt bei diesem Thema eine Fehlerquote von {anki_fail_rate:.1f}%. "
            f"Reines Kartendrücken reicht hier nicht – schau dir die Vorlesung auf 1.5x an, um die konzeptionelle "
            f"Basis zu festigen und Transferfragen in der Prüfung sicher zu lösen."
        )

    elif any(k in combined for k in focus_concepts_keywords):
        recommendation = "stream"
        recommended_mode = "stream_1_5"
        badge_label = "🟠 1.5x Focus Stream (Prüfungs-Kern)"
        badge_color = "#db6d28"
        reason = (
            "⚠️ Klinischer & physiologischer Prüfungsschwerpunkt! Beinhaltet dynamische Regelkreise, Diagramme oder Kaskaden "
            "(z.B. Druck-Volumen-Kurven, EKG, Säure-Basen oder Gerinnung). Nicht auf 2.0x rasen – auf 1.5x streamen und "
            "Diagramme aktiv nachvollziehen. Spart 30 Minuten und schützt vor gravierenden Fehlern bei Transferfragen."
        )

    elif any(k in combined for k in pure_factual_keywords):
        recommendation = "skip"
        recommended_mode = "skipped"
        badge_label = "🔴 Skippen (100% Anki – spart 90 min)"
        badge_color = "#f85149"
        reason = (
            "Reines Faktenwissen, Nomenklatur, Wandschichten oder Histologie. Passive Hörsaal-Beschallung bringt hier "
            "nahezu null Lerneffekt. Spar dir die 90 Minuten Vorlesung komplett und lerne den Stoff direkt über "
            "aktives Anki-Recall (Image Occlusion)!"
        )

    elif pdf_eval and pdf_eval["overlap_pct"] >= 80.0:
        pct = pdf_eval["overlap_pct"]
        fn = pdf_eval["pdf_name"]
        pages = pdf_eval["pages_count"]
        samples = ", ".join(pdf_eval["sample_matches"][:4])
        recommendation = "skip"
        recommended_mode = "skipped"
        badge_label = f"🔴 {round(pct)}% Anki-Deckung (Skippen & Anki)"
        badge_color = "#f85149"
        reason = (
            f"Original-Folien '{fn}' ({pages} Folien): {pct}% der Fachbegriffe (z.B. {samples}) sind bereits "
            f"in deinen Anki-Karten erfasst. Vorlesung skippen spart dir die vollen {duration_minutes} Minuten!"
        )

    else:
        # Default for descriptive / overview lectures: High-Speed 2.0x Stream
        recommendation = "stream"
        recommended_mode = "stream_2_0"
        badge_label = "🟡 2.0x High-Speed Stream (spart 45 min)"
        badge_color = "#d29922"
        reason = (
            "Wichtig für den roten Faden, Organ-Zusammenhänge und Dozenten-Schwerpunkte, aber inhaltlich unkompliziert. "
            "Auf doppelter Geschwindigkeit (2.0x) im Stream anhören – spart genau 45 Minuten bei vollem Stoffüberblick!"
        )

    # Calculate options breakdown
    modes_breakdown = []
    for m in ["live", "stream_1_25", "stream_1_5", "stream_2_0", "slides_only", "skipped"]:
        calc = calculate_mode_time_savings(duration_minutes, m)
        modes_breakdown.append(calc)

    rec_calc = calculate_mode_time_savings(duration_minutes, recommended_mode)

    return {
        "title": title,
        "recommendation": recommendation,
        "recommended_mode": recommended_mode,
        "badge_label": badge_label,
        "badge_color": badge_color,
        "reason": reason,
        "duration_minutes": duration_minutes,
        "recommended_time_saved_minutes": rec_calc["time_saved_minutes"],
        "modes_breakdown": modes_breakdown,
        "matched_slide_filename": matched_slide_filename,
        "slide_coverage_pct": slide_coverage_pct,
    }


def set_event_consumption_mode(event_id: int, mode: str) -> Dict[str, Any]:
    """Set the chosen consumption mode for a saved lecture event and record time savings."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, start_time, end_time, title, module_name FROM saved_events WHERE id = ?", (event_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Event mit ID {event_id} nicht gefunden.")

        # Compute duration
        try:
            start = datetime.fromisoformat(row["start_time"])
            end = datetime.fromisoformat(row["end_time"])
            duration = max(15, round((end - start).total_seconds() / 60))
        except Exception:
            duration = 90

        calc = calculate_mode_time_savings(duration, mode)
        speed = calc["speed_factor"]
        saved = calc["time_saved_minutes"]
        attended = 1 if mode in ["live", "stream_1_25", "stream_1_5", "stream_1_75", "stream_2_0"] else 0

        cursor.execute("""
            UPDATE saved_events SET
                consumption_mode = ?,
                speed_factor = ?,
                time_saved_minutes = ?,
                lecture_attended = ?
            WHERE id = ?;
        """, (mode, speed, saved, attended, event_id))

        return {
            "event_id": event_id,
            "consumption_mode": mode,
            "speed_factor": speed,
            "time_saved_minutes": saved,
            "duration_minutes": calc["duration_minutes"],
            "lecture_attended": attended,
        }


def get_total_time_saved_for_date(target_date: date) -> int:
    """Return total minutes saved across all lectures on a target date."""
    date_str = target_date.isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(SUM(time_saved_minutes), 0)
            FROM saved_events
            WHERE target_date = ?;
        """, (date_str,))
        row = cursor.fetchone()
        return row[0] if row else 0
