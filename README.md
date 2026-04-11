# Ollie

Monorepo für den Outlook LLM Client.

## 🛠 Setup

### 1. Pre-commit / prek
`prek` wird zentral als User-Tool installiert:
```bash
uv tool install prek
```

### 2. Backend (FastAPI)
Das Python-Projekt befindet sich im Ordner `backend/`.
```bash
cd backend
uv sync
```

## 🚀 Anwendung starten

Das Backend kann über das zentrale `justfile` im Root-Verzeichnis gestartet werden:
```bash
just backend-server
```
Die API ist unter `http://127.0.0.1:8000` erreichbar. Dokumentation: `/docs`.

## 🤖 RAG Service API
Der API-Client für den Hochschul-Service wird automatisch generiert:
```bash
just generate-rag-client
```

## ⚙️ Konfiguration
Die Konfiguration erfolgt über eine `.env` Datei im **Projekt-Root**.
1. `cp .env.example .env`
2. Variablen anpassen (z.B. `RAG_SERVICE_URL`, `LLM_MODEL`).
