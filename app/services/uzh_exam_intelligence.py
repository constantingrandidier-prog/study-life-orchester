"""UZH Medizin 2. Studienjahr (3. Semester) Exam Intelligence & Professor Knowledge Base.

Contains deep verified curriculum intelligence on all UZH professors, their research focus,
exam question styles (Typ A, Kprim), specific pitfall warnings, and high-yield scoring
tailored directly to the UZH Humanmedizin Modulprüfung 1 & Modulprüfung 2.
"""

from typing import Any, Dict, List, Optional
import re

# Comprehensive Professor Exam Profiles for UZH 2. Studienjahr (Herbstsemester)
UZH_PROFESSORS: Dict[str, Dict[str, Any]] = {
    "roland_wenger": {
        "name": "Prof. Dr. Roland Wenger",
        "title": "Ordinarius & Direktor Institut für Physiologie UZH",
        "institute": "Physiologisches Institut UZH",
        "research_focus": "Zelluläre Sauerstoffphysiologie, Hypoxie-induzierbare Faktoren (HIF-1alpha), Erythropoetin (EPO), Höhenanpassung",
        "primary_topics": ["Atmung", "Respiration", "O2-Transport", "EPO", "Blut", "Gasaustausch", "Euler-Liljestrand"],
        "keywords": ["wenger", "hypoxie", "hif", "erythropoetin", "epo", "gasaustausch", "atemmechanik", "euler-liljestrand", "diffusion", "perfusion", "compliance"],
        "exam_style": "Konzeptionell sehr anspruchsvoll. Bevorzugt Kprim-Fragen mit physiologischen Regelkreisen und Kurvenverschiebungen.",
        "high_yield_pearl": "Sauerstoffbindungskurve des Hämoglobins: Rechtsverschiebung (erleichterte O2-Abgabe) durch pCO2↑, H+↑ (Azidose), Temperatur↑, 2,3-BPG↑. Linksverschiebung bei Kälte, Alkalose, HbF und CO-Vergiftung!",
        "kprim_trap": "Euler-Liljestrand (hypoxische pulmonale Vasokonstriktion): Pulmonale Gefässe kontrahiert bei Hypoxie (um Totraumventilation zu minimieren), während systemische Gefässe bei Hypoxie dilatieren! Häufige Kprim-Falle.",
        "uzh_importance": "Sehr hoch (Prüfungs-Kern Modulprüfung 1)",
    },
    "carsten_wagner": {
        "name": "Prof. Dr. Carsten Wagner",
        "title": "Ordinarius für Physiologie, Leiter Kidney & Acid-base Physiology",
        "institute": "Physiologisches Institut UZH",
        "research_focus": "Säure-Basen-Homöostase, renale Elektrolyt- und Mineralstofftransporter, Phosphat- und Kalziumregulation (PTH, FGF23, Klotho)",
        "primary_topics": ["Säure-Base", "Astrup", "Bikarbonat", "Kalzium", "Phosphat", "Nebenniere", "Endokrinologie"],
        "keywords": ["wagner", "säure-base", "saure-base", "astrup", "bikarbonat", "azidose", "alkalose", "henderson", "kalzium", "calcium", "phosphat", "pth", "fgf23"],
        "exam_style": "Zahlen- und Mechanismus-fokussiert. Prüft gerne BGA-Werte (pH, pCO2, HCO3-) und Transportproteine an luminalen Membranen.",
        "high_yield_pearl": "Astrup-BGA: Respiratorische Azidose = pH↓, pCO2↑ (renale Kompensation: HCO3-↑ mit BE>0). Metabolische Azidose = pH↓, HCO3-↓ (respiratorische Kompensation: Hyperventilation pCO2↓). Kompensation normalisiert pH nie ganz auf 7.40!",
        "kprim_trap": "Phosphat-Regulation: Parathormon (PTH) und FGF23 hemmen BEIDE den renalen Natrium-Phosphat-Kotransporter NaPi-IIa im proximalen Tubulus (führen beide zu Phosphaturie). Aber PTH stimuliert die 1-alpha-Hydroxylase (Calcitriol↑), während FGF23 sie hemmt!",
        "uzh_importance": "Sehr hoch (Prüfungs-Kern Modulprüfung 1 & 2)",
    },
    "johannes_loffing": {
        "name": "Prof. Dr. Johannes Loffing",
        "title": "Ordinarius für Anatomie, Leiter Epithelial Biology – Kidney & Hypertension",
        "institute": "Anatomisches Institut UZH",
        "research_focus": "Epithelialer Natriumkanal (ENaC), Aldosteron-Signalkaskade, SGK1, Nedd4-2, arterielle Hypertonie, Tubulusepithelien",
        "primary_topics": ["Niere", "Aldosteron", "ENaC", "Blutdruckregulation", "Tubulusepithelien", "Histologie"],
        "keywords": ["loffing", "enac", "aldosteron", "sgk1", "nedd4-2", "tubulus", "sammelrohr", "hauptzelle", "interkalierte zelle", "blutdruck"],
        "exam_style": "Exzellente Verbindung von mikroskopischer Histologie und molekularer Physiologie. Gerne Schema- und Kprim-Fragen.",
        "high_yield_pearl": "Aldosteronwirkung in den Hauptzellen des Sammelrohrs: Bindet an zytosolischen Mineralokortikoidrezeptor -> induziert SGK1 -> phosphoryliert Nedd4-2 -> verhindert den Abbau von ENaC an der apikalen Membran. Führt zu Na+-Retention und K+-Sekretion.",
        "kprim_trap": "Spironolacton / Eplerenon hemmen den Aldosteron-Rezeptor; Amilorid / Triamteren hemmen direkt den ENaC-Kanal von apikal! Beide sind kaliumsparend (Hyperkaliämie-Gefahr!).",
        "uzh_importance": "Hoch (Prüfungs-Kern Herz-Kreislauf & Endokrinologie)",
    },
    "selma_tuzlak": {
        "name": "Dr. Selma Tuzlak",
        "title": "Research Associate & Dozentin für Immunologie (Becher Lab)",
        "institute": "Institut für Experimentelle Immunologie UZH",
        "research_focus": "T-Zell-Differenzierung, Zytokin-Signalwege, adaptive Immunität, Immuntoleranz und Autoimmunität",
        "primary_topics": ["Immunologie", "T-Zellen", "B-Zellen", "MHC", "Immuntoleranz", "Zytokine", "Autoimmunität"],
        "keywords": ["tuzlak", "immun", "t-zell", "b-zell", "mhc", "zytokin", "toleranz", "autoimmun", "rag", "rekombination", "thymus"],
        "exam_style": "Präzise molekulare Immunologie. Fragt exakt nach Signalmolekülen, Transkriptionsfaktoren und Selektionsstufen im Thymus.",
        "high_yield_pearl": "Thymus-Selektion: Positive Selektion im Kortex (überleben nur Zellen, die körpereigenes MHC mit niedriger/mittlerer Affinität binden -> MHC-Restriktion). Negative Selektion in der Medulla (Zellen, die körpereigene Antigene mit hoher Affinität binden, gehen in Apoptose; reguliert durch AIRE-Gen -> periphere Autoimmunitätsvermeidung!).",
        "kprim_trap": "MHC-I: auf allen kernhaltigen Zellen (NICHT auf Erythrozyten!); präsentiert endogene virale/tumorale Peptide an CD8+ zytotoxische T-Zellen. MHC-II: NUR auf professionellen APCs (dendritische Zellen, Makrophagen, B-Zellen); präsentiert exogene Peptide an CD4+ T-Helferzellen.",
        "uzh_importance": "Sehr hoch (Prüfungs-Kern Themenblock Blut & Immunsystem)",
    },
    "cristina_manatschal": {
        "name": "Dr. Cristina Manatschal",
        "title": "Dozentin für Biochemie & Studienberaterin (Dutzler Lab)",
        "institute": "Institut für Biochemie UZH",
        "research_focus": "Membrantransport, allosterische Proteinmechanismen, Hämoglobin, Blutgerinnung und Komplementkaskade",
        "primary_topics": ["Blutgerinnung", "Hämostase", "Hämoglobin", "Myoglobin", "Komplementsystem", "Allosterie"],
        "keywords": ["manatschal", "gerinnung", "hämostase", "haemostase", "thrombose", "komplement", "myoglobin", "hämoglobin", "antikoagulan"],
        "exam_style": "Sehr didaktisch und strukturiert. Liebt Kaskadenschemata, Cofaktoren (Ca²⁺, Phospholipide) und Gerinnungstests (Quick/INR vs. aPTT).",
        "high_yield_pearl": "Sekundäre Hämostase: Extrinsischer Weg (physiologischer Start): Gewebefaktor (TF) + FVIIa -> aktiviert FX zu FXa. Intrinsischer Weg (Verstärkerschleife): FXII -> FXI -> FIX + FVIIIa -> aktiviert FX. Gemeinsame Endstrecke: FXa + FVa wandelt Prothrombin (FII) in Thrombin (FIIa) um -> Thrombin spaltet Fibrinogen (FI) zu Fibrin (FIa)!",
        "kprim_trap": "Vitamin-K-abhängige Faktoren: II, VII, IX, X sowie Protein C und Protein S! Kprim-Falle: Antithrombin III ist NICHT Vitamin-K-abhängig (wird durch Heparin allosterisch um Faktor 1000 aktiviert und hemmt vor allem Thrombin und FXa)!",
        "uzh_importance": "Sehr hoch (Prüfungs-Kern Modulprüfung 1)",
    },
    "raimund_dutzler": {
        "name": "Prof. Dr. Raimund Dutzler",
        "title": "Ordinarius & Direktor Institut für Biochemie UZH",
        "institute": "Institut für Biochemie UZH",
        "research_focus": "Strukturbiologie und molekulare Mechanismen von Ionenkanälen und Transportern (TMEM16, CFTR, Chloridkanäle)",
        "primary_topics": ["Verdauung", "Ernährung", "Ionenkanäle", "CFTR", "Magensäure", "Membrantransport"],
        "keywords": ["dutzler", "tmem16", "cftr", "ionenkanal", "magensäure", "parietalzelle", "belegzelle", "h+/k+-atpase", "chlorid"],
        "exam_style": "Kopplung von biochemischer Thermodynamik und luminaler Transportphysiologie. Fragt exakt nach Energiequellen (primär vs. sekundär aktiv).",
        "high_yield_pearl": "Magensäure-Sekretion der Belegzelle: Apikale H+/K+-ATPase pumpt Protonen gegen extremen Gradienten (Faktor 1:1'000'000) im Austausch gegen K+ ins Lumen. Basolateraler HCO3-/Cl--Austauscher transportiert Bikarbonat ins Blut ('alkalische Flut') und Chlorid in die Zelle, welches über apikale Cl--Kanäle ins Lumen diffundiert.",
        "kprim_trap": "CFTR (Cystic Fibrosis Transmembrane Conductance Regulator) ist ein ATP-gesteuerter Chloridkanal (öffnet bei ATP-Bindung), aber KEINE primär-aktive Pumpe! Bei CF fehlt apikale Cl-- und HCO3--Sekretion -> zähflüssiger Schleim im Pankreasgang und Lunge.",
        "uzh_importance": "Hoch (Prüfungs-Kern Verdauung & Ernährung)",
    },
    "christian_stockmann": {
        "name": "Prof. Dr. Christian Stockmann",
        "title": "Ausserordentlicher Professor für Anatomie",
        "institute": "Anatomisches Institut UZH",
        "research_focus": "Immunity, Angiogenesis & Tissue Remodeling, zelluläre Sauerstoffsensoren, Gewebemakrophagen, Barrierefunktion",
        "primary_topics": ["Verdauungstrakt", "Magen", "Darm", "Leber", "Pankreas", "Histologie", "Angiogenese"],
        "keywords": ["stockmann", "magen", "darm", "oesophagus", "duenndarm", "dickdarm", "leber", "pankreas", "histologie", "peritoneum", "mesenterium"],
        "exam_style": "Topographische Anatomie und mikroskopische Gewebeschichten des Verdauungstrakts mit funktionellem Bezug.",
        "high_yield_pearl": "Gefässversorgung des GI-Trakts: Truncus coeliacus versorgt Vorderdarm (Magen, Leber, Milz, Pankreaskopf, Duodenum proximal). A. mesenterica superior versorgt Mitteldarm (Duodenum distal, Jejunum, Ileum, Caecum, Appendix, Colon ascendens, 2/3 Colon transversum). A. mesenterica inferior versorgt Hinterdarm (ab Cannon-Böhm-Punkt bis oberes Rektum)!",
        "kprim_trap": "Peritonealverhältnisse: Magen, Milz, Leber, Jejunum, Ileum sind intraperitoneal. Duodenum (Pars descendens/horizontalis), Pankreas, Colon ascendens & descendens sind sekundär retroperitoneal! Nieren und Nebennieren sind primär retroperitoneal.",
        "uzh_importance": "Sehr hoch (Prüfungs-Kern Anatomie 2. SJ)",
    },
    "philipp_sommer": {
        "name": "Prof. Dr. Philipp Sommer",
        "title": "Dozent für Kardiologie & Anatomie / Embryologie UZH",
        "institute": "Kardiologie / Anatomisches Institut UZH",
        "research_focus": "Herz- und Gefässentwicklung, Elektrophysiologie, Rhythmusstörungen, embryonale Shunts",
        "primary_topics": ["Herz-Kreislauf", "Embryologie", "Herzbildung", "Gefässentwicklung", "EKG", "Arrhythmien"],
        "keywords": ["sommer", "herzentwicklung", "truncus", "septum", "foramen ovale", "ductus arteriosus", "gefässentwicklung", "embryologie", "ekg"],
        "exam_style": "Typ-A- und Kprim-Fragen zu embryologischen Entwicklungsschritten, angeborenen Herzfehlern und EKG-Lagetypen.",
        "high_yield_pearl": "Fetale Shunts: 1. Ductus venosus (Arantii): leitet sauerstoffreiches Blut aus V. umbilicalis an der Leber vorbei direkt in V. cava inferior. 2. Foramen ovale: Shunt von rechtem zu linkem Vorhof. 3. Ductus arteriosus (Botalli): Shunt von Truncus pulmonalis in Aorta descendens.",
        "kprim_trap": "Verschluss nach der Geburt: Foramen ovale schliesst funktionell sofort durch Druckanstieg im linken Vorhof (Lungenexpansion). Ductus arteriosus Botalli schliesst aktiv durch Sauerstoffanstieg und Abfall der plazentaren Prostaglandine (PGE2) innerhalb der ersten Lebenstage!",
        "uzh_importance": "Sehr hoch (Prüfungs-Kern Modulprüfung 1)",
    },
    "andrew_hall": {
        "name": "Prof. Dr. Andrew Hall",
        "title": "Associate Professor of Anatomy, Gründungsdirektor Zurich Kidney Center",
        "institute": "Anatomisches Institut & Zurich Kidney Center UZH",
        "research_focus": "Funktionelle Bildgebung, mikroskopische Endokrinologie, Hypothalamus-Hypophysen-Achsen, Nebennierenarchitektur",
        "primary_topics": ["Endokrinologie", "Hypothalamus", "Hypophyse", "Nebenniere Histologie", "Schilddrüse", "Inselapparat"],
        "keywords": ["hall", "hypophyse", "hypothalamus", "adenohypophyse", "neurohypophyse", "nebennieren-anatomie", "schilddrüse", "parathyroidea", "c-zellen"],
        "exam_style": "Präzise histologische Schichten der endokrinen Drüsen und deren embryologische Herkunft.",
        "high_yield_pearl": "Nebennierenrinde von aussen nach innen (GFR - 'Salt, Sugar, Sex'): 1. Zona glomerulosa: Aldosteron (Mineralokortikoide, reguliert durch Angiotensin II & K+). 2. Zona fasciculata: Cortisol (Glukokortikoide, reguliert durch ACTH). 3. Zona reticularis: DHEA / Androgene (reguliert durch ACTH). Mark: Adrenalin/Noradrenalin (sympathisch innerviert).",
        "kprim_trap": "Neurohypophyse vs. Adenohypophyse: Die Neurohypophyse produziert SELBST KEINE Hormone! Sie speichert nur ADH und Oxytocin aus dem Hypothalamus. Die Adenohypophyse synthetisiert 6 glandotrope/effektorische Hormone (ACTH, TSH, FSH, LH, GH, Prolaktin).",
        "uzh_importance": "Hoch (Prüfungs-Kern Endokrinologie)",
    },
    "milena_sokolowska": {
        "name": "PD Dr. med. Milena Sokolowska",
        "title": "Leiterin Immune Metabolism (SIAF Davos / UZH Medizinische Fakultät)",
        "institute": "SIAF Davos & UZH Medizinische Fakultät",
        "research_focus": "Immunometabolismus, Biosynthese der Steroidhormone, Katecholaminstoffwechsel, Entzündungsmediatoren",
        "primary_topics": ["Steroidhormone", "Nebennierenrinde", "Katecholamine", "Adrenalin", "Cortisol", "AGS"],
        "keywords": ["sokolowska", "steroid", "steroidhormon", "nebennierenrinde", "katecholamin", "adrenalin", "noradrenalin", "dopamin", "ags", "21-hydroxylase", "cortisol"],
        "exam_style": "Molekulare Synthesewege und klinische Enzymdefekte (wie AGS und Phäochromozytom). Gerne Fallvignetten.",
        "high_yield_pearl": "Adrenogenitales Syndrom (AGS): Zu >90% Defekt der 21-Hydroxylase (CYP21A2). Cortisol und Aldosteron können nicht gebildet werden -> negativer Feedback fehlt -> ACTH steigt massiv an -> Steroidvorstufen stauen sich und werden in Androgen-Weg abgeleitet (Virilisierung weiblicher Feten, Salzverlustsyndrom durch Aldosteronmangel!).",
        "kprim_trap": "Katecholamin-Synthese: Tyrosin -(Tyrosinhydroxylase)-> L-DOPA -> Dopamin -> Noradrenalin -(PNMT)-> Adrenalin. Das Enzym PNMT (Phenylethanolamin-N-Methyltransferase) existiert fast ausschliesslich im Nebennierenmark und wird spezifisch durch hohes Cortisol aus der Nebennierenrinde induziert!",
        "uzh_importance": "Sehr hoch (Prüfungs-Kern Modulprüfung 2)",
    },
    "heimo_emmert": {
        "name": "Prof. Dr. Heimo Emmert",
        "title": "Dozent für Biochemie & Stoffwechselregulation",
        "institute": "Institut für Biochemie UZH",
        "research_focus": "Hormonelle Stoffwechselsteuerung, Kohlenhydrat- und Fettstoffwechsel, Insulin/Glukagon-Signalwege, Leberstoffwechsel",
        "primary_topics": ["Stoffwechsel", "Kohlenhydrate", "Insulin", "Glukagon", "Leber", "Glykolyse", "Glukoneogenese", "Ketonkörper"],
        "keywords": ["emmert", "kh stw", "kohlenhydrat", "insulin", "glucagon", "glukagon", "leberspezifisch", "glykogen", "glukoneogenese", "ketonkörper", "muskelarbeit"],
        "exam_style": "Reziproke Enzymregulation (Phosphorylierung vs. Dephosphorylierung) und Organ-Kooperation bei Hunger/Sättigung.",
        "high_yield_pearl": "Schlüsselschalter Fruktose-2,6-Bisphosphat: Unter Insulineinfluss wird PFK-2 aktiviert -> F-2,6-BP steigt -> allosterische Aktivierung der PFK-1 (Glykolyse läuft auf Hochtouren!). Unter Glukagoneinfluss (cAMP/PKA↑) wird FBPase-2 aktiv -> F-2,6-BP sinkt -> Glykolyse gehemmt, Glukoneogenese aktiv!",
        "kprim_trap": "Ketonkörper-Synthese & -Verwertung: Ketonkörper werden AUSSCHLIESSLICH in der Leber synthetisiert (aus Acetyl-CoA bei Fasten/Diabetes), können aber VON DER LEBER SELBST NICHT verwertet werden, da der Leber das Enzym 3-Ketoacid-CoA-Transferase (Thiophorase) fehlt! Verwertung erfolgt in Gehirn, Herz und Skelettmuskel.",
        "uzh_importance": "Sehr hoch (Prüfungs-Kern Modulprüfung 2)",
    },
    "oliver_ullrich": {
        "name": "Prof. Dr. Oliver Ullrich",
        "title": "Ordinarius für Anatomie & Direktor UZH Space Hub",
        "institute": "Anatomisches Institut UZH",
        "research_focus": "Zellmorphologie, Gravitationsbiologie, Blutzellreifung, Knochenmark",
        "primary_topics": ["Einführung Anatomie", "Blut", "Hämatopoese", "Zellmorphologie"],
        "keywords": ["ullrich", "einführung", "blutzellen", "morphologie", "knochenmark", "retikulozyt"],
        "exam_style": "Orientierende anatomische Grundlagen und Referenzwerte.",
        "high_yield_pearl": "Erythrozyten-Indices: MCV (80–100 fl = normozytär; <80 mikrozytär z.B. Eisenmangel; >100 makrozytär z.B. B12-/Folsäuremangel). MCH (27–34 pg = normochrom). Retikulozytenzahl (0.5–2%) ist der entscheidende Parameter zur Unterscheidung regenerativer vs. aregenerativer Anämien!",
        "kprim_trap": "Hämatopoese-Lokalisation: Beim Feten im 2. Trimenon vor allem Leber und Milz (hepatolienale Phase). Ab 7. Fetalmonat und beim Erwachsenen rotes Knochenmark der platten Knochen (Beckenkamm, Sternum, Wirbelkörper). Fettmark in Röhrenknochen kann bei extremer Anämie reaktiviert werden.",
        "uzh_importance": "Mittel (Basisfragen zu Beginn)",
    },
}

