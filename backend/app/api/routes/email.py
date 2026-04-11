from fastapi import APIRouter

from app.api.schemas.email import EmailAnalyzeRequest, EmailAnalyzeResponse

router = APIRouter(prefix="/api/email")


@router.post(
    "/analyze",
    response_model=EmailAnalyzeResponse,
    summary="E-Mail analysieren",
    description=(
        "Liest einen Freitext mit E-Mail-Inhalt und optionalem Kontext ein "
        "und erzeugt einen Antwortvorschlag."
    ),
    response_description="Antwortvorschlag als E-Mail-Text.",
)
async def analyze_email(
    payload: EmailAnalyzeRequest,
) -> EmailAnalyzeResponse:
    pass
