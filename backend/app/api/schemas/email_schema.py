from pydantic import Field

from app.api.schemas.base_schema import BaseSchema


class HealthResponseSchema(BaseSchema):
    status: str = Field(description="Current status of the backend.", examples=["ok"])


class EmailSuggestionRequestSchema(BaseSchema):
    email_content: str = Field(
        min_length=1,
        description="The full text of the email for which a suggestion should be generated.",
        examples=["Hello, can we move the meeting tomorrow to 2 PM? Best regards, Max"],
    )
    attendees: list[str] = Field(
        default_factory=list,
        description="Email addresses of the other recipients (To/Cc), used to check "
        "everyone's calendar availability for meeting-time suggestions.",
        examples=[["alice@contoso.com"]],
    )
