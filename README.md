# Ollie

Monorepo mit separatem Python-Backend unter `backend/` und weiterem Frontend-/Plugin-Code auf Repo-Ebene.

## Pre-commit / prek

`prek` wird zentral als User-Tool installiert, nicht als eigenes Python-Projekt im Repo-Root.

```bash
uv tool install prek
```

## Backend

Das Python-Projekt lebt bewusst nur unter `backend/`:

```bash
cd backend
uv sync
```

Danach kann das Backend wie in `backend/README.md` beschrieben gestartet werden.
