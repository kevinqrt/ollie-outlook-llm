from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.availability import CalendarServiceError
from app.services.ics_calendar_service import IcsCalendarService, IcsCalendarStore

SIMPLE_ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:event-1
DTSTART:20260810T090000Z
DTEND:20260810T093000Z
SUMMARY:Sprint Planning
ORGANIZER;CN=Alice:mailto:alice@example.com
END:VEVENT
END:VCALENDAR
"""

RECURRING_ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:event-recurring
DTSTART:20260810T090000Z
DTEND:20260810T093000Z
SUMMARY:Weekly Standup
RRULE:FREQ=WEEKLY;COUNT=4
END:VEVENT
END:VCALENDAR
"""

ALL_DAY_ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:event-allday
DTSTART;VALUE=DATE:20260812
DTEND;VALUE=DATE:20260813
SUMMARY:Ganztags-Termin
END:VEVENT
END:VCALENDAR
"""

MALFORMED_ICS = b"not a valid ics file"


@pytest.fixture
def store(tmp_path) -> IcsCalendarStore:
    return IcsCalendarStore(str(tmp_path / "ics_calendars.json"))


@pytest.fixture
def service(store: IcsCalendarStore) -> IcsCalendarService:
    return IcsCalendarService(store)


def _mock_response(content: bytes, status_ok: bool = True) -> MagicMock:
    response = MagicMock()
    response.content = content
    if status_ok:
        response.raise_for_status.return_value = None
    else:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )
    return response


class TestIcsCalendarStore:
    def test_self_url_roundtrip(self, store: IcsCalendarStore):
        assert store.get_self_url() is None
        store.set_self_url("https://outlook.office.com/owa/calendar/abc/calendar.ics")
        assert store.get_self_url() == "https://outlook.office.com/owa/calendar/abc/calendar.ics"

    def test_self_url_persists_to_disk(self, tmp_path):
        path = str(tmp_path / "ics_calendars.json")
        IcsCalendarStore(path).set_self_url("https://example.com/me.ics")

        reloaded = IcsCalendarStore(path)
        assert reloaded.get_self_url() == "https://example.com/me.ics"

    def test_known_url_roundtrip_case_insensitive(self, store: IcsCalendarStore):
        store.set_known_url("Alice@Example.com", "https://example.com/alice.ics")

        assert store.get_known_url("alice@example.com") == "https://example.com/alice.ics"
        assert store.list_known() == {"alice@example.com": "https://example.com/alice.ics"}

    def test_remove_known_url(self, store: IcsCalendarStore):
        store.set_known_url("alice@example.com", "https://example.com/alice.ics")

        assert store.remove_known_url("alice@example.com") is True
        assert store.get_known_url("alice@example.com") is None
        assert store.remove_known_url("alice@example.com") is False


class TestIcsCalendarServiceFetching:
    @pytest.mark.anyio
    async def test_list_events_raises_when_no_self_url(self, service: IcsCalendarService):
        with pytest.raises(CalendarServiceError, match="Kein eigener Kalender-Link"):
            await service.list_events(
                datetime(2026, 8, 1, tzinfo=UTC), datetime(2026, 9, 1, tzinfo=UTC)
            )

    @pytest.mark.anyio
    async def test_list_events_parses_simple_event(
        self, service: IcsCalendarService, store: IcsCalendarStore
    ):
        store.set_self_url("https://example.com/me.ics")
        service._client.get = AsyncMock(return_value=_mock_response(SIMPLE_ICS))

        events = await service.list_events(
            datetime(2026, 8, 1, tzinfo=UTC), datetime(2026, 9, 1, tzinfo=UTC)
        )

        assert len(events) == 1
        assert events[0].subject == "Sprint Planning"
        assert events[0].start == datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
        assert events[0].end == datetime(2026, 8, 10, 9, 30, tzinfo=UTC)
        assert events[0].organizer == "Alice"

    @pytest.mark.anyio
    async def test_list_events_expands_recurring_events(
        self, service: IcsCalendarService, store: IcsCalendarStore
    ):
        store.set_self_url("https://example.com/me.ics")
        service._client.get = AsyncMock(return_value=_mock_response(RECURRING_ICS))

        events = await service.list_events(
            datetime(2026, 8, 1, tzinfo=UTC), datetime(2026, 9, 1, tzinfo=UTC)
        )

        assert len(events) == 4
        starts = sorted(e.start for e in events)
        assert starts[0] == datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
        assert starts[1] == datetime(2026, 8, 17, 9, 0, tzinfo=UTC)

    @pytest.mark.anyio
    async def test_list_events_handles_all_day_events(
        self, service: IcsCalendarService, store: IcsCalendarStore
    ):
        store.set_self_url("https://example.com/me.ics")
        service._client.get = AsyncMock(return_value=_mock_response(ALL_DAY_ICS))

        events = await service.list_events(
            datetime(2026, 8, 1, tzinfo=UTC), datetime(2026, 9, 1, tzinfo=UTC)
        )

        assert len(events) == 1
        assert events[0].start == datetime(2026, 8, 12, 0, 0, tzinfo=UTC)
        assert events[0].end == datetime(2026, 8, 13, 0, 0, tzinfo=UTC)

    @pytest.mark.anyio
    async def test_list_events_raises_on_unreachable_url(
        self, service: IcsCalendarService, store: IcsCalendarStore
    ):
        store.set_self_url("https://example.com/me.ics")
        service._client.get = AsyncMock(side_effect=httpx.ConnectTimeout("timed out"))

        with pytest.raises(CalendarServiceError, match="nicht erreichbar"):
            await service.list_events(
                datetime(2026, 8, 1, tzinfo=UTC), datetime(2026, 9, 1, tzinfo=UTC)
            )

    @pytest.mark.anyio
    async def test_list_events_raises_on_malformed_ics(
        self, service: IcsCalendarService, store: IcsCalendarStore
    ):
        store.set_self_url("https://example.com/me.ics")
        service._client.get = AsyncMock(return_value=_mock_response(MALFORMED_ICS))

        with pytest.raises(CalendarServiceError, match="konnte nicht gelesen werden"):
            await service.list_events(
                datetime(2026, 8, 1, tzinfo=UTC), datetime(2026, 9, 1, tzinfo=UTC)
            )

    @pytest.mark.anyio
    async def test_validate_feed_passes_for_valid_url(self, service: IcsCalendarService):
        service._client.get = AsyncMock(return_value=_mock_response(SIMPLE_ICS))

        await service.validate_feed("https://example.com/me.ics")  # no raise

    @pytest.mark.anyio
    async def test_validate_feed_raises_for_bad_url(self, service: IcsCalendarService):
        service._client.get = AsyncMock(side_effect=httpx.ConnectTimeout("timed out"))

        with pytest.raises(CalendarServiceError):
            await service.validate_feed("https://example.com/broken.ics")


class TestIcsCalendarServiceAvailability:
    @pytest.mark.anyio
    async def test_get_availability_computes_free_slots_around_busy_event(
        self, service: IcsCalendarService, store: IcsCalendarStore
    ):
        store.set_self_url("https://example.com/me.ics")
        service._client.get = AsyncMock(return_value=_mock_response(SIMPLE_ICS))

        slots = await service.get_availability(
            datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
            datetime(2026, 8, 10, 10, 0, tzinfo=UTC),
            duration_minutes=30,
        )

        # Busy 09:00-09:30 -> free slots should be 08:00-08:30, 08:30-09:00, 09:30-10:00
        assert [(s.start.hour, s.start.minute) for s in slots] == [(8, 0), (8, 30), (9, 30)]

    @pytest.mark.anyio
    async def test_unknown_attendees_reports_missing_links(
        self, service: IcsCalendarService, store: IcsCalendarStore
    ):
        store.set_known_url("alice@example.com", "https://example.com/alice.ics")

        missing = service.unknown_attendees(["alice@example.com", "bob@example.com"])

        assert missing == ["bob@example.com"]

    @pytest.mark.anyio
    async def test_find_meeting_times_merges_self_and_known_attendee_feeds(
        self, service: IcsCalendarService, store: IcsCalendarStore
    ):
        store.set_self_url("https://example.com/me.ics")
        store.set_known_url("alice@example.com", "https://example.com/alice.ics")

        alice_busy = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:alice-busy
DTSTART:20260810T093000Z
DTEND:20260810T100000Z
SUMMARY:Alice Busy
END:VEVENT
END:VCALENDAR
"""

        async def fake_get(url: str) -> MagicMock:
            if url == "https://example.com/me.ics":
                return _mock_response(SIMPLE_ICS)
            return _mock_response(alice_busy)

        service._client.get = AsyncMock(side_effect=fake_get)

        suggestions = await service.find_meeting_times(
            ["alice@example.com"],
            datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
            datetime(2026, 8, 10, 11, 0, tzinfo=UTC),
            duration_minutes=30,
        )

        # Self busy 09:00-09:30, Alice busy 09:30-10:00 -> merged busy 09:00-10:00
        starts = [(s.start.hour, s.start.minute) for s in suggestions]
        assert (9, 0) not in starts
        assert (9, 30) not in starts
        assert (8, 0) in starts
        assert (10, 0) in starts
        assert all(s.confidence == 100.0 for s in suggestions)

    @pytest.mark.anyio
    async def test_find_meeting_times_raises_when_no_self_url(self, service: IcsCalendarService):
        with pytest.raises(CalendarServiceError, match="Kein eigener Kalender-Link"):
            await service.find_meeting_times(
                ["alice@example.com"],
                datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
                datetime(2026, 8, 10, 11, 0, tzinfo=UTC),
            )


class TestIcsCalendarServiceCreateEvent:
    @pytest.mark.anyio
    async def test_create_event_always_raises(self, service: IcsCalendarService):
        with pytest.raises(CalendarServiceError, match="nicht unterstuetzt"):
            await service.create_event(
                subject="Test",
                start=datetime(2026, 8, 10, 9, 0, tzinfo=UTC),
                end=datetime(2026, 8, 10, 9, 30, tzinfo=UTC),
            )
