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
    clarification_answer: str | None = Field(
        default=None,
        description="The user's answer to a previous 'clarification_needed' pipeline event, "
        "if any. Re-running with this set skips the clarification check and generates the "
        "reply directly, using the answer as extra context.",
    )


class ThreadSummaryRequestSchema(BaseSchema):
    thread_text: str = Field(
        min_length=1,
        description="The full text of the email thread to summarize, including quoted history.",
        examples=["Hello, can we move the meeting tomorrow to 2 PM?\n\n> On Mon, ..."],
    )


class ThreadSummaryResponseSchema(BaseSchema):
    summary: str = Field(
        description="A concise AI-generated summary of the email thread.",
        examples=["Max fragt, ob das Meeting morgen auf 14 Uhr verschoben werden kann."],
    )


class ReviseReplyRequestSchema(BaseSchema):
    email_content: str = Field(
        min_length=1, description="The text of the received email the reply answers."
    )
    previous_reply: str = Field(
        min_length=1, description="The reply that was suggested before and should be revised."
    )
    feedback: str = Field(
        min_length=1,
        description="What the user wants changed in this reply (e.g. 'kürzer').",
        examples=["kürzer und lockerer"],
    )


class ReviseReplyResponseSchema(BaseSchema):
    final_reply: str = Field(description="The revised reply text.")
