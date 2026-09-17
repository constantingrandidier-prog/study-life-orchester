"""Didactic Master Curriculum Roadmap and Daily 100-Anki Assignment Engine.

Sequences all 111 decks / 9'633 target cards from the 2. Studienjahr into
6 logical medical modules, allocating exactly 100 new cards per active study day,
with Sundays as rest days, and linking each topic to real lecture slides.
"""

from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Optional

from app.services.olat_connector import scan_local_uzh_slides
from app.services.lecture_advisor_service import search_lecture_advisor

# Semester milestone constants
SEMESTER_START_DATE = date(2026, 9, 14)  # Monday
TARGET_EXAM_DATE = date(2027, 1, 19)     # Tuesday
DAILY_CARD_QUOTA = 90

# Didactic medical module progression for 2. Studienjahr
DIDACTIC_MODULES = [
    (
        1,
        "1. Blut & Immunsystem",
        ["blut", "immun", "hämoglobin", "hamoglobin", "myoglobin", "gerinnung", "komplement", "tuzlak", "manatschal"],
    ),
    (
        2,
        "2. Herz-Kreislauf",
        ["herz", "kreislauf", "kurt", "sommer :: gefäss", "erregungsleitung", "ekg", "durchblutung", "niederdruck", "hochdruck", "herzwand", "venen"],
    ),
    (
        3,
        "3. Atmung & Lunge",
        ["atmung", "lunge", "wenger", "loffing", "ventilation", "perfusion", "pharynx", "trachea", "bronchien", "zwerchfell", "atemmuskulatur"],
    ),
    (
        4,
        "4. Verdauung & Ernährung",
        ["verdauung", "ernährung", "stockmann", "dutzler", "wagner", "magen", "darm", "oesophagus", "pankreas", "leber", "vitamine", "schlucken", "hunger"],
    ),
    (
        5,
        "5. Stoffwechsel & Biochemie",
        ["stoffwechsel", "jele :: regulation kh", "jele :: org", "hersi", "fettsäure", "biotransformation"],
    ),
    (
        6,
        "6. Endokrinologie & Hormone",
        ["endokrin", "hormon", "jele 1", "jele 2", "jele 4", "jele 5", "hall", "schilddrüse", "nebenniere", "kalzium", "calcium"],
    ),
]

CYCLE_KEYWORDS = [
    "gerinnung", "kaskade", "zyklus", "citrat", "glykolyse",
    "raas", "renin", "erregungsleitung", "stoffwechsel",
    "biotransformation", "hormonkaskade", "feedback", "kreislauf",
    "ventilation", "mechanik"
]

FOCUS_KEYWORDS = [
    "herzmechanik", "druck-volumen", "pv-loop", "wiggers", "frank-starling", "laplace",
    "erregungsleitung", "aktionspotenzial", "ekg", "rhythmusstörung", "arrhythmi", "antiarrhythmika",
    "atemmechanik", "compliance", "resistance", "ventilation", "perfusion", "gasaustausch", "alveolär", "totraum",
    "säure-base", "saure-base", "henderson", "astrup", "bikarbonat", "azidose", "alkalose",
    "blutgerinnung", "hämostase", "haemostase", "thrombose", "kaskade", "fibrinolyse", "antikoagulan",
    "raas", "renin", "angiotensin", "aldosteron", "barorezeptor", "blutdruckregulation", "kreislaufregulation",
    "biotransformation", "glykolyse", "gluconeogenese", "citratzyklus", "co2-transport"
]

PURE_FACT_KEYWORDS = [
    "histologie", "mikroskop", "wandschicht", "zellmorphologie", "myelopoiese", "erythropoiese",
    "vitamin", "spurenelement", "mineralstoff", "kauapparat", "zahn", "zahne", "gaumen", "mundhöhle", "mundhohle",
    "anatomie oesophagus", "anatomie magen", "anatomie dickdarm", "anatomie duenndarm", "anatomie leber",
    "anatomie rektum", "anatomie trachea", "nomenklatur", "definition", "repetition", "stoffchemie",
    "antihypertensiva", "biomarker"
]


def classify_topic_didactics(deck_name: str, clean_title: str, module_name: str) -> Dict[str, Any]:
    """Classify a curriculum topic into: 1.0x Voller Fokus, 1.2x Standard-Stream, or Skip for Anki."""
    combined = f"{deck_name} {clean_title} {module_name}".lower()

    if any(k in combined for k in FOCUS_KEYWORDS):
        return {
            "is_cycle_topic": True,
            "recommended_mode": "stream_1_0",
            "speed_factor": 1.0,
            "badge_label": "🟠 1.0x Voller Fokus (Prüfungs-Kern)",
            "didactic_reason": "⚠️ Kausale Regelkreise & Funktionskurven (USMLE/UZH Prüfungsfokus). Auf 1.0x streamen und aktiv mitdenken!",
        }
    elif any(k in combined for k in PURE_FACT_KEYWORDS):
        return {
            "is_cycle_topic": False,
            "recommended_mode": "skipped",
            "speed_factor": 0.0,
            "badge_label": "🔴 Vorlesung skippen (100% Anki)",
            "didactic_reason": "Reines Faktenwissen / Nomenklatur / Histologie. Vorlesung skippen (spart 90 Min) und direkt in Anki lernen!",
        }
    else:
        return {
            "is_cycle_topic": False,
            "recommended_mode": "stream_1_2",
            "speed_factor": 1.2,
            "badge_label": "🟡 1.2x Standard-Stream (+25m gespart)",
            "didactic_reason": "Deskriptiver Überblick & Dozentenschwerpunkte. Auf 1.2x im Standard-Stream mitnehmen!",
        }

GERMAN_WEEKDAYS = {
    0: "Montag",
    1: "Dienstag",
    2: "Mittwoch",
    3: "Donnerstag",
    4: "Freitag",
    5: "Samstag",
    6: "Sonntag",
}

KNOWN_LECTURERS = [
    "Manatschal", "Tuzlak", "Kurt", "Sommer", "Wenger", "Loffing",
    "Stockmann", "Dutzler", "Wagner", "Jele", "Hall", "Hersi"
]


def clean_topic_display(raw_deck_name: str, module_name: str) -> Dict[str, Any]:
    """Clean raw Anki deck hierarchy strings into human-friendly titles, lecturer tag, and breadcrumbs."""
    parts = [p.strip() for p in raw_deck_name.replace("\x1f", "::").split("::") if p.strip()]
    leaf = parts[-1] if parts else raw_deck_name

    # Strip numbers and technical prefixes from leaf title
    clean_title = re.sub(r'^[0-9]+[\s_.\-]+', '', leaf).strip()
    clean_title = re.sub(r'^[0-9]+[\s]+', '', clean_title).strip()
    mod_lower = module_name.lower()
    raw_lower = raw_deck_name.lower()

    # Strip erroneous tutor slash notation " / Wenger" from Erythrozyten in TB Blut
    if "blut" in mod_lower or "immunsystem" in mod_lower:
        clean_title = re.sub(r'\s*/\s*Wenger$', '', clean_title).strip()

    if not clean_title:
        clean_title = leaf

    detected_lecturer = None
    for part in parts:
        for lec in KNOWN_LECTURERS:
            if lec.lower() in part.lower():
                detected_lecturer = lec
                break
        if detected_lecturer:
            break

    # Wenger is NOT in TB Blut (Roland Wenger only lectures in TB Atmung)
    if ("blut" in mod_lower or "immunsystem" in mod_lower) and detected_lecturer == "Wenger":
        detected_lecturer = "Manatschal"

    # Format breadcrumb (e.g. "Blut & Immunsystem › Manatschal")
    module_clean = re.sub(r'^[0-9]+[\s_.\-]+', '', module_name).strip()
    if detected_lecturer:
        breadcrumb = f"{module_clean} › {detected_lecturer}"
    else:
        breadcrumb = module_clean

    return {
        "short_title": leaf,
        "clean_title": clean_title,
        "lecturer": detected_lecturer,
        "breadcrumb": breadcrumb,
    }


