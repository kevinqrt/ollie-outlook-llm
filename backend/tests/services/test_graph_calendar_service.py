from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.graph_auth_service import GraphAuthError, GraphAuthService
from app.services.graph_calendar_service import CalendarServiceError, GraphCalendarService

RAW_EVENT = {
    "id": "event-1",
    "subject": "Sprint Planning",
    "start": {"dateTime": "2026-08-03T10:00:00.0000000", "timeZone": "UTC"},
    "end": {"dateTime": "2026-08-03T11:00:00.0000000", "timeZone": "UTC"},
    "organizer": {"emailAddress": {"name": "Alice", "address": "alice@example.com"}},
    "isOrganizer": True,
}


@pytest.fixture
def mock_auth() -> MagicMock:
    auth = MagicMock(spec=GraphAuthService)
    auth.get_valid_access_token.return_value = "test-access-token"
    return auth


@pytest.fixture
def calendar_service(mock_auth: MagicMock) -> GraphCalendarService:
    return GraphCalendarService(mock_auth)


@pytest.mark.anyio
async def test_list_events_parses_response(calendar_service, mock_auth):
    mock_response = MagicMock()
    mock_response.json.return_value = {"value": [RAW_EVENT]}
    mock_response.raise_for_status.return_value = None
    calendar_service._client.get = AsyncMock(return_value=mock_response)

    events = await calendar_service.list_events(
        datetime(2026, 8, 3, tzinfo=UTC), datetime(2026, 8, 4, tzinfo=UTC)
    )

    assert len(events) == 1
    assert events[0].id == "event-1"
    assert events[0].subject == "Sprint Planning"
    assert events[0].organizer == "Alice"
    assert events[0].is_organizer is True
    mock_auth.get_valid_access_token.assert_called_once()


@pytest.mark.anyio
async def test_list_events_missing_subject_uses_placeholder(calendar_service):
    raw_event = {**RAW_EVENT, "subject": None}
    mock_response = MagicMock()
    mock_response.json.return_value = {"value": [raw_event]}
    mock_response.raise_for_status.return_value = None
    calendar_service._client.get = AsyncMock(return_value=mock_response)

    events = await calendar_service.list_events(
        datetime(2026, 8, 3, tzinfo=UTC), datetime(2026, 8, 4, tzinfo=UTC)
    )

    assert events[0].subject == "(Kein Betreff)"


@pytest.mark.anyio
async def test_list_events_auth_failure_raises_calendar_error(mock_auth):
    mock_auth.get_valid_access_token.side_effect = GraphAuthError("Not authenticated.")
    service = GraphCalendarService(mock_auth)

    with pytest.raises(CalendarServiceError, match="Not authenticated"):
        await service.list_events(
            datetime(2026, 8, 3, tzinfo=UTC), datetime(2026, 8, 4, tzinfo=UTC)
        )


@pytest.mark.anyio
async def test_list_events_http_error_raises_calendar_error(calendar_service):
    calendar_service._client.get = AsyncMock(side_effect=httpx.ConnectTimeout("timed out"))

    with pytest.raises(CalendarServiceError, match="Failed to list calendar events"):
        await calendar_service.list_events(
            datetime(2026, 8, 3, tzinfo=UTC), datetime(2026, 8, 4, tzinfo=UTC)
        )


@pytest.mark.anyio
async def test_get_availability_forwards_daily_window(calendar_service):
    mock_response = MagicMock()
    mock_response.json.return_value = {"value": []}
    mock_response.raise_for_status.return_value = None
    calendar_service._client.get = AsyncMock(return_value=mock_response)

    start = datetime(2026, 8, 3, 22, 0, tzinfo=UTC)  # 00:00 local Aug 4
    end = start + timedelta(hours=10)

    slots = await calendar_service.get_availability(
        start, end, duration_minutes=30, daily_window=(8, 12)
    )

    assert slots
    assert 6 <= slots[0].start.hour < 10  # 08:00-12:00 local == 06:00-10:00 UTC


