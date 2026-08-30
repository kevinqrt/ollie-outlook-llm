from enum import StrEnum

from pydantic import Field

from app.api.schemas.email_schema import BaseSchema


class ActionCategory(StrEnum):
    ACTION = "action"
    INFO = "info"
    THANKS = "thanks"
    NEWSLETTER = "newsletter"


class ActionType(StrEnum):
    MEETING = "meeting"
    CONFIRM_LINK = "confirm_link"
    REPLY_NEEDED = "reply_needed"
    DOCUMENT = "document"
    OTHER = "other"


class MeetingDetailsSchema(BaseSchema):
    subject: str | None = Field(default=None, description="Proposed meeting subject.")
    proposed_time: str | None = Field(
        default=None, description="Proposed date/time as mentioned in the email."
    )
    attendees: list[str] = Field(
        default_factory=list, description="Attendee names or emails mentioned in the email."
    )


class EmailActionRequestSchema(BaseSchema):
    email_content: str = Field(
        min_length=1,
        description="Plain text body of the email to classify.",
        examples=["Können wir uns Donnerstag um 14 Uhr treffen? Viele Grüße, Herr Schmidt"],
    )
    email_links: list[str] = Field(
        default_factory=list,
        description="Links found in the email body, in order of appearance. "
        "The model references these by index instead of generating URLs itself.",
    )
    sender: str | None = Field(default=None, description="Display name or address of the sender.")
    subject: str | None = Field(default=None, description="Subject line of the email.")


class EmailActionResponseSchema(BaseSchema):
    category: ActionCategory = Field(description="Coarse triage bucket for the email.")
    action_type: ActionType | None = Field(
        default=None, description="Subtype of the required action, set only when category='action'."
    )
    action_summary: str | None = Field(
        default=None,
        description="One concrete, ready-to-act-on sentence describing the required action.",
        examples=["Termin mit Herrn Schmidt vereinbaren: Vorschlag Do 14 Uhr"],
    )
    link_index: int | None = Field(
        default=None,
        description="Index into the request's emailLinks pointing to the relevant link, "
        "set only when actionType='confirm_link'.",
    )
    meeting: MeetingDetailsSchema | None = Field(
        default=None, description="Structured meeting details, set only when actionType='meeting'."
    )
