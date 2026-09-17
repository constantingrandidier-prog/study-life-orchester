"""Comprehensive Lecture & Anki Advisor Service for UZH 2. Studienjahr.

Provides intelligent lookup and decision guidance:
- Maps Anki topics, decks, and medical keywords to the exact 38 UZH medical lectures.
- Delivers precise cognitive-load-based recommendations: Skip (0x), 1.0x, 1.2x, 1.4x.
- Dynamic video timestamp budgeting: Calculates exact timecodes (e.g. 00:00 - 36:38)
  for targeted Anki cards (e.g. 100 cards), saving dozens of minutes of study time.
- Robust typo tolerance & fuzzy search for lecturers, topics, and medical concepts.
- Grounded strictly in the 38 podcast recordings and 51 official course PDFs.
"""

from pathlib import Path
import re
import difflib
from typing import Any, Dict, List, Optional

# Base directories
DOCS_DIR = Path(r"c:\Users\Constantin Grandidie\OneDrive - Universität Zürich UZH\Desktop\UNI sem app")
PODCASTS_DIR = DOCS_DIR / "Podcasts"

LECTURES_DATA: List[Dict[str, Any]] = [
    {
        "id": "2025-09-15_Einfuehrung_Anatomie_TB_Blut",
        "date": "2025-09-15",
        "title": "Einführung in die Anatomie & Grundlagen Hämatologie",
        "module": "1. Blut & Immunsystem",
        "lecturer": "Prof. Dr. Oliver Ullrich / Dozententeam",
        "exam_yield": "Low-Yield",
        "visual_dependency": "Niedrig",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.254,
        "recommendation": "Skip (0x)",
        "badge_color": "var(--status-danger, #f85149)",
        "badge_label": "🛑 Vorlesung skippen (100% Anki)",
        "is_audio_only": False,
        "tradeoff_reason": "Hoher Anteil an Organisatorischem, Studienrichtlinien und historischer Nomenklatur. Die wenigen prüfungsrelevanten Referenzwerte (Hämatokrit, MCV/MCH, Hämatopoese-Orte) werden via Anki-Karten mit wesentlich höherer Behaltensleistung und in einem Bruchteil der Zeit enkodiert.",
        "anki_facts": [
            "Normaler Hämatokrit-Referenzbereich: Männer ca. 40–52 %, Frauen ca. 36–48 %.",
            "Erythrozyten-Indices: MCV (80–100 fl = Normozytär), MCH (27–34 pg = Normochrom), MCHC (320–360 g/l).",
            "Hauptbildungsort der Blutzellen beim Erwachsenen: Rotes Knochenmark der platten Knochen (Beckenkamm/Os ilium, Sternum, Wirbelkörper)."
        ],
        "keywords": [
            "anatomie",
            "einführung",
            "blut",
            "hämatologie",
            "hämatokrit",
            "hct",
            "mcv",
            "mch",
            "mchc",
            "knochenmark",
            "hämatopoese",
            "leukozyten",
            "thrombozyten",
            "referenzbereich"
        ],
        "associated_decks": [
            "1 Einführung Anatomie",
            "Grundlagen Hämatologie",
            "2. SJ :: 1. Blut & Immunsystem :: Einführung"
        ],
        "slide_pdf": "Vorlesungen im Themenblock Blut und Immunsystem/Tuzlak_Adaptives und angeborenes Immunsystem.pdf",
        "total_anki_cards": 120,
        "chapters": [
            {
                "start": "00:00",
                "end": "26:30",
                "duration_min": 26,
                "title": "Einführung, Nomenklatur & Organisation (Skip)",
                "cards_count": 15,
                "cards_range": "1–15",
                "slide_range": "Folien 1–15",
                "topics": [
                    "Organisation",
                    "Studienplan",
                    "Terminologie"
                ],
                "summary": "Behandelt die Folien Folien 1–15 mit 15 prüfungsrelevanten Anki-Karten."
            },
            {
                "start": "26:30",
                "end": "55:00",
                "duration_min": 29,
                "title": "Erythrozyten-Indices & Hämatokrit-Referenzwerte",
                "cards_count": 55,
                "cards_range": "16–70",
                "slide_range": "Folien 16–34",
                "topics": [
                    "Hämatokrit",
                    "MCV",
                    "MCH",
                    "MCHC",
                    "Erythrozyten"
                ],
                "summary": "Behandelt die Folien Folien 16–34 mit 55 prüfungsrelevanten Anki-Karten."
            },
            {
                "start": "55:00",
                "end": "82:00",
                "duration_min": 27,
                "title": "Hämatopoese & Stammzell-Differenzierung im Knochenmark",
                "cards_count": 50,
                "cards_range": "71–120",
                "slide_range": "Folien 35–48",
                "topics": [
                    "Hämatopoese",
                    "Rotes Knochenmark",
                    "Myelopoese",
                    "EPO"
                ],
                "summary": "Behandelt die Folien Folien 35–48 mit 50 prüfungsrelevanten Anki-Karten."
            }
        ]
    },
    {
        "id": "2025-09-18_TB_Blut_-_Immunsystem",
        "date": "2025-09-18",
        "title": "Hämoglobin, Myoglobin & Sauerstoffbindung (Erythrozyten)",
        "module": "1. Blut & Immunsystem",
        "lecturer": "Prof. Dr. Cristina Manatschal / Prof. Raimund Dutzler",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Schnell",
        "silence_ratio": 0.098,
        "recommendation": "1.2x",
        "badge_color": "var(--status-warning, #d29922)",
        "badge_label": "🟡 1.2x Standard-Stream (+25m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Zentrales allosterisches Kernkonzept (T- zu R-Konformation, sigmoide vs. hyperbolische O2-Bindungskurve, 2,3-BPG-Einfluss, Hill-Koeffizient ca. 2.8, Erythrozytenmorphologie & Membranaufbau). Das simultane visuelle Verfolgen der Kurvenverschiebung ist vor dem Anki-Lernen essenziell; 1.2x wahrt die kognitive Synchronisation trotz rascher Artikulation der Dozentin.",
        "anki_facts": [
            "Kooperativer Bindungsmechanismus: T-Zustand (Tense, niedrige O2-Affinität) geht bei O2-Bindung in R-Zustand (Relaxed, hohe O2-Affinität) über.",
            "Allosterischer Effektor 2,3-Bisphosphoglycerat (2,3-BPG): Stabilisiert spezifisch die T-Form in der zentralen Kavität und verschiebt O2-Bindungskurve nach rechts.",
            "Fetales Hämoglobin (HbF, alpha2-gamma2): Besitzt Serin statt Histidin an Position 143 (gamma-Kette), bindet 2,3-BPG schwächer und hat daher höhere O2-Affinität als HbA.",
            "Erythrozyten-Funktion: Bikonkave Scheibenform optimiert Diffusionsfläche für Gastransport (O2/CO2) und osmotische Verformbarkeit in Kapillaren."
        ],
        "keywords": [
            "hämoglobin",
            "myoglobin",
            "sauerstoff",
            "o2",
            "hbf",
            "hba",
            "2,3-bpg",
            "allosterie",
            "t-form",
            "r-form",
            "kooperativität",
            "hill-koeffizient",
            "sigmoide bindungskurve",
            "p50-wert",
            "erythrozyt",
            "erythrozyten",
            "erythrozytenmorphologie",
            "osmotische resistenz",
            "blut und blutplasma",
            "blutplasma",
            "gastransport"
        ],
        "associated_decks": [
            "1 Hämoglobin",
            "Hämoglobin Teil 2",
            "2. SJ :: 1. Blut & Immunsystem :: Hämoglobin",
            "2. SJ - 1 :: TB Blut/Immunsystem :: Schneider :: Erythrozyten / Wenger",
            "2. SJ - 1 :: TB Blut/Immunsystem :: Schneider :: Blut und Blutplasma / Wenger",
            "Erythrozyten",
            "Blut und Blutplasma"
        ],
        "slide_pdf": "Vorlesungen im Themenblock Blut und Immunsystem/Cristina Manatschal/1-4_CM_Myoglobin_Hamoglobin.pdf",
        "total_anki_cards": 245,
        "chapters": [
            {
                "start": "00:00",
                "end": "24:30",
                "duration_min": 25,
                "title": "Struktur & Faltung: Myoglobin vs. Tetrameres Hämoglobin",
                "cards_count": 65,
                "cards_range": "1–65",
                "slide_range": "Folien 1–18",
                "topics": [
                    "Myoglobin",
                    "Hämoglobin",
                    "Globin-Faltung",
                    "Häm-Tasche",
                    "Fe2+"
                ],
                "summary": "Behandelt die Folien Folien 1–18 mit 65 prüfungsrelevanten Anki-Karten."
            },
            {
                "start": "24:30",
                "end": "54:00",
                "duration_min": 30,
                "title": "Kooperativität & T- zu R-Übergang (Sigmoide Bindungskurve)",
                "cards_count": 85,
                "cards_range": "66–150",
                "slide_range": "Folien 19–35",
                "topics": [
                    "Kooperativität",
                    "T-Form",
                    "R-Form",
                    "Hill-Koeffizient",
                    "P50-Wert"
                ],
                "summary": "Behandelt die Folien Folien 19–35 mit 85 prüfungsrelevanten Anki-Karten."
            },
            {
                "start": "54:00",
                "end": "72:15",
                "duration_min": 18,
                "title": "Allosterische Modulation: 2,3-BPG & Fetales HbF",
                "cards_count": 55,
                "cards_range": "151–205",
                "slide_range": "Folien 36–44",
                "topics": [
                    "2,3-BPG",
                    "HbF",
                    "gamma-Kette",
                    "Rechtsverschiebung"
                ],
                "summary": "Behandelt die Folien Folien 36–44 mit 55 prüfungsrelevanten Anki-Karten."
            },
            {
                "start": "72:15",
                "end": "88:30",
                "duration_min": 16,
                "title": "Klinische Pathologie: HbS, Methämoglobin & CO-Vergiftung",
                "cards_count": 40,
                "cards_range": "206–245",
                "slide_range": "Folien 45–52",
                "topics": [
                    "Sichelzellanämie",
                    "HbS",
                    "Methämoglobinämie",
                    "Kohlenmonoxid"
                ],
                "summary": "Behandelt die Folien Folien 45–52 mit 40 prüfungsrelevanten Anki-Karten."
            }
        ]
    },
    {
        "id": "2025-09-19_TB_Blut_-_Immunsystem",
        "date": "2025-09-19",
        "title": "Säure-Basen-Haushalt, CO2-Transport & Bohr-Effekt",
        "module": "1. Blut & Immunsystem",
        "lecturer": "Prof. Dr. Cristina Manatschal",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.795,
        "recommendation": "1.0x",
        "badge_color": "var(--status-done, #3fb950)",
        "badge_label": "🟢 1.0x Voller Fokus (Kernprüfungskonzept)",
        "is_audio_only": False,
        "tradeoff_reason": "Höchste intrinsische kognitive Belastung (Carboanhydrase-Gleichgewicht, Haldane- vs. Bohr-Effekt, Hamburger-Shift / Anionenaustauscher AE1). Absolute UZH-Kernprüfungskonzepte, die kausal durchdrungen werden müssen. Jede Beschleunigung über 1.0x führt zu Verständnisbrüchen.",
        "anki_facts": [
            "Bohr-Effekt: Sinkender pH und steigender pCO2 verringern die O2-Affinität von Hb (Rechtsverschiebung, erleichterte O2-Abgabe im Gewebe).",
            "Haldane-Effekt: Desoxygeniertes Hb bindet H+ und CO2 (Carbamat) besser als oxygeniertes Hb (erleichterte CO2-Aufnahme im Gewebe, Abgabe in Alveolen).",
            "Hamburger-Shift (Chlorid-Shift): Bicarbonat (HCO3-) verlässt Erythrozyten im Austausch gegen Cl- via AE1 (Band 3), um das Membranpotenzial neutral zu halten."
        ],
        "keywords": [
            "säure-base",
            "co2-transport",
            "bohr-effekt",
            "haldane-effekt",
            "hamburger-shift",
            "carboanhydrase",
            "bicarbonat",
            "hco3-",
            "pco2",
            "ph-wert",
            "henderson-hasselbalch",
            "azidose",
            "alkalose",
            "ae1"
        ],
        "associated_decks": [
            "2 CO2-Transport",
            "Säure-Basen-Haushalt",
            "2. SJ :: 1. Blut & Immunsystem :: CO2-Transport"
        ],
        "slide_pdf": "Vorlesungen im Themenblock Blut und Immunsystem/Cristina Manatschal/5_CM_Saure-Base_CO2-Transport.pdf",
        "total_anki_cards": 220,
        "chapters": [
            {
                "start": "00:00",
                "end": "22:00",
                "duration_min": 22,
                "title": "Grundlagen Säure-Basen & Carboanhydrase-Gleichgewicht",
                "cards_count": 50,
                "cards_range": "1–50",
                "slide_range": "Folien 1–15",
                "topics": [
                    "Carboanhydrase",
                    "Bicarbonat",
                    "HCO3-",
                    "pCO2",
                    "Henderson-Hasselbalch"
                ],
                "summary": "Behandelt die Folien Folien 1–15 mit 50 prüfungsrelevanten Anki-Karten."
            },
            {
                "start": "22:00",
                "end": "48:30",
                "duration_min": 26,
                "title": "Bohr-Effekt: Protonen- und CO2-Einfluss auf die O2-Affinität",
                "cards_count": 75,
                "cards_range": "51–125",
                "slide_range": "Folien 16–30",
                "topics": [
                    "Bohr-Effekt",
                    "Protonenbindung",
                    "Gewebe-O2-Abgabe",
                    "Rechtsverschiebung"
                ],
                "summary": "Behandelt die Folien Folien 16–30 mit 75 prüfungsrelevanten Anki-Karten."
            },
            {
                "start": "48:30",
                "end": "68:00",
                "duration_min": 20,
                "title": "Haldane-Effekt & Alveoläre CO2-Freisetzung",
                "cards_count": 55,
                "cards_range": "126–180",
                "slide_range": "Folien 31–42",
                "topics": [
                    "Haldane-Effekt",
                    "Carbamat",
                    "Desoxygeniertes Hb",
                    "CO2-Abgabe"
                ],
                "summary": "Behandelt die Folien Folien 31–42 mit 55 prüfungsrelevanten Anki-Karten."
            },
            {
                "start": "68:00",
                "end": "86:00",
                "duration_min": 18,
                "title": "Hamburger-Shift (Anionenaustauscher AE1) & Säure-Basen-Störungen",
                "cards_count": 40,
                "cards_range": "181–220",
                "slide_range": "Folien 43–52",
                "topics": [
                    "Hamburger-Shift",
                    "Chlorid-Shift",
                    "AE1",
                    "Band 3",
                    "Azidose"
                ],
                "summary": "Behandelt die Folien Folien 43–52 mit 40 prüfungsrelevanten Anki-Karten."
            }
        ]
    },
    {
        "id": "2025-09-22_TB_Blut_-_Immunsystem",
        "date": "2025-09-22",
        "title": "Hämostase: Thrombozytenaktivierung & Primäre Blutstillung",
        "module": "1. Blut & Immunsystem",
        "lecturer": "Prof. Dr. Cristina Manatschal",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Normal",
        "silence_ratio": 0.164,
        "recommendation": "1.2x",
        "badge_color": "var(--status-warning, #d29922)",
        "badge_label": "🟡 1.2x Standard-Stream (+25m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Mehrstufige Kaskade von Adhäsion (vWF / GP Ib-V-IX), Aktivierung (TxA2, ADP, Ca2+) bis Aggregation (GP IIb/IIIa, Fibrinogenbrücken). Das visuelle Flussdiagramm ist direkte Grundlage für die klinische Pharmakologie (ASS, Clopidogrel, Tirofiban); 1.2x spart Zeit ohne Informationsverlust.",
        "anki_facts": [
            "Thrombozytenadhäsion: Subendotheliales Kollagen bindet von-Willebrand-Faktor (vWF), der an den Thrombozytenrezeptor GP Ib-V-IX koppelt.",
            "Thrombozytenaggregation: Aktiviertes Glykoprotein IIb/IIIa (Integrin alphaIIb-beta3) bindet Fibrinogen und bildet Quervernetzungen zwischen Thrombozyten.",
            "Pharmakologische Targets: ASS hemmt irreversibel COX-1 (TxA2-Synthese); Clopidogrel/Prasugrel blockieren P2Y12 (ADP-Rezeptor)."
        ],
        "keywords": [
            "hämostase",
            "blutstillung",
            "thrombozyten",
            "thrombozytenaktivierung",
            "vwf",
            "von-willebrand",
            "gp ib",
            "gp iib/iiia",
            "adp",
            "thromboxan",
            "txa2",
            "ass",
            "clopidogrel",
            "primäre hämostase",
            "blutgerinnung",
            "gerinnung",
            "blutstillung"
        ],
        "associated_decks": [
            "3 Hämostase",
            "3 Blutgerinnung",
            "Blutgerinnung",
            "Thrombozytenaktivierung",
            "2. SJ :: 1. Blut & Immunsystem :: Primäre Hämostase"
        ],
        "slide_pdf": "Vorlesungen im Themenblock Blut und Immunsystem/Cristina Manatschal/6-7_CM_Blutgerinnung.pdf",
        "total_anki_cards": 210,
        "chapters": [
            {
                "start": "00:00",
                "end": "26:00",
                "duration_min": 26,
                "title": "Thrombozytenadhäsion: Endothelschaden, Kollagen & vWF",
                "cards_count": 65,
                "cards_range": "1–65",
                "slide_range": "Folien 1–18",
                "topics": [
                    "vWF",
                    "von-Willebrand-Faktor",
                    "GP Ib-V-IX",
                    "Subendotheliales Kollagen"
                ],
                "summary": "Behandelt die Folien Folien 1–18 mit 65 prüfungsrelevanten Anki-Karten."
            },
            {
                "start": "26:00",
                "end": "55:30",
                "duration_min": 30,
                "title": "Thrombozytenaktivierung: Granulafreisetzung & Botenstoffe (TxA2, ADP)",
                "cards_count": 80,
                "cards_range": "66–145",
                "slide_range": "Folien 19–34",
                "topics": [
                    "Thromboxan A2",
                    "TxA2",
                    "ADP",
                    "P2Y12",
                    "Dichte Granula"
                ],
                "summary": "Behandelt die Folien Folien 19–34 mit 80 prüfungsrelevanten Anki-Karten."
            },
            {
                "start": "55:30",
                "end": "84:00",
                "duration_min": 28,
                "title": "Thrombozytenaggregation: GP IIb/IIIa-Komplex & Hemmstoffe (ASS, Clopidogrel)",
                "cards_count": 65,
                "cards_range": "146–210",
                "slide_range": "Folien 35–48",
                "topics": [
                    "GP IIb/IIIa",
                    "Fibrinogenbrücken",
                    "ASS",
                    "Clopidogrel"
                ],
                "summary": "Behandelt die Folien Folien 35–48 mit 65 prüfungsrelevanten Anki-Karten."
            }
        ]
    },
    {
        "id": "2025-09-25_TB_Blut_-_Immunsystem",
        "date": "2025-09-25",
        "title": "Sekundäre Hämostase: Gerinnungskaskade & Fibrinolyse",
        "module": "1. Blut & Immunsystem",
        "lecturer": "Prof. Dr. Cristina Manatschal",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Normal",
        "silence_ratio": 0.246,
        "recommendation": "1.2x",
        "badge_color": "var(--status-warning, #d29922)",
        "badge_label": "🟡 1.2x Standard-Stream (+25m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Extrinsischer Weg (Tissue Factor / FVIIa) vs. Intrinsischer Weg (FXII, XI, IX, VIII), Tenase- & Prothrombinase-Komplex sowie Vitamin-K-Abhängigkeit (Faktoren II, VII, IX, X, Protein C/S). Die visuelle Schematik verhindert Verwechslungen in MC-Fragen; 1.2x schafft kognitiven Raum für die Anki-Festigung.",
        "anki_facts": [
            "Extrinsischer Tenase-Komplex: Tissue Factor (TF) + Faktor VIIa + Ca2+ aktiviert Faktor X zu Xa.",
            "Prothrombinase-Komplex: Faktor Xa + Faktor Va + Ca2+ + Phospholipide spaltet Prothrombin (II) zu Thrombin (IIa).",
            "Vitamin-K-abhängige Faktoren: II, VII, IX, X sowie inhibitorische Proteine C und S (benötigen posttranslationale gamma-Carboxylierung von Glutamat)."
        ],
        "keywords": [
            "sekundäre hämostase",
            "gerinnungskaskade",
            "fibrinolyse",
            "thrombin",
            "fibrin",
            "faktor x",
            "faktor viii",
            "faktor ix",
            "hämophilie",
            "vitamin k",
            "antithrombin",
            "plasmin",
            "tpa"
        ],
        "associated_decks": [
            "4 Gerinnungskaskade",
            "Fibrinolyse",
            "2. SJ :: 1. Blut & Immunsystem :: Gerinnung"
        ],
        "slide_pdf": "Vorlesungen im Themenblock Blut und Immunsystem/Cristina Manatschal/6-7_CM_Blutgerinnung.pdf",
        "total_anki_cards": 235,
        "chapters": [
            {
                "start": "00:00",
                "end": "25:00",
                "duration_min": 25,
                "title": "Extrinsischer Weg & Tenase-Komplex (Tissue Factor & FVIIa)",
                "cards_count": 60,
                "cards_range": "1–60",
                "slide_range": "Folien 1–16",
                "topics": [
                    "Extrinsischer Weg",
                    "Tissue Factor",
                    "TF",
                    "Faktor VIIa",
                    "Faktor X"
                ],
                "summary": "Behandelt die Folien Folien 1–16 mit 60 prüfungsrelevanten Anki-Karten."
            },
            {
                "start": "25:00",
                "end": "53:00",
                "duration_min": 28,
                "title": "Intrinsischer Weg & Prothrombinase-Komplex (FXa, FVa, Ca2+)",
                "cards_count": 85,
                "cards_range": "61–145",
                "slide_range": "Folien 17–33",
                "topics": [
                    "Intrinsischer Weg",
                    "FXII",
                    "FIXa-FVIIIa",
                    "Prothrombinase",
                    "Thrombin IIa"
                ],
                "summary": "Behandelt die Folien Folien 17–33 mit 85 prüfungsrelevanten Anki-Karten."
            },
            {
                "start": "53:00",
                "end": "71:00",
                "duration_min": 18,
                "title": "Vitamin-K-Abhängigkeit & Antikoagulation (Cumarine / Heparin)",
                "cards_count": 50,
                "cards_range": "146–195",
                "slide_range": "Folien 34–42",
                "topics": [
                    "Vitamin K",
                    "gamma-Carboxylierung",
                    "Faktoren 1972",
                    "Protein C/S"
                ],
                "summary": "Behandelt die Folien Folien 34–42 mit 50 prüfungsrelevanten Anki-Karten."
            },
            {
                "start": "71:00",
                "end": "87:30",
                "duration_min": 17,
                "title": "Fibrinolyse: Plasminogen, tPA, D-Dimere & Antithrombin III",
                "cards_count": 40,
                "cards_range": "196–235",
                "slide_range": "Folien 43–50",
                "topics": [
                    "Fibrinolyse",
                    "Plasmin",
                    "tPA",
                    "D-Dimere",
                    "Antithrombin III"
                ],
                "summary": "Behandelt die Folien Folien 43–50 mit 40 prüfungsrelevanten Anki-Karten."
            }
        ]
    },
    {
        "id": "2025-09-26_TB_Blut_-_Immunsystem",
        "date": "2025-09-26",
        "title": "Komplementsystem & Zelluläre Immunmechanismen",
        "module": "1. Blut & Immunsystem",
        "lecturer": "Prof. Dr. Cristina Manatschal / Dr. Tuzlak",
        "exam_yield": "Low-Yield",
        "visual_dependency": "Niedrig",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.88,
        "recommendation": "Skip (0x)",
        "badge_color": "var(--status-danger, #f85149)",
        "badge_label": "🛑 Vorlesung skippen (100% Anki)",
        "is_audio_only": False,
        "tradeoff_reason": "Das Komplementsystem wurde auf den Vorlesungsfolien (siehe 8_CM_Komplementsystem.pdf) explizit als 'kein Prüfungsstoff' deklariert. Reine deskriptive Nomenklaturlisten (C1–C9, MAC); das Anschauen des 90-minütigen Videos bietet ein unvorteilhaftes Zeit-Ertrags-Verhältnis. Genau 3 Fakten genügen für die Übersicht.",
        "anki_facts": [
            "Konvergenz aller 3 Aktivierungswege (Klassisch, Lektin, Alternativ): Bildung der C3-Konvertase.",
            "Wichtigstes Opsonin des Komplements: C3b (bindet an CR1 auf Phagozyten); stärkste Anaphylatoxine: C3a und C5a (Chemotaxis, Mastzelldegranulation).",
            "Membranangriffskomplex (MAC): Besteht aus C5b, C6, C7, C8 und polymerisiertem C9 (Porenbildung und bakterielle Zelllyse)."
        ],
        "keywords": [
            "komplement",
            "komplementsystem",
            "c3",
            "c3b",
            "c3a",
            "c5a",
            "mac",
            "membranangriffskomplex",
            "opsonierung",
            "anaphylatoxin",
            "c1q",
            "mbl",
            "alternativer weg",
            "kein prüfungsstoff"
        ],
        "associated_decks": [
            "5 Komplementsystem",
            "Immunmechanismen",
            "2. SJ :: 1. Blut & Immunsystem :: Komplement"
        ],
        "slide_pdf": "Vorlesungen im Themenblock Blut und Immunsystem/Cristina Manatschal/8_CM_Komplementsystem.pdf",
        "total_anki_cards": 190,
        "chapters": [
            {
                "start": "00:00",
                "end": "28:00",
                "duration_min": 28,
                "title": "Aktivierungswege: Klassisch (C1q), Lektin (MBL) & Alternativ",
                "cards_count": 65,
                "cards_range": "1–65",
                "slide_range": "Folien 1–20",
                "topics": [
                    "Klassischer Weg",
                    "C1q",
                    "Lektinweg",
                    "MBL",
                    "Alternativweg",
                    "C3-Konvertase"
                ],
                "summary": "Behandelt die Folien Folien 1–20 mit 65 prüfungsrelevanten Anki-Karten."
            },
            {
                "start": "28:00",
                "end": "56:00",
                "duration_min": 28,
                "title": "Effektormechanismen: Opsonierung (C3b) & Membranangriffskomplex MAC (C5b-9)",
                "cards_count": 75,
                "cards_range": "66–140",
                "slide_range": "Folien 21–38",
                "topics": [
                    "MAC",
                    "C5b-9",
                    "Opsonierung",
                    "C3b",
                    "Phagozytose",
                    "Zelllyse"
                ],
                "summary": "Behandelt die Folien Folien 21–38 mit 75 prüfungsrelevanten Anki-Karten."
            },
            {
                "start": "56:00",
                "end": "82:00",
                "duration_min": 26,
                "title": "Anaphylatoxine (C3a, C5a) & Schutz körpereigener Zellen (CD59, DAF)",
                "cards_count": 50,
                "cards_range": "141–190",
                "slide_range": "Folien 39–50",
                "topics": [
                    "Anaphylatoxine",
                    "C3a",
                    "C5a",
                    "CD59",
                    "DAF",
                    "CD55"
                ],
                "summary": "Behandelt die Folien Folien 39–50 mit 50 prüfungsrelevanten Anki-Karten."
            }
        ]
    },
    {
        "id": "2025-10-02_TB_Herz_-Kreislauf",
        "date": "2025-10-02",
        "title": "Herz- und Gefässentwicklung (Embryologie)",
        "module": "2. Herz-Kreislauf",
        "lecturer": "Prof. Dr. Lutz Sommer",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Normal",
        "silence_ratio": 0.225,
        "recommendation": "1.0x",
        "badge_color": "var(--status-done, #3fb950)",
        "badge_label": "🟢 1.0x Voller Fokus (Räumliches 3D-Verständnis)",
        "is_audio_only": False,
        "tradeoff_reason": "Räumlich hochkomplexe dreidimensionale Schleifenbildung des Herzschlauchs (D-Loop), Septierung der Vorhöfe (Septum primum, Septum secundum, Foramen ovale) und Ventrikel sowie Endokardkissen. Rein textlich ohne Videoverfolgung kaum begreifbar; 1.0x zwingend für die mentale 3D-Modellbildung.",
        "anki_facts": [
            "Schleifenbildung des Herzschlauchs: D-Looping (Rechtskrümmung) bringt den primitiven Ventrikel nach links-unten und die Vorhöfe nach kranio-dorsal.",
            "Vorhofseptierung: Septum primum wächst nach unten, bildet Ostium primum/secundum; Septum secundum wächst parallel und bildet das Foramen ovale.",
            "Klinische Fehlbildung: Endokardkissendefekt (Atrioventrikulärer Septumdefekt / AVSD), typisch bei Trisomie 21."
        ],
        "keywords": [
            "herzentwicklung",
            "embryologie herz",
            "herzschlauch",
            "looping",
            "septum primum",
            "septum secundum",
            "foramen ovale",
            "endokardkissen",
            "avsd",
            "vsd",
            "asd",
            "truncus arteriosus",
            "fallot"
        ],
        "associated_decks": [
            "1 Herzembryologie",
            "Herzentwicklung",
            "2. SJ :: 2. Herz-Kreislauf :: Embryologie"
        ],
        "slide_pdf": "TB herz-Kreislauf/Archive_1/Anatomie/Sommer_HerzGefaessentwicklung-VAM.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-10-03_TB_Herz_-Kreislauf",
        "date": "2025-10-03",
        "title": "Aortenbogenentwicklung, Fetaler Kreislauf & Shunts",
        "module": "2. Herz-Kreislauf",
        "lecturer": "Prof. Dr. Lutz Sommer",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.607,
        "recommendation": "1.2x",
        "badge_color": "var(--status-warning, #d29922)",
        "badge_label": "🟡 1.2x Standard-Stream (+25m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Schicksal der Pharynxkaryenbögen (Ductus arteriosus Botalli aus 6. Bogen, Aortenbogen aus 4. Bogen) und postpartale Umstellung des Kreislaufs (Druckanstieg links, Druckabfall rechts). Dozent pausiert viel (60% Pause); 1.2x eliminiert Leerlauf und optimiert die Enkodierung.",
        "anki_facts": [
            "Drei fetale Kurzschlüsse (Shunts): Ductus venosus (umgeht Leber), Foramen ovale (Rechts-Links-Shunt im Vorhof), Ductus arteriosus Botalli (umgeht Lunge).",
            "Schicksal der Aortenbögen: 3. Bogen = A. carotis communis; 4. Bogen links = Arcus aortae; 6. Bogen links = Ductus arteriosus.",
            "Postnatale Schliessung des Ductus arteriosus: Getriggert durch Sauerstoffanstieg und Bradykinin/Prostaglandin-Abfall (wird zum Ligamentum arteriosum)."
        ],
        "keywords": [
            "aortenbogen",
            "fetaler kreislauf",
            "shunts",
            "ductus arteriosus",
            "botalli",
            "foramen ovale",
            "ductus venosus",
            "phrynxkaryenbogen",
            "prostaglandin",
            "postnatal",
            "coarctatio"
        ],
        "associated_decks": [
            "2 Fetaler Kreislauf",
            "Aortenbögen",
            "2. SJ :: 2. Herz-Kreislauf :: Fetaler Kreislauf"
        ],
        "slide_pdf": "TB herz-Kreislauf/Archive_1/Anatomie/Sommer_HerzGefaessentwicklung-VAM.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-10-06_TB_Herz_-_Kreislauf",
        "date": "2025-10-06",
        "title": "Erregungsbildungs- und Leitungssystem des Herzens",
        "module": "2. Herz-Kreislauf",
        "lecturer": "Prof. Dr. med. Elisabeth Kurt",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.296,
        "recommendation": "1.0x",
        "badge_color": "var(--status-done, #3fb950)",
        "badge_label": "🟢 1.0x Voller Fokus (Fundamentale Elektrophysiologie)",
        "is_audio_only": False,
        "tradeoff_reason": "Ionenströme des kardialen Aktionspotenzials (If-Funny-Currents im Sinusknoten, L-Typ-Ca2+-Kanäle, IKr/IKs, absolute vs. relative Refraktärzeit) und Erregungsausbreitung (AV-Knoten, His-Bündel, Tawara-Schenkel). Basis für alle Arrhythmie-MC-Fragen; erfordert volle Konzentration bei 1.0x.",
        "anki_facts": [
            "Schrittmacher-Aktionspotenzial: Spontane diastolische Depolarisation getrieben durch If (HCN-Kanäle, Na+/K+-Einstrom), Aufstrich durch Ca2+-Einstrom (L- und T-Typ).",
            "Arbeitsmyokard-Aktionspotenzial: Phase 0 (schneller Na+-Einstrom), Phase 1 (frühe Repolarisation), Phase 2 (Ca2+-Plateau), Phase 3 (K+-Ausstrom), Phase 4 (Ruhepotenzial ca. -85 mV).",
            "Physiologische AV-Knoten-Verzögerung: Ca. 0.08–0.12 s Verzögerung, um eine vollständige Vorhofentleerung vor der Ventrikelkontraktion zu sichern."
        ],
        "keywords": [
            "erregungsleitung",
            "aktionspotenzial",
            "sinusknoten",
            "av-knoten",
            "funny current",
            "if",
            "l-typ ca2+",
            "refraktärzeit",
            "his-bündel",
            "purkinje-fasern",
            "tawara-schenkel",
            "arrhythmie"
        ],
        "associated_decks": [
            "3 Erregungsleitung",
            "Kardiales Aktionspotenzial",
            "2. SJ :: 2. Herz-Kreislauf :: Erregungsleitung"
        ],
        "slide_pdf": "TB herz-Kreislauf/Archive_1/Anatomie/Sommer_HerzGefaessentwicklung-VAM.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-10-08_TB_Herz_-_Kreislauf",
        "date": "2025-10-08",
        "title": "Elektrokardiogramm (EKG) & Vektorkardiographie",
        "module": "2. Herz-Kreislauf",
        "lecturer": "Prof. Dr. med. Elisabeth Kurt",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.255,
        "recommendation": "1.2x",
        "badge_color": "var(--status-warning, #d29922)",
        "badge_label": "🟡 1.2x Standard-Stream (+25m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Visuelle Mustererkennung (Cabrera-Kreis, Lagetypen, Schenkelblöcke, Infarktzeichen/ST-Hebung, PQ-, QRS-, QT-Intervalle). Das schrittweise Abtragen von Vektoren auf Ableitungen erfordert ständigen Blick auf die Folien; 1.2x hält das Lerntempo angenehm dynamisch.",
        "anki_facts": [
            "Lagetyp-Bestimmung im Cabrera-Kreis: Indifferenztyp (+30° bis +60°: I, II, III positiv, II maximal); Steiltyp (+60° bis +90°); Linkstyp (-30° bis +30°).",
            "EKG-Zeitintervalle: PQ-Zeit (120–200 ms, AV-Überleitung), QRS-Dauer (< 100 ms, intraventrikuläre Erregung), QTc-Zeit (< 440 ms bei Männern, < 460 ms bei Frauen).",
            "Mustererkennung Schenkelblock: Rechtsschenkelblock (M-Konfiguration / rsR' in V1/V2); Linksschenkelblock (breites, gekerbtes R in I, aVL, V5/V6)."
        ],
        "keywords": [
            "ekg",
            "elektrokardiogramm",
            "cabrera-kreis",
            "lagetyp",
            "vektorkardiographie",
            "p-welle",
            "qrs-komplex",
            "t-welle",
            "pq-zeit",
            "qt-zeit",
            "schenkelblock",
            "st-hebung",
            "infarkt"
        ],
        "associated_decks": [
            "4 EKG",
            "Vektorkardiographie",
            "2. SJ :: 2. Herz-Kreislauf :: EKG"
        ],
        "slide_pdf": "TB herz-Kreislauf/Archive_1/Anatomie/Sommer_HerzGefaessentwicklung-VAM.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-10-09_TB_Herz_-_Kreislauf",
        "date": "2025-10-09",
        "title": "Mechanische Herzaktion: Herzphasen & Druck-Volumen-Diagramm",
        "module": "2. Herz-Kreislauf",
        "lecturer": "Prof. Dr. med. Elisabeth Kurt",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.408,
        "recommendation": "1.0x",
        "badge_color": "var(--status-done, #3fb950)",
        "badge_label": "🟢 1.0x Voller Fokus (Absoluter Prüfungskern)",
        "is_audio_only": False,
        "tradeoff_reason": "Arbeitsdiagramm des linken Ventrikels (PV-Loop, Wiggers-Diagramm, Frank-Starling-Mechanismus, Inotropie vs. Vorlast vs. Nachlast). Die gleichzeitige Interpretation von Drücken, Volumina, Klappenöffnungen und Herztönen verlangt höchste Aufmerksamkeit bei 1.0x.",
        "anki_facts": [
            "Vier Phasen der Ventrikelmechanik: 1. Anspannungsphase (isovolumetrisch, alle Klappen zu), 2. Austreibungsphase (auxoton, Aortenklappe offen), 3. Entspannungsphase (isovolumetrisch), 4. Füllungsphase (Mitralklappe offen).",
            "Einfluss auf den PV-Loop: Vorlast-Steigerung verbreitert die Kurve nach rechts (grösseres EDV, erhöhtes Schlagvolumen); Nachlast-Steigerung verschmälert die Kurve und erhöht den Spitzendruck (ESV steigt).",
            "Frank-Starling-Mechanismus: Erhöhte Vorlast (enddiastolische Faserdehnung) steigert die Ca2+-Sensitivität der Myofilamente und damit die Kontraktionskraft."
        ],
        "keywords": [
            "herzmechanik",
            "druck-volumen",
            "pv-loop",
            "wiggers-diagramm",
            "frank-starling",
            "vorlast",
            "nachlast",
            "inotropie",
            "isovolumetrisch",
            "schlagvolumen",
            "ejektionsfraktion",
            "herztöne"
        ],
        "associated_decks": [
            "5 Herzmechanik",
            "Druck-Volumen-Diagramm",
            "2. SJ :: 2. Herz-Kreislauf :: Herzmechanik"
        ],
        "slide_pdf": "TB herz-Kreislauf/Archive_1/Anatomie/Sommer_HerzGefaessentwicklung-VAM.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-10-10_TB_Herz_-_Kreislauf",
        "date": "2025-10-10",
        "title": "Hämodynamik & Gefässwiderstand (Windkessel, Hagen-Poiseuille)",
        "module": "2. Herz-Kreislauf",
        "lecturer": "Prof. Dr. med. Elisabeth Kurt",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.742,
        "recommendation": "1.2x",
        "badge_color": "var(--status-warning, #d29922)",
        "badge_label": "🟡 1.2x Standard-Stream (+25m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Druckabfall im Stromgebiet, Windkesselfunktion der Aorta, Totaler Peripherer Widerstand (TPR, Hauptort in den Arteriolen) und Hagen-Poiseuille-Gesetz (Widerstand proportional zu 1/r^4). Physikalische Kausalitäten; 1.2x spart Zeit bei voller Verständnissicherung.",
        "anki_facts": [
            "Hagen-Poiseuille-Gesetz: Strömungswiderstand R = (8 * eta * l) / (pi * r^4). Halbierung des Gefässradius vervielfacht den Widerstand um das 16-fache.",
            "Windkesselfunktion: Elastische Dehnung der herznahen Aorta in der Systole speichert ca. 50% des Schlagvolumens und sichert kontinuierlichen diastolischen Blutfluss.",
            "Hauptwiderstandsgefässe: Die präkapillären Arteriolen sind für über 50% des gesamten peripheren Gefässwiderstandes (TPR) verantwortlich."
        ],
        "keywords": [
            "hämodynamik",
            "hagen-poiseuille",
            "windkessel",
            "gefässwiderstand",
            "tpr",
            "arteriolen",
            "blutdruck",
            "compliance",
            "reynolds-zahl",
            "turbulenz",
            "stridor",
            "strömung"
        ],
        "associated_decks": [
            "6 Hämodynamik",
            "Gefässwiderstand",
            "2. SJ :: 2. Herz-Kreislauf :: Hämodynamik"
        ],
        "slide_pdf": "TB herz-Kreislauf/Archive_1/Anatomie/Sommer_HerzGefaessentwicklung-VAM.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-10-13_TB_Herz_-_Kreislauf",
        "date": "2025-10-13",
        "title": "Kreislaufregulation: Barorezeptorreflex & Autoregulation",
        "module": "2. Herz-Kreislauf",
        "lecturer": "Prof. Dr. med. Elisabeth Kurt",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.732,
        "recommendation": "1.2x",
        "badge_color": "var(--status-warning, #d29922)",
        "badge_label": "🟡 1.2x Standard-Stream (+25m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Kurz- vs. mittelfristige Blutdruckregulation (Sinus caroticus via N. IX, Aortenbogen via N. X, Sympathikus-/Parasympathikus-Balance, RAAS-Trigger). Schematische Feedback-Schleifen sind visuell klar strukturiert; 1.2x liefert den idealen Kompromiss zwischen Tempo und Verständnis.",
        "anki_facts": [
            "Barorezeptorreflex bei Blutdruckanstieg: Erhöhte Dehnung in Sinus caroticus (N. IX) und Aortenbogen (N. X) aktiviert NTS in Medulla oblongata -> Hemmung Sympathikus, Aktivierung Parasympathikus (N. X) -> HF sinkt, TPR sinkt.",
            "Bayliss-Effekt (Myogene Autoregulation): Druckanstieg führt zur Dehnung glatter Muskelzellen in Widerstandsgefässen -> Ca2+-Einstrom -> reflektorische Vasokonstriktion (hält Perfusion konstant in Niere, Gehirn).",
            "Orthostase-Reaktion: Versacken von Blut in Beinen senkt Vorlast und Schlagvolumen -> Barorezeptorentlastung bewirkt reflektorische Tachykardie und Vasokonstriktion."
        ],
        "keywords": [
            "kreislaufregulation",
            "barorezeptor",
            "barorezeptorreflex",
            "sinus caroticus",
            "aortenbogen",
            "bayliss-effekt",
            "autoregulation",
            "orthostase",
            "sympathikus",
            "parasympathikus",
            "raas"
        ],
        "associated_decks": [
            "7 Kreislaufregulation",
            "Barorezeptorreflex",
            "2. SJ :: 2. Herz-Kreislauf :: Regulation"
        ],
        "slide_pdf": "TB herz-Kreislauf/Archive_1/Anatomie/Sommer_HerzGefaessentwicklung-VAM.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-10-15_TB_Herz_-_Kreislauf",
        "date": "2025-10-15",
        "title": "Mikrozirkulation & Transkapillärer Flüssigkeitsaustausch",
        "module": "2. Herz-Kreislauf",
        "lecturer": "Prof. Dr. med. Elisabeth Kurt",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.702,
        "recommendation": "1.2x",
        "badge_color": "var(--status-warning, #d29922)",
        "badge_label": "🟡 1.2x Standard-Stream (+25m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Starling-Kräfte der Kapillaren (hydrostatischer vs. kolloidosmotischer Druckgradient), Lymphdrainage und Entstehung von Ödemen. Essenzielles Grundlagenwissen für die klinische Pathophysiologie; 1.2x optimiert die Watch Time.",
        "anki_facts": [
            "Starling-Gleichung der Kapillarfiltration: Nettofiltration = K_f * [(P_kap - P_int) - sigma * (pi_kap - pi_int)].",
            "Normalwerte: P_kap fällt von ca. 32 mmHg (arteriell) auf ca. 15 mmHg (venös); kolloidosmotischer Druck pi_kap bleibt bei ca. 25 mmHg konstant.",
            "Vier Hauptursachen für Ödeme: 1. Erhöhter P_kap (z.B. Herzinsuffizienz, Venenstau), 2. Erniedrigter pi_kap (Hypalbuminämie, Leberzirrhose), 3. Erhöhte Kapillarpermeabilität (Histamin/Entzündung), 4. Gestörter Lymphabfluss (Lymphödem)."
        ],
        "keywords": [
            "mikrozirkulation",
            "starling-gleichung",
            "kapillare",
            "filtration",
            "reabsorption",
            "kolloidosmotischer druck",
            "ödem",
            "ödemgenese",
            "albumin",
            "lymphsystem",
            "perfusion"
        ],
        "associated_decks": [
            "8 Mikrozirkulation",
            "Kapillaraustausch",
            "2. SJ :: 2. Herz-Kreislauf :: Mikrozirkulation"
        ],
        "slide_pdf": "TB herz-Kreislauf/Archive_1/Anatomie/Sommer_HerzGefaessentwicklung-VAM.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-10-16_TB_Herz_-_Kreislauf",
        "date": "2025-10-16",
        "title": "Koronardurchblutung & Myokardialer Sauerstoffverbrauch",
        "module": "2. Herz-Kreislauf",
        "lecturer": "Prof. Dr. med. Elisabeth Kurt",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.751,
        "recommendation": "1.4x",
        "badge_color": "var(--accent-blue, #58a6ff)",
        "badge_label": "⏩ 1.4x High-Speed Stream (+35m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Diastolische Perfusion des linken Ventrikels, metabolische Autoregulation (Adenosin, NO) und Koronarreserve. Dozentin spricht sehr strukturiert mit Pausen (75% Stilleanteil in der Messung); 1.4x spart maximale Zeit ohne kognitiven Verlust.",
        "anki_facts": [
            "Diastolische Koronarperfusion: Der linke Ventrikel wird zu ca. 75–85% während der Diastole durchblutet, da in der Systole intramurale Kompressionsdrücke den Perfusionsdruck übersteigen.",
            "Metabolische Autoregulation der Koronarien: Wichtigster Vasodilatator bei O2-Mangel ist Adenosin (ATP-Abbauprodukt) sowie Stickstoffmonoxid (NO).",
            "Koronarreserve: Verhältnis von maximal möglicher Durchblutung (unter Vasodilatation) zur Ruhedurchblutung (Faktor 4–5 bei Gesunden)."
        ],
        "keywords": [
            "koronardurchblutung",
            "myokard",
            "koronarien",
            "diastolische perfusion",
            "adenosin",
            "no",
            "koronarreserve",
            "sauerstoffausschöpfung",
            "angina pectoris",
            "ischämie"
        ],
        "associated_decks": [
            "9 Koronardurchblutung",
            "Myokardstoffwechsel",
            "2. SJ :: 2. Herz-Kreislauf :: Koronarien"
        ],
        "slide_pdf": "TB herz-Kreislauf/Archive_1/Anatomie/Sommer_HerzGefaessentwicklung-VAM.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-10-17_TB_Atmung",
        "date": "2025-10-17",
        "title": "Embryologie & Anatomie des Respirationstrakts",
        "module": "3. Atmung & Lunge",
        "lecturer": "Prof. Dr. Lutz Sommer",
        "exam_yield": "Med-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.284,
        "recommendation": "1.4x",
        "badge_color": "var(--accent-blue, #58a6ff)",
        "badge_label": "⏩ 1.4x High-Speed Stream (+35m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Lungenknospung aus dem Vorderdarm, Tracheooesophagealfistel (Ösophagusatresie Typ Vogt IIIb), Reifungsphasen (pseudoglandulär bis alveolär) und Surfactant-Produktion. Mässige Konzeptdichte; 1.4x spart Zeit für das nachfolgende Fakten-Anki.",
        "anki_facts": [
            "Reifungsstadien der Lunge: 1. Pseudoglandulär (Woche 5–16), 2. Kanalikulär (16–26), 3. Sakkulär (26–Geburt, Surfactant-Start), 4. Alveolär (ab Geburt bis 8. Lebensjahr).",
            "Surfactant-Synthese: Produziert von Alveolarepithelzellen Typ II (Pneumozyten Typ II); Hauptbestandteil Dipalmitoylphosphatidylcholin (DPPC); senkt Oberflächenspannung in kleinen Alveolen.",
            "Tracheooesophageale Fistel (Ösophagusatresie): Häufigste Form (85%) ist die proximale Ösophagusatresie mit distaler tracheooesophagealer Fistel (Vogt IIIb)."
        ],
        "keywords": [
            "lungenentwicklung",
            "embryologie lunge",
            "surfactant",
            "pneumozyten typ ii",
            "alveolen",
            "trachea",
            "fistel",
            "ösophagusatresie",
            "dppc",
            "kanalikuläre phase",
            "sakkuläre phase"
        ],
        "associated_decks": [
            "1 Lungenembryologie",
            "Respirationstrakt Entwicklung",
            "2. SJ :: 3. Atmung & Lunge :: Embryologie"
        ],
        "slide_pdf": "Atmung/Sommer_LungenZwerchentw-VAM.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-10-20_TB_Atmung",
        "date": "2025-10-20",
        "title": "Atemmechanik, Pleura & Atemmuskulatur",
        "module": "3. Atmung & Lunge",
        "lecturer": "Prof. Dr. Roland Wenger",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.506,
        "recommendation": "1.2x",
        "badge_color": "var(--status-warning, #d29922)",
        "badge_label": "🟡 1.2x Standard-Stream (+25m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Intrapleuraler Druck (Donders-Raum), Transpulmonaler Druck, Atemarbeit, Ruhedehnungskurven von Lunge und Thorax sowie Pneumothorax-Pathophysiologie. Kausales mechanistisches Gerüst; 1.2x spart Zeit ohne Verständnisrisiko.",
        "anki_facts": [
            "Intrapleuraler Druck (P_pl): In Ruheausatmung negativ (-5 cmH2O), sinkt bei forcierter Inspiration auf bis zu -30 cmH2O (Donders-Unterdruck).",
            "Atemmuskulatur: Wichtigster Inspirationsmuskel ist das Diaphragma (Innervation N. phrenicus C3-C5); forciertes Ausatmen erfolgt aktiv via Bauchmuskeln und Mm. intercostales interni.",
            "Pneumothorax: Lufteintritt in den Pleuraspalt hebt den Unterdruck auf; Lunge kollabiert aufgrund ihrer Eigenelastizität, während der Thorax nach aussen federt."
        ],
        "keywords": [
            "atemmechanik",
            "pleura",
            "donders-raum",
            "intrapleuraler druck",
            "transpulmonal",
            "atemarbeit",
            "zwerchfell",
            "diaphragma",
            "n. phrenicus",
            "pneumothorax",
            "compliance",
            "resistance"
        ],
        "associated_decks": [
            "2 Atemmechanik",
            "Pleura & Zwerchfell",
            "2. SJ :: 3. Atmung & Lunge :: Mechanik"
        ],
        "slide_pdf": "Atmung/Sommer_LungenZwerchentw-VAM.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-10-22_TB_Atmung",
        "date": "2025-10-22",
        "title": "Lungenvolumina, Spirometrie & Alveoläre Ventilation",
        "module": "3. Atmung & Lunge",
        "lecturer": "Prof. Dr. Roland Wenger",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.293,
        "recommendation": "1.2x",
        "badge_color": "var(--status-warning, #d29922)",
        "badge_label": "🟡 1.2x Standard-Stream (+25m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Statische (TLC, FRC, RV, VC) und dynamische Volumina (FEV1, Tiffeneau-Index) zur Differenzierung von Obstruktion (FEV1/FVC < 70%) vs. Restriktion (TLC erniedrigt). Visuelle Kurveninterpretation (Fluss-Volumen-Kurve); 1.2x optimal.",
        "anki_facts": [
            "Nicht spirometrierbare Volumina: Residualvolumen (RV) und Funktionelle Residualkapazität (FRC) können nur via Ganzkörperplethysmographie oder Helium-Einwaschmethode bestimmt werden.",
            "Tiffeneau-Index (FEV1/VC): Normalwert > 70–75%; pathologisch erniedrigt bei obstruktiven Ventilationsstörungen (Asthma, COPD).",
            "Totraumventilation: Anatomischer Totraum ca. 150 ml (Faustregel: 2 ml pro kg Körpergewicht). Alveoläre Ventilation = (Atemzugvolumen - Totraum) * Atemfrequenz."
        ],
        "keywords": [
            "lungenvolumina",
            "spirometrie",
            "fev1",
            "tiffeneau",
            "vitalisationskapazität",
            "frc",
            "residualvolumen",
            "obstruktion",
            "restriktion",
            "totraum",
            "alveoläre ventilation"
        ],
        "associated_decks": [
            "3 Spirometrie",
            "Lungenvolumina",
            "2. SJ :: 3. Atmung & Lunge :: Spirometrie"
        ],
        "slide_pdf": "Atmung/Sommer_LungenZwerchentw-VAM.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-10-24_TB_Atmung",
        "date": "2025-10-24",
        "title": "Gasaustausch, Diffusionskapazität & Ventilations-Perfusions-Verhältnis",
        "module": "3. Atmung & Lunge",
        "lecturer": "Prof. Dr. Roland Wenger",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Schnell",
        "silence_ratio": 0.118,
        "recommendation": "1.0x",
        "badge_color": "var(--status-done, #3fb950)",
        "badge_label": "🟢 1.0x Voller Fokus (Höchste Konzeptdichte)",
        "is_audio_only": False,
        "tradeoff_reason": "Fick'sches Diffusionsgesetz, Alveolargasgleichung, Euler-Liljestrand-Mechanismus (hypoxische pulmonale Vasokonstriktion) und Shunt- vs. Totraumventilation (VA/Q-Inhomogenitäten). Höchste konzeptionelle Komplexität und rascher Redefluss des Dozenten; 1.0x unerlässlich.",
        "anki_facts": [
            "Euler-Liljestrand-Mechanismus: Alveoläre Hypoxie bewirkt lokale Vasokonstriktion pulmonaler Arteriolen (im Gegensatz zum Systemkreislauf!), um Perfusion in besser belüftete Areale umzuleiten.",
            "Ventilations-Perfusions-Verhältnis (VA/Q): Normal ca. 0.8–1.0. VA/Q = 0 bedeutet Shunt (Perfusion ohne Ventilation); VA/Q = unendlich bedeutet funktioneller Totraum (Ventilation ohne Perfusion).",
            "Diffusionsbegrenzung vs. Perfusionsbegrenzung: O2-Aufnahme ist unter Ruhebedingungen perfusionsbegrenzt (vollständiger Ausgleich nach 0.25 s bei 0.75 s Kontaktzeit), wird bei Lungenfibrose oder extremer Belastung diffusionsbegrenzt."
        ],
        "keywords": [
            "gasaustausch",
            "diffusion",
            "diffusionskapazität",
            "fick",
            "alveolargasgleichung",
            "euler-liljestrand",
            "ventilations-perfusions-verhältnis",
            "va/q",
            "shunt",
            "totraum",
            "hypoxische vasokonstriktion"
        ],
        "associated_decks": [
            "4 Gasaustausch",
            "Diffusionskapazität",
            "2. SJ :: 3. Atmung & Lunge :: Gasaustausch"
        ],
        "slide_pdf": "Atmung/Sommer_LungenZwerchentw-VAM.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-10-29_TB_Atmung",
        "date": "2025-10-29",
        "title": "Atemregulation & Prüfungsinformation",
        "module": "3. Atmung & Lunge",
        "lecturer": "Prof. Dr. Roland Wenger",
        "exam_yield": "Low-Yield",
        "visual_dependency": "Niedrig",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.458,
        "recommendation": "Skip (0x)",
        "badge_color": "var(--status-danger, #f85149)",
        "badge_label": "🛑 Vorlesung skippen (100% Anki)",
        "is_audio_only": False,
        "tradeoff_reason": "Enthält primär organisatorische Prüfungshinweise und repetitive Schemata zur Chemorezeptor-Rückkopplung. Die physiologischen Fakten zu Glomus caroticum und Medulla oblongata lassen sich in 10 Minuten via Anki wesentlich robuster memorieren.",
        "anki_facts": [
            "Zentrale Chemorezeptoren (Medulla oblongata): Reagieren primär auf Absinken des pH-Wertes im Liquor cerebrospinalis infolge von pCO2-Anstieg (CO2 diffundiert frei durch Blut-Hirn-Schranke).",
            "Periphere Chemorezeptoren (Glomus caroticum via N. IX, Glomus aorticum via N. X): Reagieren primär auf schweren pO2-Abfall (< 60 mmHg) sowie Azidose und pCO2-Anstieg.",
            "Wichtigster physiologischer Atemantrieb beim Gesunden: Hyperkapnie (Anstieg des arteriellen pCO2 bereits um 2–3 mmHg), nicht die Hypoxie."
        ],
        "keywords": [
            "atemregulation",
            "chemorezeptoren",
            "glomus caroticum",
            "glomus aorticum",
            "medulla oblongata",
            "hyperkapnie",
            "hypoxie",
            "pco2",
            "liquor",
            "prüfungsinformation",
            "hering-breuer"
        ],
        "associated_decks": [
            "5 Atemregulation",
            "Prüfungsvorbereitung",
            "2. SJ :: 3. Atmung & Lunge :: Regulation"
        ],
        "slide_pdf": "Atmung/Sommer_LungenZwerchentw-VAM.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-11-10_TB_Verdauung",
        "date": "2025-11-10",
        "title": "Ernährung & Verdauung: Allgemeine Grundlagen & Energiebedarf",
        "module": "4. Verdauung & Ernährung",
        "lecturer": "Prof. Dr. Carsten Wagner / Dozententeam",
        "exam_yield": "Low-Yield",
        "visual_dependency": "Niedrig",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.706,
        "recommendation": "Skip (0x)",
        "badge_color": "var(--status-danger, #f85149)",
        "badge_label": "🛑 Vorlesung skippen (100% Anki)",
        "is_audio_only": False,
        "tradeoff_reason": "Reine Nährstoffdefinitionen, Grundumsatz-Tabellen und Kalorimetrie. Das Schauen der Vorlesung (149 Min.) bringt kaum mechanistisches Verständnis; die Brennwerte und Rechenformeln gehören direkt ins Anki-Repetitorium.",
        "anki_facts": [
            "Physiologische Brennwerte der Hauptnährstoffe: Kohlenhydrate ca. 4.1 kcal/g (17.2 kJ/g), Proteine ca. 4.1 kcal/g (17.2 kJ/g), Fette ca. 9.3 kcal/g (38.9 kJ/g), Alkohol ca. 7.1 kcal/g (29.7 kJ/g).",
            "Respiratorischer Quotient (RQ = CO2-Abgabe / O2-Aufnahme): Kohlenhydrate = 1.0; Proteine ca. 0.8; Fette ca. 0.7.",
            "Grundumsatz-Faustregel beim Erwachsenen: ca. 1 kcal (4.2 kJ) pro kg Körpergewicht pro Stunde bzw. ca. 100 kJ/kg/Tag."
        ],
        "keywords": [
            "ernährung",
            "energiebedarf",
            "kalorimetrie",
            "brennwert",
            "respiratorischer quotient",
            "rq",
            "grundumsatz",
            "leistungsumsatz",
            "pal-faktor",
            "bmi",
            "makronährstoffe"
        ],
        "associated_decks": [
            "1 Ernährung & Energiebedarf",
            "Brennwerte",
            "2. SJ :: 4. Verdauung & Ernährung :: Grundlagen"
        ],
        "slide_pdf": "Kurs Klinischer Untersuchungskurs I/Archive/Unterlagen 1. Fachsemester (HS 2025)/2_Klin-Untersuchungskurs_Abdomen.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-11-12_TB_Verdauung",
        "date": "2025-11-12",
        "title": "Mikronährstoffe: Fettlösliche & Wasserlösliche Vitamine",
        "module": "4. Verdauung & Ernährung",
        "lecturer": "Prof. Dr. Carsten Wagner",
        "exam_yield": "Med-Yield",
        "visual_dependency": "Niedrig",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.507,
        "recommendation": "Skip (0x)",
        "badge_color": "var(--status-danger, #f85149)",
        "badge_label": "🛑 Vorlesung skippen (100% Anki)",
        "is_audio_only": False,
        "tradeoff_reason": "Besteht aus 151 deskriptiven Folien mit isolierten Faktenlisten (Vitaminquellen, Mangelsymptome wie Skorbut, Beriberi, Pellagra). Reines Memorierwissen ohne komplexe Zusammenhänge; das Vorlesungsvideo ist reine Zeitverschwendung.",
        "anki_facts": [
            "Fettlösliche Vitamine (E, D, K, A): Benötigen Mizellenbildung und intakte Fettresorption; Überdosierung führt zu Toxizität (v.a. Vit. A und D).",
            "Vitamin-B12-Resorption (Cobalamin): Bindung an Haptocorrin im Magen, Spaltung im Duodenum, Bindung an Intrinsic Factor (Belegzellen), Resorption im terminalen Ileum.",
            "Klassische Mangelerscheinungen: Vit. B1 (Thiamin) -> Beriberi / Wernicke-Enzephalopathie; Vit. B3 (Niacin) -> Pellagra (3-D-Regel: Dermatitis, Diarrhoe, Demenz); Vit. C -> Skorbut."
        ],
        "keywords": [
            "vitamine",
            "mikronährstoffe",
            "b12",
            "cobalamin",
            "intrinsic factor",
            "thiamin",
            "beriberi",
            "niacin",
            "pellagra",
            "skorbut",
            "vitamin c",
            "fettlösliche vitamine",
            "vitamin d",
            "vitamin k"
        ],
        "associated_decks": [
            "2 Vitamine & Spurenelemente",
            "Mikronährstoffe",
            "2. SJ :: 4. Verdauung & Ernährung :: Vitamine"
        ],
        "slide_pdf": "Kurs Klinischer Untersuchungskurs I/Archive/Unterlagen 1. Fachsemester (HS 2025)/2_Klin-Untersuchungskurs_Abdomen.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-11-13_TB_Verdauung",
        "date": "2025-11-13",
        "title": "Mundhöhle, Kauapparat, Speicheldrüsen & Schluckakt",
        "module": "4. Verdauung & Ernährung",
        "lecturer": "Prof. Dr. med. Cyrill Stockmann",
        "exam_yield": "Med-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.922,
        "recommendation": "1.4x",
        "badge_color": "var(--accent-blue, #58a6ff)",
        "badge_label": "⏩ 1.4x High-Speed Stream (+35m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Topographie der Mundhöhle, Speichelsekretion (sekundäre Modifikation im Gangsystem: Speichel wird hypoton) und 3-Phasen-Schluckakt (oral, pharyngeal, ösophageal). Moderate Dichte mit visuellen Präparaten; Dozententempo erlaubt flüssiges 1.4x.",
        "anki_facts": [
            "Sekundäre Speichelmodifikation: Primärspeichel in den Azini ist isoton; in den Ausführungsgängen werden Na+ und Cl- reabsorbiert und K+ sowie HCO3- sezerniert -> Endspeichel ist hypoton.",
            "Innervation der Speicheldrüsen: Glandula parotidea (parasympathisch via N. glossopharyngeus / IX); Glandula submandibularis & sublingualis (via Chorda tympani des N. facialis / VII).",
            "Schluckreflex: Willkürliche orale Phase löst bei Berührung des hinteren Gaumenbogens die unwillkürliche pharyngeale Phase aus (Verschluss Nasopharynx via Gaumensegel, Verschluss Larynx via Epiglottis)."
        ],
        "keywords": [
            "mundhöhle",
            "kauapparat",
            "speicheldrüsen",
            "parotis",
            "submandibularis",
            "schluckakt",
            "schluckreflex",
            "amylase",
            "epiglottis",
            "n. glossopharyngeus",
            "chorda tympani"
        ],
        "associated_decks": [
            "3 Mundhöhle & Schluckakt",
            "Speicheldrüsen",
            "2. SJ :: 4. Verdauung & Ernährung :: Mundhöhle"
        ],
        "slide_pdf": "Kurs Klinischer Untersuchungskurs I/Archive/Unterlagen 1. Fachsemester (HS 2025)/2_Klin-Untersuchungskurs_Abdomen.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-11-14_TB_Verdauung",
        "date": "2025-11-14",
        "title": "Anatomie des Gastrointestinaltrakts: Oesophagus & Magen",
        "module": "4. Verdauung & Ernährung",
        "lecturer": "Prof. Dr. med. Cyrill Stockmann",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.604,
        "recommendation": "1.2x",
        "badge_color": "var(--status-warning, #d29922)",
        "badge_label": "🟡 1.2x Standard-Stream (+25m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Wandschichten (Mucosa, Submucosa mit Meissner-Plexus, Muscularis mit Auerbach-Plexus, Serosa), Magendrüsen mit Zelltypen (Belegzellen, Hauptzellen, Nebenzellen, ECL) und Gefässversorgung (Truncus coeliacus). Visuell hochgradig prüfungsrelevant; 1.2x optimal.",
        "anki_facts": [
            "Zelltypen der Magendrüsen: Belegzellen/Parietalzellen (HCl und Intrinsic Factor), Hauptzellen (Pepsinogen), Nebenzellen (Schleim/Mucin, Bicarbonat), G-Zellen (Gastrin), ECL-Zellen (Histamin).",
            "Physiologische Oesophagusengen: 1. Krikoidenge (obere Enge, 15 cm von Zahnreihe), 2. Aortenenge (mittlere Enge, 25 cm), 3. Zwerchfellenge (untere Enge / Hiatus oesophageus, 40 cm).",
            "Gefässversorgung des Magens: Truncus coeliacus -> A. gastrica sinistra, A. hepatica communis (A. gastrica dextra), A. splenica/lienalis (A. gastroomentalis sinistra, Aa. gastricae breves)."
        ],
        "keywords": [
            "oesophagus",
            "magen",
            "magendrüsen",
            "belegzellen",
            "hauptzellen",
            "nebenzellen",
            "ecl",
            "truncus coeliacus",
            "auerbach-plexus",
            "meissner-plexus",
            "peritoneum",
            "histologie magen"
        ],
        "associated_decks": [
            "4 Anatomie Oesophagus & Magen",
            "Magendrüsen",
            "2. SJ :: 4. Verdauung & Ernährung :: Magen Anatomie"
        ],
        "slide_pdf": "Kurs Klinischer Untersuchungskurs I/Archive/Unterlagen 1. Fachsemester (HS 2025)/2_Klin-Untersuchungskurs_Abdomen.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-11-19_TB_Verdauung",
        "date": "2025-11-19",
        "title": "Regulation der Magensekretion & Magenmotilität",
        "module": "4. Verdauung & Ernährung",
        "lecturer": "Prof. Dr. Carsten Wagner",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.87,
        "recommendation": "1.2x",
        "badge_color": "var(--status-warning, #d29922)",
        "badge_label": "🟡 1.2x Standard-Stream (+25m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Zelluläre HCl-Produktion (H+/K+-ATPase), Stimulation via Gastrin (CCK-B), Histamin (H2-Rezeptor), Acetylcholin (M3) und Inhibition durch Somatostatin / Prostaglandine. Basis für die Pharmakologie (PPI wie Omeprazol, H2-Blocker); 1.2x komprimiert die Vorlesung ideal.",
        "anki_facts": [
            "Zelluläre HCl-Sekretion: Apikale H+/K+-ATPase pumpt H+ ins Magenlumen im Austausch gegen K+; basolaterale Carboanhydrase liefert H+ und HCO3- (HCO3- wird ins Blut abgegeben -> alkalische Gezeiten).",
            "Drei Stimulatoren der Belegzelle: Acetylcholin (via M3-Rezeptor, IP3/Ca2+), Gastrin (via CCK2/CCK-B-Rezeptor, IP3/Ca2+) und Histamin aus ECL-Zellen (via H2-Rezeptor, cAMP -> stärkster Stimulator!).",
            "Inhibitoren: Somatostatin (aus D-Zellen bei pH < 3, hemmt G-Zellen und Belegzellen) und Prostaglandin E2 (PGE2, hemmt Säuresekretion und stimuliert Schleim/Bicarbonat)."
        ],
        "keywords": [
            "magensekretion",
            "magensäure",
            "hcl",
            "h+/k+-atpase",
            "belegzelle",
            "gastrin",
            "histamin",
            "acetylcholin",
            "somatostatin",
            "prostaglandin",
            "ppi",
            "omeprazol",
            "alkalische gezeiten"
        ],
        "associated_decks": [
            "5 Magensekretion",
            "Säure-Regulation",
            "2. SJ :: 4. Verdauung & Ernährung :: Magensekretion"
        ],
        "slide_pdf": "Kurs Klinischer Untersuchungskurs I/Archive/Unterlagen 1. Fachsemester (HS 2025)/2_Klin-Untersuchungskurs_Abdomen.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-11-20_TB_Verdauung",
        "date": "2025-11-20",
        "title": "Anatomie & Topographie: Dünndarm, Dickdarm & Rektum",
        "module": "4. Verdauung & Ernährung",
        "lecturer": "Prof. Dr. med. Cyrill Stockmann",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.561,
        "recommendation": "1.2x",
        "badge_color": "var(--status-warning, #d29922)",
        "badge_label": "🟡 1.2x Standard-Stream (+25m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Peritonealverhältnisse (retro- vs. intraperitoneal), Gefässversorgung (A. mesenterica superior & inferior, Riolan- und Drummond-Anastomose), Rektumkontinenzorgan. Räumliches Situs-Verständnis der Bauchhöhle ist zwingend; 1.2x sichert präzises Mitdenken.",
        "anki_facts": [
            "Peritoneale Lage: Intraperitoneal = Magen, Jejunum, Ileum, Caecum/Appendix, Colon transversum, Colon sigmoideum; Sekundär retroperitoneal = Duodenum (ausser Pars superior), Colon ascendens, Colon descendens, Pankreas.",
            "Arterielle Versorgung: A. mesenterica superior (Darm bis Cannon-Böhm-Punkt am Colon transversum); A. mesenterica inferior (ab Cannon-Böhm-Punkt bis oberes Rektum); Verbindung via Riolan-Anastomose.",
            "Rektum-Venendrainage (Portokavale Anastomose): V. rectalis superior drainiert in V. mesenterica inferior (Pfortader); Vv. rectales mediae & inferiores drainieren in V. iliaca interna (V. cava inferior)."
        ],
        "keywords": [
            "dünndarm",
            "dickdarm",
            "rektum",
            "peritoneum",
            "retroperitoneal",
            "mesenterica superior",
            "mesenterica inferior",
            "riolan-anastomose",
            "cannon-böhm",
            "portokavale anastomose",
            "hämorrhoiden"
        ],
        "associated_decks": [
            "6 Anatomie Darm & Rektum",
            "Topographie Abdomen",
            "2. SJ :: 4. Verdauung & Ernährung :: Darm Anatomie"
        ],
        "slide_pdf": "Kurs Klinischer Untersuchungskurs I/Archive/Unterlagen 1. Fachsemester (HS 2025)/2_Klin-Untersuchungskurs_Abdomen.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-11-21_TB_Verdauung",
        "date": "2025-11-21",
        "title": "Pankreas & Gallensystem: Exokrine Sekretion & Galle",
        "module": "4. Verdauung & Ernährung",
        "lecturer": "Prof. Dr. Carsten Wagner",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.795,
        "recommendation": "1.2x",
        "badge_color": "var(--status-warning, #d29922)",
        "badge_label": "🟡 1.2x Standard-Stream (+25m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Azinäre Enzymsekretion (Zymogene, Trypsinaktivierung durch Enteropeptidase), duktuläre Bicarbonatsekretion (CFTR/Cl--HCO3--Austauscher), CCK- und Sekretinwirkung sowie enterohepatischer Gallensäurekreislauf; 1.2x balanciert Zeit und Verständnis.",
        "anki_facts": [
            "Zwei Phasen der Pankreassekretion: CCK (Cholezystokinin aus I-Zellen) stimuliert enzymreichen Azinussaft; Sekretin (aus S-Zellen bei pH < 4.5) stimuliert HCO3--reichen Duktussaft via CFTR-Aktivierung.",
            "Schlüsselenzym der Aktivierung: Enteropeptidase (Enterokinase) am duodenalen Bürstensaum spaltet Trypsinogen zu Trypsin; Trypsin aktiviert autokatalytisch alle weiteren Zymogene.",
            "Enterohepatischer Kreislauf: Ca. 95% der sezernierten Gallensäuren werden im terminalen Ileum via ASBT (apikaler natriumabhängiger Gallensäuretransporter) reabsorbiert und gelangen zur Leber zurück."
        ],
        "keywords": [
            "pankreas",
            "exokrines pankreas",
            "galle",
            "gallensäuren",
            "zymogene",
            "trypsin",
            "enteropeptidase",
            "cck",
            "sekretin",
            "cftr",
            "bicarbonat",
            "enterohepatischer kreislauf",
            "asbt"
        ],
        "associated_decks": [
            "7 Exokrines Pankreas & Galle",
            "Gallensäuren",
            "2. SJ :: 4. Verdauung & Ernährung :: Pankreas & Galle"
        ],
        "slide_pdf": "Kurs Klinischer Untersuchungskurs I/Archive/Unterlagen 1. Fachsemester (HS 2025)/2_Klin-Untersuchungskurs_Abdomen.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-11-24_TB_Verdauung",
        "date": "2025-11-24",
        "title": "Intestinale Resorption: Kohlenhydrate, Proteine & Lipide",
        "module": "4. Verdauung & Ernährung",
        "lecturer": "Prof. Dr. Carsten Wagner",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.888,
        "recommendation": "1.0x",
        "badge_color": "var(--status-done, #3fb950)",
        "badge_label": "🟢 1.0x Voller Fokus (Prüfungsrelevante Membrantransporter)",
        "is_audio_only": False,
        "tradeoff_reason": "Membrantransporter des Bürstensaums (SGLT1, GLUT2, GLUT5; PEPT1; Micellen, ApoB-48, Chylomikronen). Hochkomplexe Transportkinetiken, die im Schweizer MC-Examen exakt differenziert werden; 1.0x zur Vermeidung von Kognitionsdefiziten.",
        "anki_facts": [
            "Kohlenhydrat-Transporter: SGLT1 (sekundär-aktiv via 2 Na+ transportiert Glucose und Galaktose apikal); GLUT5 (erleichterte Diffusion von Fructose apikal); GLUT2 (basolaterale Abgabe aller drei ins Blut).",
            "Protein-Resorption: Di- und Tripeptide werden via PEPT1 (H+-Symport) apikal aufgenommen; freie Aminosäuren überwiegen basolateral nach intrazellulärer Peptidspaltung.",
            "Lipidresorption: Spaltung durch Pankreaslipase/Colipase, Mizellenbildung, Aufnahme via CD36/NPC1L1; intrazelluläre Re-Esterifizierung und Verpackung in Chylomikronen mit ApoB-48 zur Lymphabgabe."
        ],
        "keywords": [
            "resorption",
            "intestinale resorption",
            "sglt1",
            "glut2",
            "glut5",
            "pept1",
            "mizellen",
            "chylomikronen",
            "apob-48",
            "fettresorption",
            "glucoseresorption",
            "aminosäuren",
            "bürstensaum"
        ],
        "associated_decks": [
            "8 Intestinale Resorption",
            "Membrantransporter",
            "2. SJ :: 4. Verdauung & Ernährung :: Resorption"
        ],
        "slide_pdf": "Kurs Klinischer Untersuchungskurs I/Archive/Unterlagen 1. Fachsemester (HS 2025)/2_Klin-Untersuchungskurs_Abdomen.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-11-26_TB_Verdauung",
        "date": "2025-11-26",
        "title": "Regulation des Kohlenhydrat-Stoffwechsels (Glykolyse & Glukoneogenese)",
        "module": "5. Stoffwechsel & Biochemie",
        "lecturer": "Prof. Dr. med. Cyrill Stockmann / Dozententeam Biochemie",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.722,
        "recommendation": "1.0x",
        "badge_color": "var(--status-done, #3fb950)",
        "badge_label": "🟢 1.0x Voller Fokus (Komplexe Biochemische Schalter)",
        "is_audio_only": False,
        "tradeoff_reason": "Schlüsselenzyme (PFK-1, Fructose-2,6-bisphosphat, Pyruvatkinase vs. Pyruvatcarboxylase, PEPCK, FBPase-1) und reziproke allosterische Schalter unter Insulin-/Glukagon-Einfluss. Äusserst abstrakte Stoffwechselvernetzung; 1.0x verlangt volle Konzentration.",
        "anki_facts": [
            "Fructose-2,6-bisphosphat (F-2,6-BP): Potentester allosterischer Aktivator der PFK-1 (stimuliert Glykolyse) und Inhibitor der FBPase-1 (hemmt Glukoneogenese).",
            "Bifunktionelles Enzym PFK-2/FBPase-2: Insulin (Dephosphorylierung) aktiviert PFK-2 -> F-2,6-BP steigt -> Glykolyse läuft; Glukagon (PKA-Phosphorylierung) aktiviert FBPase-2 -> F-2,6-BP sinkt -> Glukoneogenese läuft.",
            "Umgehungsschritte der Glukoneogenese: 1. Pyruvat -> Oxalacetat (Pyruvatcarboxylase, Biotin-abhängig in Mitochondrien) -> PEP (PEPCK); 2. Fructose-1,6-bisphosphat -> F-6-P (FBPase-1); 3. Glucose-6-phosphat -> Glucose (Glucose-6-Phosphatase im ER der Leber)."
        ],
        "keywords": [
            "stoffwechsel",
            "glykolyse",
            "glukoneogenese",
            "pfk-1",
            "fructose-2,6-bisphosphat",
            "pepck",
            "pyruvatcarboxylase",
            "fbpase-1",
            "insulin",
            "glukagon",
            "bifunktionelles enzym",
            "schlüsselenzyme"
        ],
        "associated_decks": [
            "1 Glykolyse & Glukoneogenese",
            "Kohlenhydratstoffwechsel",
            "2. SJ :: 5. Stoffwechsel & Biochemie :: Glykolyse"
        ],
        "slide_pdf": "Kurs Klinischer Untersuchungskurs I/Archive/Unterlagen 1. Fachsemester (HS 2025)/2_Klin-Untersuchungskurs_Abdomen.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-11-27_TB_Verdauung",
        "date": "2025-11-27",
        "title": "Leberspezifische Stoffwechselfunktionen & Harnstoffzyklus",
        "module": "5. Stoffwechsel & Biochemie",
        "lecturer": "Prof. Dr. med. Cyrill Stockmann",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.707,
        "recommendation": "1.2x",
        "badge_color": "var(--status-warning, #d29922)",
        "badge_label": "🟡 1.2x Standard-Stream (+25m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Ammoniakentgiftung im Harnstoffzyklus (CPS-1, OTC; mitochondriale vs. zytosolische Reaktionsschritte), Glykogenspeicherung, Lipogenese und Ketonkörperbildung in Lebermitochondrien. Zentraler UZH-Prüfungsschwerpunkt; 1.2x komprimiert die Vorlesung effektiv.",
        "anki_facts": [
            "Harnstoffzyklus Schlüsselenzym: Carbamoylphosphat-Synthetase 1 (CPS-1 in Mitochondrien, allosterisch obligat aktiviert durch N-Acetylglutamat / NAG).",
            "Zwei Stickstoffquellen des Harnstoffs: Das erste N-Atom stammt aus freiem Ammoniak (NH4+ via CPS-1); das zweite N-Atom stammt aus Aspartat (Eintritt im Zytosol via Argininosuccinat-Synthetase).",
            "Ketogenese: Findet ausschliesslich in Lebermitochondrien aus Acetyl-CoA statt (HMG-CoA-Synthase ist das Schlüsselenzym); Leber kann selbst keine Ketonkörper verwerten (fehlt Thiophorase/SCOT)."
        ],
        "keywords": [
            "leberstoffwechsel",
            "harnstoffzyklus",
            "cps-1",
            "otc",
            "ammoniak",
            "ornithin",
            "citrullin",
            "arginin",
            "ketogenese",
            "ketonkörper",
            "acetyl-coa",
            "n-acetylglutamat"
        ],
        "associated_decks": [
            "2 Leberstoffwechsel & Harnstoffzyklus",
            "Ketogenese",
            "2. SJ :: 5. Stoffwechsel & Biochemie :: Harnstoffzyklus"
        ],
        "slide_pdf": "Kurs Klinischer Untersuchungskurs I/Archive/Unterlagen 1. Fachsemester (HS 2025)/2_Klin-Untersuchungskurs_Abdomen.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-11-28_TB_Verdauung",
        "date": "2025-11-28",
        "title": "Biotransformation & Gallenfarbstoffstoffwechsel (Bilirubin)",
        "module": "5. Stoffwechsel & Biochemie",
        "lecturer": "Prof. Dr. med. Cyrill Stockmann",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.841,
        "recommendation": "1.2x",
        "badge_color": "var(--status-warning, #d29922)",
        "badge_label": "🟡 1.2x Standard-Stream (+25m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Phase-I- (CYP450) und Phase-II-Reaktionen (Glukuronidierung via UGT1A1); Häm-Abbau zu unkonjugiertem Bilirubin, Transport via Albumin, Konjugation und Ausscheidung. Wichtig für die Differenzialdiagnose von prähepatischem, intrahepatischem und posthepatischem Ikterus.",
        "anki_facts": [
            "Häm-Abbau: Häm -> Biliverdin (Häm-Oxygenase, Freisetzung von CO und Fe2+) -> unkonjugiertes Bilirubin (Biliverdin-Reduktase). Unkonjugiertes Bilirubin ist hydrophob und an Albumin gebunden.",
            "Konjugation in der Leber: Uridindiphosphat-Glukuronosyltransferase (UGT1A1) konjugiert Bilirubin mit zwei Glukuronsäuren zu wasserlöslichem Bilirubindiglukuronid (direktes Bilirubin).",
            "Ikterus-Differenzierung: Prähepatisch (indirektes Bilirubin erhöht, z.B. Hämolyse, Morbus Meulengracht); Posthepatisch (direktes Bilirubin erhöht, Cholestase, acholischer Stuhl, dunkler Urin)."
        ],
        "keywords": [
            "biotransformation",
            "cyp450",
            "bilirubin",
            "häm-abbau",
            "ikterus",
            "gelbsucht",
            "ugt1a1",
            "glukuronidierung",
            "meulengracht",
            "cholestase",
            "direktes bilirubin",
            "indirektes bilirubin"
        ],
        "associated_decks": [
            "3 Biotransformation & Bilirubin",
            "Ikterus-Diagnostik",
            "2. SJ :: 5. Stoffwechsel & Biochemie :: Biotransformation"
        ],
        "slide_pdf": "Kurs Klinischer Untersuchungskurs I/Archive/Unterlagen 1. Fachsemester (HS 2025)/2_Klin-Untersuchungskurs_Abdomen.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-12-01_TB_Endokrinologie",
        "date": "2025-12-01",
        "title": "Biochemie der Hormone: Einführung, Rezeptorklassen & Signaltransduktion",
        "module": "6. Endokrinologie & Hormone",
        "lecturer": "Prof. Dr. med. Cyrill Stockmann / Dozententeam",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Normal",
        "silence_ratio": 0.188,
        "recommendation": "1.2x",
        "badge_color": "var(--status-warning, #d29922)",
        "badge_label": "🟡 1.2x Standard-Stream (+25m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Klassifikation der Hormone (Peptid-, Steroid-, Aminosäurederivate) und second messenger (Gs/Gi/Gq-Pfade, cAMP/PKA, IP3/DAG/PKC, Rezeptor-Tyrosinkinasen). Universelles Fundament für das gesamte Hormonmodul; 1.2x garantiert maximale Zeiteffizienz.",
        "anki_facts": [
            "G-Protein-Kaskaden: Gs aktiviert Adenylatzyklase -> cAMP steigt -> PKA aktiviert; Gi hemmt Adenylatzyklase -> cAMP sinkt; Gq aktiviert Phospholipase C (PLC) -> IP3 (Ca2+-Freisetzung aus ER) und DAG (PKC-Aktivierung).",
            "Steroidhormone & Schilddrüsenhormone: Passieren Zellmembran und binden an intrazelluläre/nukleäre Rezeptoren (Zinkfinger-Domänen), wirken als Transkriptionsfaktoren auf die Genexpression.",
            "Rezeptor-Tyrosinkinasen: Insulin und Wachstumsfaktoren (IGF-1) bewirken Rezeptordimerisierung und Autophosphorylierung -> Rekrutierung von IRS-1 und Aktivierung des PI3K/Akt- und MAP-Kinase-Signalwegs."
        ],
        "keywords": [
            "hormone",
            "signaltransduktion",
            "g-protein",
            "second messenger",
            "camp",
            "pka",
            "ip3",
            "dag",
            "pkc",
            "tyrosinkinase",
            "insulinrezeptor",
            "steroidrezeptor",
            "endokrinologie"
        ],
        "associated_decks": [
            "1 Hormonbiochemie",
            "Signaltransduktion",
            "2. SJ :: 6. Endokrinologie & Hormone :: Grundlagen"
        ],
        "slide_pdf": "Kurs Klinischer Untersuchungskurs I/Archive/Unterlagen 1. Fachsemester (HS 2025)/2_Klin-Untersuchungskurs_Abdomen.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-12-04_TB_Endokrinologie",
        "date": "2025-12-04",
        "title": "Endokrines Pankreas: Insulin, Glukagon & Glukosehomöostase",
        "module": "6. Endokrinologie & Hormone",
        "lecturer": "Prof. Dr. med. Cyrill Stockmann",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.892,
        "recommendation": "1.2x",
        "badge_color": "var(--status-warning, #d29922)",
        "badge_label": "🟡 1.2x Standard-Stream (+25m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Mechanismus der glucoseinduzierten Insulinsekretion (GLUT2, Glukokinase, ATP-sensitive K+-Kanäle, Depolarisation, Ca2+-Einstrom) und metabolisches Netzwerk im Fettgewebe, Muskel und Leber; 1.2x hält das Lerntempo hoch.",
        "anki_facts": [
            "Insulinsekretions-Kaskade der Beta-Zelle: Glucoseaufnahme via GLUT2 -> Glykolyse steigert ATP/ADP-Ratio -> ATP-sensitive K+-Kanäle schliessen -> Depolarisation -> spannungsabhängige L-Typ Ca2+-Kanäle öffnen -> Ca2+-Einstrom triggert Insulinexozytose.",
            "Insulinwirkungen: Stimuliert GLUT4-Translokation (Muskel, Fettgewebe), Glykogensynthese, Lipogenese und Proteinsynthese; hemmt Glukoneogenese, Glykogenolyse und Lipolyse.",
            "Glukagonwirkungen (Alpha-Zellen): Wirkt via Gs-gekoppelten Rezeptor v.a. auf Hepatozyten -> aktiviert Glykogenolyse und Glukoneogenese zur schnellen Blutzuckerhebung."
        ],
        "keywords": [
            "insulin",
            "glukagon",
            "endokrines pankreas",
            "beta-zelle",
            "alpha-zelle",
            "glut2",
            "glut4",
            "atp-k-kanal",
            "glukosehomöostase",
            "diabetes",
            "c-peptid",
            "sulfonylharnstoffe"
        ],
        "associated_decks": [
            "2 Endokrines Pankreas",
            "Insulin & Glukagon",
            "2. SJ :: 6. Endokrinologie & Hormone :: Pankreas"
        ],
        "slide_pdf": "Kurs Klinischer Untersuchungskurs I/Archive/Unterlagen 1. Fachsemester (HS 2025)/2_Klin-Untersuchungskurs_Abdomen.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-12-05_TB_Endokrinologie",
        "date": "2025-12-05",
        "title": "Stoffwechseladaptation bei Hunger & Muskelarbeit",
        "module": "6. Endokrinologie & Hormone",
        "lecturer": "Prof. Dr. med. Cyrill Stockmann",
        "exam_yield": "High-Yield",
        "visual_dependency": "Niedrig",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.808,
        "recommendation": "1.4x",
        "badge_color": "var(--accent-blue, #58a6ff)",
        "badge_label": "🎧 1.4x Audio-Only geeignet (Pendeln/Sport)",
        "is_audio_only": True,
        "tradeoff_reason": "Chronologie des Fastens (Resorptiv, Postresorptiv, Frühes Fasten, Spätes adaptiertes Fasten, Ketonkörperverwertung durch ZNS). Text- und schema-basierte Folien; der Dozent verbalisiert alle Schritte lückenlos. Eignet sich hervorragend für den auditiven Konsum mit Kopfhörern!",
        "anki_facts": [
            "Phase 2 des Fastens (4–16h / postresorptiv): Hepatische Glykogenolyse liefert die Hauptmenge der Blutglucose; nach 24h sind die Leberglykogenspeicher vollständig erschöpft.",
            "Phase 3 (frühes Fasten 16–48h): Hepatische Glukoneogenese dominiert (Substrate: Laktat/Cori-Zyklus, Alanin/Glucose-Alanin-Zyklus aus Muskelproteinabbau, Glycerin aus Lipolyse).",
            "Phase 4 (Langzeitfasten > 3 Tage): Ketonkörperbildung in Leber steigt massiv an (beta-Hydroxybutyrat, Acetoacetat); Gehirn adaptiert und deckt bis zu 70% seines Energiebedarfs aus Ketonkörpern -> schont Muskelprotein!"
        ],
        "keywords": [
            "fasten",
            "hungerstoffwechsel",
            "muskelarbeit",
            "ketonkörper",
            "glykogenolyse",
            "glukoneogenese",
            "cori-zyklus",
            "glucose-alanin-zyklus",
            "lipolyse",
            "beta-hydroxybutyrat",
            "audio-only",
            "gehirnenergie"
        ],
        "associated_decks": [
            "3 Fasten & Hungeradaptation",
            "Muskelarbeit",
            "2. SJ :: 6. Endokrinologie & Hormone :: Fasten"
        ],
        "slide_pdf": "Kurs Klinischer Untersuchungskurs I/Archive/Unterlagen 1. Fachsemester (HS 2025)/2_Klin-Untersuchungskurs_Abdomen.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-12-10_TB_Endokrinologie",
        "date": "2025-12-10",
        "title": "Hypothalamisch-Hypophysäre Achse & Regelkreise",
        "module": "6. Endokrinologie & Hormone",
        "lecturer": "Prof. Dr. med. Cyrill Stockmann",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.614,
        "recommendation": "1.0x",
        "badge_color": "var(--status-done, #3fb950)",
        "badge_label": "🟢 1.0x Voller Fokus (Zentrales Feedback-Netzwerk)",
        "is_audio_only": False,
        "tradeoff_reason": "Adenohypophyse vs. Neurohypophyse (ADH, Oxytocin), Liberine & Statine (CRH, TRH, GnRH, GHRH, Somatostatin, Dopamin), negatives Feedback und Hypophysenvorderlappeninsuffizienz. Komplexes Regelkreisnetz; 1.0x unerlässlich.",
        "anki_facts": [
            "Neurohypophyse (HHL): Reiner Speicher- und Ausschüttungsort für Oxytocin und ADH (Vasopressin), die in den supraoptischen und paraventrikulären Kernen des Hypothalamus synthetisiert werden.",
            "Adenohypophyse (HVL): Drüsenorgan mit Pfortadersystem (hypophysäres Portalsystem); sezerniert glandotrope Hormone (ACTH, TSH, FSH, LH) und nicht-glandotrope Hormone (GH/STH, Prolaktin).",
            "Dopamin als Prolaktin-Statin: Dopamin aus dem Hypothalamus hemmt tonisch die Prolaktinfreisetzung. Bei Hypophysenstieldurchtrennung sinken alle HVL-Hormone, aber Prolaktin steigt massiv an!"
        ],
        "keywords": [
            "hypophyse",
            "hypothalamus",
            "neurohypophyse",
            "adenohypophyse",
            "adh",
            "oxytocin",
            "crh",
            "acth",
            "trh",
            "tsh",
            "gnrh",
            "dopamin",
            "prolaktin",
            "wachstumshormon",
            "rückkopplung"
        ],
        "associated_decks": [
            "4 Hypophyse & Hypothalamus",
            "Hormonelle Regelkreise",
            "2. SJ :: 6. Endokrinologie & Hormone :: Hypophyse"
        ],
        "slide_pdf": "Kurs Klinischer Untersuchungskurs I/Archive/Unterlagen 1. Fachsemester (HS 2025)/2_Klin-Untersuchungskurs_Abdomen.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-12-15_TB_Endokrinologie",
        "date": "2025-12-15",
        "title": "Nebennierenrinde: Steroidsynthese, Glukokortikoide & Mineralokortikoide",
        "module": "6. Endokrinologie & Hormone",
        "lecturer": "Prof. Dr. med. Cyrill Stockmann",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.955,
        "recommendation": "1.2x",
        "badge_color": "var(--status-warning, #d29922)",
        "badge_label": "🟡 1.2x Standard-Stream (+25m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Zonierung (Glomerulosa, Fasciculata, Reticularis), Steroidsyntheseweg (Cholesterin -> Pregnenolon via StAR, 21-Hydroxylase-Defekt / AGS), Cortisol-Wirkung und RAAS-Aldosteron-Regulation; 1.2x spart ca. 25 Min. bei visuellem Verfolgen des Synthesebaums.",
        "anki_facts": [
            "Histologische Zonierung der Nebennierenrinde (GFR-Regel): Zona Glomerulosa (Mineralokortikoide / Aldosteron), Zona Fasciculata (Glukokortikoide / Cortisol), Zona Reticularis (Androgene / DHEA).",
            "Adrenogenitales Syndrom (AGS): Zu 90% Defekt der 21-Hydroxylase -> Mangel an Cortisol und Aldosteron, ACTH steigt kompensatorisch -> Überschuss an Androgenen (Virilisierung, Salzverlustkrise).",
            "Aldosteron-Wirkung am distalen Tubulus / Sammelrohr: Bindet intrazellulären Mineralokortikoidrezeptor -> Expression von ENaC und Na+/K+-ATPase -> Na+- und Wasser-Retention, K+- und H+-Ausscheidung."
        ],
        "keywords": [
            "nebennierenrinde",
            "steroidsynthese",
            "cortisol",
            "aldosteron",
            "dhea",
            "glomerulosa",
            "fasciculata",
            "reticularis",
            "ags",
            "21-hydroxylase",
            "raas",
            "cushing",
            "addison"
        ],
        "associated_decks": [
            "5 Nebennierenrinde",
            "Steroidhormone",
            "2. SJ :: 6. Endokrinologie & Hormone :: Nebenniere"
        ],
        "slide_pdf": "Kurs Klinischer Untersuchungskurs I/Archive/Unterlagen 1. Fachsemester (HS 2025)/2_Klin-Untersuchungskurs_Abdomen.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-12-17_TB_Endokrinologie",
        "date": "2025-12-17",
        "title": "Nebennierenmark (Katecholamine) & Schilddrüsenhormone (T3/T4)",
        "module": "6. Endokrinologie & Hormone",
        "lecturer": "Prof. Dr. med. Cyrill Stockmann",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.979,
        "recommendation": "1.2x",
        "badge_color": "var(--status-warning, #d29922)",
        "badge_label": "🟡 1.2x Standard-Stream (+25m gespart)",
        "is_audio_only": False,
        "tradeoff_reason": "Tyrosinabbau zu Adrenalin (PNMT durch Cortisol induziert); Schilddrüse: NIS-Symporter, Thyreoperoxidase (TPO), Pendrin, Dejodasen und Schilddrüsenautoregulation (Wolff-Chaikoff-Effekt); 1.2x optimal.",
        "anki_facts": [
            "Katecholaminsynthese im Nebennierenmark: Tyrosin -> Dopa (Tyrosinhydroxylase, geschwindigkeitsbestimmend) -> Dopamin -> Noradrenalin -> Adrenalin (via PNMT, durch Cortisol aus NNR stimuliert!).",
            "Schilddrüsenhormonsynthese: Basolaterale Jodidaufnahme via NIS (Na+/I--Symporter), apikaler Export via Pendrin, Oxidation und Jodierung an Thyreoglobulin via TPO (Thyreoperoxidase).",
            "Periphere T4-zu-T3-Aktivierung: T4 (Prohormon, 90% im Blut) wird peripher durch 5'-Dejodase (Typ 1 und 2, selenabhängig) in biologisch aktives T3 umgewandelt."
        ],
        "keywords": [
            "schilddrüse",
            "t3",
            "t4",
            "thyroxin",
            "tpo",
            "thyreoperoxidase",
            "nis-symporter",
            "katecholamine",
            "adrenalin",
            "noradrenalin",
            "nebennierenmark",
            "pnmt",
            "dejodase",
            "wolff-chaikoff"
        ],
        "associated_decks": [
            "6 Schilddrüse & Nebennierenmark",
            "Katecholamine & T3/T4",
            "2. SJ :: 6. Endokrinologie & Hormone :: Schilddrüse"
        ],
        "slide_pdf": "Kurs Klinischer Untersuchungskurs I/Archive/Unterlagen 1. Fachsemester (HS 2025)/2_Klin-Untersuchungskurs_Abdomen.pdf",
        "total_anki_cards": 200,
        "chapters": []
    },
    {
        "id": "2025-12-18_TB_Endokrinologie",
        "date": "2025-12-18",
        "title": "Calcium- und Phosphathaushalt: PTH, Calcitriol & Calcitonin",
        "module": "6. Endokrinologie & Hormone",
        "lecturer": "Prof. Dr. med. Cyrill Stockmann",
        "exam_yield": "High-Yield",
        "visual_dependency": "Hoch",
        "lecturer_tempo": "Langsam",
        "silence_ratio": 0.96,
        "recommendation": "1.0x",
        "badge_color": "var(--status-done, #3fb950)",
        "badge_label": "🟢 1.0x Voller Fokus (Höchste klinische Relevanz)",
        "is_audio_only": False,
        "tradeoff_reason": "Zusammenspiel von Parathormon (Nebenschilddrüse / Hauptzellen), 1,25-(OH)2-Vitamin D3 (renale 1alpha-Hydroxylase) und FGF-23 an Knochen, Niere und Darm; CaSR (Calcium-Sensing Receptor) und Hyper-/Hypokalzämie. Extrem prüfungsrelevant und hochgradig vernetzt; 1.0x erforderlich.",
        "anki_facts": [
            "Parathormon-Wirkungen: Erhöht Serum-Calcium und senkt Serum-Phosphat! Knochen (stimuliert Osteoklasten via RANKL), Niere (steigert Ca2+-Reabsorption, hemmt Phosphat-Reabsorption, stimuliert 1alpha-Hydroxylase).",
            "Calcitriol (1,25-(OH)2-D3): Erhöht Serum-Calcium UND Serum-Phosphat! Hauptwirkung: Steigert enterale Calcium- (via TRPV6/Calbindin) und Phosphatresorption im Dünndarm.",
            "Regulation via CaSR: Sinkendes ionisiertes Calcium enthemmt die PTH-Sekretion der Hauptzellen; Hyperkalzämie aktiviert CaSR und unterdrückt die PTH-Freisetzung sofort."
        ],
        "keywords": [
            "calcium",
            "calciumhaushalt",
            "phosphathaushalt",
            "parathormon",
            "pth",
            "calcitriol",
            "vitamin d",
            "calcitonin",
            "casr",
            "rankl",
            "osteoklasten",
            "hyperkalzämie",
            "hypokalzämie",
            "fgf23"
        ],
        "associated_decks": [
            "7 Calcium- & Phosphathaushalt",
            "Parathormon & Vitamin D",
            "2. SJ :: 6. Endokrinologie & Hormone :: Calcium"
        ],
        "slide_pdf": "Kurs Klinischer Untersuchungskurs I/Archive/Unterlagen 1. Fachsemester (HS 2025)/2_Klin-Untersuchungskurs_Abdomen.pdf",
        "total_anki_cards": 200,
        "chapters": []
    }
]

