import shutil
import tempfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, status, UploadFile, File

from app.api.schemas.email_schema import (
    EmailSuggestionRequestSchema,
    EmailSuggestionResponseSchema,
    ErrorResponseSchema,
    HealthResponseSchema,
)
from app.api.schemas.knowledge_schema import (
    SearchRequest,
    SearchResult,
    DocumentListResponse,
    GenericResponse
)
from app.services.llm_service import LlmService, LlmServiceError
from app.services.vector_store_service import vector_store_service

api_router = APIRouter()


@api_router.get(
    "/health",
    response_model=HealthResponseSchema,
    summary="Check service availability",
    tags=["health"],
    operation_id="getHealth",
)
async def health_check() -> HealthResponseSchema:
    """Returns 'ok' status if the API service is running correctly."""
    return HealthResponseSchema(status="ok")


@api_router.post(
    "/email/suggestion",
    response_model=EmailSuggestionResponseSchema,
    summary="Generate AI email suggestion",
    response_description="The successfully generated answer suggestion",
    responses={
        503: {"model": ErrorResponseSchema, "description": "RAG Service unavailable"},
        422: {"description": "Validation Error (e.g. empty email content)"},
    },
    tags=["email"],
    operation_id="getEmailSuggestion",
)
async def get_email_suggestion(
    payload: EmailSuggestionRequestSchema,
) -> EmailSuggestionResponseSchema:
    """Generate a professional AI-driven reply suggestion for an incoming email."""
    service = LlmService()
    try:
        reply_text = await service.generate_suggestion(payload.email_content)
        return EmailSuggestionResponseSchema(suggested_reply=reply_text)
    except LlmServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


# --- Knowledge Base Endpunkte ---

@api_router.post(
    "/knowledge/pdf",
    response_model=GenericResponse,
    summary="PDF hochladen",
    tags=["knowledge"],
    operation_id="uploadPdf",
)
async def upload_pdf(file: UploadFile = File(...)) -> GenericResponse:
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Nur PDF-Dateien sind erlaubt.")

    # Temporäre Datei erstellen
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        # Den Originalnamen beibehalten für die Metadaten
        # Da ingest_pdf Path(file_path).name nutzt, benennen wir die Datei ggf. um oder
        # wir passen ingest_pdf an. Hier: Wir kopieren es in einen Namen der passt.
        final_path = Path(tmp_path).parent / file.filename
        shutil.move(tmp_path, final_path)
        
        vector_store_service.ingest_pdf(str(final_path))
        
        # Cleanup
        if final_path.exists():
            final_path.unlink()
            
        return GenericResponse(message=f"Datei '{file.filename}' erfolgreich verarbeitet.")
    except Exception as e:
        if Path(tmp_path).exists(): Path(tmp_path).unlink()
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get(
    "/knowledge/search",
    response_model=List[SearchResult],
    summary="Wissensbasis durchsuchen",
    tags=["knowledge"],
    operation_id="searchKnowledge",
)
async def search_knowledge(query: str, k: int = 4) -> List[SearchResult]:
    results = vector_store_service.search(query, k=k)
    return [
        SearchResult(content=doc.page_content, metadata=doc.metadata)
        for doc in results
    ]


@api_router.get(
    "/knowledge/documents",
    response_model=DocumentListResponse,
    summary="Alle Dokumente auflisten",
    tags=["knowledge"],
    operation_id="listDocuments",
)
async def list_documents() -> DocumentListResponse:
    docs = vector_store_service.list_documents()
    return DocumentListResponse(documents=docs)


@api_router.delete(
    "/knowledge/documents/{doc_name}",
    response_model=GenericResponse,
    summary="Dokument löschen",
    tags=["knowledge"],
    operation_id="deleteDocument",
)
async def delete_document(doc_name: str) -> GenericResponse:
    success = vector_store_service.delete_document(doc_name)
    if not success:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    return GenericResponse(message=f"Dokument '{doc_name}' gelöscht.")
