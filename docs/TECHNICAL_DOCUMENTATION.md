# Study-Life Orchestrator – Technische Dokumentation

Diese Dokumentation beschreibt die vollständige Systemarchitektur, Algorithmen, Datenmodelle, Datenbankschemata und API-Schnittstellen des **Study-Life Orchestrators**.

---

## 1. Systemarchitektur & Komponentenübersicht

Die Anwendung folgt einer sauberen Schichtenarchitektur (*Clean Layered Architecture*):

```
+-------------------------------------------------------------+
|               Frontend (SPA - HTML5 / CSS3 / ES6)           |
|  - Executive KPI Strip, Interactive Timeline, 4 Fach-Tabs   |
+-------------------------------------------------------------+
                              |
                              | HTTP / JSON REST
                              v
+-------------------------------------------------------------+
|                      FastAPI Backend                        |
|  - app/main.py: App-Factory, CORS, Statische Assets         |
|  - app/api/v1/endpoints.py: Validierte REST-Endpunkte       |
+-------------------------------------------------------------+
        |                     |                     |
        v                     v                     v
+----------------+   +-----------------+   +------------------+
| Domain Models  |   | Core Services   |   | Persistence / DB |
| app/models.py  |   | - slot_finder   |   | app/db/database  |
| app/schemas/   |   | - time_grid     |   | app/db/repository|
+----------------+   | - calendar_parse|   | SQLite (WAL)     |
                     | - anki_analyzer |   +------------------+
                     | - ankiweb_serv. |
                     | - efficiency    |
                     +-----------------+
```

### Modulverzeichnis

| Modul | Pfad | Verantwortung |
|---|---|---|
| **API Routers** | `app/api/v1/endpoints.py` | FastAPI Endpunkte, Input-Validierung, Response-Serialisierung, Fehlerbehandlung |
| **Main App** | `app/main.py` | Server-Initialisierung, Static Files Mount (`/static`), HTML-Fallback, CORS-Policy |
| **Domain Models** | `app/models.py` | Pydantic V2 Modelle für Kalender, Aktivitäten, Anki-Themen, Profile und Telemetrie |
| **Legacy Schemas** | `app/schemas/calendar.py`, `request.py` | Rückwärtskompatible Schemas für Phase-1 Interval-Endpoints |
| **Time Grid Engine** | `app/services/time_grid.py` | Robuste Intervall-Arithmetik für freie Zeitfenster, Clamping & Back-to-Back Merging |
| **Calendar Parser** | `app/services/calendar_parser.py` | RFC 5545 iCal/ICS & Google Calendar JSON Parser, Async HTTP Client mit SSL-Toleranz |
| **Anki Analyzer** | `app/services/anki_analyzer.py` | `.apkg` (SQLite) & TSV Parser, Vorlesungs-Matching, Study Orchestration, Rollover |
| **Anki Local Sync** | `app/services/anki_local_service.py` | Automatische Erkennung lokaler Anki Desktop Profile (`%APPDATA%\Anki2`), schreibgeschützter SQLite-Zugriff (`?mode=ro`), `revlog`-Telemetrie & AnkiConnect Bridge |
| **AnkiWeb Sync** | `app/services/ankiweb_service.py` | Synchronisation von Flashcard-Telemetrie (Geschwindigkeit, Behaltensrate, Streaks) |
| **Efficiency Analyzer**| `app/services/efficiency_analyzer.py` | Data-Driven Vorlesungs-ROI: Vergleich Lerntempo & Retention mit vs. ohne Vorlesung |
| **Database & Repo** | `app/db/database.py`, `repository.py` | SQLite Verbindungs-Pool mit WAL-Modus, Transaktionssicherheit und CRUD-Methoden |
| **Frontend Assets** | `app/static/` (`index.html`, `app.js`, `style.css`) | Schlanke Single-Page-App im Linear/GitHub-Stil mit responsivem Design |

---

## 2. Kernalgorithmen

### 2.1 Intervall-Arithmetik (`calculate_free_slots`)

Der Algorithmus in `app/services/time_grid.py` und `app/services/slot_finder.py` berechnet freie Arbeitszeitfenster unter Berücksichtigung fester Verpflichtungen:

