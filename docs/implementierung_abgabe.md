# Dokumentation der Implementierungsabgabe (SEP 2026)

Dieses Dokument beschreibt die Einhaltung der technischen Anforderungen und Standards für das Projekt **OLLIE (Outlook Local Language Inference Engine)** im Rahmen der Implementierungsphase.

**Datum:** 12.05.2026

---

## 1. Gewählter Code Style & Änderungen

Für OLLIE wurden etablierte Industriestandards gewählt, um eine hohe Codequalität und Lesbarkeit zu gewährleisten.

### Backend (Python)
*   **Standard:** [PEP 8](https://peps.python.org/pep-0008/) – Offizieller Python Style Guide.
*   **Tools:**
    *   **Ruff:** Einsatz als schneller Linter und Formatter zur Durchsetzung von PEP 8 und weiteren Best Practices (z. B. isort, pyupgrade).
    *   **Mypy:** Strikte statische Typprüfung zur Vermeidung von Laufzeitfehlern.
*   **Dokumentation:** Google Python Style Guide für Docstrings. Wir verzichten bewusst auf Generatoren wie z.B. MkDocs zugunsten der nativen **OpenAPI-Dokumentation (Swagger UI)** von FastAPI. Dies garantiert eine stets konsistente, interaktive API-Beschreibung direkt aus dem Code und vermeidet redundante Dokumentationsschichten.

### Frontend (React / TypeScript)
*   **Standard:** [Airbnb JavaScript Style Guide](https://github.com/airbnb/javascript) als konzeptionelle Basis für Code-Qualität.
*   **Umsetzung:** Die Durchsetzung erfolgt automatisiert über **Biome** (konfiguriert in `biome.json`), das moderne Regeln für Linting und Formatierung (z. B. Single Quotes, 2-Space Indentation) vorgibt und performanter als traditionelle ESLint-Setups ist.
*   **Qualitätsmerkmale:**
    *   **Funktionale Architektur:** Konsequente Nutzung von funktionalen Komponenten und React Hooks; Klassen-Komponenten sind im gesamten Projekt ausgeschlossen.
    *   **Typsicherheit:** Strikte Typisierung aller API-Interaktionen durch das automatisch generierte SDK. Manuelle `any`-Typen oder untypisierte API-Aufrufe werden zur Vermeidung von Laufzeitfehlern unterbunden.

---

## 2. Checkstyle & Codegenerator Konfigurationen

Die Einhaltung der Code Styles wird durch automatisierte Tools sowohl lokal als auch zentral sichergestellt. Ein zentraler Bestandteil unserer Strategie ist der Einsatz von **Pre-commit Hooks**, die sicherstellen, dass nur valider Code in das Repository gelangt.

### Lokale Qualitätssicherung (Pre-commit Hooks)
Wir nutzen das `pre-commit` Framework, um folgende Prüfungen vor jedem Commit automatisch auszuführen:
*   **Allgemein:** Entfernen von Trailing Whitespaces, Fixen von Dateieinden, Check von YAML/TOML-Dateien, Erkennung von Private Keys.
*   **Backend (Python):**
    *   **Ruff:** Automatisches Linting und Fixen von Stilfehlern.
    *   **Ruff-format:** Konsistente Formatierung des Backend-Codes.
    *   **Mypy:** Statische Typprüfung, um Laufzeitfehler im Backend zu minimieren.
*   **Frontend (TypeScript/React):**
    *   **Biome:** Wir setzen Biome als modernen All-in-One Linter und Formatter für das Frontend ein, um Performance und Konsistenz zu maximieren.

### Codegeneratoren
*   **OpenAPI-Frontend-Client:** Basierend auf der von FastAPI generierten Spezifikation aktualisiert das Frontend über `just sync-openapi` automatisch den TypeScript-Client (`src/api/generated`). Dies garantiert eine typsichere Kommunikation zwischen Frontend und Backend.
*   **RAG-Service-Client (Backend):** Für die Kommunikation zwischen dem OLLIE-Backend und dem [Universal RAG Service](https://github.com/detti97/universal-rag-service) wird der **openapi-python-client** eingesetzt. Über den Befehl `just generate-rag-client` wird der Python-Client im Verzeichnis `backend/packages/rag_service_api` basierend auf der `openapi.json` des RAG-Services generiert. Dies stellt sicher, dass auch die interne Kommunikation zwischen den Microservices strikt typisiert und konsistent bleibt.

---

## 3. Definierte Code Quality Gates & Plattform

Zur Sicherstellung der Qualität setzen wir auf automatisierte Prozesse innerhalb der GitHub-Infrastruktur, die als "Hard Gates" fungieren:

*   **Security Gate:** **GitHub Dependabot** überwacht kontinuierlich alle Abhängigkeiten auf bekannte Sicherheitslücken und meldet notwendige Updates sofort.
*   **Static Analysis Gate:** Die im Abschnitt 2 beschriebenen Tools (Ruff, Mypy, Biome) sind sowohl in die CI-Pipeline integriert als auch über die **[.pre-commit-config.yaml](../.pre-commit-config.yaml)** lokal konfiguriert. Commits werden nur akzeptiert, wenn alle Linter und Type-Checker fehlerfrei durchlaufen (lokale Vorprüfung).
*   **Testing Gate:** Wir nutzen **pytest-cov**, um die Testabdeckung zu messen.

---

## 4. Sourcecode-Dokumentation

Wir setzen konsequent auf **automatisierte Dokumentation** und **Self-Documenting Code**, um Redundanzen zu vermeiden und eine stets aktuelle Dokumentation zu garantieren.

*   **Backend API (Swagger UI):** Durch den Einsatz von **FastAPI** wird die API-Dokumentation (OpenAPI-Spezifikation) automatisch aus dem Code und den Pydantic-Modellen generiert. Die interaktive Dokumentation ist im laufenden Betrieb unter `/docs` erreichbar.
*   **Self-Documenting Code:** Durch strikte **Type-Hints** in Python und TypeScript sowie aussagekräftige Benennungen von Funktionen und Variablen ist die Logik des Quellcodes ohne zusätzliche manuelle Dokumentationsschichten nachvollziehbar.
*   **Fokus:** Auf zusätzliche statische Generatoren (wie MkDocs) wurde bewusst verzichtet, um die Konsistenz zwischen Code und Dokumentation zu maximieren und den Wartungsaufwand gering zu halten.

---

## 5. Versionskontrollsystem & CI/CD-Pipeline

Das Projekt wird professionell versioniert und durch automatisierte Workflows unterstützt.

*   **System:** Git (gehostet auf GitHub).
*   **Projekt-Management:** Nutzung des Issue Boards zur Verteilung von Aufgaben und Verfolgung des Fortschritts.
*   **Versionsschema:** [Semantic Versioning](https://semver.org/lang/de/) (Major.Feature.Bugfix).
*   **CI/CD-Pipeline:**
    *   Wird bei jedem Push und Pull-Request ausgelöst.
    *   **Schritte:** Setup Environment -> Linting (Ruff/Biome) -> Type-Check (Mypy/TSC) -> Testing & Coverage (Pytest/Vitest).

---

## 6. Reviewprozesse

Änderungen am Code folgen einem strikten Review-Verfahren.

*   **Pull Requests (PR):** Kein Code gelangt direkt in den `main`-Branch. Jede Änderung erfordert einen PR.
*   **Branch Protection:** Der `main`-Branch ist geschützt und erfordert mindestens ein "Approve" durch ein anderes Teammitglied nach einem Review.
*   **Dokumentation:** (Exemplarisch durchgeführte Reviews und Kommentare sind in den GitHub/GitLab PRs dokumentiert).

---

## 7. Überarbeitung der technischen Durchstiche

Initial erstellte Prototypen (Spikes) wurden für die finale Implementierung reflektiert und überarbeitet.

*   **Vom Prototyp zur Architektur:**
    *   Erste experimentelle Skripte zur Anbindung der AnythingLLM-API wurden in die formale Struktur des `LlmService` überführt.
    *   Die Trennung von Belangen (Separation of Concerns) wurde konsequent umgesetzt: Logik zur Kontext-Extraktion wurde aus der API-Schicht in dedizierte Services (`ContextExtractor`) ausgelagert.
    *   Fehlerbehandlung und Logging wurden von einfachen `print`-Statements auf robuste Python-Exception-Handling und Logging-Module umgestellt.
