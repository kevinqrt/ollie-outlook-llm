# Azure AD Setup für die Outlook-Kalender-Integration

> **Nur zum Testen und noch keine Lust auf Azure Portal?** `CALENDAR_MOCK_MODE=true` in `.env` setzen und Backend neu starten — dann liefert die Kalender-Integration Fake-Daten ganz ohne Azure AD. Details im README unter "Ohne Azure AD testen". Dieses Dokument brauchst du erst, wenn du mit dem echten Outlook-Kalender testen willst.

OLLIE braucht eine eigene Azure AD App-Registrierung, um per Microsoft Graph auf den Outlook-Kalender zuzugreifen. Diese Schritte müssen einmalig von jedem Entwickler (oder einmalig fürs Team, mit gemeinsam genutzten Werten) im [Azure Portal](https://portal.azure.com) durchgeführt werden.

## 1. App-Registrierung anlegen

1. Azure Portal → **Microsoft Entra ID** → **App registrations** → **New registration**.
2. Name: z. B. `OLLIE Outlook Add-in (Dev)`.
3. Supported account types: **Accounts in this organizational directory only (Single tenant)**.
4. Redirect URI: Plattform **Web**, Wert:
   ```
   https://localhost:3000/auth-callback.html
   ```
5. **Register** klicken.

## 2. Werte notieren

Auf der Übersichtsseite der App-Registrierung:
- **Application (client) ID** → `GRAPH_CLIENT_ID`
- **Directory (tenant) ID** → `GRAPH_TENANT_ID`

## 3. Client Secret erzeugen

1. **Certificates & secrets** → **New client secret**.
2. Beliebige Beschreibung, Ablaufdatum nach Bedarf (z. B. 6 oder 12 Monate).
3. Den **Value** (nicht die Secret-ID!) direkt nach Erstellung kopieren — er ist danach nicht mehr einsehbar.
4. → `GRAPH_CLIENT_SECRET`

## 4. API-Permissions setzen

1. **API permissions** → **Add a permission** → **Microsoft Graph** → **Delegated permissions**.
2. Hinzufügen:
   - `Calendars.ReadWrite`
   - `User.Read`
   - `offline_access` (für Token-Refresh, meist schon standardmäßig vorhanden)
3. Falls die Organisation es verlangt: **Grant admin consent** klicken.

## 5. Werte in `.env` eintragen

```bash
GRAPH_TENANT_ID=<Directory (tenant) ID>
GRAPH_CLIENT_ID=<Application (client) ID>
GRAPH_CLIENT_SECRET=<Client Secret Value>
GRAPH_REDIRECT_URI=https://localhost:3000/auth-callback.html
```

Backend danach neu starten (`just backend` bzw. `just dev`).

## 6. Verbindung testen

1. `just dev` starten, Add-in in Outlook Web laden.
2. Im Taskpane den Tab **Chat** öffnen und in der Statusleiste oben auf **Verbinden** klicken.
3. Im sich öffnenden Dialog mit dem Microsoft-Konto anmelden, dessen Kalender du testen willst, und die angeforderten Berechtigungen bestätigen.
4. Nach erfolgreichem Login zeigt die Statusleiste "📅 Kalender verbunden". Eine Chat-Nachricht wie "Können wir uns morgen treffen?" sollte jetzt eine Zeit basierend auf deinem echten Kalender vorschlagen.

## Hinweise

- Die Tokens (Access/Refresh) werden lokal in `backend/token_cache.json` gecacht (git-ignored). Diese Datei löschen, um die Verbindung zurückzusetzen.
- Dieses Setup ist bewusst für ein einzelnes Test-Postfach ausgelegt (Entwicklungsprojekt), nicht für produktiven Multi-User-Betrieb.
- Die Terminvorschläge unter Berücksichtigung mehrerer Kalender (`findMeetingTimes`) brauchen **keine zusätzlichen** API-Permissions — dieselben Werte aus Schritt 4 reichen aus. Ob die Verfügbarkeit von Kollegen sichtbar ist, hängt von der Exchange-Free/Busy-Policy des Tenants ab (bei den meisten Standard-Konfigurationen ist das organisationsintern erlaubt). Funktioniert nur für Personen im selben Tenant, nicht für externe/private Kalender.