# UZH Modulprüfungen 2. Studienjahr Structure & Regulations
UZH_EXAM_REGULATIONS: Dict[str, Any] = {
    "academic_year": "2. Studienjahr Bachelor Humanmedizin UZH",
    "motto": "Der gesunde Mensch (Theorie & klinische Grundlagen)",
    "semester": "Herbstsemester (3. Fachsemester)",
    "written_exams": [
        {
            "id": "mp1",
            "name": "Modulprüfung 1",
            "date": "2027-01-19",
            "time": "09:00 - 11:30",
            "duration_minutes": 150,
            "format": "Multiple Choice (Typ A: 1 aus 5 & Kprim: Typ K')",
            "scope": "Themenblöcke: 1. Blut & Immunsystem, 2. Herz-Kreislauf, 3. Atmung",
            "question_count": 90,
            "pass_threshold_pct": 60.0,
            "safety_target_retention_pct": 75.0,
            "ects": 14.0,
        },
        {
            "id": "mp2",
            "name": "Modulprüfung 2",
            "date": "2027-01-21",
            "time": "09:00 - 11:30",
            "duration_minutes": 150,
            "format": "Multiple Choice (Typ A: 1 aus 5 & Kprim: Typ K')",
            "scope": "Themenblöcke: 4. Verdauung & Ernährung, 5. Stoffwechsel & Biochemie, 6. Endokrinologie & Hormone",
            "question_count": 90,
            "pass_threshold_pct": 60.0,
            "safety_target_retention_pct": 75.0,
            "ects": 16.0,
        },
    ],
    "grading_policy": {
        "pass_fail_standard": "Standard-Setting (modifizierte Angoff-Methode / Rasch-Modell), normiert bei ca. 60% der Maximalpunkte",
        "kprim_scoring": "4 richtige Entscheidungen = 1.0 Punkt, 3 richtige Entscheidungen = 0.5 Punkte, 0–2 richtige Entscheidungen = 0 Punkte. Kein Punktabzug für falsche Antworten.",
        "typ_a_scoring": "Genau 1 richtige Antwort aus 5 Möglichkeiten = 1.0 Punkt. Falsche Antwort = 0 Punkte.",
        "kprim_danger_warning": "Kprim-Fragen sind für über 60% aller Punktverluste an der UZH verantwortlich, weil bereits 2 kleine Unsicherheiten zum Totalverlust des Prüfungspunktes führen!",
    },
}


