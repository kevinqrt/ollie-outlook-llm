from pydantic import BaseModel, ConfigDict, Field


class EmailAnalyzeResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "summary": "Kunde bittet um Bestaetigung der Vertragsdetails.",
                "classification": "request",
                "drafts": [
                    "Vielen Dank fuer Ihre Nachricht. Gern bestaetige ich Ihnen die Vertragsdetails ..."
                ],
            }
        }
    )

    summary: str = Field(..., description="Kurze Zusammenfassung.")
    classification: str = Field(..., description="Einfache Klassifikation.")
    drafts: list[str] = Field(default_factory=list, description="Antwortvorschlaege.")
