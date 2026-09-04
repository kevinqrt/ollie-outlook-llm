from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.api.schemas.calendar_schema import (
    CalendarEventSchema,
    MeetingTimeSuggestionSchema,
    TimeSlotSchema,
)
from app.mcp_server import check_availability, create_event, find_meeting_times, list_events

EVENT = CalendarEventSchema(
    id="event-1",
    subject="Sprint Planning",
    start=datetime(2026, 8, 3, 10, 0, tzinfo=UTC),
    end=datetime(2026, 8, 3, 11, 0, tzinfo=UTC),
    organizer="Alice",
    is_organizer=True,
)


@pytest.mark.anyio
async def test_list_events_tool_delegates_to_calendar_service():
    with patch(
        "app.mcp_server._calendar_service.list_events", new=AsyncMock(return_value=[EVENT])
    ) as mock_list:
        result = await list_events("2026-08-03T00:00:00+00:00", "2026-08-04T00:00:00+00:00")

    assert result == [EVENT.model_dump(mode="json")]
    mock_list.assert_called_once_with(
        datetime(2026, 8, 3, tzinfo=UTC), datetime(2026, 8, 4, tzinfo=UTC)
    )


@pytest.mark.anyio
async def test_check_availability_tool_delegates_to_calendar_service():
    slot = TimeSlotSchema(
        start=datetime(2026, 8, 3, 9, 0, tzinfo=UTC), end=datetime(2026, 8, 3, 9, 30, tzinfo=UTC)
    )
    with patch(
        "app.mcp_server._calendar_service.get_availability", new=AsyncMock(return_value=[slot])
    ) as mock_availability:
        result = await check_availability(
            "2026-08-03T00:00:00+00:00", "2026-08-04T00:00:00+00:00", duration_minutes=45
        )

    assert result == [slot.model_dump(mode="json")]
    mock_availability.assert_called_once_with(
        datetime(2026, 8, 3, tzinfo=UTC), datetime(2026, 8, 4, tzinfo=UTC), 45
    )


@pytest.mark.anyio
async def test_find_meeting_times_tool_delegates_to_calendar_service():
    suggestion = MeetingTimeSuggestionSchema(
        start=datetime(2026, 8, 3, 11, 0, tzinfo=UTC),
        end=datetime(2026, 8, 3, 11, 30, tzinfo=UTC),
        confidence=100.0,
    )
    with patch(
        "app.mcp_server._calendar_service.find_meeting_times",
        new=AsyncMock(return_value=[suggestion]),
    ) as mock_find:
        result = await find_meeting_times(
            ["alice@example.com"],
            "2026-08-03T00:00:00+00:00",
            "2026-08-04T00:00:00+00:00",
            duration_minutes=45,
            max_candidates=3,
        )

    assert result == [suggestion.model_dump(mode="json")]
    mock_find.assert_called_once_with(
        ["alice@example.com"],
        datetime(2026, 8, 3, tzinfo=UTC),
        datetime(2026, 8, 4, tzinfo=UTC),
        45,
        3,
    )


@pytest.mark.anyio
async def test_create_event_tool_delegates_to_calendar_service():
    with patch(
        "app.mcp_server._calendar_service.create_event", new=AsyncMock(return_value=EVENT)
    ) as mock_create:
        result = await create_event(
            subject="Sprint Planning",
            start="2026-08-03T10:00:00+00:00",
            end="2026-08-03T11:00:00+00:00",
            attendees=["bob@example.com"],
            body="Let's plan.",
        )

    assert result == EVENT.model_dump(mode="json")
    mock_create.assert_called_once_with(
        subject="Sprint Planning",
        start=datetime(2026, 8, 3, 10, 0, tzinfo=UTC),
        end=datetime(2026, 8, 3, 11, 0, tzinfo=UTC),
        attendees=["bob@example.com"],
        body="Let's plan.",
    )