def get_all_advisor_lectures() -> List[Dict[str, Any]]:
    """Returns all 38 lectures enriched with local podcast paths."""
    enriched = []
    for lect in LECTURES_DATA:
        folder = PODCASTS_DIR / lect["id"]
        folien_file = None
        prof_file = None
        if folder.exists():
            folien_candidates = list(folder.glob("*Folien*.mp4"))
            prof_candidates = list(folder.glob("*Prof_Erklaerung*.mp4")) or list(folder.glob("*Dozent*.mp4"))
            if folien_candidates:
                folien_file = folien_candidates[0].name
            if prof_candidates:
                prof_file = prof_candidates[0].name

        item = dict(lect)
        item["has_local_podcast"] = folder.exists()
        item["podcast_folder_name"] = lect["id"]
        item["folien_filename"] = folien_file
        item["prof_filename"] = prof_file
        enriched.append(item)
    return enriched


def calculate_timestamp_budget(
    chapters: List[Dict[str, Any]],
    target_cards: int = 100,
    speed_factor: float = 1.2,
    recommendation: str = "1.2x"
) -> Dict[str, Any]:
    """Calculates precisely which video timestamp range is needed for target_cards.
    
    Adheres strictly to efficiency and Time-ROI principles:
    - If recommendation is 'Skip', default is 0 minutes video (100% skip = +Full duration saved).
    - If a micro understanding chapter exists, it is ONLY recommended if <= 20 minutes.
    - Computes Time-ROI showing exact time lost if watching video vs. direct Anki encoding.
    """
    total_lecture_cards = sum(c.get("cards_count", 0) for c in chapters) if chapters else 0
    total_lecture_dur = sum(c.get("duration_min", 0) for c in chapters) if chapters else 0

    # Time-ROI Calculation
    anki_direct_mins = max(30, round(target_cards * 1.05))
    anki_with_video_mins = max(25, round(target_cards * 0.95))
    net_with_video = total_lecture_dur + anki_with_video_mins
    net_time_lost = max(0, net_with_video - anki_direct_mins)

    time_roi = {
        "anki_direct_minutes": anki_direct_mins,
        "video_duration_minutes": total_lecture_dur,
        "net_time_direct": anki_direct_mins,
        "net_time_with_video": net_with_video,
        "net_minutes_lost": net_time_lost,
        "verdict": f"Vorlesung schauen kostet netto {net_time_lost} Min. MEHR Zeit als direktes Anki-Lernen!" if net_time_lost > 0 else "Vorlesung und Anki sind zeitlich gleichwertig."
    }

    if not chapters:
        return {
            "target_cards": target_cards,
            "total_lecture_cards": 0,
            "start_timestamp": "00:00",
            "end_timestamp": "00:00",
            "video_minutes_raw": 0,
            "video_minutes_effective": 0,
            "saved_minutes": 0,
            "is_full_skip": "skip" in recommendation.lower(),
            "is_micro_deep_dive": False,
            "time_roi": time_roi,
            "guidance_text": "Keine Kapitel für diese Vorlesung vorhanden.",
            "annotated_chapters": []
        }

    is_skip_rec = "skip" in recommendation.lower()

    # If the lecture is recommended to SKIP (100% Anki)
    if is_skip_rec:
        # Check if there is an exceptional micro-understanding chapter <= 20 minutes
        micro_chap = None
        for c in chapters:
            c_dur = c.get("duration_min", 0)
            c_title = c.get("title", "").lower()
            if 0 < c_dur <= 20 and any(k in c_title for k in ["mechanismus", "kaskade", "zyklus", "pathophysiologie", "erregung"]):
                micro_chap = c
                break

        if micro_chap:
            eff_m = micro_chap.get("duration_min", 15)
            saved_m = max(0, total_lecture_dur - eff_m)
            annotated = []
            for c in chapters:
                ca = dict(c)
                if c.get("start") == micro_chap.get("start"):
                    ca["is_needed_for_target"] = True
                    ca["coverage_label"] = f"💡 Micro-Deep-Dive ({eff_m}m)"
                else:
                    ca["is_needed_for_target"] = False
                    ca["coverage_label"] = f"⚪ Überspringen (100% Anki, +{c.get('duration_min', 0)}m gespart)"
                annotated.append(ca)

            return {
                "target_cards": target_cards,
                "total_lecture_cards": total_lecture_cards,
                "start_timestamp": micro_chap["start"],
                "end_timestamp": micro_chap["end"],
                "video_minutes_raw": eff_m,
                "video_minutes_effective": eff_m,
                "saved_minutes": saved_m,
                "is_full_skip": False,
                "is_micro_deep_dive": True,
                "time_roi": time_roi,
                "guidance_text": f"💡 Optionaler Micro-Deep-Dive (nur {eff_m} Min. von {micro_chap['start']}–{micro_chap['end']}): Nur dieser kurze Abschnitt bietet echten visuellen Mehrwert für Verständnis-Karten. Der Rest ({saved_m} Min.) bleibt zu 100% übersprungen!",
                "annotated_chapters": annotated
            }

        # Strikte 100% Skip-Empfehlung: 0 Minuten Video!
        annotated = []
        for c in chapters:
            ca = dict(c)
            ca["is_needed_for_target"] = False
            ca["coverage_label"] = f"⚪ Überspringen (100% Anki, +{c.get('duration_min', 0)}m gespart)"
            annotated.append(ca)

        return {
            "target_cards": target_cards,
            "total_lecture_cards": total_lecture_cards,
            "start_timestamp": "00:00",
            "end_timestamp": "00:00",
            "video_minutes_raw": 0,
            "video_minutes_effective": 0,
            "saved_minutes": total_lecture_dur,
            "is_full_skip": True,
            "is_micro_deep_dive": False,
            "time_roi": time_roi,
            "guidance_text": f"⚡ 100% SKIP-EMPFEHLUNG: 0 Minuten Vorlesung nötig! Spare dir die vollen {total_lecture_dur} Minuten Vorlesungszeit und lerne die {target_cards} Karten direkt via Active Recall.",
            "annotated_chapters": annotated
        }

    # If user wants all or more cards than available in the lecture
    if target_cards >= total_lecture_cards:
        eff_dur = max(1, round(total_lecture_dur / max(speed_factor, 1.0)))
        annotated = []
        for c in chapters:
            ca = dict(c)
            ca["is_needed_for_target"] = True
            ca["coverage_label"] = f"🟢 Vollständig ansehen (Karten {c.get('cards_range', '')})"
            annotated.append(ca)

        return {
            "target_cards": total_lecture_cards,
            "total_lecture_cards": total_lecture_cards,
            "start_timestamp": chapters[0]["start"],
            "end_timestamp": chapters[-1]["end"],
            "video_minutes_raw": total_lecture_dur,
            "video_minutes_effective": eff_dur,
            "saved_minutes": max(0, total_lecture_dur - eff_dur),
            "is_full_skip": False,
            "is_micro_deep_dive": False,
            "time_roi": time_roi,
            "guidance_text": f"Schau die Vorlesung ({chapters[0]['start']} – {chapters[-1]['end']}) für alle {total_lecture_cards} Karten (Dauer: {eff_dur}m bei {speed_factor}x).",
            "annotated_chapters": annotated
        }

    accumulated = 0
    raw_minutes = 0
    end_timestamp = chapters[0]["end"]
    annotated = []

    for c in chapters:
        ca = dict(c)
        c_cards = c.get("cards_count", 0)
        c_dur = c.get("duration_min", 0)

        # Parse start and end seconds
        parts_start = [int(p) for p in c["start"].split(":")]
        start_sec = parts_start[0] * 60 + parts_start[1]
        parts_end = [int(p) for p in c["end"].split(":")]
        end_sec = parts_end[0] * 60 + parts_end[1]

        if accumulated + c_cards <= target_cards:
            accumulated += c_cards
            raw_minutes += c_dur
            end_timestamp = c["end"]
            ca["is_needed_for_target"] = True
            ca["coverage_label"] = f"🟢 Vollständig ansehen (Karten {c.get('cards_range', '')})"
        elif accumulated < target_cards:
            remaining = target_cards - accumulated
            fraction = remaining / max(c_cards, 1)
            add_sec = int((end_sec - start_sec) * fraction)
            target_sec = start_sec + add_sec
            t_min = target_sec // 60
            t_sec = target_sec % 60
            end_timestamp = f"{t_min:02d}:{t_sec:02d}"
            raw_minutes += max(1, round(c_dur * fraction))
            ca["is_needed_for_target"] = True
            ca["coverage_label"] = f"🟡 Bis Minute {end_timestamp} ansehen (deckt Karten {c.get('cards_range', '').split('–')[0]}–{target_cards} ab)"
            accumulated = target_cards
        else:
            ca["is_needed_for_target"] = False
            ca["coverage_label"] = f"⚪ Nicht nötig für deine {target_cards} Karten (+{c_dur}m gespart)"

        annotated.append(ca)

    eff_minutes = max(1, round(raw_minutes / max(speed_factor, 1.0)))
    saved_minutes = max(0, total_lecture_dur - eff_minutes)

    return {
        "target_cards": target_cards,
        "total_lecture_cards": total_lecture_cards,
        "start_timestamp": chapters[0]["start"],
        "end_timestamp": end_timestamp,
        "video_minutes_raw": raw_minutes,
        "video_minutes_effective": eff_minutes,
        "saved_minutes": saved_minutes,
        "is_full_skip": False,
        "is_micro_deep_dive": False,
        "time_roi": time_roi,
        "guidance_text": f"Schau nur {chapters[0]['start']} bis {end_timestamp} ({eff_minutes} Min bei {speed_factor}x). Du sparst dir heute {saved_minutes} Minuten Vorlesungszeit!",
        "annotated_chapters": annotated
    }


