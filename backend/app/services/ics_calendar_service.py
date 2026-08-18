import json
import logging
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import icalendar
import recurring_ical_events

from app.api.schemas.calendar_schema import (
    CalendarEventSchema,
    MeetingTimeSuggestionSchema,
    TimeSlotSchema,
)
from app.services.availability import CalendarServiceError, _compute_free_slots

logger = logging.getLogger(__name__)


def _to_utc_datetime(value: Any) -> datetime:
    """ICS DTSTART/DTEND can be a plain `date` (all-day event) or a

    timezone-aware `datetime` - normalizes both to a UTC-aware datetime.
    """
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    return datetime(value.year, value.month, value.day, tzinfo=UTC)


def _organizer_name(organizer: Any) -> str | None:
    if organizer is None:
        return None
    common_name = organizer.params.get("CN")
    if common_name:
        return str(common_name)
    return str(organizer).removeprefix("mailto:")


class IcsCalendarStore:
    """Persists the user's own calendar-feed URL and other people's known

    feed URLs in a small local JSON file (analogous to `token_cache.json`).
    """

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        if self._path.exists():
            return json.loads(self._path.read_text(encoding="utf-8"))
        return {"self": None, "known": {}}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def get_self_url(self) -> str | None:
        return self._data.get("self")

    def set_self_url(self, url: str) -> None:
        with self._lock:
            self._data["self"] = url
            self._save()

    def get_known_url(self, email: str) -> str | None:
        return self._data.get("known", {}).get(email.lower())

    def set_known_url(self, email: str, url: str) -> None:
        with self._lock:
            self._data.setdefault("known", {})[email.lower()] = url
            self._save()

    def remove_known_url(self, email: str) -> bool:
        with self._lock:
            removed = self._data.get("known", {}).pop(email.lower(), None)
            if removed is not None:
                self._save()
            return removed is not None

    def list_known(self) -> dict[str, str]:
        return dict(self._data.get("known", {}))


class IcsCalendarService:
    """Reads calendar availability from published Outlook ICS feeds instead of

    Microsoft Graph - no Azure AD app registration, OAuth, or admin consent
    needed. Each user publishes their own calendar once (Outlook web ->
    Settings -> Calendar -> Shared calendars -> "Publish a calendar") and
    pastes that link into OLLIE; other people's availability is looked up the
    same way, via saved "known" links keyed by email address.

    Known limitation, inherent to how Outlook implements calendar publishing
    (not something fetching more often can fix): the published feed can lag
    the real calendar by several hours (Microsoft's own guidance: ~3h typical,
    up to 24h, sometimes longer in practice) - a meeting booked minutes ago may
    not show up yet. Fine for week-ahead planning, not for minute-precision
    up-to-date checks.
    """

    def __init__(self, store: IcsCalendarStore) -> None:
        self.store = store
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _fetch_events(
        self, url: str, start: datetime, end: datetime
    ) -> list[CalendarEventSchema]:
        try:
            response = await self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise CalendarServiceError(f"Kalender-Link nicht erreichbar: {exc}") from exc

        try:
            calendar = icalendar.Calendar.from_ical(response.content)
            occurrences = recurring_ical_events.of(calendar).between(start, end)
        except Exception as exc:
            raise CalendarServiceError(f"Kalender-Feed konnte nicht gelesen werden: {exc}") from exc

        events: list[CalendarEventSchema] = []
        for index, occurrence in enumerate(occurrences):
            try:
                events.append(
                    CalendarEventSchema(
                        id=str(occurrence.get("UID") or f"ics-{index}"),
                        subject=str(occurrence.get("SUMMARY") or "(Kein Betreff)"),
                        start=_to_utc_datetime(occurrence["DTSTART"].dt),
                        end=_to_utc_datetime(occurrence["DTEND"].dt),
                        organizer=_organizer_name(occurrence.get("ORGANIZER")),
                        is_organizer=False,
                    )
                )
            except (KeyError, ValueError) as exc:
                logger.warning("Skipping malformed ICS event: %s", exc)
        return events

    async def validate_feed(self, url: str) -> None:
        """Raises `CalendarServiceError` if `url` isn't a reachable, parseable ICS feed."""
        now = datetime.now(UTC)
        await self._fetch_events(url, now, now + timedelta(days=1))

    async def list_events(self, start: datetime, end: datetime) -> list[CalendarEventSchema]:
        url = self.store.get_self_url()
        if not url:
            raise CalendarServiceError("Kein eigener Kalender-Link hinterlegt.")
        return await self._fetch_events(url, start, end)

    async def get_availability(
        self,
        start: datetime,
        end: datetime,
        duration_minutes: int = 30,
        daily_window: tuple[int, int] | None = None,
    ) -> list[TimeSlotSchema]:
        events = await self.list_events(start, end)
        return _compute_free_slots(events, start, end, duration_minutes, daily_window=daily_window)

    def unknown_attendees(self, attendees: list[str]) -> list[str]:
        """Which of `attendees` have no saved calendar link, so the caller can

        surface that gap back to the user instead of silently ignoring them.
        """
        return [a for a in attendees if not self.store.get_known_url(a)]

    async def find_meeting_times(
        self,
        attendees: list[str],
        start: datetime,
        end: datetime,
        duration_minutes: int = 30,
        max_candidates: int = 5,
        daily_window: tuple[int, int] | None = None,
    ) -> list[MeetingTimeSuggestionSchema]:
        """Merge the user's own feed with every known attendee's feed and

        compute free slots locally - the ICS-mode equivalent of Graph's
        server-side `findMeetingTimes`. Attendees with no saved link are
        simply not considered (see `unknown_attendees` to surface that).
        """
        self_url = self.store.get_self_url()
        if not self_url:
            raise CalendarServiceError("Kein eigener Kalender-Link hinterlegt.")

        busy = list(await self._fetch_events(self_url, start, end))
        for attendee in attendees:
            url = self.store.get_known_url(attendee)
            if url:
                busy.extend(await self._fetch_events(url, start, end))

        slots = _compute_free_slots(
            busy,
            start,
            end,
            duration_minutes,
            max_slots=max_candidates,
            daily_window=daily_window,
        )
        return [
            MeetingTimeSuggestionSchema(start=slot.start, end=slot.end, confidence=100.0)
            for slot in slots
        ]

    async def create_event(
        self,
        subject: str,  # noqa: ARG002
        start: datetime,  # noqa: ARG002
        end: datetime,  # noqa: ARG002
        attendees: list[str] | None = None,  # noqa: ARG002
        body: str = "",  # noqa: ARG002
    ) -> CalendarEventSchema:
        raise CalendarServiceError(
            "Direktes Anlegen von Terminen wird im ICS-Modus nicht unterstuetzt "
            "(veroeffentlichte Kalender-Feeds sind nur lesbar)."
        )
