# OLLIE 🤖
**Outlook Local Language Inference Engine**

An intelligent AI assistant for Outlook generating context-aware email replies using RAG and LLMs.

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