@pytest.mark.anyio
async def test_get_availability_rounds_unaligned_window_start(calendar_service):
    mock_response = MagicMock()
    mock_response.json.return_value = {"value": []}
    mock_response.raise_for_status.return_value = None
    calendar_service._client.get = AsyncMock(return_value=mock_response)

    # 16:23:07 must not produce a slot starting at that exact odd moment.
    window_start = datetime(2026, 8, 3, 16, 23, 7, tzinfo=UTC)
    window_end = datetime(2026, 8, 3, 18, 0, tzinfo=UTC)

    slots = await calendar_service.get_availability(window_start, window_end, duration_minutes=30)

    assert [(s.start.hour, s.start.minute, s.start.second) for s in slots] == [
        (16, 30, 0),
        (17, 0, 0),
        (17, 30, 0),
    ]


@pytest.mark.anyio
async def test_get_availability_returns_free_slots_around_busy_event(calendar_service):
    mock_response = MagicMock()
    mock_response.json.return_value = {"value": [RAW_EVENT]}
    mock_response.raise_for_status.return_value = None
    calendar_service._client.get = AsyncMock(return_value=mock_response)

    window_start = datetime(2026, 8, 3, 9, 0, tzinfo=UTC)
    window_end = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)

    slots = await calendar_service.get_availability(window_start, window_end, duration_minutes=30)

    # Busy 10:00-11:00 -> free slots should be 09:00-09:30, 09:30-10:00, 11:00-11:30, 11:30-12:00
    assert [(s.start.hour, s.start.minute) for s in slots] == [
        (9, 0),
        (9, 30),
        (11, 0),
        (11, 30),
    ]


@pytest.mark.anyio
async def test_get_availability_no_events_fills_entire_window(calendar_service):
    mock_response = MagicMock()
    mock_response.json.return_value = {"value": []}
    mock_response.raise_for_status.return_value = None
    calendar_service._client.get = AsyncMock(return_value=mock_response)

    window_start = datetime(2026, 8, 3, 9, 0, tzinfo=UTC)
    window_end = datetime(2026, 8, 3, 10, 0, tzinfo=UTC)

    slots = await calendar_service.get_availability(window_start, window_end, duration_minutes=30)

    assert len(slots) == 2
    assert slots[0].start == window_start
    assert slots[1].end == window_end


@pytest.mark.anyio
async def test_get_availability_merges_overlapping_busy_events(calendar_service):
    overlapping_event = {
        **RAW_EVENT,
        "id": "event-2",
        "start": {"dateTime": "2026-08-03T10:30:00.0000000", "timeZone": "UTC"},
        "end": {"dateTime": "2026-08-03T11:30:00.0000000", "timeZone": "UTC"},
    }
    mock_response = MagicMock()
    mock_response.json.return_value = {"value": [RAW_EVENT, overlapping_event]}
    mock_response.raise_for_status.return_value = None
    calendar_service._client.get = AsyncMock(return_value=mock_response)

    window_start = datetime(2026, 8, 3, 9, 0, tzinfo=UTC)
    window_end = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)

    slots = await calendar_service.get_availability(window_start, window_end, duration_minutes=30)

    # Merged busy window is 10:00-11:30 -> only 09:00-09:30, 09:30-10:00, 11:30-12:00 stay free
    assert [(s.start.hour, s.start.minute) for s in slots] == [(9, 0), (9, 30), (11, 30)]


@pytest.mark.anyio
async def test_get_availability_stops_at_max_slots(calendar_service):
    mock_response = MagicMock()
    mock_response.json.return_value = {"value": []}
    mock_response.raise_for_status.return_value = None
    calendar_service._client.get = AsyncMock(return_value=mock_response)

    window_start = datetime(2026, 8, 3, 8, 0, tzinfo=UTC)
    window_end = datetime(2026, 8, 3, 18, 0, tzinfo=UTC)

    slots = await calendar_service.get_availability(window_start, window_end, duration_minutes=30)

    assert len(slots) == 5


