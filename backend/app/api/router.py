from fastapi import APIRouter, HTTPException, status

from app.api.schemas.email_schema import EmailSuggestionRequestSchema, EmailSuggestionResponseSchema
from app.services.llm_service import LlmService, LlmServiceError

api_router = APIRouter()


@api_router.get("/health", summary="Health check", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@api_router.post(
    "/email/suggestion",
    response_model=EmailSuggestionResponseSchema,
    summary="Antwortvorschlag generieren",
    tags=["email"],
    description="Liest eine E-Mail ein und erzeugt einen passenden Antwortvorschlag.",
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
