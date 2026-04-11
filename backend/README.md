# Backend

Minimale FastAPI-Basis fuer das Outlook-LLM-Projekt.

## Installation der Abhängigkeiten

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```bash
brew install just
```

## Projekt einrichten

```bash
cd backend
uv sync
```

## Anwendung starten

```bash
just backend-server
```

Die API ist danach unter `http://127.0.0.1:8000` erreichbar. Die Dokumentation findest du unter `http://127.0.0.1:8000/docs`.

## Universal RAG Client generieren

Der API-Client für den externen RAG-Service wird automatisch aus der `openapi.json` im Verzeichnis `app/clients/universal_rag/` generiert. Die Spezifikation stammt aus dem Repository [universal-rag-service](https://github.com/detti97/universal-rag-service).

Um den Client zu aktualisieren:

```bash
just generate-rag-client
```

Dies nutzt `openapi-python-client`, um den Code in `app/clients/universal_rag` zu überschreiben.

## Konfiguration

Die URL des externen RAG-Services kann über die Umgebungsvariable `RAG_SERVICE_URL` angepasst werden (Standard: `http://localhost:8000`).
