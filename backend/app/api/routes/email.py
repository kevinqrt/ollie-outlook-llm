from fastapi import APIRouter, HTTPException, status
from starlette.concurrency import run_in_threadpool

from app.api.schemas.email import EmailAnalyzeRequest, EmailAnalyzeResponse
from app.services.email_analysis import OllamaError, analyze_email_request


router = APIRouter(prefix="/api/email")


@router.post(
    "/analyze",
    response_model=EmailAnalyzeResponse,
    summary="E-Mail analysieren",
    description="Liest einen Freitext mit E-Mail-Inhalt und optionalem Kontext ein und erzeugt einen Antwortvorschlag.",
    response_description="Antwortvorschlag als E-Mail-Text.",
)
async def analyze_email(
    payload: EmailAnalyzeRequest,
) -> EmailAnalyzeResponse:
    try:
        return await run_in_threadpool(analyze_email_request, payload)
    except OllamaError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
