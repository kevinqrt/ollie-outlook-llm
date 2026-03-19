from pydantic import BaseModel, ConfigDict, Field


class EmailAnalyzeRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": (
                    "Guten Tag Herr Mustermann, ist am Samstag Uni? Mit Freundlichen Grüßen Malte"
                ),
            }
        }
    )

    text: str = Field(
        ...,
        min_length=1,
        description="Freitext mit der eingehenden E-Mail und optionalem Kontext.",
    )


class EmailAnalyzeResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "Guten Tag,\n\nNein, regulaere Lehrveranstaltungen finden nur montags bis freitags statt.\n\nViele Gruesse",
            }
        }
    )

    text: str = Field(..., description="Der erzeugte Antwortvorschlag als E-Mail-Text.")
