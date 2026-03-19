from fastapi import APIRouter, HTTPException, status

from app.api.schemas.rag import RagRetrieveResponse


router = APIRouter(prefix="/api/rag")


@router.post(
    "/retrieve",
    response_model=RagRetrieveResponse,
    summary="RAG-Kontext abrufen",
    description="Liefert passende Textstellen aus der Wissensbasis fuer RAG.",
    response_description="Gefundene Textstellen.",
    responses={501: {"description": "Noch nicht implementiert."}},
)
async def retrieve_rag_context(
) -> RagRetrieveResponse:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="RAG retrieval is not implemented yet.",
    )