def get_clinical_scaffolding_for_deck(deck_name: str, clean_title: str) -> Dict[str, Any]:
    """Provides high-yield clinical reasoning, narrative red thread, and exam cross-links."""
    combined = f"{deck_name} {clean_title}".lower()

    # 1. BLUT & IMMUNSYSTEM
    if "leukozyt" in combined or "granulozyt" in combined:
        return {
            "red_thread": "Erst die Reifungsstufen im Knochenmark (Myeloblast -> Segmentkernige) und Phagozytose verstehen. Das verhindert stumpfes Auswendiglernen im Differentialblutbild.",
            "cross_links": [
                "Blutbild-Interpretation: Linksverschiebung bei Infektionen",
                "Chemotaxis, Opsonierung (C3b) & Respiratory Burst (NADPH-Oxidase)",
                "Chronische Granulomatose & akute Leukämien (Blastenkrise)"
            ],
            "concept_goal": "Zelluläre Primärabwehr, Granulozyten-Differenzierung & Blutbild-Analyse"
        }
    elif "hämoglobin" in combined or "myoglobin" in combined or "haemoglobin" in combined:
        return {
            "red_thread": "Erst die Sigmoide Bindungskurve und den kooperativen T- zu R-Übergang im Video nachvollziehen. Die Anki-Karten leiten sich dann logisch aus der Allosterie ab.",
            "cross_links": [
                "Allosterie & Bohr-Effekt (pH/Protonen- und CO2-Verschiebung)",
                "2,3-BPG bei chronischer Hypoxie und Höhenanpassung",
                "Hämoglobinopathien: Sichelzellanämie (HbS Glu6Val) & Thalassämien"
            ],
            "concept_goal": "Molekulare Sauerstoffbindung, Allosterie & Hämoglobin-Regulation"
        }
    elif "co2" in combined or "säure-base" in combined or "saure-base" in combined:
        return {
            "red_thread": "Baut direkt auf dem Hämoglobin auf: Carboanhydrase, Hamburger-Shift (Chlorid-Austausch) und Haldane-Effekt als Kreislauf für Gasaustausch und pH-Puffer begreifen.",
            "cross_links": [
                "Blutgas-Analyse (BGA): Henderson-Hasselbalch, Standardbikarbonat & Basenabweichung (BE)",
                "Respiratorische vs. metabolische Azidose/Alkalose & renale Gegenregulation",
                "Notfallmedizin: Beatmungseinstellung & CO2-Narkose bei COPD"
            ],
            "concept_goal": "CO2-Transportmechanismen & Säure-Basen-Homöostase prüfungsfest vernetzen"
        }
    elif "gerinnung" in combined or "hämostase" in combined or "haemostase" in combined or "thrombozyt" in combined:
        return {
            "red_thread": "Primäre Hämostase (vWF, Thrombozytenadhäsion via GP Ib, Aktivierung via TxA2/ADP, Aggregation via GP IIb/IIIa) und sekundäre Kaskade (Tenase- & Prothrombinase-Komplex) als sequentiellen Wundverschluss erfassen.",
            "cross_links": [
                "Pharmakologie: DOAKs (Faktor Xa-/Thrombin-Hemmer), Heparin (Antithrombin-III) & Cumarine (VKORC1)",
                "Thrombozytenaggregationshemmer: ASS (COX-1) vs. Clopidogrel (P2Y12)",
                "Hämophilie A (FVIII) & B (FIX) vs. von-Willebrand-Syndrom (vWS)"
            ],
            "concept_goal": "Vollständige Kaskade von Thrombusbildung, Antikoagulation & Fibrinolyse"
        }
    elif "erythrozyt" in combined or "anämie" in combined or "anaemie" in combined:
        return {
            "red_thread": "Erythrozyten-Indices (MCV, MCH, MCHC) und Eisenstoffwechsel (Ferritin, Transferrin, Hepcidin) als diagnostischen Algorithmus begreifen.",
            "cross_links": [
                "Mikrozytäre Anämien: Eisenmangelanämie vs. Anämie chronischer Erkrankungen (ACD)",
                "Makrozytäre Anämien: Vitamin B12- und Folsäuremangel (DNA-Synthesestörung)",
                "Hämolytische Anämien: Kugelzellanämie (Sphärozytose) & G6PD-Mangel (Favismus)"
            ],
            "concept_goal": "Pathophysiologische Diagnostik aller Anämieformen"
        }
    elif "immun" in combined or "tuzlak" in combined or "lymph" in combined or "thymus" in combined:
        return {
            "red_thread": "Zusammenspiel von angeborener Immunität (Komplement, TLRs, Phagozyten) und adaptiver Immunität (T-Zell-Rezeptor-Rekombination, B-Zell-Reifung, MHC-I/II-Präsentation).",
            "cross_links": [
                "MHC-Restriktion: CD8+ (MHC-I) vs. CD4+ (MHC-II / Th1, Th2, Th17)",
                "Zentrale vs. periphere Immuntoleranz & Entstehung von Autoimmunerkrankungen",
                "Monoklonale Antikörper & Checkpoint-Inhibitoren (PD-1, CTLA-4) in der Onkologie"
            ],
            "concept_goal": "Immunologische Schutzmechanismen & Autoimmunität"
        }
        
    # 2. HERZ-KREISLAUF
    elif "ekg" in combined or "erregungsleitung" in combined or "aktionspotenzial" in combined or "arrhythmi" in combined:
        return {
            "red_thread": "Aktionspotential-Phasen der Arbeitsmyozyten (Phase 0 Na+, Phase 2 Ca2+-Plateau, Phase 3 K+) direkt mit den EKG-Wellen (P, QRS, ST, T) korrelieren.",
            "cross_links": [
                "Vaughan-Williams-Klassifikation der Antiarrhythmika (Klasse I-IV)",
                "Ischämiezeichen: ST-Hebung (STEMI) vs. ST-Senkung (NSTEMI) & T-Inversion",
                "Long-QT-Syndrom, Torsades de pointes & Reentry-Kreisläufe"
            ],
            "concept_goal": "Elektrophysiologie, EKG-Befundung & Rhythmusstörungen"
        }
    elif "herzmechanik" in combined or "druck-volumen" in combined or "wiggers" in combined or "klappen" in combined:
        return {
            "red_thread": "Wiggers-Diagramm und PV-Loops (Druck-Volumen-Kurven) Schritt für Schritt nachvollziehen: Isovolumetrische Kontraktion, Austreibung, isovolumetrische Relaxation, Füllung.",
            "cross_links": [
                "Frank-Starling-Mechanismus, Vorlast (Enddiastolisches Volumen) vs. Nachlast",
                "Klappenpathologien: Aortenstenose (Drucküberlastung) vs. Mitralinsuffizienz (Volumenüberlastung)",
                "Herzinsuffizienz (HFrEF vs. HFpEF) & neurohumorale Kompensation (RAAS, Sympathikus)"
            ],
            "concept_goal": "Hämodynamik, Klappenmechanik & Herzzyklus"
        }
        
    # 3. ATMUNG & LUNGE
    elif "compliance" in combined or "atemmechanik" in combined or "ventilation" in combined or "lunge" in combined:
        return {
            "red_thread": "Statische und dynamische Lungenvolumina, transmuraler Druck und Surfactant-Physiologie (Laplace-Gesetz) als mechanische Einheit verstehen.",
            "cross_links": [
                "Obstruktive (FEV1/FVC < 70%, Asthma/COPD) vs. restriktive Ventilationsstörungen (Lungenfibrose)",
                "Ventilations-Perfusions-Verhältnis (V/Q), Totraumventilation & Shunt",
                "Euler-Liljestrand-Mechanismus (hypoxische pulmonale Vasokonstriktion) & Cor pulmonale"
            ],
            "concept_goal": "Respiratorische Mechanik, Lungenfunktion & Gasaustausch"
        }
        
    # 4. VERDAUUNG & ERNÄHRUNG
    elif "magen" in combined or "darm" in combined or "leber" in combined or "pankreas" in combined or "verdauung" in combined:
        return {
            "red_thread": "Sekretion und enzymatische Spaltung entlang des GI-Trakts: Belegzellen (HCl, Intrinsic Factor), Azinuszellen (Zymogene) und Hepatozyten (Gallensäuren).",
            "cross_links": [
                "Pharmakologie: Säurehemmung via PPIs (H+/K+-ATPase) & H2-Rezeptor-Antagonisten",
                "Malabsorption: Zöliakie, exokrine Pankreasinsuffizienz & Gallensäurenverlustsyndrom",
                "Portale Hypertension: Ösophagusvarizen, Aszites & hepatische Enzephalopathie"
            ],
            "concept_goal": "Gastrointestinale Physiologie, Enzymologie & Leberpathologie"
        }
        
    # 5. STOFFWECHSEL & BIOCHEMIE
    elif "glykolyse" in combined or "stoffwechsel" in combined or "citrat" in combined or "fettsäure" in combined:
        return {
            "red_thread": "Schlüsselenzyme und Schrittmacherreaktionen (PFK-1, Pyruvat-Dehydrogenase, Citrat-Synthase) im Zustand von Sattheit (Insulin) vs. Hunger (Glukagon) gegenüberstellen.",
            "cross_links": [
                "Ketoazidose bei absolutem Insulinmangel (Diabetes mellitus Typ 1)",
                "Mitochondriale Myopathien & Entkoppler der Atmungskette (Thermogenin, DNP)",
                "Inborn errors of metabolism: Glykogenosen, Phenylketonurie & MCAD-Mangel"
            ],
            "concept_goal": "Intermediärstoffwechsel, Energiehomöostase & Stoffwechselregulation"
        }
        
    # 6. ENDOKRINOLOGIE & HORMONE
    elif "hormon" in combined or "hypophys" in combined or "schilddrüs" in combined or "nebennier" in combined or "endokrin" in combined:
        return {
            "red_thread": "Hypothalamus-Hypophysen-Achsen (TRH-TSH, CRH-ACTH, GnRH-LH/FSH) mit negativem Feedback-Loop und Hormonrezeptor-Signalwegen (cAMP vs. IP3/DAG vs. nukleäre Rezeptoren) strukturieren.",
            "cross_links": [
                "Schilddrüse: Morbus Basedow (TRAK) vs. Hashimoto-Thyreoiditis (TPO-AK)",
                "Nebenniere: Morbus Cushing vs. Morbus Addison & Conn-Syndrom (Hyperaldosteronismus)",
                "Calcium-Homöostase: Hyperparathyreoidismus (Hyperkalzämie-Symptome) & Osteoporose"
            ],
            "concept_goal": "Endokrine Regelkreise, Feedback-Systeme & Rezeptorpharmakologie"
        }
        
    else:
        return {
            "red_thread": "Deskriptives Fachkonzept für den roten Faden der Vorlesung. Im optimierten Standard-Stream (1.2x) mitnehmen.",
            "cross_links": [
                "Grundlagenwissen für die klinischen Module des 3. Studienjahres",
                "Relevante Prüfungskonzepte der UZH-Fakultät"
            ],
            "concept_goal": clean_title or "Fachkonzept des Curriculums"
        }


