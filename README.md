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

## 📡 Aufgabenradar / Graph-API-Setup

Der Tab "Aufgaben" scannt das Postfach per Microsoft Graph API und braucht dafür
eine eigene Azure-AD/Entra-ID-App-Registrierung mit Nested App Authentication (SSO):

1. In [portal.azure.com](https://portal.azure.com) → **Microsoft Entra ID → App registrations
   → New registration**.
   - Name: frei wählbar (z. B. "Ollie Aufgabenradar").
   - Supported account types: **Accounts in this organizational directory only
     (Single tenant)** — unauffälligste Option, am ehesten ohne Admin-Freigabe möglich.
   - Redirect URI: Plattform *Single-page application (SPA)*, Wert
     `brk-multihub://localhost:3000`.
2. **API permissions** → Add a permission → Microsoft Graph → Delegated permissions →
   `Mail.Read` → Add permissions. (Kein Klick auf "Grant admin consent" nötig/möglich
   ohne Admin-Rechte — der eigentliche Consent kommt beim ersten Login über Ollie.)
3. Auf der **Overview**-Seite der App: *Application (client) ID* → `.env` als
   `VITE_AAD_CLIENT_ID`. *Directory (tenant) ID* → `.env` als `VITE_AAD_TENANT_ID`.
4. In `manifest/manifest.xml` den Platzhalter `00000000-0000-0000-0000-000000000000`
   im `<WebApplicationInfo>`-Block durch dieselbe Client-ID ersetzen.
5. `just frontend` neu starten, damit die neuen `.env`-Werte geladen werden, dann im
   Aufgaben-Tab „Postfach scannen" klicken — beim ersten Mal öffnet sich ein
   Login-Popup mit dem Consent-Bildschirm. Steht dort **„Admin approval required"**
   statt der normalen Zustimmungsabfrage, ist das die Bestätigung des Consent-Risikos
   aus dem Konzept — dann Hochschul-IT einschalten oder auf Plan B wechseln.

Ohne diese Schritte zeigt der "Postfach scannen"-Button einen Login-Fehler.
Bei einem Uni-Tenant kann Schritt 2 Admin-Freigabe durch die Hochschul-IT
erfordern — das vorher klären.
