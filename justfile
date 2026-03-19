[group('backend')]
backend-server:
    cd backend && uv run uvicorn app.app:app --reload
