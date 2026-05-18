# OLLIE 🤖
**Outlook Local Language Inference Engine**

An intelligent AI assistant for Outlook generating context-aware email replies using RAG and LLMs.

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

## Desktop Host (Windows Dev)

Lokaler Start des gemeinsamen HTTPS-Hosts:

```powershell
.\start-ollie-dev.bat
```

Dabei passiert:

1. Das Frontend wird nach `frontend/dist` gebaut.
2. Ein lokales `localhost`-Zertifikat wird erzeugt und in `.env` eingetragen.
3. Ein `customtkinter`-Fenster startet den gemeinsamen Host:
   - Frontend unter `/`
   - API unter `/api`
   - HTTPS auf `https://localhost:8000`

## Windows Build

Die erste echte Windows-`.exe` wird mit PyInstaller gebaut:

```powershell
.\build-desktop-windows.bat
```

Das Ergebnis liegt danach unter:

```text
backend\dist\OllieDesktopHost.exe
```

Die gebaute App liest gebündelte Ressourcen aus dem Bundle und speichert lokale Konfiguration sowie Zertifikate neben der `.exe`.
