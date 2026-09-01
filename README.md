# OLLIE 🤖
**Outlook Local Language Inference Engine**

An intelligent AI assistant for Outlook generating context-aware email replies using RAG and LLMs.


## 🛠 Setup (Für Nutzer)
1. **Voraussetzung**
   - Sie müssen sich im Hochschulnetz befinden. (Vor Ort sein oder per VPN)

2. **Programme per Konsole Starten**
   - per CD Befehl in den Projektordner wechseln
   - Das Backend starten mit: cd backend; uv run uvicorn app.app:app --reload
   - Das Frontend starten mit: cd frontend; npm run dev

3. **Tunnel zur LLM Aufbauen**
   - ssh -L 8001:localhost:8000 ollie@131.173.64.53
   - Passwort eingeben

4. **Outlook starten und nutzen**

## 🛠 Setup (Für Entwickler)

1. **Tools installieren:**
   - [uv](https://docs.astral.sh/uv/) (Python Paketmanager)
   - [just](https://github.com/casey/just) (Task Runner)
   - Node.js & npm

2. **Installation & Initialisierung:**
   ```bash
   just setup
   ```

## 🚀 Start (Lokal)

1. **Anwendung starten:**
   ```bash
   just dev
   ```
   - Backend: `http://127.0.0.1:8000`
   - Frontend: `https://localhost:3000` (via Vite & mkcert)

## 🔄 Workflow

Bei Backend-Änderungen: `just sync-openapi`

## 🧪 Testing

*   **Outlook:** Manifest unter `manifest/manifest.xml` im Outlook Web-Client hochladen.