1. **Window Definition & Timezone Normalization**:
   - Definiert das operative Tageszeitfenster (Standard: 07:00 bis 23:00 Uhr).
   - Gleicht Zeitzonenunterschiede zwischen Naive- und Aware-Datetimes automatisch an.
2. **Clamping & Filterung**:
   - Termine außerhalb des Fensters werden ignoriert.
   - Termine, die über die Grenzen hinausragen, werden exakt auf `[win_start, win_end]` beschnitten.
3. **Sortierung**:
   - Alle belegten Intervalle werden chronologisch nach Startzeit aufsteigend sortiert.
4. **Intervall-Verschmelzung (Merging)**:
   - Überlappende Termine (`start <= last_end`) und direkt aneinandergrenzende Vorlesungen (Back-to-Back, `start == last_end`) werden nahtlos zu einem kontinuierlichen Belegungsblock zusammengefasst.
   - Verhindert 0-Minuten-Geisterlücken.
5. **Komplementär-Invertierung**:
   - Durchläuft die verschmolzenen Blöcke und generiert freie Slots für alle Lücken `[current_time, block_start]`.
   - Berücksichtigt Pufferzeit von Beginn des Tages bis zur ersten Vorlesung und von der letzten Vorlesung bis zum Tagesende.

### 2.2 Anki-Themenextraktion & Vorlesungs-Matching

1. **Dekompression & Tag-Parsing**:
   - Extrahiert `collection.anki21` bzw. `collection.anki2` aus `.apkg`-Archiven.
   - Extrahiert hierarchische Tags (z.B. `Informatik::Algorithmen::Graphen` $\rightarrow$ `Informatik - Algorithmen - Graphen`).
   - Fallback für ungetaggte Karten über semantische Schlüsselwörter des ersten Notizfeldes.
2. **Relevanz-Scoring**:
   - Vergleicht Themen mit den Titeln und Beschreibungen des Vorlesungsplans.
   - Score $\in [0.0, 1.0]$: Exakter Substring-Match liefert $\ge 0.85$, semantische Schnittmengen liefern $\ge 0.60$.
   - Vorlesungen des gleichen Tages erhöhen die Dringlichkeit (`urgency = 'high'`).

### 2.3 Smart Study Orchestration & Rollover

1. **Orchestrierung**:
   - Freie Slots $\ge 20$ Minuten werden priorisiert mit hochrelevanten Anki-Themen belegt.
   - Beachtet maximale tägliche Lerndauer (`max_daily_study_minutes`) und Pomodoro-Einheiten.
   - Platziert Vorbereitungseinheiten idealerweise vor der zugehörigen Vorlesung.
2. **Rollover unvollständiger Lernziele**:
   - Am Tagesende nicht erledigte Flashcard-Stapel werden erfasst.
   - Verteilt offene Karten kognitiv optimiert über die Folgetage ($+1$, $+2$, $+3$), um Überlastung zu verhindern, während thematische Cluster zusammengehalten werden.

### 2.4 Data-Driven Lecture ROI & Effizienz-Analyse

Vergleicht das Lernen mit Vorlesungsbesuch vs. reines Selbststudium:
- **Geschwindigkeitsfaktor ($S$)**:
  $$S = \frac{\text{Sekunden pro Karte (ohne Vorlesung)}}{\text{Sekunden pro Karte (mit Vorlesung)}}$$
- **Behaltensraten-Delta ($\Delta R$)**:
  $$\Delta R = R_{\text{mit}} - R_{\text{ohne}}$$
- **Netto-Zeitbilanz**:
  Berechnet die eingesparte Anki-Wiederholungszeit abzüglich der 90 Minuten Vorlesungsdauer:
  $$\text{Netto-Zeitgewinn} = t_{\text{gespart}}(\text{Anki}) - 90\,\text{min}$$
- **Entscheidungsmatrix**:
  - $S \ge 1.6$ oder $\Delta R \ge 15\%$: **VORLESUNG BESUCHEN ✅**
  - $S \le 1.2$ und $\Delta R \le 5\%$: **REINES SELBSTSTUDIUM 🚀** (spart 90 min)
  - Dazwischen: **HYBRID ⚖️** (Schwerpunkte vor Ort, Basics via Folien/Anki)

### 2.5 Lokale Anki-Desktop & AnkiWeb Synchronisation

