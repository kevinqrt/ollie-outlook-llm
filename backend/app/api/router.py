from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.schemas.email_schema import (
    EmailSuggestionRequestSchema,
    EmailSuggestionResponseSchema,
    ErrorResponseSchema,
    HealthResponseSchema,
)
from app.pipeline import run_pipeline
from app.services.llm_service import LlmService, LlmServiceError

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


@api_router.post(
    "/email/suggestion/stream",
    response_class=StreamingResponse,
    summary="Generate AI email suggestion with live pipeline progress",
    response_description="SSE stream of pipeline steps, ending in a done or error event",
    responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},
    tags=["email"],
    operation_id="streamEmailSuggestion",
)
async def stream_email_suggestion(
    payload: EmailSuggestionRequestSchema,
) -> StreamingResponse:
    """Generate a reply suggestion, streaming each pipeline step as it completes."""

    async def event_stream() -> AsyncIterator[str]:
        async for event in run_pipeline(payload.email_content):
            yield f"data: {event.model_dump_json(by_alias=True)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
