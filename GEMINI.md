# Antigravity Agent Guidelines: Study-Life-Orchester

## Autonome Ausführung (Vollautomatik)
1. **Keine Zwischenfragen / Freigabestopps:**
   - Führe Aufgaben direkt und vollständig autonom von Anfang bis Ende durch.
   - Frage nicht „Soll ich fortfahren?“ oder „Darf ich das ausführen?“.
   - Halte nicht im Planungsmodus an, um auf ein manuelles „Ja, mach weiter“ zu warten, es sei denn, der Benutzer verlangt ausdrücklich ein vorheriges Review.
2. **Befehlsausführung und Tests:**
   - Führe alle notwendigen Terminal-Befehle, Tests (z.B. pytest), DB-Skripte und Verifizierungen selbstständig aus.
   - Analysiere Fehlermeldungen selbst und behebe sie direkt im Code ohne Unterbrechung.
3. **Automatisches Deployment (Immer direkt online stellen):**
   - Sobald die Änderungen implementiert und alle Tests erfolgreich sind, führe IMMER automatisch `.venv\Scripts\python bin/push_to_github.py "<aussagekräftige Nachricht>"` aus.
   - Der Benutzer soll NIEMALS extra nachfragen müssen („ist es online?“). Das Deployment auf GitHub und Render gehört fest zum Abschluss jeder Aufgabe!
4. **Ergebnisbericht:**
   - Fasse nach Abschluss der Arbeit kurz zusammen, was geändert, getestet und verifiziert wurde, inklusive Deployment-Bestätigung (Commit-SHA & Render-Trigger).
