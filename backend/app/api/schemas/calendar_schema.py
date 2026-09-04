from datetime import datetime

from pydantic import Field

from app.api.schemas.base_schema import BaseSchema


class CalendarEventSchema(BaseSchema):
    id: str
    subject: str
    start: datetime
    end: datetime
    organizer: str | None = None
    is_organizer: bool = False


class CalendarEventListSchema(BaseSchema):
    events: list[CalendarEventSchema]


class TimeSlotSchema(BaseSchema):
    start: datetime
    end: datetime


class AvailabilitySchema(BaseSchema):
    slots: list[TimeSlotSchema]


class AuthStatusSchema(BaseSchema):
    authenticated: bool


class AuthUrlSchema(BaseSchema):
    auth_url: str


class AuthCallbackRequestSchema(BaseSchema):
    code: str


class MeetingTimeSuggestionSchema(BaseSchema):
    start: datetime
    end: datetime
    confidence: float


class MeetingTimeSuggestionListSchema(BaseSchema):
    suggestions: list[MeetingTimeSuggestionSchema]


class FindMeetingTimesRequestSchema(BaseSchema):
    attendees: list[str] = Field(
        min_length=1,
        description="Email addresses of attendees whose calendars should be considered.",
        examples=[["alice@contoso.com", "bob@contoso.com"]],
    )
    duration_minutes: int = Field(default=30, gt=0)
    lookahead_days: int = Field(default=7, gt=0)


class MeetingProposalSchema(BaseSchema):
    """A concrete, ready-to-create meeting suggestion for the Outlook compose form."""

    subject: str
    body: str = ""
    start: datetime
    end: datetime
    attendees: list[str] = Field(default_factory=list)


class IcsStatusSchema(BaseSchema):
    configured: bool


class SetSelfIcsUrlRequestSchema(BaseSchema):
    url: str = Field(
        description="Published Outlook calendar ICS feed URL (Outlook web -> "
        "Settings -> Calendar -> Shared calendars -> Publish a calendar).",
        examples=["https://outlook.office.com/owa/calendar/abc123/calendar.ics"],
    )


class KnownCalendarSchema(BaseSchema):
    email: str
    url: str


class KnownCalendarListSchema(BaseSchema):
    calendars: list[KnownCalendarSchema]


class SetKnownIcsUrlRequestSchema(BaseSchema):
    email: str
    url: str = Field(examples=["https://outlook.office.com/owa/calendar/def456/calendar.ics"])
