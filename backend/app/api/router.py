from fastapi import APIRouter, HTTPException, status

from app.api.schemas.email_schema import (
    EmailSuggestionRequestSchema,
    EmailSuggestionResponseSchema,
    HealthResponseSchema,
)
from app.services.llm_service import LlmService, LlmServiceError

api_router = APIRouter()


@api_router.get(
    "/health",
    response_model=HealthResponseSchema,
    summary="Health check",
    tags=["health"],
    operation_id="getHealth",
)
async def health_check() -> HealthResponseSchema:
    return HealthResponseSchema(status="ok")


@api_router.post(
    "/email/suggestion",
    response_model=EmailSuggestionResponseSchema,
    summary="Antwortvorschlag generieren",
    tags=["email"],
    description="Liest eine E-Mail ein und erzeugt einen passenden Antwortvorschlag.",
    operation_id="getEmailSuggestion",
)
async def get_email_suggestion(
    payload: EmailSuggestionRequestSchema,
) -> EmailSuggestionResponseSchema:
    service = LlmService()
    try:
        reply_text = await service.generate_suggestion(payload.email_content)
        return EmailSuggestionResponseSchema(suggested_reply=reply_text)
    except LlmServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