Um Datenverlust und API-Beschränkungen von AnkiWeb (`ankiweb.net`) zu umgehen, setzt der Orchestrator auf eine hybride 3-in-1 Synchronisationsarchitektur:

1. **Lokaler Read-Only SQLite Adapter (`collection.anki2?mode=ro`)**:
   - Erkennt standardmäßige Anki 2 Verzeichnisse (`%APPDATA%\Anki2` unter Windows, `~/Library/Application Support/Anki2` unter macOS, `~/.local/share/Anki2` unter Linux).
   - Öffnet die Datenbank im strikten Nur-Lese-Modus (`mode=ro`), wodurch Lesezugriffe vollkommen risikofrei und ohne Dateisperren möglich sind, selbst wenn Anki Desktop parallel geöffnet ist.
   - **Aktiver Curriculum-Scope**: Filtert und fokussiert gezielt auf die **9'319 Karten des 2. Studienjahres (2. SJ)** sowie die **314 Karten von HS 2021** (Gesamt: **9'633 aktive Karten**). Ältere Semesterkarten aus der Rohsammlung (13'531) werden ausgeblendet.
   - Extrahiert aktive Decks, fällige Karten (`queue in (1,2,3)`), neue Karten (`queue = 0`) und ordnet sie thematischen Clustern (z.B. *Anatomie & Bewegungsapparat*, *Chemie & Stoffwechsel*, *Molekulare Zellbiologie & Genetik*, *Embryologie & Zellbiologie*, *Hämatologie & Immunologie*, *Medizinische Grundlagen*) zu.
2. **Reale Telemetrie-Berechnung aus `revlog`**:
   - **Lerngeschwindigkeit**: $v = \frac{\sum \text{time}}{1000 \cdot N}$ Sekunden pro Karte.
   - **Reale Behaltensrate**: $R = \frac{\sum [\text{ease} > 1]}{N}$.
   - **Lern-Streak**: Zählung eindeutiger Lerntage aus den Unix-Zeitstempeln der Review-Logs.
### 2.6 Deadline-basierte Exam Engine, Pacing-Kurve & Ist-Tracker (Phase 1)

Um zielgerichtet auf die UZH-Prüfungen im 2. Studienjahr hinzuarbeiten, berechnet die Exam Engine ein tagesaktuelles Soll-Kartenpensum:
1. **Prüfungstermine**:
   - Prüfung 1: **19.01.2027**
   - Prüfung 2: **21.01.2027**
2. **Curriculum-Umfang & Revisionspuffer**:
   - Gesamtkarten: **9'633 Karten** (9'319 aus 2. SJ + 314 aus HS 2021).
   - **14 Tage Revisionspuffer**: Die letzten zwei Wochen vor der Prüfung (ab 05.01.2027) sind für reines Wiederholen reserviert ($\text{Soll}_{\text{neu}} = 0$).
3. **Pacing-Kurve & Ruhetage**:
   - **Reguläre freie Tage**: Zieht konfigurierte freie Wochentage (Standard: Sonntag als Ruhetag) automatisch ab.
   - **Spontane Joker-Tage**: Beliebige Tage können per 1-Klick als Ruhetag (z. B. bei Krankheit, Urlaub) deklariert werden.
   - **Pacing-Formel**:
     $$\text{Tagesziel (Soll)} = \left\lceil \frac{\text{Verbleibende neue Karten}}{\text{Aktive Lerntage vor Revisionspuffer}} \right\rceil$$
   - Bei 6 Lerntagen/Woche (Sonntag frei): **~99–100 Karten/Tag**.
   - Bei 7 Lerntagen/Woche: **~85–86 Karten/Tag**.
   - Bei 5 Lerntagen/Woche: **~120 Karten/Tag**.
    - Bei 5 Lerntagen/Woche: **~120 Karten/Tag**.
4. **Ist-Erfassung (Progress Tracking)**:
   - Protokolliert tatsächlich gelernte Karten (`daily_progress_logs`) via Schnellwahltasten (`+10`, `+25`, `+50`, `✓ Erledigt`, `⚡ Anki`) oder manueller Eingabe.
   - Rebalanciert bei Verzug oder Vorsprung sofort das Soll für alle verbleibenden Tage.

### 2.7 Vorlesungs-Ampel & Speed-Simulator („Lohnt sich das überhaupt?“)

