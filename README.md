# Ollie 🤖

Outlook KI-Assistent. Backend: FastAPI | Frontend: React (Office Add-in).

## 🛠 Setup (Ersteinrichtung)

1. **Tools installieren:**
   - [uv](https://docs.astral.sh/uv/) (Python Paketmanager)
   - [just](https://github.com/casey/just) (Task Runner)
   - Node.js & npm

2. **Installation & Initialisierung:**
   ```bash
   just setup
   ```
   *Dieser Befehl installiert alle Python- und NPM-Abhängigkeiten und generiert das initiale SDK.*

## 🚀 Start

1. **Anwendung starten:**
   ```bash
   just dev
   ```
   - Backend: `http://127.0.0.1:8000`
   - Frontend: `https://localhost:3000`

## 🔄 Workflow

Bei Backend-Änderungen (Endpunkte/Schemas):
```bash
just sync-openapi
```
Dies aktualisiert das SDK in `src/api/generated` für das Frontend.

## 🧪 Testing

*   **Browser:** Microsoft Edge.
*   **Outlook:** Manifest unter `manifest/manifest.xml` im Outlook Web-Client hochladen.
