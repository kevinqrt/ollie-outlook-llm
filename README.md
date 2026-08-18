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

## 📅 Outlook-Kalender-Integration

Es gibt **keinen eigenen Kalender-Tab** — Kalenderwissen steckt direkt im Chat-Tab und im automatischen Antwortvorschlag ("E-Mail Assistent"-Tab).

Voraussetzung für echte Daten: Azure AD App-Registrierung (siehe [`docs/azure-ad-setup.md`](docs/azure-ad-setup.md)) und die zugehörigen `GRAPH_*`-Variablen in `.env`. Im Chat-Tab oben in der Statusleiste auf "Verbinden" klicken, um den Microsoft-Login-Dialog zu öffnen.

### Wie es funktioniert

- **Chat:** Schreibt man z. B. "Können wir uns morgen für 30 Minuten treffen?", erkennt Ollie die Terminanfrage, prüft die eigene Kalenderverfügbarkeit und nennt eine konkrete Zeit. Steht eine echte E-Mail-Adresse im Chattext (z. B. "...mit anna@firma.de"), wird stattdessen die Verfügbarkeit **aller genannten Personen** über Microsoft Graphs `findMeetingTimes` geprüft, sodass der vorgeschlagene Termin für alle passt.
- **E-Mail-Antwortvorschlag:** Dieselbe Logik greift, zusätzlich werden die To/Cc-Empfänger der geöffneten Mail automatisch als Teilnehmer berücksichtigt.
- **Termin direkt öffnen:** Erkennt Ollie einen konkreten Terminvorschlag, erscheint ein Button "📅 Termin im Kalender öffnen" — ein Klick öffnet das native Outlook-Termin-Fenster mit Betreff, Beschreibung, Zeit und Teilnehmern vorausgefüllt; es muss nur noch auf Senden/Speichern geklickt werden.

**Wichtige Einschränkung:** Die Mehrpersonen-Verfügbarkeit funktioniert nur für Personen im selben Microsoft-365-Unternehmen (Tenant). Für private/fremde Kalender (z. B. Gmail) hat Microsoft Graph grundsätzlich keine Einsicht — das ist eine Grenze der API, nicht der Implementierung.

### Ohne Azure AD testen (Mock-Modus)

Für einen schnellen lokalen Test ohne Azure-AD-App-Registrierung: `CALENDAR_MOCK_MODE=true` in `.env` setzen und Backend neu starten. Die Statusleiste im Chat-Tab zeigt dann sofort "verbunden" an, mit Fake-Kalenderdaten (Präfix `[MOCK]`) — ganz ohne Login-Dialog. Für den echten Betrieb wieder auf `false` setzen.

### MCP-Server

Der Kalenderzugriff steht zusätzlich als eigenständiger MCP-Server zur Verfügung (`backend/app/mcp_server.py`), der dieselbe authentifizierte Sitzung (Token-Cache-Datei) wie das Backend nutzt. Tools: `list_events`, `check_availability`, `find_meeting_times`, `create_event`. Dieser Server ist optional — das Add-in-Feature selbst spricht direkt mit dem FastAPI-Backend, nicht über MCP.

Starten:
```bash
just mcp-server
```

Registrierung in Claude Code (`.mcp.json` im Projektroot):
```json
{
  "mcpServers": {
    "ollie-calendar": {
      "command": "uv",
      "args": ["run", "python", "-m", "app.mcp_server"],
      "cwd": "backend"
    }
  }
}
```

Für Claude Desktop analog in dessen `claude_desktop_config.json` unter `mcpServers` eintragen.