@pytest.mark.anyio
async def test_get_availability_stops_at_max_slots_after_busy_event(calendar_service):
    mock_response = MagicMock()
    mock_response.json.return_value = {"value": [RAW_EVENT]}
    mock_response.raise_for_status.return_value = None
    calendar_service._client.get = AsyncMock(return_value=mock_response)

    window_start = datetime(2026, 8, 3, 8, 0, tzinfo=UTC)
    window_end = datetime(2026, 8, 3, 18, 0, tzinfo=UTC)

    slots = await calendar_service.get_availability(window_start, window_end, duration_minutes=15)

    assert len(slots) == 5


@pytest.mark.anyio
async def test_aclose_closes_http_client(calendar_service):
    calendar_service._client.aclose = AsyncMock()

    await calendar_service.aclose()

    calendar_service._client.aclose.assert_called_once()


@pytest.mark.anyio
async def test_find_meeting_times_parses_suggestions(calendar_service):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "meetingTimeSuggestions": [
            {
                "confidence": 100.0,
                "meetingTimeSlot": {
                    "start": {"dateTime": "2026-08-03T09:00:00.0000000", "timeZone": "UTC"},
                    "end": {"dateTime": "2026-08-03T09:30:00.0000000", "timeZone": "UTC"},
                },
            }
        ]
    }
    mock_response.raise_for_status.return_value = None
    calendar_service._client.post = AsyncMock(return_value=mock_response)

    suggestions = await calendar_service.find_meeting_times(
        ["alice@example.com"],
        datetime(2026, 8, 3, tzinfo=UTC),
        datetime(2026, 8, 4, tzinfo=UTC),
        duration_minutes=30,
    )

    assert len(suggestions) == 1
    assert suggestions[0].confidence == 100.0
    assert suggestions[0].start == datetime(2026, 8, 3, 9, 0, tzinfo=UTC)
    assert suggestions[0].end == datetime(2026, 8, 3, 9, 30, tzinfo=UTC)

    calendar_service._client.post.assert_called_once()
    _, kwargs = calendar_service._client.post.call_args
    assert kwargs["json"]["attendees"] == [
        {"emailAddress": {"address": "alice@example.com"}, "type": "required"}
    ]
    assert kwargs["json"]["meetingDuration"] == "PT30M"
    assert kwargs["json"]["minimumAttendeePercentage"] == 100.0


@pytest.mark.anyio
async def test_find_meeting_times_rounds_unaligned_start(calendar_service):
    mock_response = MagicMock()
    mock_response.json.return_value = {"meetingTimeSuggestions": []}
    mock_response.raise_for_status.return_value = None
    calendar_service._client.post = AsyncMock(return_value=mock_response)

    await calendar_service.find_meeting_times(
        ["alice@example.com"],
        datetime(2026, 8, 3, 16, 23, 7, tzinfo=UTC),
        datetime(2026, 8, 4, tzinfo=UTC),
    )

    _, kwargs = calendar_service._client.post.call_args
    sent_start = kwargs["json"]["timeConstraint"]["timeSlots"][0]["start"]["dateTime"]
    assert sent_start == datetime(2026, 8, 3, 16, 30, tzinfo=UTC).isoformat()


@pytest.mark.anyio
async def test_find_meeting_times_builds_daily_slots_when_daily_window_set(calendar_service):
    mock_response = MagicMock()
    mock_response.json.return_value = {"meetingTimeSuggestions": []}
    mock_response.raise_for_status.return_value = None
    calendar_service._client.post = AsyncMock(return_value=mock_response)

    await calendar_service.find_meeting_times(
        ["alice@example.com"],
        datetime(2026, 8, 3, 6, 0, tzinfo=UTC),  # 08:00 local
        datetime(2026, 8, 5, 6, 0, tzinfo=UTC),  # 08:00 local, 2 days later
        duration_minutes=30,
        daily_window=(8, 12),
    )

    _, kwargs = calendar_service._client.post.call_args
    time_constraint = kwargs["json"]["timeConstraint"]
    assert time_constraint["activityDomain"] == "unrestricted"
    slots = time_constraint["timeSlots"]
    assert len(slots) == 2
    assert slots[0]["start"]["dateTime"] == datetime(2026, 8, 3, 6, 0, tzinfo=UTC).isoformat()
    assert slots[0]["end"]["dateTime"] == datetime(2026, 8, 3, 10, 0, tzinfo=UTC).isoformat()
    assert slots[1]["start"]["dateTime"] == datetime(2026, 8, 4, 6, 0, tzinfo=UTC).isoformat()
    assert slots[1]["end"]["dateTime"] == datetime(2026, 8, 4, 10, 0, tzinfo=UTC).isoformat()