Um zeitraubende Vorlesungen zu optimieren, evaluiert das System jede Lehrveranstaltung anhand von Prüfungsrelevanz, Vorkenntnissen und Anki-Schwachstellen:
1. **Drei-Stufen-Ampel**:
   - 🟢 **Empfehlung: Besuchen**: Hohe Prüfungsrelevanz, anatomisches Verständnis oder Pflichtveranstaltung.
   - 🟡 **Empfehlung: Stream (1.25x – 2.0x)**: Strukturierte Inhalte mit hohem Wiederholungspotenzial.
   - 🔴 **Empfehlung: Skippen & Anki**: Reine Nomenklatur oder Faktenwissen, das zu >80% bereits in den Anki-Karten abgedeckt ist.
2. **Interaktive Konsum-Modi & Zeitersparnis-Rechner**:
   - `live` (1.0x, 0 min gespart)
   - `stream_1_25` (1.25x, spart ca. 18 min bei 90 min Vorlesung)
   - `stream_1_5` (1.5x, spart 30 min)
   - `stream_2_0` (2.0x, spart 45 min)
   - `slides_only` (30 min Bearbeitung, spart 60 min)
   - `skipped` (0 min Bearbeitung, spart volle 90 min)
   Die eingesparte Zeit wird tagesaktuell aggregiert und im Executive Ribbon ausgewiesen.

### 2.8 Anki Due Reviews & Schwachstellen-Analyse (`app/services/anki_weakness_service.py`)

1. **Sperrfreier SQLite-Zugriff mit `immutable=1`**:
   - Öffnet `collection.anki2` via `file:///<path>?mode=ro&immutable=1`.
   - Verhindert jegliche `sqlite3.OperationalError: database is locked`-Fehler, selbst wenn die Anki Desktop Applikation parallel geöffnet ist.
2. **Kombiniertes Tagespensum ($N_{\text{total}}$)**:
   - Täglicher Arbeitsaufwand = $N_{\text{neu}} (\approx 100) + N_{\text{due}}$ (fällige Wiederholungskarten).
3. **Automatisierte Schwachstellen-Erkennung**:
   - Analysiert `revlog` auf Decks mit Fehlerraten ($\text{Again-Quote} \ge 10\%$).
   - Erkennt überfällige Themengebiete ($\Delta t > 14\,\text{Tage}$ seit der letzten Wiederholung) und markiert sie mit Warn-Badges (`⚠️ Schwachstelle`, `⏳ Überfällig`).

### 2.9 UZH VAM (Virtuelle Ausbildungsplattform Medizin) & OpenOLAT Integration

1. **Architektur & SSO-Toleranz**:
   - VAM ist auf UZH OpenOLAT unter Kurs-ID `#666697737` (2. Studienjahr B Med, Kursknoten `76022446801983`) angesiedelt.
   - Zur dateibasierten Synchronisation nutzt das System die standardisierte **WebDAV-Schnittstelle** von UZH OpenOLAT: `https://lms.uzh.ch/webdav` mit hinterlegtem Anmeldenamen (`553131393539353502@uzh.ch`).
2. **Netzwerk-Sicherheitsbarriere der UZH Zentralen Informatik**:
   - WebDAV (`/webdav`) und REST-Endpunkte (`/restapi`) sind von UZH-Seite aus Sicherheitsgründen streng auf das interne Universitätsnetzwerk beschränkt.
   - Ein Zugriff von externen IP-Adressen (z. B. Heim-WLAN) liefert HTTP 403 (*„Bitte stellen Sie eine Verbindung zum UZH-Netzwerk her“*).
   - Zur WebDAV-Synchronisation außerhalb des Campus muss das **UZH VPN (Cisco AnyConnect / Secure Client)** aktiv sein. Innerhalb des UZH eduroam-Campusnetzes funktioniert die Verbindung unmittelbar.
