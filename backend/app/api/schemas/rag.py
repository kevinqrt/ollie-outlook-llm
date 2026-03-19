from pydantic import BaseModel, ConfigDict, Field


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