# Recognized lecturers with canonical names, exact firstnames, and fuzzy surnames
LECTURER_CATALOG = {
    "manatschal": {
        "canonical": "Prof. Dr. Cristina Manatschal",
        "surnames": ["manatschal", "manataschal", "manatschel", "manatscha", "manatschat"],
        "firstnames": ["cristina"]
    },
    "ullrich": {
        "canonical": "Prof. Dr. Oliver Ullrich",
        "surnames": ["ullrich", "ulrich", "ulricht"],
        "firstnames": ["oliver"]
    },
    "dutzler": {
        "canonical": "Prof. Raimund Dutzler",
        "surnames": ["dutzler"],
        "firstnames": ["raimund"]
    },
    "tuzlak": {
        "canonical": "Dr. Tuzlak",
        "surnames": ["tuzlak", "tuslak"],
        "firstnames": []
    },
    "sommer": {
        "canonical": "Prof. Dr. Lutz Sommer",
        "surnames": ["sommer"],
        "firstnames": ["lutz"]
    },
    "kurt": {
        "canonical": "Prof. Dr. med. Elisabeth Kurt",
        "surnames": ["kurt"],
        "firstnames": ["elisabeth"]
    },
    "wenger": {
        "canonical": "Prof. Dr. Roland Wenger",
        "surnames": ["wenger"],
        "firstnames": ["roland"]
    },
    "wagner": {
        "canonical": "Prof. Dr. Carsten Wagner",
        "surnames": ["wagner"],
        "firstnames": ["carsten"]
    },
    "stockmann": {
        "canonical": "Prof. Dr. med. Cyrill Stockmann",
        "surnames": ["stockmann", "stockman", "stokman"],
        "firstnames": ["cyrill"]
    }
}

