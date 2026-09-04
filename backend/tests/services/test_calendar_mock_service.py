from datetime import UTC, datetime, timedelta

import pytest

from app.services.calendar_mock_service import MockCalendarService, MockGraphAuthService


@pytest.fixture
def mock_auth() -> MockGraphAuthService:
    return MockGraphAuthService()


@pytest.fixture
def mock_calendar(mock_auth: MockGraphAuthService) -> MockCalendarService:
    return MockCalendarService(mock_auth)


def test_mock_auth_is_always_authenticated(mock_auth: MockGraphAuthService) -> None:
    assert mock_auth.is_authenticated() is True


def test_mock_auth_returns_fake_token(mock_auth: MockGraphAuthService) -> None:
    assert mock_auth.get_valid_access_token() == "mock-access-token"


@pytest.mark.anyio
async def test_list_events_returns_events_within_window(mock_calendar: MockCalendarService) -> None:
    start = datetime(2026, 8, 3, 0, 0, tzinfo=UTC)
    end = start + timedelta(days=7)

    events = await mock_calendar.list_events(start, end)

    assert len(events) == 4
    assert all(event.subject.startswith("[MOCK]") for event in events)
    assert events[0].start.hour == 10


@pytest.mark.anyio
async def test_list_events_excludes_events_outside_window(
    mock_calendar: MockCalendarService,
) -> None:
    start = datetime(2026, 8, 3, 0, 0, tzinfo=UTC)
    end = start + timedelta(hours=12)

    events = await mock_calendar.list_events(start, end)

    assert len(events) == 1
    assert events[0].subject == "[MOCK] Sprint Planning"


@pytest.mark.anyio
async def test_get_availability_uses_real_free_slot_logic(
    mock_calendar: MockCalendarService,
) -> None:
    start = datetime(2026, 8, 3, 0, 0, tzinfo=UTC)
    end = start + timedelta(hours=12)

    slots = await mock_calendar.get_availability(start, end, duration_minutes=30)

    assert all(slot.end <= end for slot in slots)
    assert all(not (slot.start.hour == 10 and slot.start.minute == 0) for slot in slots)


@pytest.mark.anyio
async def test_find_meeting_times_excludes_colleague_busy_slot(
    mock_calendar: MockCalendarService,
) -> None:
    start = datetime(2026, 8, 3, 8, 0, tzinfo=UTC)
    end = start + timedelta(hours=4)

    solo_slots = await mock_calendar.get_availability(start, end, duration_minutes=30)
    group_slots = await mock_calendar.find_meeting_times(
        ["colleague@example.com"], start, end, duration_minutes=30
    )

    solo_starts = {(s.start.hour, s.start.minute) for s in solo_slots}
    group_starts = {(s.start.hour, s.start.minute) for s in group_slots}

    assert (9, 0) in solo_starts
    assert (9, 0) not in group_starts


@pytest.mark.anyio
async def test_find_meeting_times_returns_high_confidence(
    mock_calendar: MockCalendarService,
) -> None:
    start = datetime(2026, 8, 3, 0, 0, tzinfo=UTC)
    end = start + timedelta(hours=12)

    suggestions = await mock_calendar.find_meeting_times(
        ["colleague@example.com"], start, end, duration_minutes=30
    )

    assert all(s.confidence == 100.0 for s in suggestions)


@pytest.mark.anyio
async def test_get_availability_forwards_daily_window(
    mock_calendar: MockCalendarService,
) -> None:
    # daily_window=(8, 12) local == (6, 10) UTC in August (CEST).
    start = datetime(2026, 8, 3, 6, 0, tzinfo=UTC)
    end = start + timedelta(days=2)

    slots = await mock_calendar.get_availability(
        start, end, duration_minutes=30, daily_window=(8, 12)
    )

    assert slots
    assert all(6 <= s.start.hour < 10 for s in slots)


@pytest.mark.anyio
async def test_find_meeting_times_forwards_daily_window(
    mock_calendar: MockCalendarService,
) -> None:
    start = datetime(2026, 8, 3, 6, 0, tzinfo=UTC)
    end = start + timedelta(days=2)

    suggestions = await mock_calendar.find_meeting_times(
        ["colleague@example.com"], start, end, duration_minutes=30, daily_window=(8, 12)
    )

    assert suggestions
    assert all(6 <= s.start.hour < 10 for s in suggestions)


@pytest.mark.anyio
async def test_create_event_returns_fake_confirmation(mock_calendar: MockCalendarService) -> None:
    start = datetime(2026, 8, 3, 10, 0, tzinfo=UTC)
    end = datetime(2026, 8, 3, 11, 0, tzinfo=UTC)

    event = await mock_calendar.create_event(subject="Testtermin", start=start, end=end)

    assert event.id == "mock-created-event"
    assert event.subject == "[MOCK] Testtermin"
    assert event.start == start
    assert event.end == end
