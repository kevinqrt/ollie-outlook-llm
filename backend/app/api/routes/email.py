from fastapi import APIRouter, HTTPException, status

from app.api.schemas.email import EmailAnalyzeResponse


router = APIRouter(prefix="/api/email")


@router.post(
    "/analyze",
    response_model=EmailAnalyzeResponse,
    summary="E-Mail analysieren",
    description="Analysiert E-Mail und Thread und beschreibt Summary, Classification und Drafts.",
    response_description="Summary, Classification und Drafts.",
    responses={501: {"description": "Noch nicht implementiert."}},
)
async def analyze_email(
) -> EmailAnalyzeResponse:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Email analysis orchestration is not implemented yet.",
    )