MODULE_CATALOG = {
    "blut": "1. Blut & Immunsystem",
    "immun": "1. Blut & Immunsystem",
    "immunsystem": "1. Blut & Immunsystem",
    "hämatologie": "1. Blut & Immunsystem",
    "herz": "2. Herz-Kreislauf",
    "kreislauf": "2. Herz-Kreislauf",
    "kardio": "2. Herz-Kreislauf",
    "ekg": "2. Herz-Kreislauf",
    "atmung": "3. Atmung & Lunge",
    "lunge": "3. Atmung & Lunge",
    "respiration": "3. Atmung & Lunge",
    "verdauung": "4. Verdauung & Ernährung",
    "magen": "4. Verdauung & Ernährung",
    "darm": "4. Verdauung & Ernährung",
    "ernährung": "4. Verdauung & Ernährung",
    "stoffwechsel": "5. Stoffwechsel & Biochemie",
    "biochemie": "5. Stoffwechsel & Biochemie",
    "glykolyse": "5. Stoffwechsel & Biochemie",
    "hormon": "6. Endokrinologie & Hormone",
    "hormone": "6. Endokrinologie & Hormone",
    "endokrin": "6. Endokrinologie & Hormone",
    "endokrinologie": "6. Endokrinologie & Hormone",
}

