from pydantic import BaseModel, Field


class EmailSuggestionRequestSchema(BaseModel):
    email_content: str = Field(
        min_length=1,
        description="Der Inhalt der zu analysierenden E-Mail.",
    )


class EmailSuggestionResponseSchema(BaseModel):
    suggested_reply: str = Field(
        description="Der von der KI generierte Antwortvorschlag.",
    )