@pytest.mark.anyio
async def test_find_meeting_times_omits_activity_domain_without_daily_window(calendar_service):
    mock_response = MagicMock()
    mock_response.json.return_value = {"meetingTimeSuggestions": []}
    mock_response.raise_for_status.return_value = None
    calendar_service._client.post = AsyncMock(return_value=mock_response)

    await calendar_service.find_meeting_times(
        ["alice@example.com"],
        datetime(2026, 8, 3, tzinfo=UTC),
        datetime(2026, 8, 4, tzinfo=UTC),
    )

    _, kwargs = calendar_service._client.post.call_args
    assert "activityDomain" not in kwargs["json"]["timeConstraint"]


@pytest.mark.anyio
async def test_find_meeting_times_returns_empty_when_no_suggestions(calendar_service):
    mock_response = MagicMock()
    mock_response.json.return_value = {"meetingTimeSuggestions": []}
    mock_response.raise_for_status.return_value = None
    calendar_service._client.post = AsyncMock(return_value=mock_response)

    suggestions = await calendar_service.find_meeting_times(
        ["alice@example.com"], datetime(2026, 8, 3, tzinfo=UTC), datetime(2026, 8, 4, tzinfo=UTC)
    )

    assert suggestions == []


@pytest.mark.anyio
async def test_find_meeting_times_http_error_raises_calendar_error(calendar_service):
    calendar_service._client.post = AsyncMock(side_effect=httpx.ConnectTimeout("timed out"))

    with pytest.raises(CalendarServiceError, match="Failed to find meeting times"):
        await calendar_service.find_meeting_times(
            ["alice@example.com"],
            datetime(2026, 8, 3, tzinfo=UTC),
            datetime(2026, 8, 4, tzinfo=UTC),
        )


@pytest.mark.anyio
async def test_find_meeting_times_auth_failure_raises_calendar_error(mock_auth):
    mock_auth.get_valid_access_token.side_effect = GraphAuthError("Not authenticated.")
    service = GraphCalendarService(mock_auth)

    with pytest.raises(CalendarServiceError, match="Not authenticated"):
        await service.find_meeting_times(
            ["alice@example.com"],
            datetime(2026, 8, 3, tzinfo=UTC),
            datetime(2026, 8, 4, tzinfo=UTC),
        )


@pytest.mark.anyio
async def test_create_event_success(calendar_service):
    mock_response = MagicMock()
    mock_response.json.return_value = RAW_EVENT
    mock_response.raise_for_status.return_value = None
    calendar_service._client.post = AsyncMock(return_value=mock_response)

    event = await calendar_service.create_event(
        subject="Sprint Planning",
        start=datetime(2026, 8, 3, 10, 0, tzinfo=UTC),
        end=datetime(2026, 8, 3, 11, 0, tzinfo=UTC),
        attendees=["bob@example.com"],
        body="Let's plan the sprint.",
    )

    assert event.id == "event-1"
    calendar_service._client.post.assert_called_once()
    _, kwargs = calendar_service._client.post.call_args
    assert kwargs["json"]["attendees"] == [
        {"emailAddress": {"address": "bob@example.com"}, "type": "required"}
    ]


@pytest.mark.anyio
async def test_create_event_http_error_raises_calendar_error(calendar_service):
    calendar_service._client.post = AsyncMock(side_effect=httpx.ConnectTimeout("timed out"))

    with pytest.raises(CalendarServiceError, match="Failed to create calendar event"):
        await calendar_service.create_event(
            subject="X",
            start=datetime(2026, 8, 3, 10, 0, tzinfo=UTC),
            end=datetime(2026, 8, 3, 11, 0, tzinfo=UTC),
        )