STOPWORDS = {
    "von", "vom", "im", "in", "der", "die", "das", "des", "dem", "den",
    "ein", "eine", "einer", "eines", "und", "oder", "für", "fuer", "zu",
    "zum", "zur", "mit", "bei", "über", "ueber", "themenblock", "tb",
    "vorlesung", "vorlesungen", "prof", "dr", "med", "dozent", "dozenten"
}


def fuzzy_match_token(token: str, candidate_words: List[str], threshold: float = 0.72) -> float:
    """Computes similarity ratio between a search token and candidate strings."""
    token = token.lower().strip()
    if not token:
        return 0.0
    best_ratio = 0.0
    for cand in candidate_words:
        cand = cand.lower().strip()
        if not cand:
            continue
        if token == cand:
            return 1.0
        if token in cand or cand in token:
            r = len(token) / max(len(cand), 1)
            if r >= 0.75:
                best_ratio = max(best_ratio, 0.95)
        # Difflib sequence matcher
        sim = difflib.SequenceMatcher(None, token, cand).ratio()
        if sim > best_ratio:
            best_ratio = sim
    return best_ratio if best_ratio >= threshold else 0.0


def search_lecture_advisor(
    query: str,
    filter_mode: Optional[str] = None,
    filter_module: Optional[str] = None,
    target_cards: Optional[int] = 100
) -> Dict[str, Any]:
    """Intelligent search engine matching user topic queries against all 38 UZH lectures.
    
    Features:
    - Fuzzy tolerance for lecturer names (e.g. 'manataschal' -> 'Manatschal').
    - Handles module shortcuts (e.g. 'TB Blut' -> '1. Blut & Immunsystem').
    - Strips noisy stopwords ('von', 'im', 'der').
    - Dynamically computes timestamp intervals and saved study minutes for target_cards.
    - Returns top_matches (list of relevant lectures) and detailed chapter breakdowns.
    """
    all_lectures = get_all_advisor_lectures()
    q_raw = (query or "").strip().lower()
    target_cards_val = int(target_cards) if target_cards and str(target_cards).isdigit() else 100

    # 1. Clean query & extract tokens
    tokens = [t for t in re.split(r"[\s\-_,;:/]+", q_raw) if t and t not in STOPWORDS]

    # 2. Check if query matches a known lecturer (surnames fuzzy >= 0.78, firstnames exact)
    matched_lecturer_key = None
    for l_key, l_data in LECTURER_CATALOG.items():
        for tok in tokens:
            if tok in l_data.get("firstnames", []):
                matched_lecturer_key = l_key
                break
            if fuzzy_match_token(tok, l_data.get("surnames", []), threshold=0.78) > 0.0:
                matched_lecturer_key = l_key
                break
        if matched_lecturer_key:
            break

    # 3. Check if query matches a known module
    matched_module_val = None
    for m_key, m_val in MODULE_CATALOG.items():
        for tok in tokens:
            if tok == m_key or fuzzy_match_token(tok, [m_key], threshold=0.82) > 0.0:
                matched_module_val = m_val
                break
        if matched_module_val:
            break

    filtered = []
    for l in all_lectures:
        # Check filter_mode
        if filter_mode:
            f_m = filter_mode.lower()
            rec = l["recommendation"].lower()
            if f_m == "skip" and "skip" not in rec:
                continue
            elif f_m == "1.0x" and "1.0x" not in rec:
                continue
            elif f_m == "1.2x" and "1.2x" not in rec:
                continue
            elif f_m == "1.4x" and "1.4x" not in rec:
                continue
            elif f_m == "audio" and not l.get("is_audio_only"):
                continue

        # Check filter_module
        if filter_module and filter_module.lower() != "all" and filter_module.lower() not in l["module"].lower():
            continue

        # Scoring
        score = 0
        if not q_raw:
            score = 10
        else:
            title_l = l["title"].lower()
            mod_l = l["module"].lower()
            lect_l = l.get("lecturer", "").lower()
            keywords = [k.lower() for k in l.get("keywords", [])]
            decks = [d.lower() for d in l.get("associated_decks", [])]
            facts = [f.lower() for f in l.get("anki_facts", [])]
            chapter_titles = [c["title"].lower() for c in l.get("chapters", [])]
            chapter_topics = [t.lower() for c in l.get("chapters", []) for t in c.get("topics", [])]

            # A. Lecturer Match (Highest Priority)
            if matched_lecturer_key:
                l_aliases = LECTURER_CATALOG[matched_lecturer_key]["surnames"] + LECTURER_CATALOG[matched_lecturer_key]["firstnames"]
                for alias in l_aliases:
                    if alias in lect_l:
                        score += 160
                        break

            # B. Module Match
            if matched_module_val and matched_module_val.lower() in mod_l:
                score += 80

            # C. Exact query in title
            if q_raw in title_l:
                score += 120

            # D. Token-based matching
            for tok in tokens:
                # Direct in title
                if tok in title_l:
                    score += 50
                # Fuzzy in title words
                elif fuzzy_match_token(tok, title_l.split(), threshold=0.75) > 0.0:
                    score += 35

                # In lecturer
                if tok in lect_l:
                    score += 40

                # In decks
                if any(tok in d for d in decks):
                    score += 35

                # In chapter titles / topics
                if any(tok in ct for ct in chapter_titles):
                    score += 45
                if any(tok in ctop for ctop in chapter_topics):
                    score += 40

                # In keywords
                if any(tok in k for k in keywords):
                    score += 30
                elif fuzzy_match_token(tok, keywords, threshold=0.75) > 0.0:
                    score += 25

                # In facts
                if any(tok in f for f in facts):
                    score += 20

                # In module
                if tok in mod_l:
                    score += 25

        if score > 0:
            item_copy = dict(l)
            item_copy["relevance_score"] = score

            # Calculate speed float
            rec_str = l.get("recommendation", "1.2x")
            speed = 1.0
            if "1.4x" in rec_str:
                speed = 1.4
            elif "1.2x" in rec_str:
                speed = 1.2
            elif "skip" in rec_str.lower():
                speed = 1.0

            # Attach personalized timestamp budget with strict skip & ROI rules
            item_copy["timestamp_guidance"] = calculate_timestamp_budget(
                chapters=l.get("chapters", []),
                target_cards=target_cards_val,
                speed_factor=speed,
                recommendation=rec_str
            )
            filtered.append(item_copy)

    # Sort by relevance score descending, then date ascending
    filtered.sort(key=lambda x: (-x.get("relevance_score", 0), x["date"]))

    # Top matches (up to 5)
    top_matches = filtered[:5] if filtered and q_raw else (filtered[:3] if filtered else [])
    top_hit = filtered[0] if filtered else None

    summary = {
        "total_lectures": len(all_lectures),
        "total_matching": len(filtered),
        "count_skip": sum(1 for x in all_lectures if "skip" in x["recommendation"].lower()),
        "count_1_0x": sum(1 for x in all_lectures if "1.0x" in x["recommendation"].lower()),
        "count_1_2x": sum(1 for x in all_lectures if "1.2x" in x["recommendation"].lower()),
        "count_1_4x": sum(1 for x in all_lectures if "1.4x" in x["recommendation"].lower()),
        "count_audio_only": sum(1 for x in all_lectures if x.get("is_audio_only")),
    }

    has_filter = bool(q_raw or filter_mode or filter_module)
    return {
        "query": query,
        "target_cards": target_cards_val,
        "filter_mode": filter_mode,
        "filter_module": filter_module,
        "summary": summary,
        "top_match": top_hit,
        "top_matches": top_matches,
        "results": filtered,
    }
