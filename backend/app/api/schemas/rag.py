from pydantic import BaseModel, ConfigDict, Field


class RagIngestRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": (
                    "Die regulaeren Lehrveranstaltungen finden montags bis freitags statt.\n"
                    "Das Sekretariat ist samstags geschlossen."
                ),
            }
        }
    )

    text: str = Field(
        ...,
        min_length=1,
        description="Freitext, der spaeter gechunkt und in den RAG-Store geschrieben werden soll.",
    )


class RagIngestResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "accepted",
                "ingested_count": 1,
            }
        }
    )

    status: str = Field(..., description="Status der Ingest-Anfrage.")


class RagRetrieveResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "snippets": ["Die Laufzeit betraegt 12 Monate."],
                "total_hits": 1,
            }
        }
    )

    snippets: list[str] = Field(default_factory=list, description="Gefundene Textstellen.")
    total_hits: int = Field(..., ge=0, description="Anzahl Treffer.")
