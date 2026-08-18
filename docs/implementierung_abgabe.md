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
*   **Testing Gate:** Wir nutzen **pytest-cov**, um die Testabdeckung im Backend sicherzustellen. Die CI-Pipeline bricht ab, wenn Tests fehlschlagen.

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
*   **Versionsschema:** [Semantic Versioning](https://semver.org/lang/de/) (Major.Feature.Bugfix).
*   **CI/CD-Pipeline:**
    *   Wird bei jedem Push und Pull-Request ausgelöst. Konfiguration dafür findet man unter `.github/workflows/ci.yml`.

---

## 6. Reviewprozesse

Änderungen am Code folgen einem strukturierten Review-Verfahren.

*   **Pull Requests (PR):** Kein Code gelangt direkt in den `main`-Branch. Jede Änderung erfordert einen PR.
*   **Branch Protection:** Der `main`-Branch ist geschützt. Änderungen erfordern einen Pull Request und den erfolgreichen Durchlauf aller CI-Checks (Linting & Tests), bevor sie gemergt werden können.
*   **Dokumentation:** Durchgeführte Reviews und Kommentare sind exemplarisch in den GitHub PRs dokumentiert, um den Entscheidungsprozess nachvollziehbar zu machen.

---

## 7. Übersicht Frameworks, Tools und Konfiguration

Diese Zusammenfassung bietet einen schnellen Überblick über die technische Basis und die Konfigurationsstruktur des Projekts.

### 7.1 Frameworks und Tools
| Bereich | Tool / Framework | Zweck |
| :--- | :--- | :--- |
| **Backend** | **FastAPI** | Web-Framework für die API |
| | **uv** | Package-Manager & Runtime |
| | **pytest** | Unit- & Integrationstests |
| | **pytest-cov** | Testabdeckungsmessung |
| | **Ruff** | Linter & Formatter |
| | **mypy** | Statische Typprüfung |
| **Frontend** | **React (v19)** | UI-Framework |
| | **Vite** | Build-Tool & Dev-Server |
| | **TypeScript** | Programmiersprache |
| | **Biome** | Linter & Formatter |
| | **Vitest** | Unit- & Integrationstests |
| | **@hey-api/openapi-ts**| SDK-Generierung |
| **Orchestrierung**| **Just** | Task-Runner (lokale Befehle) |

### 7.2 Konfigurationsstrategie
*   **Lokal:** Die Konfiguration erfolgt primär über das `justfile` (Task-Automatisierung) und `.pre-commit-config.yaml` (lokale Quality Gates). Umgebungsvariablen werden über eine `.env` Datei gesteuert.
*   **Zentral (CI/CD):** GitHub Actions (`.github/workflows/`) bilden die zentrale Instanz für die Qualitätssicherung. Die Workflows stellen sicher, dass alle Tests, Linting- und Type-Checks erfolgreich durchlaufen, bevor Code in den `main`-Branch integriert werden kann.
*   **Teststrategie:** Wir setzen auf eine Kombination aus funktionalen Tests und Exception-Handling-Prüfungen:
    *   **Backend:** Umfassende Testabdeckung der API-Endpunkte und Service-Layer (100% Coverage), inklusive Validierungsfehlern (422) und Ausfallszenarien externer Services (503).
    *   **Frontend:** Test der zentralen Geschäftslogik (Workflows) mit Vitest, wobei API-Interaktionen und Office-Integrationen zur Prüfung der Fehlerbehandlung gemockt werden.

---

## 8. Nicht-funktionale Anforderungen (NFA)

Neben den funktionalen Features wurde die Software auf zentrale Qualitätsattribute geprüft:

### 8.1 Performance (Leistung)
*   **Anforderung:** Die API darf nicht unbegrenzt blockieren, falls der KI-Service (RAG) verzögert antwortet.
*   **Prüfung:** Der `LlmService` nutzt einen konfigurierten Timeout von **60 Sekunden** für Anfragen an den RAG-Service. Dies wird automatisiert über `test_llm_service_timeout_handling` verifiziert.

### 8.2 Sicherheit (Security)
*   **Eingabevalidierung:** Durch den Einsatz von **Pydantic** werden alle API-Eingaben strikt validiert. Extrem große Payloads werden getestet (`test_input_validation_security`), um Denial-of-Service-Szenarien durch Speicherüberlastung zu vermeiden.
*   **Informationsfluss:** Die Fehlerbehandlung im API-Router (`router.py`) ist so implementiert, dass interne Fehler in generische `503 Service Unavailable` Antworten übersetzt werden. Dadurch wird verhindert, dass Stack-Traces oder interne Systemdetails (Informationsleckage) an den Client gelangen.
*   **Statische Analyse:** Tools wie **Ruff** prüfen den Code kontinuierlich auf sicherheitskritische Muster (z.B. Nutzung unsicherer Zufallszahlen oder hartkodierte Passwörter).

### 8.3 Zuverlässigkeit (Reliability)
*   **Health-Monitoring:** Ein dedizierter `/health`-Endpunkt ermöglicht ein kontinuierliches Monitoring der Systemverfügbarkeit. Die Korrektheit dieses Endpunkts wird durch automatisierte Tests (`test_reliability_health_check`) sichergestellt.
*   **Resilienz:** Das System erkennt den Ausfall des RAG-Services und reagiert mit einer kontrollierten Fehlermeldung, statt unkontrolliert abzustürzen. Dies wurde durch Mock-Tests simuliert und verifiziert.

---
