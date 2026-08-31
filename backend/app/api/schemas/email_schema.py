from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class HealthResponseSchema(BaseSchema):
    status: str = Field(description="Current status of the backend.", examples=["ok"])


class EmailSuggestionRequestSchema(BaseSchema):
    email_content: str = Field(
        min_length=1,
        description="The full text of the email for which a suggestion should be generated.",
        examples=["Hello, can we move the meeting tomorrow to 2 PM? Best regards, Max"],
    )