3. **Aufbau des VAM-Kurses & Bereitstellung**:
   - **Skripte & Folien:** Liegen in den jeweiligen Themen-Kursordnern (z. B. Anatomie, Hämatologie, Verdauung) und werden dateibasiert synchronisiert oder aus `OneDrive - Universität Zürich UZH/alles/Studium` indexiert.
   - **Alte Vorlesungsaufzeichnungen (Videos):** Liegen im Kursknoten „Archiv“. Da Video-Streams auf SWITCHtube/UZH Cast als Webseiten eingebunden sind, stellt der Orchestrator auf jeder Timeline-Vorlesungskarte direkte Schnellzugriff-Links (`[🎬 VAM-Archiv]`, `[📄 Skripte]`) bereit, die die Vorlesung direkt im Browser mit aktiver SWITCH edu-ID Sitzung öffnen.

### 2.10 Zero-Baseline & AnkiWeb Synchronisation

- Das reale Profil `constantingrandidier@gmail.com` ist hinterlegt.
- Zum Semesterstart (14.09.2026) ist der Fortschritt exakt auf **0.0% (0 von 9'633 Karten)** gesetzt.
- Formel für Exam-Readiness skaliert dynamisch: Bei $0.0\%$ gelernten Karten ist die Readiness strikt **0.0%**.

---

## 3. Datenbank-Architektur (SQLite / WAL)

Die SQLite-Datenbank liegt standardmäßig unter `app/data/studylife.db` und arbeitet im **WAL-Modus** (Write-Ahead-Logging) für konkurrierende Lese- und Schreibzugriffe.

### Tabellenübersicht

- `user_profile`: Einstellungen, Biorhythmus (Schlaf-/Wachzeiten), Pomodoro, hinterlegte Kalender-URL, AnkiWeb-E-Mail.
- `saved_events`: Aus iCal/webcal synchronisierte Vorlesungen, Übungen und Seminare inkl. Anwesenheitsstatus (`lecture_attended`).
- `saved_activities`: Manuelle Aktivitäten (Sport, Essen, Pendelzeit, Pausen).
- `anki_decks` & `anki_topics`: Importierte Decks und extrahierte Themencluster mit Schwierigkeit und Vorlesungs-Relevanz.
- `study_session_logs`: Historische Lernprotokolle mit Lerngeschwindigkeit ($s/\text{card}$), Behaltensrate und Vorlesungsbezug.
- `ankiweb_stats`: Telemetrie-Snapshot aus der AnkiWeb Cloud.
- `exams`: Prüfungstermine ($T_{\text{Exam}}$), Modulbezeichnung und Ziel-Kartenvolumen.
- `study_schedule_config`: Lernrhythmus-Konfiguration (freie Wochentage, Joker-Tage, Revisionspuffer in Tagen).
- `daily_progress_logs`: Tägliche Ist-Erfassung von gelernten Karten und Zeitaufwand.

---

## 4. REST-API Schnittstellen-Dokumentation

Alle Routen besitzen den Präfix `/api/v1/schedule` (interaktiv erreichbar unter `/docs`).

### 4.1 Kalender & Tageszeitplan

- `GET /today`: Liefert Tagesplan mit Vorlesungen, Aktivitäten und freien Slots (`?target_date=YYYY-MM-DD`).
- `POST /sync-url`: Importiert Remote-Kalenderfeed (iCal/webcal), speichert alle Termine des Semesters in SQLite.
- `POST /upload-ics`: Lädt `.ics`-Datei hoch und persistiert Termine.
- `POST /custom`: Berechnet freie Lücken neu unter Hinzunahme manueller Aktivitäten.
- `GET /dummy`: Statischer Referenzplan für Benchmark-Tests.
- `POST /from-events`: Intervallberechnung auf nativer Event-Liste.
- `POST /from-gcal`: Intervallberechnung auf Google Calendar JSON.
- `POST /from-ical`: Intervallberechnung auf iCal-String / URL.

### 4.2 Anki-Integration & Orchestrierung

- `GET /anki/detect-local`: Durchsucht das lokale Dateisystem nach Anki 2 Profilen und prüft den AnkiConnect-Status.
- `POST /anki/local-sync`: 1-Klick-Synchronisation der erkannten lokalen `collection.anki2` (Themen, Karten, `revlog`-Telemetrie).
- `POST /anki/upload`: Parst `.apkg` oder Text-Export, speichert Themen in SQLite.
- `POST /anki/orchestrate`: Platziert Anki-Themen bedarfsorientiert in freie Slots.
- `POST /anki/rollover`: Verteilt nicht beendete Karten kognitiv optimiert auf Folgetage.
- `GET /persisted/anki`: Lädt das zuletzt gespeicherte Anki-Deck.
- `POST /ankiweb/sync`: Synchronisiert Telemetriedaten von AnkiWeb oder greift transparent auf die lokale Datenbank zurück.
- `GET /ankiweb/stats`: Liefert aktuelle AnkiWeb-Lernmetriken.

### 4.3 Vorlesungs-ROI & Effizienz-Analytics

- `GET /analytics/efficiency`: Berechnet ROI pro Modul und Gesamt-Verdict.
- `POST /study/log`: Protokolliert eine abgeschlossene Lerneinheit mit Telemetrie.
- `POST /attendance`: Markiert Vorlesung als besucht (1) oder geschwänzt (0).

### 4.4 Profil & Persistierte Aktivitäten

- `GET /profile`: Ruft Studierendenprofil & Konfiguration ab.
- `POST /profile`: Aktualisiert Studierendenprofil & Biorhythmus.
- `POST /persisted/activity`: Speichert manuelle Aktivität in SQLite.
- `DELETE /persisted/activity/{id}`: Löscht gespeicherte Aktivität.

### 4.5 Prüfungs-Pacing & Ist-Tracking (Phase 1)

- `GET /exam/pacing`: Berechnet verbleibende Tage bis 19.01.2027, aktive Lerntage (unter Abzug freier Tage und Puffer), tägliches Soll (z. B. 99–100 Karten) und Exam-Readiness.
- `POST /exam/log-progress`: Erfasst tatsächlich gelernte Karten (`cards_completed`, `minutes_spent`) und rebalanciert die Pacing-Kurve sofort.
- `POST /exam/toggle-joker`: Schaltet einen spontanen Pausentag/Joker-Tag für ein Datum ein oder aus.
- `POST /exam/config`: Ändert freie Wochentage (z. B. Sonntag frei) und die Revisionspuffer-Dauer.
- `GET /exam/list`: Liefert alle hinterlegten Prüfungen mit Resttagen.

### 4.6 Vorlesungs-Entscheidungslogik & Schwachstellen (Phase 2)

- `POST /lecture/mode`: Setzt Konsum-Modus einer Vorlesung (`live`, `stream_1_25`, `stream_1_5`, `stream_2_0`, `slides_only`, `skipped`) und berechnet Zeitersparnis.
- `GET /anki/weaknesses`: Liefert fällige Wiederholungen, Decks mit hoher Fehlerquote und überfällige Themen aus lokaler `collection.anki2`.
- `GET /stats/comparison`: Liefert Vortagsvergleich (+/- Delta, %-Veränderung), 7-Tage-Schnitt, Streak und eingesparte Vorlesungsminuten.
- `GET /olat/status`: Prüft Erreichbarkeit von UZH OpenOLAT (`https://lms.uzh.ch`), WebDAV-Endpunkt und scannt lokale UZH-OneDrive-Folien.
- **Echte Folien-Extraktion & Anki-Cross-Matching (`app/services/lecture_decision_service.py`)**:
  - Scannt den Ordner `C:\Users\Constantin Grandidie\OneDrive - Universität Zürich UZH\Desktop\UNI sem app` (51+ Vorlesungs-PDFs aus Themenblöcken *Blut & Immunsystem*, *Herz-Kreislauf*, *Atmung*, *Endokrinologie*, *Verdauung & Ernährung*, *Klinischer Untersuchungskurs*).
  - Extrahiert Volltext via `pypdf` und gleicht medizinische Fachbegriffe direkt mit den 9'633 Karten in `%APPDATA%\Anki2\Benutzer 1\collection.anki2` ab.
  - Berechnet exakte Deckungsgrade (z. B. Hämoglobin 87.6%, CO2-Transport 92.7%, Herzentwicklung 91.4%, Blutgerinnung 81.6%, Adaptives Immunsystem 66.7%).
  - **Reverse Deckungsgrad**: **7'184 von 9'633 Anki-Karten (74.6%)** des 2. Studienjahrs werden durch die 51 Vorlesungs-Folien direkt abgedeckt (viele Kern-Decks wie Blutgerinnung, Pankreashormone, Hämoglobin zu 100%).
  - **Zyklen- & Kaskaden-Erkennung**: Bei systemischen Kreisläufen, Stoffwechselwegen oder Kaskaden (z. B. Gerinnung, Komplement, RAAS, Herzmechanik, Hypophysenachsen) wird trotz hoher Einzelfakten-Deckung nicht blind "Skip" empfohlen, sondern `🟡 Stream (1.5x / 2.0x) – Zyklen/Grobübersicht`, um das vernetzte Systemverständnis und den roten Faden zu sichern.
  - Blendet auf den Vorlesungskarten der Timeline Badges (`🔴 88% Anki-Deckung (Skippen & Anki)`, `📑 Folie: 1-4_CM_Myoglobin_Hamoglobin.pdf`) ein.



### 4.7 Didaktische Semester-Roadmap & Täglicher 100-Anki Lernauftrag (Phase 3)

- `GET /schedule/curriculum/today?target_date=YYYY-MM-DD`:
  - Liefert den verbindlichen, didaktisch sequenzierten Lernauftrag für den Tag.
  - **Exakte 100-Karten-Zuteilung**: Berechnet exakt, aus welchem Deck wie viele Karten gelernt werden müssen (z. B. *48 Karten Deck A + 52 Karten Deck B*).
  - **Sonntags-Schutz**: Sonntage sind automatisch als Ruhetage deklariert (`target_cards: 0`).
  - **Reale Folien-Verknüpfung**: Jedes Subthema ist direkt mit der zugehörigen PDF-Vorlesungsfolie aus `UNI sem app` verknüpft.
  - **Zyklen- & Kaskaden-Tagging**: Hebt Themen mit systemischen Kreisläufen oder biochemischen Kaskaden als `🟡 Zyklen/Grobübersicht (1.5x Stream)` hervor.
- `GET /schedule/curriculum/roadmap`:
  - Liefert den vollständigen Semesterplan über alle **111 Decks** und **9'633 Karten** des 2. Studienjahrs.
  - Strukturiert den Stoff in 6 logische medizinische Module:
    1. *1. Blut & Immunsystem* (684 Karten, 8 Decks, ~7 Lerntage)
    2. *2. Herz-Kreislauf* (2'152 Karten, 26 Decks, ~21.5 Lerntage)
    3. *3. Atmung & Lunge* (1'875 Karten, 18 Decks, ~18.8 Lerntage)
    4. *4. Verdauung & Ernährung* (3'507 Karten, 42 Decks, ~35 Lerntage)
    5. *5. Stoffwechsel & Biochemie* (490 Karten, 6 Decks, ~4.9 Lerntage)
    6. *6. Endokrinologie & Hormone* (925 Karten, 11 Decks, ~9.2 Lerntage)
  - **Timeline**: Semesterstart am `14.09.2026`, Gesamtabschluss am `04.01.2027` nach 97 aktiven Lerntagen.
  - **Garantierter Revisionspuffer**: Exakt **15 freie Tage vor dem Examen am 19.01.2027** für Probeprüfungen und gezielte Wiederholungen.

---

## 5. Frontend-Architektur

Die Benutzeroberfläche unter `app/static/index.html` ist als reaktive, abhängigkeitsfreie Single-Page Application (Vanilla ES6 JavaScript, HTML5, CSS3) umgesetzt.

- **Design System**: Inspiriert von Linear / GitHub (dunkles High-Clarity Theme, klare Typografie, dezente Badges, segmentierte Filter).
- **Tages-Kompass Banner (Phase 1 & 2)**:
  - Zeigt Prüfungs-Countdown (`19.01.2027`), Tagesziel (z. B. 100 neue Karten + Due Reviews), Ist-Stand, Status (`🟢 Lerntag aktiv` vs. `🏖️ Ruhetag`), Revisionspuffer (14 Tage ab 05.01.2027) und Exam-Readiness.
  - Schnell-Erfassung per Ein-Klick: `+10`, `+25`, `+50`, `✓ Erledigt` oder `⚡ Anki`.
  - Spontaner Joker-Tag-Schalter zur flexiblen Pausenplanung.
  - **4-Item Telemetrie-Streifen**: Vortagsvergleich (+/- Delta), 7-Tage-Schnitt, Streak und heute gesparte Vorlesungszeit.
  - **Schwachstellen-Warnbox**: Hebt Themen mit über 10% Fehlerquote oder >14 Tage Inaktivität hervor.
- **🎯 Dein heutiger Lernauftrag (Phase 3 Hero-Card)**:
  - Prominente Karte direkt unter dem Pacing-Banner.
  - Zeigt tagesaktuell:
    - Tag im Semester (z. B. `Tag 1 von 97`), Modulname und Quota (`100 neue Karten`).
    - Subthemen-Aufschlüsselung mit exakter Kartenzahl pro Deck.
    - Direkte Verknüpfung zur Vorlesungsfolie (`📄 Tuzlak_Vorlesung_11_Blutgerinnung_HS24.pdf`).
    - Didaktischer Badge (`🟡 Zyklen / 1.5x Stream` vs. `🟢 Anki Prio (Skip)`).
    - Semester-Gesamtfortschrittsbalken und Prüfungs-Countdown.
    - Button `[🗺️ Semester-Roadmap ansehen]`.
- **🗺️ Didaktische Semester-Roadmap Modal (Phase 3)**:
  - Übersicht aller 6 Module mit Start-/Endterminen, Lerntagen und Kartenanzahl.
  - Durchsuchbarer Tag-für-Tag Kalender für das gesamte Semester bis zum 04.01.2027.
- **Interaktive Vorlesungs-Ampel auf Timeline**:
  - Jede Vorlesungskarte besitzt eine datenbasierte Empfehlung (`🟢 Besuchen`, `🟡 Streamen`, `🔴 Skippen`) samt fundierter Begründung.
  - Interaktive Speed-Pills (`[Live 1.0x]`, `[1.25x]`, `[1.5x]`, `[2.0x]`, `[Folien]`, `[Skip]`), die bei Klick sofort die Zeitersparnis erfassen und den Tagesplaner entlasten.
- **UZH VAM & OpenOLAT Connector-Karte**:
  - Zeigt Live-Status der UZH Lernplattform (`https://lms.uzh.ch/url/RepositoryEntry/666697737/CourseNode/76022446801983`), WebDAV-Anbindung und automatisch indexierte PDF-Folien aus dem UZH OneDrive.
- **AnkiWeb Hierarchischer Deckbaum Modal**:
  - Vollwertige Baumansicht (Ordner-Hierarchie wie auf AnkiWeb) über alle 111 Decks des 2. Studienjahrs.
  - Echtzeit-Suchfilter und Schnellausklappfunktionen.
- **Zustandsverwaltung (`state` in `app.js`)**:
  - `state.targetDate`: Aktuell ausgewähltes Datum (reaktiv an API übergeben).
  - `state.fixedEvents`, `state.freeSlots`, `state.manualActivities`: Aktuelle Tageskomponenten.
  - `state.taskCompletions`: Checkbox-Status für Aufgaben (Vorlesungen, Aktivitäten, Lerneinheiten), persistent im `localStorage` gespeichert.
  - `state.efficiencyData`: Geladene Vorlesungs-ROI-Statistiken zur dynamischen Einblendung von Besuchsempfehlungen direkt auf den Vorlesungskarten der Timeline.
- **Executive KPI Strip**: Zeigt auf einen Blick offene/erledigte Aufgaben, prozentualen Tagesfortschritt, freie Stunden und Vorlesungstermine.

---

## 6. Testabdeckung & Qualitätssicherung

Die automatisierte Testsuite umfasst **63 Unit- und Integrationstests** mit `pytest`:
- `tests/test_curriculum_roadmap.py`: 7 Tests (Phase 3 Didaktische Semester-Roadmap, 100-Karten Tageszuteilung, Sonntagsruhe, Revision & REST-APIs)
- `tests/test_slot_finder.py`: 6 Tests
- `tests/test_time_grid.py`: 10 Tests
- `tests/test_calendar_parser.py`: 3 Tests
- `tests/test_anki_analyzer.py`: 6 Tests
- `tests/test_anki_local.py`: 5 Tests
- `tests/test_efficiency_analyzer.py`: 3 Tests
- `tests/test_exam_pacing.py`: 5 Tests (Phase 1)
- `tests/test_phase2_decisions.py`: 6 Tests (Phase 2 Vorlesungs-Ampel, Speed-Simulator, Anki Weaknesses, OLAT)
- `tests/test_api.py`: 12 Tests

Ergebnis: **63 passed (100% Erfolgsquote)**.

