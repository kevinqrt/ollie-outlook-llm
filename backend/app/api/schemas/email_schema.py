from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class HealthResponseSchema(BaseSchema):
    status: str = Field(description="Der Status des Backends.")


class EmailSuggestionRequestSchema(BaseSchema):
    email_content: str = Field(
        min_length=1,
        description="Der Inhalt der zu analysierenden E-Mail.",
    )


class EmailSuggestionResponseSchema(BaseSchema):
    suggested_reply: str = Field(
        description="Der von der KI generierte Antwortvorschlag.",
    )
