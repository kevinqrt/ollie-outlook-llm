[group('backend')]
backend-server:
    cd backend && uv run uvicorn app.app:app --reload

generate-rag-client:
    cd backend/packages/rag_service_api && rm -rf rag_service_api/generated && uv run openapi-python-client generate --path openapi.json --output-path rag_service_api/generated --meta none --overwrite