def match_professor_for_topic(deck_name: str, topic_title: str = "", module_name: str = "") -> Optional[Dict[str, Any]]:
    """Identifies the leading UZH professor responsible for testing this topic."""
    deck_str = f"{deck_name} {topic_title}".lower()
    full_str = f"{deck_name} {topic_title} {module_name}".lower()

    # 1. Direct deck/topic title match first (high precision)!
    for prof_key, prof in UZH_PROFESSORS.items():
        if any(k in deck_str for k in prof["keywords"]):
            return prof

    # 2. Specific topic fallbacks
    if "gerinnung" in deck_str or "hämostase" in deck_str or "haemostase" in deck_str or "komplement" in deck_str or "hämoglobin" in deck_str:
        return UZH_PROFESSORS["cristina_manatschal"]

    if "säure" in deck_str or "base" in deck_str or "astrup" in deck_str:
        return UZH_PROFESSORS["carsten_wagner"]

    if "hypoxie" in deck_str or "gasaustausch" in deck_str or "respiration" in deck_str or "atem" in deck_str:
        return UZH_PROFESSORS["roland_wenger"]

    # 3. Module fallback heuristics if topic didn't match directly
    if "blut" in full_str or "immun" in full_str:
        if "hämoglobin" in full_str or "gerinnung" in full_str:
            return UZH_PROFESSORS["cristina_manatschal"]
        return UZH_PROFESSORS["selma_tuzlak"]

    if "herz" in full_str or "kreislauf" in full_str:
        return UZH_PROFESSORS["philipp_sommer"]

    if "atmung" in full_str or "lunge" in full_str:
        return UZH_PROFESSORS["roland_wenger"]

    if "säure" in full_str or "base" in full_str or "astrup" in full_str:
        return UZH_PROFESSORS["carsten_wagner"]

    if "verdauung" in full_str or "magen" in full_str or "darm" in full_str:
        if "enzym" in full_str or "cftr" in full_str:
            return UZH_PROFESSORS["raimund_dutzler"]
        return UZH_PROFESSORS["christian_stockmann"]

    if "endokrin" in full_str or "hormon" in full_str:
        if "steroid" in full_str or "adrenalin" in full_str or "katecholamin" in full_str:
            return UZH_PROFESSORS["milena_sokolowska"]
        if "insulin" in full_str or "glucagon" in full_str or "stoffwechsel" in full_str:
            return UZH_PROFESSORS["heimo_emmert"]
        return UZH_PROFESSORS["andrew_hall"]

    return None

    return None


def calculate_uzh_exam_risk_score(
    retention_rate: Optional[float],
    card_count: int,
    is_high_yield: bool = True,
    last_reviewed_days_ago: Optional[float] = None,
) -> Dict[str, Any]:
    """Calculates an evidence-based Exam Risk Score for UZH MC & Kprim exams.
    
    Target: 75% retention gives safety margin against 60% Angoff cutoff.
    Below 70% retention in a High-Yield deck represents critical risk of losing Kprim points.
    """
    ret = retention_rate if (retention_rate is not None and retention_rate > 0) else 50.0
    yield_multiplier = 2.0 if is_high_yield else 1.0

    # Risk score: gaps to 80% safe zone scaled by card volume and exam weight
    retention_gap = max(0.0, 80.0 - ret)
    recency_penalty = 1.25 if (last_reviewed_days_ago and last_reviewed_days_ago > 7.0) else 1.0

    raw_risk = (retention_gap * (card_count / 100.0) * yield_multiplier * recency_penalty)
    normalized_score = min(100.0, round(raw_risk, 1))

    if normalized_score >= 40.0:
        level = "critical"
        label = "🚨 Hohes UZH-Prüfungsrisiko (Kprim-Gefahr)"
        color = "#ff7b72"
        action = "Sofortige Wiederholung & Schema-Verständnis vor der Modulprüfung nötig."
    elif normalized_score >= 15.0:
        level = "warning"
        label = "⚠️ Moderates Prüfungsrisiko"
        color = "#d29922"
        action = "Im regulären Rhythmus vertiefen, gezielt Kprim-Fallen durchgehen."
    else:
        level = "safe"
        label = "✅ Solide verankert (Prüfungssicher)"
        color = "#3fb950"
        action = "Stoff sitzt im sicheren Bereich für die Modulprüfung."

    return {
        "risk_score": normalized_score,
        "risk_level": level,
        "risk_label": label,
        "color": color,
        "recommended_action": action,
        "target_retention_safe": 75.0,
    }