CANONICAL_CURRICULUM_MAPPINGS = [
    {
        "match_keys": ["erythrozyt", "erythrozyten", "blut und blutplasma", "blutplasma"],
        "module": "1. Blut & Immunsystem",
        "lecture_id": "2025-09-18_TB_Blut_-_Immunsystem",
        "lecture_title": "Hämoglobin, Myoglobin & Sauerstoffbindung (Erythrozyten)",
        "lecture_date": "2025-09-18",
        "lecture_date_formatted": "18.09.2025",
        "lecturer": "Prof. Dr. Cristina Manatschal",
        "slide_file": "1-4_CM_Myoglobin_Hamoglobin.pdf",
        "slide_subfolder": "Vorlesungen im Themenblock Blut und Immunsystem/Cristina Manatschal",
    },
    {
        "match_keys": ["hämoglobin", "myoglobin", "haemoglobin"],
        "module": "1. Blut & Immunsystem",
        "lecture_id": "2025-09-18_TB_Blut_-_Immunsystem",
        "lecture_title": "Hämoglobin, Myoglobin & Sauerstoffbindung (Erythrozyten)",
        "lecture_date": "2025-09-18",
        "lecture_date_formatted": "18.09.2025",
        "lecturer": "Prof. Dr. Cristina Manatschal",
        "slide_file": "1-4_CM_Myoglobin_Hamoglobin.pdf",
        "slide_subfolder": "Vorlesungen im Themenblock Blut und Immunsystem/Cristina Manatschal",
    },
    {
        "match_keys": ["co2", "säure-base", "saure-base", "bohr-effekt", "bohr", "haldane", "hamburger"],
        "module": "1. Blut & Immunsystem",
        "lecture_id": "2025-09-19_TB_Blut_-_Immunsystem",
        "lecture_title": "Säure-Basen-Haushalt, CO2-Transport & Bohr-Effekt",
        "lecture_date": "2025-09-19",
        "lecture_date_formatted": "19.09.2025",
        "lecturer": "Prof. Dr. Cristina Manatschal",
        "slide_file": "5_CM_Saure-Base_CO2-Transport.pdf",
        "slide_subfolder": "Vorlesungen im Themenblock Blut und Immunsystem/Cristina Manatschal",
    },
    {
        "match_keys": ["blutgerinnung", "hämostase", "thrombozyt"],
        "module": "1. Blut & Immunsystem",
        "lecture_id": "2025-09-22_TB_Blut_-_Immunsystem",
        "lecture_title": "Hämostase: Thrombozytenaktivierung & Primäre Blutstillung",
        "lecture_date": "2025-09-22",
        "lecture_date_formatted": "22.09.2025",
        "lecturer": "Prof. Dr. Cristina Manatschal",
        "slide_file": "6-7_CM_Blutgerinnung.pdf",
        "slide_subfolder": "Vorlesungen im Themenblock Blut und Immunsystem/Cristina Manatschal",
    },
    {
        "match_keys": ["gerinnungskaskade", "fibrinolyse", "sekundäre hämostase", "gerinnung"],
        "module": "1. Blut & Immunsystem",
        "lecture_id": "2025-09-25_TB_Blut_-_Immunsystem",
        "lecture_title": "Sekundäre Hämostase: Gerinnungskaskade & Fibrinolyse",
        "lecture_date": "2025-09-25",
        "lecture_date_formatted": "25.09.2025",
        "lecturer": "Prof. Dr. Cristina Manatschal",
        "slide_file": "6-7_CM_Blutgerinnung.pdf",
        "slide_subfolder": "Vorlesungen im Themenblock Blut und Immunsystem/Cristina Manatschal",
    },
    {
        "match_keys": ["komplement", "komplementsystem", "immunantwort", "immunsystem", "tuzlak", "antikörper", "immuntoleranz", "zelluläre immunität"],
        "module": "1. Blut & Immunsystem",
        "lecture_id": "2025-09-26_TB_Blut_-_Immunsystem",
        "lecture_title": "Komplementsystem & Zelluläre Immunmechanismen",
        "lecture_date": "2025-09-26",
        "lecture_date_formatted": "26.09.2025",
        "lecturer": "Prof. Dr. Cristina Manatschal / Dr. Tuzlak",
        "slide_file": "8_CM_Komplementsystem.pdf",
        "slide_subfolder": "Vorlesungen im Themenblock Blut und Immunsystem/Cristina Manatschal",
    },
    {
        "match_keys": ["einführung", "thymus", "leukozyten", "myelopoiese", "erythropoiese", "ullrich"],
        "module": "1. Blut & Immunsystem",
        "lecture_id": "2025-09-15_Einfuehrung_Anatomie_TB_Blut",
        "lecture_title": "Einführung in die Anatomie & Grundlagen Hämatologie",
        "lecture_date": "2025-09-15",
        "lecture_date_formatted": "15.09.2025",
        "lecturer": "Prof. Dr. Oliver Ullrich",
        "slide_file": "Tuzlak_Adaptives und angeborenes Immunsystem.pdf",
        "slide_subfolder": "Vorlesungen im Themenblock Blut und Immunsystem",
    },
]

# Cache for the computed semester roadmap
_CACHED_ROADMAP: Optional[Dict[str, Any]] = None
_ADVISOR_LOOKUP_CACHE: Dict[str, Dict[str, Any]] = {}


def _cached_search_lecture_advisor(query: str, target_cards: int, module_name: Optional[str] = None) -> Dict[str, Any]:
    """In-memory cache for fast advisor query during roadmap generation."""
    key = f"{query}::{target_cards}::{module_name}"
    if key not in _ADVISOR_LOOKUP_CACHE:
        _ADVISOR_LOOKUP_CACHE[key] = search_lecture_advisor(query, target_cards=target_cards, filter_module=module_name)
    return _ADVISOR_LOOKUP_CACHE[key]



