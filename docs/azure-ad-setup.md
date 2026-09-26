# Azure AD Setup für die Outlook-Kalender-Integration

> **Nur zum Testen und noch keine Lust auf Azure Portal?** `CALENDAR_MOCK_MODE=true` in `.env` setzen und Backend neu starten — dann liefert die Kalender-Integration Fake-Daten ganz ohne Azure AD. Details im README unter "Ohne Azure AD testen". Dieses Dokument brauchst du erst, wenn du mit dem echten Outlook-Kalender testen willst.

Mit `CALENDAR_BACKEND=graph` greift OLLIE per Microsoft Graph auf deinen Outlook-Kalender und (nur lesend) auf dein Postfach zu:

- Die Termine der nächsten 14 Tage fließen in jede Chat-Nachricht als Kontext ein.
- Terminvorschläge lassen sich per Klick auf **„Im Kalender eintragen“** direkt anlegen. Sind Teilnehmer dabei, verschickt Outlook echte Einladungen.
- Im Chat kannst du nach Mails fragen, z. B. „Was hat Max mir wegen dem Projekt geschrieben?“ oder „Was ist heute reingekommen?“.
- Bei **Antwort generieren** bekommt Ollie frühere Mails aus demselben Verlauf mit.

Dafür braucht OLLIE eine eigene App-Registrierung in Microsoft Entra ID (Azure AD). Die Anleitung beschreibt den Weg für ein **privates Microsoft-Konto** (outlook.com / hotmail / live). Die Abweichungen für Arbeits- und Schulkonten stehen jeweils dabei.

## 1. Azure-Zugang

Unter [portal.azure.com](https://portal.azure.com) mit dem Microsoft-Konto anmelden, dessen Kalender OLLIE nutzen soll. Hat das private Konto noch kein Verzeichnis, legst du das kostenlose Azure-Konto an. Dabei entsteht automatisch ein „Default Directory“. App-Registrierungen kosten nichts.

## 2. App-Registrierung anlegen

1. **Microsoft Entra ID** → **App registrations** → **New registration**.
2. Name: z. B. `Ollie (privat)`.
3. Supported account types:
   - privates Konto: **Personal Microsoft accounts only**
   - Arbeits- oder Schulkonto: **Accounts in this organizational directory only (Single tenant)**
4. Redirect URI: Plattform **Web**, Wert:
   ```
   https://localhost:3000/auth-callback.html
   ```
5. **Register** klicken.

## 3. Werte notieren

Auf der Übersichtsseite der App-Registrierung:
- **Application (client) ID** → `GRAPH_CLIENT_ID`
- Nur bei Arbeits- oder Schulkonto: **Directory (tenant) ID** → `GRAPH_TENANT_ID`. Bei privaten Konten ist `GRAPH_TENANT_ID=consumers`.

## 4. Client Secret erzeugen

1. **Certificates & secrets** → **New client secret**.
2. Beliebige Beschreibung, Ablaufdatum nach Bedarf (z. B. 6 oder 12 Monate).
3. Den **Value** (nicht die Secret-ID!) direkt nach Erstellung kopieren — er ist danach nicht mehr einsehbar.
4. → `GRAPH_CLIENT_SECRET`

## 5. API-Permissions setzen

1. **API permissions** → **Add a permission** → **Microsoft Graph** → **Delegated permissions**.
2. Hinzufügen:
   - `Calendars.ReadWrite`
   - `Mail.Read`
   - `User.Read`
   - `offline_access` (für Token-Refresh, meist schon standardmäßig vorhanden)
3. Nur bei Arbeits- oder Schulkonto, falls die Organisation es verlangt: **Grant admin consent**. Bei privaten Konten stimmst du beim ersten Login selbst zu.

## 6. Werte in `.env` eintragen

```bash
CALENDAR_BACKEND=graph
GRAPH_TENANT_ID=consumers            # bzw. Directory (tenant) ID
GRAPH_CLIENT_ID=<Application (client) ID>
GRAPH_CLIENT_SECRET=<Client Secret Value>
GRAPH_REDIRECT_URI=https://localhost:3000/auth-callback.html
VITE_OUTLOOK_WEB_URL=https://outlook.live.com   # nur bei privaten Konten
```

Danach Backend und Frontend neu starten (`just dev`).

## 7. Verbindung herstellen

1. `just dev` starten, Add-in in Outlook im Web laden.
2. Im Taskpane den Tab **Chat** öffnen. In der Statusleiste steht „Outlook-Kalender nicht verbunden“. Auf **Verbinden** klicken.
3. Im Dialog mit dem Microsoft-Konto anmelden und die Berechtigungen bestätigen.
4. Danach zeigt die Statusleiste „📅 Outlook-Kalender verbunden“. Zum Testen:
   - „Was steht diese Woche an?“ → Ollie antwortet mit deinen echten Terminen.
   - „Such mir morgen Vormittag 30 Minuten für Sport“ → Vorschlag → **Im Kalender eintragen**.

## Mails: was Ollie liest und weitergibt

- Ollie darf Mails nur **lesen** (`Mail.Read`). Er kann nichts senden, löschen oder verschieben.
- Im Chat sucht Ollie nur dann im Postfach, wenn deine Nachricht nach Mails fragt, also Wörter wie „Mail“, „Nachricht“, „geschrieben“ oder „Posteingang“ enthält. Dann schaut ein kurzer LLM-Aufruf, wonach gesucht werden soll.
- An das LLM (RAG-Service bzw. DGX-Server) gehen nur die gefundenen Treffer: bis zu 8 Suchtreffer bzw. 15 neue Mails, jeweils Absender, Betreff, Datum und eine kurze Vorschau. Bei **Antwort generieren** sind es bis zu 6 Mails aus dem Verlauf, jede auf ca. 1500 Zeichen gekürzt.
- **Nach einem Update, das neue Berechtigungen anfordert** (z. B. `Mail.Read`), zeigt Ollie wieder „Outlook nicht verbunden“. Einmal auf **Verbinden** klicken und zustimmen, dann gilt die Anmeldung für alles.

## Hinweise

- Die Tokens (Access/Refresh) werden lokal in `backend/token_cache.json` gecacht (git-ignored). Die Verbindung übersteht also Neustarts. Diese Datei löschen, um die Verbindung zurückzusetzen.
- Dieses Setup ist bewusst für ein einzelnes Postfach ausgelegt (Entwicklungsprojekt), nicht für produktiven Multi-User-Betrieb.
- Die Kalenderübersicht im Chat wird 5 Minuten gecacht. Änderungen, die du direkt in Outlook machst, sieht Ollie also mit bis zu 5 Minuten Verzögerung. Termine, die Ollie selbst einträgt, sieht er sofort.
- **Verfügbarkeit anderer Personen** (`findMeetingTimes`) gibt es nur bei Arbeits- und Schulkonten, und zwar für Personen im selben Tenant. Bei privaten Konten schlägt Ollie Zeiten vor, in denen **du** frei bist. Ob die Teilnehmer Zeit haben, wird dann nicht geprüft.