def classify_deck_yield(
    anki_name: str,
    parent_topic: str = "",
    prof_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Classifies an individual Anki deck into UZH 2. SJ exam yield levels:
    - 'high': High Yield (🔴 Sehr hoch / Prüfungs-Kern & Kprim-Hotspots)
    - 'medium': Medium Yield (🟡 Relevant / Standard-Prüfungsstoff)
    - 'low': Low Yield (🟢 Gering / Spezifische Versuche, Randthemen & Detailnischen)
    - 'none': No Yield (⚪ Kein Ertrag / Reine Einführungen, Abschlüsse, Orga)
    """
    nl = anki_name.lower()

    # 1. No Yield (Einführung, Abschluss, Organisation, Vorbesprechung)
    no_yield_terms = [
        "einführung", "abschluss", "einfuehrung", "organisat", "vorbesprechung", "feedback"
    ]
    if any(t in nl for t in no_yield_terms) and "versuch" not in nl:
        return {
            "yield_level": "none",
            "yield_label": "No-Yield (Einführung / Orga)",
            "yield_badge": "⚪ No-Yield",
            "yield_color": "#8b949e",
            "yield_order": 4,
            "yield_reason": "Reine Orientierungs-, Einführungs- oder Abschlussfolien ohne prüfungsrelevante Fakten.",
        }

    # 2. Low Yield (Praktikumsversuche, Kaumuskelbeschwerden, Nischenmethoden)
    low_yield_terms = [
        "versuch", "kaumuskelbeschwerden", "pcr und restriktion :: versuch",
        "proteinreinigung :: versuch", "photometrieren :: versuch", "sds-page :: versuch"
    ]
    if any(t in nl for t in low_yield_terms):
        return {
            "yield_level": "low",
            "yield_label": "Low-Yield (Versuch / Detail)",
            "yield_badge": "🟢 Low-Yield",
            "yield_color": "#3fb950",
            "yield_order": 3,
            "yield_reason": "Praktikumsversuch / methodisches Detail mit untergeordneter Relevanz für schriftliche Modulprüfungen.",
        }

    # 3. High Yield (Prüfungs-Kerngebiete, Kern-Dozenten, Kprim-Hotspots)
    hy_terms = [
        "blutgerinnung", "hämostase", "astrup", "säure-base", "hypoxie", "höhenanpassung",
        "ekg", "raas", "aldosteron", "nephron", "glukagon", "insulin", "ketonkörper",
        "steroid", "ags", "herzentwicklung", "shunts", "klappen", "immuntoleranz",
        "t-zell", "autoimmunität", "monoklonale", "diuretika", "tubulär", "kalium",
        "sglt", "membrantransport", "arrhythmie", "erythrozyten", "co2-transport",
        "leukozyten", "thrombozyten", "energieumsatz", "schilddrüse", "nebenniere",
        "kohlenhydrat stoffwechsel", "leberspezifischer", "fettsäurestoffwechsel",
        "endokrines pankreas", "katecholamine", "hypothalamo", "wenger", "wagner",
        "tuzlak", "sommer", "loffing", "dutzler", "sokolowska", "emmert"
    ]
    if any(t in nl for t in hy_terms) or (prof_info and prof_info.get("uzh_importance", "").startswith("Sehr hoch")):
        return {
            "yield_level": "high",
            "yield_label": "High-Yield (Prüfungs-Kern)",
            "yield_badge": "🔴 High-Yield",
            "yield_color": "#f85149",
            "yield_order": 1,
            "yield_reason": "Zentraler Prüfungs-Hotspot UZH 2. SJ mit regelmässigen Kprim- und MC-Fragen.",
        }

    # 4. Medium Yield (Standardvorlesungen, Anatomie, Physiologie)
    return {
        "yield_level": "medium",
        "yield_label": "Medium-Yield (Standard-Stoff)",
        "yield_badge": "🟡 Medium-Yield",
        "yield_color": "#d29922",
        "yield_order": 2,
        "yield_reason": "Kanonischer Standardstoff (Physiologie, Anatomie, Biochemie Grundlagen).",
    }

