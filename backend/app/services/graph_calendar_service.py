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
_EVENT_FIELDS = "id,subject,start,end,location,organizer,isOrganizer,isAllDay,attendees,webLink"
# Safety cap for calendarview paging (50 events per page).
_MAX_PAGES = 20

__all__ = ["CalendarServiceError", "GraphCalendarService"]


def _parse_event(item: dict[str, Any]) -> CalendarEventSchema:
    location = ((item.get("location") or {}).get("displayName") or "").strip()
    attendees = [
        address
        for attendee in item.get("attendees") or []
        if (address := (attendee.get("emailAddress") or {}).get("address"))
    ]
    return CalendarEventSchema(
        id=item["id"],
        subject=item.get("subject") or "(Kein Betreff)",
        start=datetime.fromisoformat(item["start"]["dateTime"]).replace(tzinfo=UTC),
        end=datetime.fromisoformat(item["end"]["dateTime"]).replace(tzinfo=UTC),
        organizer=(item.get("organizer") or {}).get("emailAddress", {}).get("name"),
        is_organizer=bool(item.get("isOrganizer")),
        location=location or None,
        is_all_day=bool(item.get("isAllDay")),
        attendees=attendees,
        web_link=item.get("webLink"),
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


def _is_unsupported_for_account(response: httpx.Response) -> bool:
    """Whether Graph rejected a request because the account type doesn't support it.

    Personal Microsoft accounts get a 4xx for tenant-only features like
    findMeetingTimes - in practice a 401 "UnknownError", even with a valid
    token. A genuinely broken login fails the own-calendar fallback too.
    """
    return 400 <= response.status_code < 500


class GraphCalendarService:
    """Wraps the Microsoft Graph Calendar REST API for the authenticated user."""

    def __init__(self, auth_service: GraphAuthService) -> None:
        self._auth_service = auth_service
        self._client = httpx.AsyncClient(base_url=GRAPH_BASE_URL, timeout=httpx.Timeout(30.0))
        # Flipped once Graph rejects findMeetingTimes for this account, so later
        # calls go straight to the own-calendar fallback.
        self._meeting_times_supported = True

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _auth_headers(self) -> dict[str, str]:
        try:
            token = self._auth_service.get_valid_access_token()
        except GraphAuthError as exc:
            raise CalendarServiceError(str(exc)) from exc
        return {"Authorization": f"Bearer {token}", "Prefer": 'outlook.timezone="UTC"'}

    async def list_events(self, start: datetime, end: datetime) -> list[CalendarEventSchema]:
        """List calendar events within [start, end), following Graph's paging links."""
        headers = await self._auth_headers()
        params: dict[str, str] | None = {
            "startDateTime": start.isoformat(),
            "endDateTime": end.isoformat(),
            "$orderby": "start/dateTime",
            "$top": "50",
            "$select": _EVENT_FIELDS,
        }
        url = "/me/calendarview"
        items: list[dict[str, Any]] = []
        try:
            for _ in range(_MAX_PAGES):
                response = await self._client.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
                items.extend(data.get("value", []))
                next_link = data.get("@odata.nextLink")
                if not next_link:
                    break
                # The next link already carries all query parameters.
                url, params = next_link, None
        except httpx.HTTPError as exc:
            logger.error("Graph list_events failed: %s", exc)
            raise CalendarServiceError(f"Failed to list calendar events: {exc}") from exc

        return [_parse_event(item) for item in items]

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
        if not self._meeting_times_supported:
            return await self._own_free_slots(
                start, end, duration_minutes, max_candidates, daily_window
            )
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
        except httpx.HTTPStatusError as exc:
            if not _is_unsupported_for_account(exc.response):
                logger.error("Graph find_meeting_times failed: %s", exc)
                raise CalendarServiceError(f"Failed to find meeting times: {exc}") from exc
            # Personal Microsoft accounts (outlook.com) don't support
            # findMeetingTimes - fall back to the user's own free slots.
            logger.info("findMeetingTimes not supported for this account, using own calendar.")
            self._meeting_times_supported = False
            return await self._own_free_slots(
                start, end, duration_minutes, max_candidates, daily_window
            )
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

    async def _own_free_slots(
        self,
        start: datetime,
        end: datetime,
        duration_minutes: int,
        max_candidates: int,
        daily_window: tuple[int, int] | None,
    ) -> list[MeetingTimeSuggestionSchema]:
        """Free slots in the user's own calendar only - attendees are not checked."""
        slots = await self.get_availability(start, end, duration_minutes, daily_window=daily_window)
        return [
            MeetingTimeSuggestionSchema(start=slot.start, end=slot.end, confidence=0.0)
            for slot in slots[:max_candidates]
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
