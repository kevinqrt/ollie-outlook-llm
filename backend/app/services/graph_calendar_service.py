import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.api.schemas.calendar_schema import (
    CalendarEventSchema,
    MeetingTimeSuggestionSchema,
    TimeSlotSchema,
)
from app.core.datetime_utils import LOCAL_TZ
from app.services.availability import (
    CalendarServiceError,
    _compute_free_slots,
    _round_up_to_quarter_hour,
)
from app.services.graph_auth_service import GraphAuthError, GraphAuthService

logger = logging.getLogger(__name__)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

__all__ = ["CalendarServiceError", "GraphCalendarService"]


def _parse_event(item: dict[str, Any]) -> CalendarEventSchema:
    return CalendarEventSchema(
        id=item["id"],
        subject=item.get("subject") or "(Kein Betreff)",
        start=datetime.fromisoformat(item["start"]["dateTime"]).replace(tzinfo=UTC),
        end=datetime.fromisoformat(item["end"]["dateTime"]).replace(tzinfo=UTC),
        organizer=(item.get("organizer") or {}).get("emailAddress", {}).get("name"),
        is_organizer=bool(item.get("isOrganizer")),
    )


def _daily_time_slots(
    start: datetime, end: datetime, daily_window: tuple[int, int]
) -> list[dict[str, Any]]:
    """Build one Graph timeSlot per local calendar day in [start, end), each

    bounded to `daily_window` (local hour-of-day) - used in findMeetingTimes'
    timeConstraint when a specific time-of-day was requested, since Graph has
    no native "same hour range on every day" primitive.
    """
    start_hour, end_hour = daily_window
    local_day = start.astimezone(LOCAL_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    slots: list[dict[str, Any]] = []
    while True:
        day_start = local_day.replace(hour=start_hour).astimezone(UTC)
        if day_start >= end:
            break
        day_end = local_day.replace(hour=end_hour).astimezone(UTC)
        slots.append(
            {
                "start": {"dateTime": day_start.isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": day_end.isoformat(), "timeZone": "UTC"},
            }
        )
        local_day += timedelta(days=1)
    return slots


class GraphCalendarService:
    """Wraps the Microsoft Graph Calendar REST API for the authenticated user."""

    def __init__(self, auth_service: GraphAuthService) -> None:
        self._auth_service = auth_service
        self._client = httpx.AsyncClient(base_url=GRAPH_BASE_URL, timeout=httpx.Timeout(30.0))

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _auth_headers(self) -> dict[str, str]:
        try:
            token = self._auth_service.get_valid_access_token()
        except GraphAuthError as exc:
            raise CalendarServiceError(str(exc)) from exc
        return {"Authorization": f"Bearer {token}", "Prefer": 'outlook.timezone="UTC"'}

    async def list_events(self, start: datetime, end: datetime) -> list[CalendarEventSchema]:
        """List calendar events within [start, end)."""
        headers = await self._auth_headers()
        params = {
            "startDateTime": start.isoformat(),
            "endDateTime": end.isoformat(),
            "$orderby": "start/dateTime",
            "$top": "50",
        }
        try:
            response = await self._client.get("/me/calendarview", params=params, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Graph list_events failed: %s", exc)
            raise CalendarServiceError(f"Failed to list calendar events: {exc}") from exc

        return [_parse_event(item) for item in response.json().get("value", [])]

    async def get_availability(
        self,
        start: datetime,
        end: datetime,
        duration_minutes: int = 30,
        daily_window: tuple[int, int] | None = None,
    ) -> list[TimeSlotSchema]:
        """Compute free time slots of `duration_minutes` within [start, end).

        Derived from the user's own busy events rather than the Graph
        `getSchedule` endpoint, since that avoids needing the user's UPN.
        `daily_window` (local hour-of-day bounds, e.g. (8, 12) for "vormittags")
        restricts suggestions to that time of day on each day - see
        `_compute_free_slots`.
        """
        events = await self.list_events(start, end)
        return _compute_free_slots(events, start, end, duration_minutes, daily_window=daily_window)

    async def find_meeting_times(
        self,
        attendees: list[str],
        start: datetime,
        end: datetime,
        duration_minutes: int = 30,
        max_candidates: int = 5,
        daily_window: tuple[int, int] | None = None,
    ) -> list[MeetingTimeSuggestionSchema]:
        """Ask Graph for meeting slots where all `attendees` (plus the user) are free.

        Uses `minimumAttendeePercentage: 100` so Graph only returns slots where
        every requested attendee is actually available, instead of us having to
        merge free/busy data ourselves. `daily_window` (local hour-of-day bounds,
        e.g. (8, 12) for "vormittags") restricts suggestions to that time of day
        on each day, via one Graph timeSlot per calendar day (Graph has no native
        "same hour range every day" primitive) - `activityDomain: "unrestricted"`
        is set in that case so Graph's own default work-hours filter doesn't
        additionally intersect with our explicit, already-correct time slots.
        """
        headers = await self._auth_headers()
        rounded_start = _round_up_to_quarter_hour(start)
        if daily_window is not None:
            time_constraint: dict[str, Any] = {
                "activityDomain": "unrestricted",
                "timeSlots": _daily_time_slots(rounded_start, end, daily_window),
            }
        else:
            time_constraint = {
                "timeSlots": [
                    {
                        "start": {"dateTime": rounded_start.isoformat(), "timeZone": "UTC"},
                        "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
                    }
                ]
            }
        payload = {
            "attendees": [
                {"emailAddress": {"address": address}, "type": "required"} for address in attendees
            ],
            "timeConstraint": time_constraint,
            "meetingDuration": f"PT{duration_minutes}M",
            "maxCandidates": max_candidates,
            "minimumAttendeePercentage": 100.0,
        }
        try:
            response = await self._client.post(
                "/me/findMeetingTimes", json=payload, headers=headers
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Graph find_meeting_times failed: %s", exc)
            raise CalendarServiceError(f"Failed to find meeting times: {exc}") from exc

        return [
            MeetingTimeSuggestionSchema(
                start=datetime.fromisoformat(item["meetingTimeSlot"]["start"]["dateTime"]).replace(
                    tzinfo=UTC
                ),
                end=datetime.fromisoformat(item["meetingTimeSlot"]["end"]["dateTime"]).replace(
                    tzinfo=UTC
                ),
                confidence=float(item.get("confidence", 0.0)),
            )
            for item in response.json().get("meetingTimeSuggestions", [])
        ]

    async def create_event(
        self,
        subject: str,
        start: datetime,
        end: datetime,
        attendees: list[str] | None = None,
        body: str = "",
    ) -> CalendarEventSchema:
        headers = await self._auth_headers()
        payload = {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
            "attendees": [
                {"emailAddress": {"address": address}, "type": "required"}
                for address in (attendees or [])
            ],
        }
        try:
            response = await self._client.post("/me/events", json=payload, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Graph create_event failed: %s", exc)
            raise CalendarServiceError(f"Failed to create calendar event: {exc}") from exc

        return _parse_event(response.json())
