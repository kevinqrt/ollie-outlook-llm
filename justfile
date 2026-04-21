[group('backend')]
backend:
    cd backend && uv run uvicorn app.app:app --reload

generate-rag-client:
    cd backend/packages/rag_service_api && rm -rf rag_service_api/generated && uv run openapi-python-client generate --path openapi.json --output-path rag_service_api/generated --meta none --overwrite

[group('frontend')]
frontend:
    cd frontend && npm run dev

# Synchronize OpenAPI spec from backend to frontend and regenerate TypeScript SDK
sync-openapi:
    @echo "Extracting OpenAPI spec from backend..."
    cd backend && uv run python -c "import json; from app.app import app; print(json.dumps(app.openapi(), indent=2))" > ../frontend/src/api/openapi.json
    @echo "Generating TypeScript types..."
    cd frontend && npm run api:generate

[group('development')]
dev:
