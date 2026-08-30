from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.schemas.action_schema import EmailActionRequestSchema, EmailActionResponseSchema
from app.api.schemas.chat_schema import ChatRequestSchema, ChatResponseSchema
from app.api.schemas.email_schema import (
    EmailSuggestionRequestSchema,
    EmailSuggestionResponseSchema,
    ErrorResponseSchema,
    HealthResponseSchema,
)
from app.api.schemas.knowledge_schema import (
    KnowledgeDocumentListSchema,
    KnowledgeSearchResponseSchema,
    KnowledgeUploadResponseSchema,
)
from app.core.dependencies import LlmServiceDep, VectorStoreServiceDep
from app.services.llm_service import LlmServiceError

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
    "/chat",
    response_model=ChatResponseSchema,
    summary="Classical LLM chat",
    tags=["chat"],
    operation_id="postChat",
)
async def post_chat(
    payload: ChatRequestSchema,
    service: LlmServiceDep,
) -> ChatResponseSchema:
    """Provide a classical chat interface with history and RAG context."""
    try:
        reply = await service.chat(payload.messages)
        return ChatResponseSchema(reply=reply)
    except LlmServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


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
    service: LlmServiceDep,
) -> EmailSuggestionResponseSchema:
    """Generate a professional AI-driven reply suggestion for an incoming email."""
    try:
        reply_text = await service.generate_suggestion(payload.email_content)
        return EmailSuggestionResponseSchema(suggested_reply=reply_text)
    except LlmServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@api_router.post(
    "/email/action-summary",
    response_model=EmailActionResponseSchema,
    summary="Classify an email and extract an actionable summary",
    response_description="Category, action subtype and a directly executable action summary",
    responses={
        503: {"model": ErrorResponseSchema, "description": "RAG Service unavailable"},
        422: {"description": "Validation Error (e.g. empty email content)"},
    },
    tags=["email"],
    operation_id="getEmailActionSummary",
)
async def get_email_action_summary(
    payload: EmailActionRequestSchema,
    service: LlmServiceDep,
) -> EmailActionResponseSchema:
    """Classify an incoming email and extract a directly actionable summary."""
    try:
        return await service.extract_action(
            payload.email_content, payload.email_links, payload.sender, payload.subject
        )
    except LlmServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@api_router.post(
    "/knowledge/pdf",
    response_model=KnowledgeUploadResponseSchema,
    summary="Upload and index a PDF document",
    tags=["knowledge"],
)
async def upload_pdf(
    file: Annotated[UploadFile, File()],
    service: VectorStoreServiceDep,
) -> KnowledgeUploadResponseSchema:
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    content = await file.read()
    try:
        filename = await service.ingest_pdf(content, file.filename)
        return KnowledgeUploadResponseSchema(filename=filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@api_router.get(
    "/knowledge/search",
    response_model=KnowledgeSearchResponseSchema,
    summary="Search in the knowledge base",
    tags=["knowledge"],
)
async def search_knowledge(
    query: str,
    service: VectorStoreServiceDep,
) -> KnowledgeSearchResponseSchema:
    results = await service.search(query)
    return KnowledgeSearchResponseSchema(results=results)


@api_router.get(
    "/knowledge/documents",
    response_model=KnowledgeDocumentListSchema,
    summary="List all indexed documents",
    tags=["knowledge"],
)
async def list_documents(
    service: VectorStoreServiceDep,
) -> KnowledgeDocumentListSchema:
    docs = await service.list_documents()
    return KnowledgeDocumentListSchema(documents=docs)


@api_router.delete(
    "/knowledge/documents/{filename}",
    summary="Delete a document from the knowledge base",
    tags=["knowledge"],
)
async def delete_document(
    filename: str,
    service: VectorStoreServiceDep,
) -> dict[str, str]:
    success = await service.delete_document(filename)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"status": "deleted", "filename": filename}
