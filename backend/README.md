# Backend

Minimale FastAPI-Basis fuer das Outlook-LLM-Projekt.

## Installation der Abhängigkeiten

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```bash
brew install just
```

Falls `uv` danach noch nicht gefunden wird, oeffne ein neues Terminal und versuche es erneut.

## Projekt einrichten

```bash
cd backend
uv sync
```

## Anwendung starten

Wenn du den Start als Kurzkommando haben willst, gibt es im Projekt-Root ein `justfile`.

```bash
just backend-server
```

Die API ist danach unter `http://127.0.0.1:8000` erreichbar. Dokumentation der Schnittstellen kann unter: `http://127.0.0.1:8000/docs` gefunden werden.

## Lokales LLM

Die E-Mail-Verarbeitung nutzt einen lokalen Ollama-Endpunkt.

Am einfachsten mit dem Script:

```bash
./backend/scripts/start_ollama_docker.sh
```
