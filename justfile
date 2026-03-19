[group('backend')]
backend-server:
    cd backend && uv run uvicorn app.app:app --reload
start-ollama:
    cd backend/scripts/start_ollama_docker.sh