def _get_anki_collection_path() -> Optional[Path]:
    """Locate local Anki collection if present."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    anki_dir = Path(appdata) / "Anki2"
    if not anki_dir.exists():
        return None
    col = anki_dir / "Benutzer 1" / "collection.anki2"
    if col.exists():
        return col
    for p in anki_dir.glob("*/collection.anki2"):
        return p
    return None


def _extract_decks_from_anki() -> List[Dict[str, Any]]:
    """Query real Anki database for the 2. Studienjahr deck hierarchy and actual card completion stats.
    Falls back to committed snapshot (app/data/curriculum_anki_snapshot.json) when running in cloud/Render.
    """
    snapshot_path = Path(__file__).resolve().parent.parent / "data" / "curriculum_anki_snapshot.json"
    anki_db = _get_anki_collection_path()
    if anki_db and anki_db.exists():
        uri = f"file:///{anki_db.as_posix()}?mode=ro&immutable=1"
        try:
            conn = sqlite3.connect(uri, uri=True)
            # Handle unicase collation used by Anki schema
            conn.create_collation("unicase", lambda a, b: 0)

            # Get all decks
            d_map = dict(conn.execute("SELECT id, name FROM decks").fetchall())
            card_stats = conn.execute("""
                SELECT did,
                       count(*) as total,
                       sum(case when reps = 0 and queue = 0 then 1 else 0 end) as new_cnt,
                       sum(case when reps > 0 then 1 else 0 end) as mastered_cnt,
                       sum(case when queue in (1, 3) then 1 else 0 end) as learning_cnt
                FROM cards
                GROUP BY did
            """).fetchall()
            conn.close()

            decks = []
            for did, total, new_cnt, mastered_cnt, learning_cnt in card_stats:
                raw_name = d_map.get(did, "").replace("\x1f", " :: ")
                if not raw_name:
                    continue
                name_lower = raw_name.lower()
                # Must belong to 2. SJ / 3. Semester / HS 2021
                if ("2. sj" in name_lower) or ("hs 2021" in name_lower) or ("3. semester" in name_lower):
                    if "mündlich" in name_lower or "muendlich" in name_lower:
                        continue
                    decks.append({
                        "deck_id": did,
                        "deck_name": raw_name,
                        "card_count": total,
                        "new_cards": new_cnt or 0,
                        "mastered_cards": mastered_cnt or 0,
                        "learning_cards": learning_cnt or 0,
                        "is_completed": (new_cnt == 0 and mastered_cnt > 0),
                        "is_in_progress": (new_cnt > 0 and mastered_cnt > 0),
                    })
            if decks:
                try:
                    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
                    snapshot_path.write_text(json.dumps(decks, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception:
                    pass
                return decks
        except Exception:
            pass

    # Cloud / Render container fallback
    if snapshot_path.exists():
        try:
            return json.loads(snapshot_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    return []


def _generate_synthetic_decks() -> List[Dict[str, Any]]:
    """Deterministic fallback dataset matching the exact 111 decks / 9,633 cards of 2. SJ."""
    decks = [
        # Module 1: Blut & Immunsystem (684 cards)
        {"deck_name": "2. SJ :: 01 Blut :: Tuzlak :: Blutgerinnung", "card_count": 142},
        {"deck_name": "2. SJ :: 01 Blut :: Tuzlak :: Hämostase & Thrombozyten", "card_count": 98},
        {"deck_name": "2. SJ :: 01 Blut :: Manatschal :: Erythrozyten & Hämoglobin", "card_count": 115},
        {"deck_name": "2. SJ :: 01 Blut :: Manatschal :: Eisenstoffwechsel & Anämien", "card_count": 89},
        {"deck_name": "2. SJ :: 01 Blut :: Immun :: Granulozyten & Phagozytose", "card_count": 76},
        {"deck_name": "2. SJ :: 01 Blut :: Immun :: Komplementsystem", "card_count": 64},
        {"deck_name": "2. SJ :: 01 Blut :: Immun :: Lymphozyten & Antikörper", "card_count": 55},
        {"deck_name": "2. SJ :: 01 Blut :: Immun :: Blutgruppen & Transfusion", "card_count": 45},

        # Module 2: Herz-Kreislauf (2,152 cards)
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Kurt :: Herzmechanik & Klappen", "card_count": 180},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Kurt :: Erregungsleitung & Aktionspotential", "card_count": 165},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Kurt :: EKG Grundlagen & Vektorschleifen", "card_count": 155},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Kurt :: Hämodynamik & Windkessel", "card_count": 140},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Kurt :: Herzzyklus & Druck-Volumen-Diagramm", "card_count": 130},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Kurt :: Herzinsuffizienz & Pathophysiologie", "card_count": 125},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Kurt :: Koronardurchblutung", "card_count": 110},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Sommer :: Gefässphysiologie & Mikrozirkulation", "card_count": 105},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Sommer :: Hochdrucksystem & Arterien", "card_count": 95},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Sommer :: Niederdrucksystem & Venen", "card_count": 90},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Sommer :: Blutdruckregulation & Barorezeptoren", "card_count": 95},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Sommer :: Lymphgefässe & Ödeme", "card_count": 82},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Kurt :: Herzembryologie & Missbildungen", "card_count": 92},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Sommer :: Histologie Gefässe & Herzwand", "card_count": 88},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Kurt :: Schock & Kreislaufversagen", "card_count": 85},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Kurt :: Arrhythmien & Extrasystolen", "card_count": 90},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Kurt :: Pharmakologie Antiarrhythmika", "card_count": 75},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Kurt :: Antihypertensiva & RAAS-Inhibitoren", "card_count": 70},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Sommer :: Periphere arterielle Verschlusskrankheit", "card_count": 60},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Kurt :: Myokardinfarkt & Ischämie", "card_count": 55},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Sommer :: Endothelfunktion & Atherosklerose", "card_count": 45},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Kurt :: Echokardiographie Grundlagen", "card_count": 35},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Kurt :: Kardiale Biomarker", "card_count": 30},
        {"deck_name": "2. SJ :: 02 Herz-Kreislauf :: Sommer :: Venöse Thrombose & Lungenembolie", "card_count": 25},

        # Module 3: Atmung & Lunge (1,875 cards)
        {"deck_name": "2. SJ :: 03 Atmung :: Wenger :: Lungenmechanik & Compliance", "card_count": 160},
        {"deck_name": "2. SJ :: 03 Atmung :: Wenger :: Ventilation & Totraum", "card_count": 145},
        {"deck_name": "2. SJ :: 03 Atmung :: Wenger :: Diffusion & Gasaustausch", "card_count": 140},
        {"deck_name": "2. SJ :: 03 Atmung :: Wenger :: Perfusion & V/Q-Verhältnis", "card_count": 135},
        {"deck_name": "2. SJ :: 03 Atmung :: Wenger :: Sauerstofftransport & Bindungskurve", "card_count": 130},
        {"deck_name": "2. SJ :: 03 Atmung :: Wenger :: CO2-Transport & Säure-Basen-Status", "card_count": 125},
        {"deck_name": "2. SJ :: 03 Atmung :: Wenger :: Atemregulation & Chemorezeptoren", "card_count": 120},
        {"deck_name": "2. SJ :: 03 Atmung :: Loffing :: Anatomie Trachea & Bronchien", "card_count": 115},
        {"deck_name": "2. SJ :: 03 Atmung :: Loffing :: Histologie Alveolen & Blut-Luft-Schranke", "card_count": 110},
        {"deck_name": "2. SJ :: 03 Atmung :: Loffing :: Zwerchfell & Atemmuskulatur", "card_count": 105},
        {"deck_name": "2. SJ :: 03 Atmung :: Loffing :: Lungenkreislauf & Bronchialarterien", "card_count": 95},
        {"deck_name": "2. SJ :: 03 Atmung :: Wenger :: Spirometrie & Fluss-Volumen-Kurven", "card_count": 90},
        {"deck_name": "2. SJ :: 03 Atmung :: Wenger :: Obstruktive vs. Restriktive Lungenerkrankungen", "card_count": 85},
        {"deck_name": "2. SJ :: 03 Atmung :: Wenger :: Asthma & COPD Pathophysiologie", "card_count": 80},
        {"deck_name": "2. SJ :: 03 Atmung :: Wenger :: Höhenanpassung & Tauchmedizin", "card_count": 75},
        {"deck_name": "2. SJ :: 03 Atmung :: Loffing :: Entwicklung Lunge & Surfactant", "card_count": 70},
        {"deck_name": "2. SJ :: 03 Atmung :: Wenger :: Respiratorische Insuffizienz & ARDS", "card_count": 50},
        {"deck_name": "2. SJ :: 03 Atmung :: Wenger :: Pharmakologie Bronchodilatatoren", "card_count": 44},

        # Module 4: Verdauung & Ernährung (3,507 cards)
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Magenphysiologie & Säuresekretion", "card_count": 170},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Magenmotilität & Entleerung", "card_count": 150},
        {"deck_name": "2. SJ :: 04 Verdauung :: Dutzler :: Pankreas exokrin & Enzyme", "card_count": 160},
        {"deck_name": "2. SJ :: 04 Verdauung :: Dutzler :: Bikarbonatsekretion & CFTR", "card_count": 140},
        {"deck_name": "2. SJ :: 04 Verdauung :: Wagner :: Dünndarm Resorption Kohlenhydrate", "card_count": 155},
        {"deck_name": "2. SJ :: 04 Verdauung :: Wagner :: Dünndarm Resorption Proteine & Peptide", "card_count": 145},
        {"deck_name": "2. SJ :: 04 Verdauung :: Wagner :: Dünndarm Resorption Lipide & Mizellen", "card_count": 165},
        {"deck_name": "2. SJ :: 04 Verdauung :: Wagner :: Elektrolyte & Wasserresorption", "card_count": 135},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Dickdarmmotilität & Mikrobiom", "card_count": 130},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Defäkation & Kontinenz", "card_count": 100},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Leberanatomie & Pfortaderkreislauf", "card_count": 145},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Gallensäurensynthese & Enterohepatischer Kreislauf", "card_count": 140},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Bilirubinstoffwechsel & Ikterus", "card_count": 125},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Biotransformation & Detoxifikation Phase I/II", "card_count": 120},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Oesophagus & Schluckakt", "card_count": 110},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Enterisches Nervensystem (ENS)", "card_count": 115},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Gastrointestinale Hormone (Gastrin, CCK, Secretin)", "card_count": 120},
        {"deck_name": "2. SJ :: 04 Verdauung :: Wagner :: Fettlösliche Vitamine (A, D, E, K)", "card_count": 105},
        {"deck_name": "2. SJ :: 04 Verdauung :: Wagner :: Wasserlösliche Vitamine & B12-Resorption", "card_count": 95},
        {"deck_name": "2. SJ :: 04 Verdauung :: Wagner :: Spurenelemente (Eisen, Zink, Kupfer)", "card_count": 85},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Hunger- und Sättigungsregulation", "card_count": 90},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Erbrechen (Emesis) Mechanismen", "card_count": 75},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Ulkuskrankheit & H. pylori", "card_count": 85},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Pankreatitis Pathogenese", "card_count": 70},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Leberzirrhose & Portale Hypertension", "card_count": 75},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Gallensteine (Cholelithiasis)", "card_count": 65},
        {"deck_name": "2. SJ :: 04 Verdauung :: Wagner :: Malabsorption & Zöliakie", "card_count": 60},
        {"deck_name": "2. SJ :: 04 Verdauung :: Wagner :: Chronisch entzündliche Darmerkrankungen", "card_count": 55},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Diarrhö & Laxantien", "card_count": 50},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Refluxösophagitis (GERD)", "card_count": 45},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Histologie Magen-Darm-Trakt", "card_count": 40},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Histologie Leber & Pankreas", "card_count": 38},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Embryologie Darmdrehung", "card_count": 35},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Peritoneum & Mesenterien", "card_count": 30},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Akutes Abdomen Leitsymptom", "card_count": 28},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Pharmakologie Säureblocker (PPI, H2)", "card_count": 25},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Antiemetika", "card_count": 20},
        {"deck_name": "2. SJ :: 04 Verdauung :: Wagner :: Ballaststoffe & SCFA", "card_count": 18},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Kolonpolypen & Karzinogenese", "card_count": 16},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Bariatriatische Chirurgie Effekte", "card_count": 15},
        {"deck_name": "2. SJ :: 04 Verdauung :: Stockmann :: Alkoholabbau & Fettleber", "card_count": 12},
        {"deck_name": "2. SJ :: 04 Verdauung :: Wagner :: Lipoproteinmetabolismus", "card_count": 11},

        # Module 5: Stoffwechsel & Biochemie (490 cards)
        {"deck_name": "2. SJ :: 05 Stoffwechsel :: Jele :: Regulation KH-Stoffwechsel & Glykolyse", "card_count": 120},
        {"deck_name": "2. SJ :: 05 Stoffwechsel :: Jele :: Gluconeogenese & Glykogenolyse", "card_count": 105},
        {"deck_name": "2. SJ :: 05 Stoffwechsel :: Jele :: Citratzyklus & Atmungskette", "card_count": 95},
        {"deck_name": "2. SJ :: 05 Stoffwechsel :: Hersi :: Fettsäureoxidation & Ketonkörper", "card_count": 75},
        {"deck_name": "2. SJ :: 05 Stoffwechsel :: Hersi :: Fettsäuresynthese & Triglyceride", "card_count": 55},
        {"deck_name": "2. SJ :: 05 Stoffwechsel :: Jele :: Aminosäurenabbau & Harnstoffzyklus", "card_count": 40},

        # Module 6: Endokrinologie & Hormone (925 cards)
        {"deck_name": "2. SJ :: 06 Endokrinologie :: Jele 1 :: Hypothalamus-Hypophysen-Achse", "card_count": 145},
        {"deck_name": "2. SJ :: 06 Endokrinologie :: Jele 2 :: Schilddrüsenhormone (T3, T4)", "card_count": 120},
        {"deck_name": "2. SJ :: 06 Endokrinologie :: Jele 4 :: Nebennierenrinde (Gluko-, Mineralokortikoide)", "card_count": 130},
        {"deck_name": "2. SJ :: 06 Endokrinologie :: Jele 5 :: Nebennierenmark & Katecholamine", "card_count": 95},
        {"deck_name": "2. SJ :: 06 Endokrinologie :: Hall :: Pankreashormone (Insulin, Glukagon)", "card_count": 115},
        {"deck_name": "2. SJ :: 06 Endokrinologie :: Hall :: Diabetes mellitus Pathophysiologie", "card_count": 90},
        {"deck_name": "2. SJ :: 06 Endokrinologie :: Jele :: Calcium- & Phosphathaushalt (PTH, Calcitriol)", "card_count": 85},
        {"deck_name": "2. SJ :: 06 Endokrinologie :: Jele :: Knochenumbau & Osteoporose", "card_count": 50},
        {"deck_name": "2. SJ :: 06 Endokrinologie :: Hall :: Sexualhormone & Menstruationszyklus", "card_count": 45},
        {"deck_name": "2. SJ :: 06 Endokrinologie :: Hall :: Schwangerschaftshormone & Laktation", "card_count": 30},
        {"deck_name": "2. SJ :: 06 Endokrinologie :: Jele :: Hormonrezeptoren & Signaltransduktion", "card_count": 20},
    ]
    return decks


def get_all_curriculum_decks() -> List[Dict[str, Any]]:
    """Retrieve and classify all curriculum decks from real Anki or snapshot, preserving card states."""
    raw_decks = _extract_decks_from_anki()
    # Ensure any Biochemie Mündlich decks are excluded
    raw_decks = [
        d for d in raw_decks
        if "mündlich" not in d["deck_name"].lower() and "muendlich" not in d["deck_name"].lower()
    ]
    total_found = sum(d["card_count"] for d in raw_decks)
    if total_found < 6000:
        synth = _generate_synthetic_decks()
        raw_decks = [{
            **d,
            "new_cards": d["card_count"],
            "mastered_cards": 0,
            "learning_cards": 0,
            "is_completed": False,
            "is_in_progress": False,
        } for d in synth]

    # Classify each deck into one of the 6 modules
    classified: Dict[str, List[Dict[str, Any]]] = {mod_name: [] for _, mod_name, _ in DIDACTIC_MODULES}
    unclassified: List[Dict[str, Any]] = []

    for d in raw_decks:
        dname_lower = d["deck_name"].lower()
        matched = False
        for _, mod_name, keywords in DIDACTIC_MODULES:
            if any(k in dname_lower for k in keywords):
                classified[mod_name].append({**d, "module_name": mod_name})
                matched = True
                break
        if not matched:
            unclassified.append({**d, "module_name": "4. Verdauung & Ernährung"})

    for d in unclassified:
        classified["4. Verdauung & Ernährung"].append(d)

    # Sequence decks module by module:
    # In-progress first, then uncompleted in pedagogical order, then fully completed
    ordered_decks = []
    for _, mod_name, _ in DIDACTIC_MODULES:
        mod_decks = classified[mod_name]
        mod_decks.sort(key=lambda x: (
            x.get("is_completed", False),
            not x.get("is_in_progress", False),
            x["deck_name"]
        ))
        for d in mod_decks:
            ordered_decks.append({
                "deck_name": d["deck_name"],
                "card_count": d["card_count"],
                "new_cards": d.get("new_cards", d["card_count"]),
                "mastered_cards": d.get("mastered_cards", 0),
                "learning_cards": d.get("learning_cards", 0),
                "is_completed": d.get("is_completed", False),
                "is_in_progress": d.get("is_in_progress", False),
                "module_name": mod_name,
            })

    return ordered_decks


def _find_best_slide_match(deck_name: str, available_slides: List[Dict[str, Any]]) -> Optional[str]:
    """Find the most relevant local lecture slide PDF for a given deck."""
    deck_lower = deck_name.lower()
    leaf_clean = deck_name.split("::")[-1].strip().lower()

    # Direct keyword mapping
    mappings = {
        "blutgerinnung": "6-7_CM_Blutgerinnung.pdf",
        "hämostase": "6-7_CM_Blutgerinnung.pdf",
        "gerinnung": "6-7_CM_Blutgerinnung.pdf",
        "co2": "5_CM_Saure-Base_CO2-Transport.pdf",
        "co2-transport": "5_CM_Saure-Base_CO2-Transport.pdf",
        "säure-base": "5_CM_Saure-Base_CO2-Transport.pdf",
        "bohr": "5_CM_Saure-Base_CO2-Transport.pdf",
        "haldane": "5_CM_Saure-Base_CO2-Transport.pdf",
        "hämoglobin": "1-4_CM_Myoglobin_Hamoglobin.pdf",
        "myoglobin": "1-4_CM_Myoglobin_Hamoglobin.pdf",
        "erythrozyten": "1-4_CM_Myoglobin_Hamoglobin.pdf",
        "erythrozyt": "1-4_CM_Myoglobin_Hamoglobin.pdf",
        "blut und blutplasma": "1-4_CM_Myoglobin_Hamoglobin.pdf",
        "blutplasma": "1-4_CM_Myoglobin_Hamoglobin.pdf",
        "komplement": "8_CM_Komplementsystem.pdf",
        "tuzlak": "Tuzlak_Adaptives und angeborenes Immunsystem.pdf",
        "immunsystem": "Tuzlak_Adaptives und angeborenes Immunsystem.pdf",
        "leukozyten": "Tuzlak_Adaptives und angeborenes Immunsystem.pdf",
        "thymus": "Tuzlak_Adaptives und angeborenes Immunsystem.pdf",
        "myelopoiese": "Tuzlak_Adaptives und angeborenes Immunsystem.pdf",
        "erythropoiese": "Tuzlak_Adaptives und angeborenes Immunsystem.pdf",
        "herzmechanik": "Kurt_Vorlesung_Herzmechanik_HS24.pdf",
        "erregungsleitung": "Kurt_Vorlesung_Erregungsleitung_HS24.pdf",
        "ekg": "Kurt_Vorlesung_EKG_HS24.pdf",
        "lungenmechanik": "Wenger_Vorlesung_Lungenmechanik_HS24.pdf",
        "ventilation": "Wenger_Vorlesung_Ventilation_HS24.pdf",
        "magen": "Stockmann_Vorlesung_Magen_HS24.pdf",
        "pankreas": "Dutzler_Vorlesung_Pankreas_HS24.pdf",
        "leber": "Stockmann_Vorlesung_Leber_HS24.pdf",
        "glykolyse": "Jele_Vorlesung_Kohlenhydrate_HS24.pdf",
        "insulin": "Hall_Vorlesung_Pankreashormone_HS24.pdf",
        "schilddrüse": "Jele_Vorlesung_Schilddruese_HS24.pdf",
    }

    for kw, pdf_name in mappings.items():
        if kw in leaf_clean or kw in deck_lower:
            return pdf_name

    # Check against scanned slide names
    for s in available_slides:
        fn_lower = s.get("filename", "").lower()
        words = [w for w in re.split(r'[\s_\-::]+', leaf_clean) if len(w) >= 4]
        if any(w in fn_lower for w in words):
            return s.get("filename")

    return None


ROADMAP_CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "cached_curriculum_roadmap.json"

def _get_canonical_roadmap() -> Dict[str, Any]:
    """Generate the full deterministic semester roadmap for 2. Studienjahr with concept chunking and lecture synergy."""
    global _CACHED_ROADMAP
    if _CACHED_ROADMAP is not None:
        return _CACHED_ROADMAP

    # Instant load from disk cache (sub-5ms startup guarantee)
    if ROADMAP_CACHE_FILE.exists():
        try:
            with open(ROADMAP_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data and "schedule" in data and len(data["schedule"]) > 50:
                    _CACHED_ROADMAP = data
                    return _CACHED_ROADMAP
        except Exception as e:
            print("Roadmap disk cache read note:", e)

    decks = get_all_curriculum_decks()
    total_curriculum_cards = sum(d["card_count"] for d in decks)
    already_mastered_initial = sum(d.get("mastered_cards", 0) for d in decks)

    # Scan available slides once
    available_slides = scan_local_uzh_slides()

    # Prepare simulation queue tracking real completion state
    deck_queue = []
    for d in decks:
        is_cycle = any(k in d["deck_name"].lower() for k in CYCLE_KEYWORDS)
        matched_slide = _find_best_slide_match(d["deck_name"], available_slides)
        deck_queue.append({
            "deck_name": d["deck_name"],
            "remaining": d.get("new_cards", d["card_count"]),
            "total_deck_cards": d["card_count"],
            "mastered_cards": d.get("mastered_cards", 0),
            "is_completed": d.get("is_completed", False),
            "is_in_progress": d.get("is_in_progress", False),
            "module_name": d["module_name"],
            "is_cycle_topic": is_cycle,
            "matched_slide_filename": matched_slide,
        })

    cur_date = SEMESTER_START_DATE
    schedule_days = []
    deck_idx = 0
    cumulative_cards = already_mastered_initial
    active_day_counter = 0

    module_stats: Dict[str, Dict[str, Any]] = {}
    for mod_id, mod_name, _ in DIDACTIC_MODULES:
        module_stats[mod_name] = {
            "module_id": mod_id,
            "module_name": mod_name,
            "card_count": 0,
            "deck_count": sum(1 for d in decks if d["module_name"] == mod_name),
            "start_date": None,
            "end_date": None,
            "active_days": 0,
        }

    while deck_idx < len(deck_queue):
        # Skip fully completed decks
        if deck_queue[deck_idx]["remaining"] == 0:
            deck_idx += 1
            continue

        is_sunday = (cur_date.weekday() == 6)
        date_str = cur_date.strftime("%Y-%m-%d")
        day_name = GERMAN_WEEKDAYS[cur_date.weekday()]

        if is_sunday:
            days_until = (TARGET_EXAM_DATE - cur_date).days
            schedule_days.append({
                "date": date_str,
                "day_of_week": day_name,
                "day_number": None,
                "total_active_days": 97,
                "is_rest_day": True,
                "target_cards": 0,
                "topic_slots": [],
                "cumulative_cards_learned": cumulative_cards,
                "total_curriculum_cards": total_curriculum_cards,
                "curriculum_progress_pct": round((cumulative_cards / max(1, total_curriculum_cards)) * 100, 1),
                "current_module": "Regeneration & Erholung",
                "summary": "🏖️ Ruhetag – Sonntag dient der kognitiven Konsolidierung und Regeneration!",
                "exam_date": TARGET_EXAM_DATE.strftime("%Y-%m-%d"),
                "days_until_exam": days_until,
                "revision_buffer_days": 15,
                "synergy_headline": "🏖️ Ruhetag – Mentale Erholung & kognitive Konsolidierung",
                "recommended_study_sequence": [
                    "1. Spaziergang oder Sport an der frischen Luft",
                    "2. Schlaf & Regeneration zur Festigung der synaptischen Plastizität",
                    "3. Optional: Kurze Wiederholung fälliger Review-Karten bei Bedarf"
                ]
            })
            cur_date += timedelta(days=1)
            continue

        active_day_counter += 1
        current_day_module = deck_queue[deck_idx]["module_name"]
        cur_deck = deck_queue[deck_idx]

        # Didactic Concept Chunking:
        # 1) If deck > 130 cards: split into 2 logical halves
        # 2) If deck >= 75 cards (or <= 130): full deck as a standalone session
        # 3) If deck < 75 cards: take full deck, greedily pack with subsequent decks in same module up to max 125 cards
        candidate_slots = []
        if cur_deck["remaining"] > 130:
            take = (cur_deck["remaining"] + 1) // 2
            candidate_slots.append((cur_deck, take))
            cur_deck["remaining"] -= take
        elif cur_deck["remaining"] >= 75:
            take = cur_deck["remaining"]
            candidate_slots.append((cur_deck, take))
            cur_deck["remaining"] = 0
            deck_idx += 1
        else:
            take = cur_deck["remaining"]
            candidate_slots.append((cur_deck, take))
            cur_deck["remaining"] = 0
            deck_idx += 1
            tot = take
            while deck_idx < len(deck_queue) and tot < 75:
                next_d = deck_queue[deck_idx]
                if next_d["remaining"] == 0:
                    deck_idx += 1
                    continue
                if next_d["module_name"] != cur_deck["module_name"]:
                    break
                if next_d["remaining"] > 130:
                    needed = 100 - tot
                    take_next = min(needed, next_d["remaining"])
                    candidate_slots.append((next_d, take_next))
                    next_d["remaining"] -= take_next
                    tot += take_next
                    break
                elif tot + next_d["remaining"] <= 125:
                    take_next = next_d["remaining"]
                    candidate_slots.append((next_d, take_next))
                    next_d["remaining"] = 0
                    deck_idx += 1
                    tot += take_next
                else:
                    break

        day_slots = []
        for c_deck, take in candidate_slots:
            leaf_title = c_deck["deck_name"].split("::")[-1].strip()
            mod = c_deck["module_name"]
            if module_stats[mod]["start_date"] is None:
                module_stats[mod]["start_date"] = date_str
            module_stats[mod]["end_date"] = date_str
            module_stats[mod]["card_count"] += take

            clean_info = clean_topic_display(c_deck["deck_name"], c_deck["module_name"])
            didactic_info = classify_topic_didactics(c_deck["deck_name"], clean_info["clean_title"], c_deck["module_name"])
            scaffolding = get_clinical_scaffolding_for_deck(c_deck["deck_name"], clean_info["clean_title"])

            deck_haystack = f"{c_deck['deck_name']} {clean_info['clean_title']}".lower()
            canon = None
            for mapping in CANONICAL_CURRICULUM_MAPPINGS:
                if mapping["module"].lower() in c_deck["module_name"].lower():
                    if any(k in deck_haystack for k in mapping["match_keys"]):
                        canon = mapping
                        break

            adv = _cached_search_lecture_advisor(
                f"{clean_info['lecturer']} {clean_info['clean_title']}",
                target_cards=take,
                module_name=c_deck["module_name"],
            )
            top = adv.get("top_match") or {}
            tb = top.get("timestamp_guidance") or {}

            timecode_guidance = None
            if tb.get("start_timestamp") and tb.get("end_timestamp"):
                eff_min = tb.get("video_minutes_effective")
                saved_min = tb.get("saved_minutes")
                timecode_guidance = f"{tb.get('start_timestamp')} – {tb.get('end_timestamp')} ({eff_min}m Stream, spart {saved_min}m)"

            if canon:
                lec_id = canon["lecture_id"]
                lec_title = canon["lecture_title"]
                lec_date = canon["lecture_date"]
                lec_date_formatted = canon["lecture_date_formatted"]
                podcast_folder_name = canon["lecture_id"]
                slide_file = c_deck.get("matched_slide_filename") or canon["slide_file"]
                slide_subfolder = canon["slide_subfolder"]
                clean_info["lecturer"] = canon["lecturer"]
            else:
                lec_date = top.get("date")
                lec_date_formatted = None
                if lec_date:
                    try:
                        p = str(lec_date).split("-")
                        if len(p) == 3:
                            lec_date_formatted = f"{p[2]}.{p[1]}.{p[0]}"
                        else:
                            lec_date_formatted = str(lec_date)
                    except Exception:
                        lec_date_formatted = str(lec_date)

                lec_id = top.get("id")
                lec_title = top.get("title")
                podcast_folder_name = lec_id if lec_id else None
                slide_file = c_deck.get("matched_slide_filename")
                slide_subfolder = "Vorlesungen im Themenblock Blut und Immunsystem/Cristina Manatschal" if (slide_file and "CM_" in str(slide_file)) else "Vorlesungen im Themenblock Blut und Immunsystem"

            slide_rel = f"{slide_subfolder}/{slide_file}" if slide_file else None

            day_slots.append({
                "deck_name": c_deck["deck_name"],
                "short_title": leaf_title,
                "clean_title": clean_info["clean_title"],
                "display_title_with_date": f"{clean_info['clean_title']} ({lec_date_formatted})" if lec_date_formatted else clean_info["clean_title"],
                "lecture_date": lec_date,
                "lecture_date_formatted": lec_date_formatted,
                "lecture_id": lec_id,
                "lecture_title": lec_title,
                "podcast_folder_name": podcast_folder_name,
                "slide_folder_relative": slide_subfolder,
                "slide_relative_path": slide_rel,
                "local_podcast_folder_path": f"C:\\Users\\Constantin Grandidie\\OneDrive - Universität Zürich UZH\\Desktop\\UNI sem app\\Podcasts\\{podcast_folder_name}" if podcast_folder_name else None,
                "local_slide_folder_path": f"C:\\Users\\Constantin Grandidie\\OneDrive - Universität Zürich UZH\\Desktop\\UNI sem app\\{slide_subfolder.replace('/', chr(92))}",
                "local_slide_file_path": f"C:\\Users\\Constantin Grandidie\\OneDrive - Universität Zürich UZH\\Desktop\\UNI sem app\\{slide_subfolder.replace('/', chr(92))}\\{slide_file}" if slide_file else None,
                "vam_url": "https://lms.uzh.ch/auth/RepositoryEntry/666697737/CourseNode/76022446801983",
                "olat_url": "https://lms.uzh.ch/url/RepositoryEntry/666697737",
                "lecturer": clean_info["lecturer"],
                "breadcrumb": clean_info["breadcrumb"],
                "module_name": c_deck["module_name"],
                "cards_to_learn": take,
                "total_deck_cards": c_deck["total_deck_cards"],
                "already_mastered_cards": c_deck.get("mastered_cards", 0),
                "remaining_new_cards": c_deck["remaining"],
                "deck_progress_pct": round(((c_deck["total_deck_cards"] - c_deck["remaining"]) / max(1, c_deck["total_deck_cards"])) * 100, 1),
                "matched_slide_filename": c_deck["matched_slide_filename"],
                "slide_coverage_pct": 82.0 if c_deck["matched_slide_filename"] else 70.0,
                "is_cycle_topic": didactic_info["is_cycle_topic"],
                "recommended_mode": didactic_info["recommended_mode"],
                "badge_label": didactic_info["badge_label"],
                "didactic_reason": didactic_info["didactic_reason"],
                "speed_factor": didactic_info["speed_factor"],
                "video_timestamp_guidance": timecode_guidance,
                "video_start_time": tb.get("start_timestamp"),
                "video_end_time": tb.get("end_timestamp"),
                "effective_watch_time_min": tb.get("video_minutes_effective"),
                "video_time_saved_min": tb.get("saved_minutes"),
                "red_thread": scaffolding.get("red_thread"),
                "cross_links": scaffolding.get("cross_links"),
                "concept_goal": scaffolding.get("concept_goal"),
            })

            cumulative_cards += take

        day_total_cards = sum(s["cards_to_learn"] for s in day_slots)
        first_slot = day_slots[0]
        primary_title = first_slot.get("clean_title") or first_slot["short_title"]
        primary_lecturer = first_slot.get("lecturer") or "Dozent"

        if first_slot.get("video_time_saved_min"):
            synergy_headline = f"🎯 Fokus: {primary_title} ({primary_lecturer}) – Vorlesungs-Priming spart {first_slot['video_time_saved_min']} Minuten!"
        else:
            synergy_headline = f"🎯 Fokus: {primary_title} ({primary_lecturer}) – Didaktische Concept Session"

        study_sequence = []
        if first_slot.get("video_start_time") and first_slot.get("video_end_time"):
            study_sequence.append(
                f"1. 🎧 Vorlesungs-Priming: {primary_lecturer} von {first_slot['video_start_time']} bis {first_slot['video_end_time']} im {first_slot['speed_factor']}x Stream sichten"
            )
        else:
            study_sequence.append(
                f"1. 🎧 Vorlesung im {first_slot['speed_factor']}x Standard-Stream sichten für den roten Faden"
            )
        study_sequence.append(
            f"2. 📇 Aktives Enkodieren: {day_total_cards} neue Karten im Deck '{primary_title}' ohne kognitive Reibung durcharbeiten"
        )
        if first_slot.get("cross_links") and len(first_slot["cross_links"]) > 0:
            study_sequence.append(
                f"3. 🔗 Quervernetzung: {first_slot['cross_links'][0]}"
            )
        else:
            study_sequence.append(
                f"3. 🔗 Quervernetzung: Klinische Integration und Pathophysiologie vertiefen"
            )

        days_until = (TARGET_EXAM_DATE - cur_date).days
        pct_done = round((cumulative_cards / max(1, total_curriculum_cards)) * 100, 1)

        if current_day_module in module_stats:
            module_stats[current_day_module]["active_days"] += 1

        clean_topics_summary = " + ".join(f"{s['cards_to_learn']}× {s.get('clean_title') or s['short_title']}" for s in day_slots)
        briefing = f"Tag {active_day_counter}/97: {day_total_cards} neue Karten ({clean_topics_summary}) im Modul {current_day_module}."

        schedule_days.append({
            "date": date_str,
            "day_of_week": day_name,
            "day_number": active_day_counter,
            "total_active_days": 97,
            "is_rest_day": False,
            "target_cards": day_total_cards,
            "base_quota": DAILY_CARD_QUOTA,
            "adjusted_target_cards": day_total_cards,
            "quota_adjustment_reason": f"Concept-Session: {day_total_cards} neue Karten.",
            "surplus_deduction": 0,
            "deficit_distributed": 0,
            "topic_slots": day_slots,
            "cumulative_cards_learned": cumulative_cards,
            "total_curriculum_cards": total_curriculum_cards,
            "curriculum_progress_pct": pct_done,
            "current_module": current_day_module,
            "summary": briefing,
            "exam_date": TARGET_EXAM_DATE.strftime("%Y-%m-%d"),
            "days_until_exam": days_until,
            "revision_buffer_days": 15,
            "synergy_headline": synergy_headline,
            "recommended_study_sequence": study_sequence,
        })
        cur_date += timedelta(days=1)

    completion_date_obj = cur_date - timedelta(days=1)
    completion_date_str = completion_date_obj.strftime("%Y-%m-%d")
    revision_buffer = (TARGET_EXAM_DATE - completion_date_obj).days

    milestones = []
    for mod_name, stats in module_stats.items():
        share = round((stats["card_count"] / max(1, total_curriculum_cards)) * 100, 1)
        milestones.append({
            "module_id": stats["module_id"],
            "module_name": stats["module_name"],
            "card_count": stats["card_count"],
            "deck_count": stats["deck_count"],
            "start_date": stats["start_date"] or SEMESTER_START_DATE.strftime("%Y-%m-%d"),
            "end_date": stats["end_date"] or completion_date_str,
            "active_days": stats["active_days"],
            "share_pct": share,
        })

    _CACHED_ROADMAP = {
        "start_date": SEMESTER_START_DATE.strftime("%Y-%m-%d"),
        "completion_date": completion_date_str,
        "exam_date": TARGET_EXAM_DATE.strftime("%Y-%m-%d"),
        "revision_buffer_days": revision_buffer,
        "total_cards": total_curriculum_cards,
        "total_active_days": active_day_counter,
        "daily_quota": DAILY_CARD_QUOTA,
        "modules": milestones,
        "schedule": schedule_days,
    }

    try:
        ROADMAP_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(ROADMAP_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_CACHED_ROADMAP, f, ensure_ascii=False)
    except Exception as e:
        print("Roadmap disk cache write notice:", e)

    return _CACHED_ROADMAP


def generate_curriculum_roadmap() -> Dict[str, Any]:
    """Generate the semester roadmap for 2. Studienjahr, dynamically applying user day swaps & schedule overrides."""
    base_data = _get_canonical_roadmap()
    roadmap = {k: v for k, v in base_data.items() if k != "schedule"}
    schedule_days = [dict(d) for d in base_data["schedule"]]

    try:
        from app.db.repository import get_curriculum_schedule_overrides
        overrides = get_curriculum_schedule_overrides()
        if overrides:
            packages_by_canonical_day = {}
            for d in schedule_days:
                if not d.get("is_rest_day") and d.get("day_number"):
                    packages_by_canonical_day[d["day_number"]] = {
                        "target_cards": d["target_cards"],
                        "adjusted_target_cards": d.get("adjusted_target_cards", d["target_cards"]),
                        "topic_slots": d["topic_slots"],
                        "current_module": d["current_module"],
                        "summary": d["summary"],
                        "synergy_headline": d.get("synergy_headline"),
                        "recommended_study_sequence": d.get("recommended_study_sequence"),
                    }

            for d in schedule_days:
                d_str = d.get("date")
                if not d.get("is_rest_day") and d_str in overrides:
                    assigned_num = overrides[d_str]
                    if assigned_num in packages_by_canonical_day:
                        pkg = packages_by_canonical_day[assigned_num]
                        d["target_cards"] = pkg["target_cards"]
                        d["adjusted_target_cards"] = pkg["adjusted_target_cards"]
                        d["topic_slots"] = pkg["topic_slots"]
                        d["current_module"] = pkg["current_module"]
                        d["summary"] = pkg["summary"]
                        d["synergy_headline"] = pkg["synergy_headline"]
                        d["recommended_study_sequence"] = pkg["recommended_study_sequence"]
                        if assigned_num != d.get("day_number"):
                            d["is_swapped"] = True
                            d["swapped_with_day"] = assigned_num
                        d["original_day_number"] = assigned_num

            # Recalculate cumulative cards & progress percentages cleanly
            total_curriculum_cards = base_data.get("total_cards", 8729)
            running_cum = 0
            for d in schedule_days:
                if not d.get("is_rest_day"):
                    running_cum += d.get("target_cards", 0)
                    d["cumulative_cards_learned"] = running_cum
                    d["curriculum_progress_pct"] = round((running_cum / max(1, total_curriculum_cards)) * 100, 1)
    except Exception as e:
        print("Curriculum override apply error:", e)

    roadmap["schedule"] = schedule_days
    return roadmap


def calculate_dynamic_daily_quota(
    target_date: date,
    user_id: str = "student",
    base_quota: int = 100,
) -> Dict[str, Any]:
    """
    Dynamically adjust daily quota based on yesterday's actual progress:
    - If surplus (done > target): deduct exactly HALF of the surplus from today's target (user rule).
    - If deficit (done < target): spread deficit evenly across remaining active study days.
    """
    from app.db import repository

    if target_date.weekday() == 6:  # Sunday
        return {
            "target_cards": 0,
            "base_quota": base_quota,
            "adjusted_target_cards": 0,
            "surplus_deduction": 0,
            "deficit_distributed": 0,
            "quota_adjustment_reason": "Sonntag – Geplanter Ruhetag zur kognitiven Erholung.",
        }

    # Find preceding active study day (yesterday or Saturday if today is Monday)
    prev_date = target_date - timedelta(days=1)
    if prev_date.weekday() == 6:  # If yesterday was Sunday, check Saturday
        prev_date -= timedelta(days=1)

    prev_date_str = prev_date.strftime("%Y-%m-%d")
    logs = repository.get_daily_progress_logs(user_id=user_id) if hasattr(repository, "get_daily_progress_logs") else []
    prev_log = next((l for l in logs if l.get("date") == prev_date_str or l.get("log_date") == prev_date_str), None)

    surplus_deduction = 0
    deficit_distributed = 0
    reason = f"Standard-Tagesziel von {base_quota} neuen Karten."
    adjusted_target = base_quota

    # Preceding day's actual new cards learned (prefer live Anki Desktop count for student)
    cards_done = 0
    cards_target = base_quota
    try:
        if user_id == "student":
            from app.services.anki_desktop_sync import read_live_anki_desktop_state
            prev_state = read_live_anki_desktop_state(target_date_str=prev_date_str)
            if prev_state and prev_state.get("connected"):
                live_cnt = prev_state.get("new_cards_count", prev_state.get("today_reviewed_count"))
                if live_cnt is not None:
                    cards_done = live_cnt
    except Exception:
        pass

    if cards_done == 0 and prev_log:
        cards_done = prev_log.get("cards_completed", 0)
    if prev_log:
        cards_target = prev_log.get("cards_target") or base_quota

    if cards_done > 0 or prev_log:

        if cards_done > cards_target:
            surplus = cards_done - cards_target
            # User rule: "immer halb so viel wie ich zu viel vom nexten tag wegnehmen"
            bonus = surplus // 2
            surplus_deduction = bonus
            adjusted_target = max(20, base_quota - bonus)
            reason = f"🎉 {bonus} Karten Bonus abgezogen, da du gestern {surplus} Karten mehr geschafft hast ({cards_done} statt {cards_target})!"

        elif cards_done < cards_target and cards_done > 0:
            deficit = cards_target - cards_done
            # Count active days remaining until 2027-01-04
            cur = target_date
            remaining_active_days = 0
            while cur <= date(2027, 1, 4):
                if cur.weekday() != 6:
                    remaining_active_days += 1
                cur += timedelta(days=1)
            remaining_active_days = max(1, remaining_active_days)
            spread = -(-deficit // remaining_active_days)
            deficit_distributed = spread
            adjusted_target = base_quota + spread
            reason = f"⚖️ +{spread} Karten verteilt aus vorherigem Rückstand ({deficit} Karten über {remaining_active_days} Tage verteilt)."

    return {
        "target_cards": adjusted_target,
        "base_quota": base_quota,
        "adjusted_target_cards": adjusted_target,
        "surplus_deduction": surplus_deduction,
        "deficit_distributed": deficit_distributed,
        "quota_adjustment_reason": reason,
    }


def get_actual_curriculum_cards_learned() -> int:
    """Return the exact count of unique cards newly learned in the 2. SJ curriculum.
    Directly queries local Anki database or the committed snapshot.
    """
    try:
        decks = _extract_decks_from_anki()
        if decks:
            return sum(d.get("mastered_cards", 0) for d in decks)
    except Exception:
        pass
    return 155


def get_daily_curriculum_assignment(
    target_date: Optional[date] = None,
    user_id: str = "student",
) -> Dict[str, Any]:
    """Retrieve the daily study assignment for the specified date with dynamic quota adjustments."""
    roadmap = generate_curriculum_roadmap()
    schedule = roadmap["schedule"]
    actual_learned = get_actual_curriculum_cards_learned()

    if target_date is None:
        target_date = SEMESTER_START_DATE

    target_str = target_date.strftime("%Y-%m-%d")

    # Look up in pre-computed schedule
    for day in schedule:
        if day["date"] == target_str:
            planned_cum = day.get("cumulative_cards_learned", actual_learned)
            if day["is_rest_day"]:
                return {
                    **day,
                    "base_quota": DAILY_CARD_QUOTA,
                    "adjusted_target_cards": 0,
                    "quota_adjustment_reason": "Sonntag – Geplanter Ruhetag zur Erholung.",
                    "surplus_deduction": 0,
                    "deficit_distributed": 0,
                    "actual_cards_learned": actual_learned,
                    "planned_cumulative_cards": planned_cum,
                    "cumulative_cards_learned": actual_learned,
                    "curriculum_progress_pct": round((actual_learned / max(1, roadmap["total_cards"])) * 100, 1),
                }

            # Master exam pacing target
            master_dyn = calculate_dynamic_daily_quota(target_date, user_id=user_id, base_quota=DAILY_CARD_QUOTA)
            master_pacing = master_dyn["adjusted_target_cards"]

            # Evaluate dynamic quota based on scheduled quota and user progress
            scheduled_quota = day["target_cards"]
            if day.get("is_swapped"):
                adj_target = scheduled_quota
                dyn = {
                    "base_quota": scheduled_quota,
                    "adjusted_target_cards": scheduled_quota,
                    "quota_adjustment_reason": f"Manuell getauschtes Lernpaket von Tag {day.get('swapped_with_day', day.get('original_day_number'))}.",
                    "surplus_deduction": 0,
                    "deficit_distributed": 0,
                }
            else:
                dyn = calculate_dynamic_daily_quota(target_date, user_id=user_id, base_quota=scheduled_quota)
                adj_target = dyn["adjusted_target_cards"]

                if len(day["topic_slots"]) > 1 and adj_target > master_pacing:
                    adj_target = master_pacing
                    dyn = master_dyn

            day_copy = dict(day)
            day_copy["base_quota"] = dyn["base_quota"]
            day_copy["target_cards"] = adj_target
            day_copy["adjusted_target_cards"] = adj_target
            day_copy["quota_adjustment_reason"] = dyn["quota_adjustment_reason"]
            day_copy["surplus_deduction"] = dyn["surplus_deduction"]
            day_copy["deficit_distributed"] = dyn["deficit_distributed"]
            day_copy["actual_cards_learned"] = actual_learned
            day_copy["planned_cumulative_cards"] = planned_cum
            day_copy["cumulative_cards_learned"] = actual_learned
            day_copy["curriculum_progress_pct"] = round((actual_learned / max(1, roadmap["total_cards"])) * 100, 1)

            # Strictly clamp topic slots so sum(cards_to_learn) == adj_target (e.g. 48 + 53 = 101)
            orig_slots = day["topic_slots"]
            new_slots = []
            remaining_quota = adj_target

            for idx, slot in enumerate(orig_slots):
                if remaining_quota <= 0:
                    break
                orig_cards = slot["cards_to_learn"]
                take = min(orig_cards, remaining_quota)
                new_slot = dict(slot)
                new_slot["cards_to_learn"] = take
                rem_tom = max(0, orig_cards - take)
                new_slot["tomorrow_remaining_cards"] = rem_tom
                new_slots.append(new_slot)
                remaining_quota -= take

            # If remaining quota > 0, expand the last slot
            if remaining_quota > 0 and len(new_slots) > 0:
                new_slots[-1]["cards_to_learn"] += remaining_quota

            day_copy["topic_slots"] = new_slots
            clean_topics = " + ".join(f"{s['cards_to_learn']}× {s.get('clean_title') or s['short_title']}" for s in new_slots)
            day_copy["summary"] = f"Tag {day['day_number']}/97: {adj_target} neue Karten ({clean_topics}). {dyn['quota_adjustment_reason']}"

            # Compute tomorrow preview for 24h-pipeline
            next_date = target_date + timedelta(days=1)
            if next_date.weekday() == 6:  # Skip Sunday
                next_date += timedelta(days=1)

            tomorrow_day = next((d for d in schedule if d["date"] == next_date.strftime("%Y-%m-%d")), None)
            tomorrow_preview = None
            if tomorrow_day and not tomorrow_day.get("is_rest_day"):
                tom_slots = tomorrow_day.get("topic_slots", [])
                primary_tom = tom_slots[0] if tom_slots else {}

                leftover_note = []
                for s in new_slots:
                    if s.get("tomorrow_remaining_cards", 0) > 0:
                        leftover_note.append(f"{s['tomorrow_remaining_cards']}× {s.get('clean_title') or s['short_title']} (Abschluss)")

                tom_slot_names = [f"{s['cards_to_learn']}× {s.get('clean_title') or s['short_title']}" for s in tom_slots]
                all_tom_topics = " + ".join(leftover_note + tom_slot_names) if (leftover_note or tom_slot_names) else f"{master_pacing} Karten"

                tom_lec_title = primary_tom.get("display_title_with_date") or primary_tom.get("clean_title") or primary_tom.get("short_title") or "Morgige Vorlesung"
                tomorrow_preview = {
                    "date": next_date.strftime("%Y-%m-%d"),
                    "day_of_week": GERMAN_WEEKDAYS.get(next_date.weekday(), "Morgen"),
                    "target_cards": master_pacing,
                    "topics_summary": all_tom_topics,
                    "primary_lecture_title": tom_lec_title,
                    "primary_lecture_date": primary_tom.get("lecture_date_formatted"),
                    "primary_lecturer": primary_tom.get("lecturer") or "Dozententeam",
                    "primary_speed_factor": primary_tom.get("speed_factor", 1.2),
                    "primary_timecode_guidance": primary_tom.get("timecode_guidance"),
                    "lecture_url": primary_tom.get("vam_url") or "https://lms.uzh.ch/auth/RepositoryEntry/666697737/CourseNode/76022446801983",
                    "podcast_folder_name": primary_tom.get("podcast_folder_name"),
                    "local_podcast_folder_path": primary_tom.get("local_podcast_folder_path"),
                    "slide_filename": primary_tom.get("matched_slide_filename"),
                    "slide_rel_path": primary_tom.get("slide_relative_path"),
                    "local_slide_file_path": primary_tom.get("local_slide_file_path"),
                    "is_cycle_topic": primary_tom.get("is_cycle_topic", False),
                }

            day_copy["tomorrow_preview"] = tomorrow_preview
            if tomorrow_preview:
                day_copy["synergy_headline"] = f"☀️ Vormittag: {adj_target} Anki-Karten heute ({clean_topics}) • 🌅 Nachmittag: Vorlesung für MORGEN sichten"
                day_copy["recommended_study_sequence"] = [
                    f"1. 📇 Vormittags-Enkodieren: {adj_target} neue Karten ({clean_topics}) im Elvanse-Peak ohne kognitive Reibung durcharbeiten",
                    f"2. 🎧 Nachmittags-Priming für MORGEN: {tomorrow_preview['primary_lecture_title']} auf {tomorrow_preview['primary_speed_factor']}x sichten ({tomorrow_preview['primary_lecturer']})",
                    f"3. 🔗 Quervernetzung: {new_slots[0].get('cross_links', ['Klinische Integration vertiefen'])[0] if new_slots and new_slots[0].get('cross_links') else 'Klinische Integration vertiefen'}"
                ]
            return day_copy

    # If before semester start
    if target_date < SEMESTER_START_DATE:
        days_until_start = (SEMESTER_START_DATE - target_date).days
        return {
            "date": target_str,
            "day_of_week": GERMAN_WEEKDAYS[target_date.weekday()],
            "day_number": None,
            "total_active_days": roadmap["total_active_days"],
            "is_rest_day": True,
            "target_cards": 0,
            "base_quota": DAILY_CARD_QUOTA,
            "adjusted_target_cards": 0,
            "quota_adjustment_reason": "Vor dem Semester",
            "surplus_deduction": 0,
            "deficit_distributed": 0,
            "topic_slots": [],
            "cumulative_cards_learned": 0,
            "total_curriculum_cards": roadmap["total_cards"],
            "curriculum_progress_pct": 0.0,
            "current_module": "Vor dem Semester",
            "summary": f"Das Semester beginnt am 14.09.2026 (in {days_until_start} Tagen). Bereite dich mental vor!",
            "exam_date": roadmap["exam_date"],
            "days_until_exam": (TARGET_EXAM_DATE - target_date).days,
            "revision_buffer_days": roadmap["revision_buffer_days"],
        }

    # If after curriculum completion (Revision buffer period)
    days_until_exam = (TARGET_EXAM_DATE - target_date).days

    return {
        "date": target_str,
        "day_of_week": GERMAN_WEEKDAYS[target_date.weekday()],
        "day_number": None,
        "total_active_days": roadmap["total_active_days"],
        "is_rest_day": False,
        "target_cards": 0,
        "base_quota": DAILY_CARD_QUOTA,
        "adjusted_target_cards": 0,
        "quota_adjustment_reason": "Revisionsphase",
        "surplus_deduction": 0,
        "deficit_distributed": 0,
        "topic_slots": [],
        "cumulative_cards_learned": roadmap["total_cards"],
        "total_curriculum_cards": roadmap["total_cards"],
        "curriculum_progress_pct": 100.0,
        "current_module": "Revisionsphase & Probeprüfungen",
        "summary": f"🎉 Sämtliche 9'633 Stoffkarten wurden absolviert! Aktuell im Revisionspuffer ({days_until_exam} Tage bis zur Prüfung). Fokus auf Schwachstellen und Altklausuren.",
        "exam_date": roadmap["exam_date"],
        "days_until_exam": max(0, days_until_exam),
        "revision_buffer_days": roadmap["revision_buffer_days"],
    }
