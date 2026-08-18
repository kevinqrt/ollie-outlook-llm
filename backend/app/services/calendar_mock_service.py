from datetime import datetime, timedelta

from app.api.schemas.calendar_schema import (
    CalendarEventSchema,
    MeetingTimeSuggestionSchema,
    TimeSlotSchema,
)
from app.services.graph_auth_service import GraphAuthService
from app.services.graph_calendar_service import GraphCalendarService, _compute_free_slots

# (offset from start of the requested window, duration, subject, organizer)
_MOCK_EVENT_TEMPLATE: list[tuple[timedelta, timedelta, str, str]] = [
    (timedelta(hours=10), timedelta(hours=1), "[MOCK] Sprint Planning", "Alice"),
    (timedelta(days=1, hours=14), timedelta(minutes=30), "[MOCK] 1:1 mit Team", "Bob"),
    (timedelta(days=2, hours=9), timedelta(minutes=45), "[MOCK] Projekt Review", "Charlie"),
    (timedelta(days=3, hours=15), timedelta(hours=1), "[MOCK] Kundentermin", "Dana"),
]

# Fake busy blocks representing "a colleague's calendar" - only used to make
# find_meeting_times() visibly differ from the solo get_availability() result.
_COLLEAGUE_BUSY_TEMPLATE: list[tuple[timedelta, timedelta]] = [
    (timedelta(hours=9), timedelta(minutes=30)),
    (timedelta(days=1, hours=9, minutes=30), timedelta(hours=1)),
]


def _generate_mock_events(
    window_start: datetime, window_end: datetime
) -> list[CalendarEventSchema]:
    """Fixed fake events anchored to the start of the requested window (usually 'today')."""
    base = window_start.replace(hour=0, minute=0, second=0, microsecond=0)
    events = []
    for index, (start_offset, duration, subject, organizer) in enumerate(_MOCK_EVENT_TEMPLATE):
        start = base + start_offset
        end = start + duration
        if window_start <= start < window_end:
            events.append(
                CalendarEventSchema(
                    id=f"mock-event-{index}",
                    subject=subject,
                    start=start,
                    end=end,
                    organizer=organizer,
                    is_organizer=index % 2 == 0,
                )
            )
    return events


def _generate_mock_colleague_busy(
    window_start: datetime, window_end: datetime
) -> list[CalendarEventSchema]:
    base = window_start.replace(hour=0, minute=0, second=0, microsecond=0)
    events = []
    for index, (start_offset, duration) in enumerate(_COLLEAGUE_BUSY_TEMPLATE):
        start = base + start_offset
        end = start + duration
        if window_start <= start < window_end:
            events.append(
                CalendarEventSchema(
                    id=f"mock-colleague-busy-{index}",
                    subject="[MOCK] Kollege beschaeftigt",
                    start=start,
                    end=end,
                    organizer=None,
                    is_organizer=False,
                )
            )
    return events


class MockGraphAuthService(GraphAuthService):
    """Pretends to always be authenticated, without ever touching MSAL/Graph."""

    def is_authenticated(self) -> bool:
        return True

    def get_valid_access_token(self) -> str:
        return "mock-access-token"


class MockCalendarService(GraphCalendarService):
    """Returns fixed fake calendar data instead of calling Microsoft Graph.

    Reuses the real free-slot computation so `SchedulingService`'s meeting-detection
    behaves believably in mock mode too.
    """

    async def list_events(self, start: datetime, end: datetime) -> list[CalendarEventSchema]:
        return _generate_mock_events(start, end)

    async def get_availability(
        self,
        start: datetime,
        end: datetime,
        duration_minutes: int = 30,
        daily_window: tuple[int, int] | None = None,
    ) -> list[TimeSlotSchema]:
        events = await self.list_events(start, end)
        return _compute_free_slots(events, start, end, duration_minutes, daily_window=daily_window)

    async def find_meeting_times(
        self,
        attendees: list[str],  # noqa: ARG002
        start: datetime,
        end: datetime,
        duration_minutes: int = 30,
        max_candidates: int = 5,
        daily_window: tuple[int, int] | None = None,
    ) -> list[MeetingTimeSuggestionSchema]:
        my_events = await self.list_events(start, end)
        colleague_busy = _generate_mock_colleague_busy(start, end)
        free_slots = _compute_free_slots(
            my_events + colleague_busy,
            start,
            end,
            duration_minutes,
            max_slots=max_candidates,
            daily_window=daily_window,
        )
        return [
            MeetingTimeSuggestionSchema(start=slot.start, end=slot.end, confidence=100.0)
            for slot in free_slots
        ]

    async def create_event(
        self,
        subject: str,
        start: datetime,
        end: datetime,
        attendees: list[str] | None = None,  # noqa: ARG002
        body: str = "",  # noqa: ARG002
    ) -> CalendarEventSchema:
        return CalendarEventSchema(
            id="mock-created-event",
            subject=f"[MOCK] {subject}",
            start=start,
            end=end,
            organizer="Du",
            is_organizer=True,
        )
