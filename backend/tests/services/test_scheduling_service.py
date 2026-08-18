from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.schemas.calendar_schema import (
    CalendarEventSchema,
    MeetingTimeSuggestionSchema,
    TimeSlotSchema,
)
from app.services.availability import CalendarServiceError
from app.services.graph_auth_service import GraphAuthError
from app.services.graph_calendar_service import GraphCalendarService
from app.services.ics_calendar_service import IcsCalendarService
from app.services.llm_service import LlmService, LlmServiceError
from app.services.scheduling_service import AvailabilityAugmentation, SchedulingService

SLOT = TimeSlotSchema(
    start=datetime(2026, 8, 3, 9, 0, tzinfo=UTC), end=datetime(2026, 8, 3, 9, 30, tzinfo=UTC)
)
SLOT_2 = TimeSlotSchema(
    start=datetime(2026, 8, 3, 10, 0, tzinfo=UTC), end=datetime(2026, 8, 3, 10, 30, tzinfo=UTC)
)

SUGGESTION = MeetingTimeSuggestionSchema(
    start=datetime(2026, 8, 3, 11, 0, tzinfo=UTC),
    end=datetime(2026, 8, 3, 11, 30, tzinfo=UTC),
    confidence=100.0,
)


@pytest.fixture
def mock_llm() -> MagicMock:
    return MagicMock(spec=LlmService)


@pytest.fixture
def mock_calendar() -> MagicMock:
    return MagicMock(spec=GraphCalendarService)


@pytest.fixture
def scheduling_service(mock_llm: MagicMock, mock_calendar: MagicMock) -> SchedulingService:
    return SchedulingService(llm_service=mock_llm, calendar_service=mock_calendar)


def _empty() -> AvailabilityAugmentation:
    return AvailabilityAugmentation()


@pytest.mark.anyio
async def test_augment_returns_empty_for_blank_text(scheduling_service):
    assert await scheduling_service.augment_with_availability("   ") == _empty()


@pytest.mark.anyio
async def test_augment_returns_empty_when_not_a_meeting_request(scheduling_service, mock_llm):
    mock_llm.chat = AsyncMock(return_value='{"is_meeting_request": false}')

    result = await scheduling_service.augment_with_availability("Danke fuer die Info.")

    assert result == _empty()


@pytest.mark.anyio
async def test_augment_returns_empty_when_classification_reply_is_not_json(
    scheduling_service, mock_llm
):
    mock_llm.chat = AsyncMock(return_value="Das ist keine Terminanfrage.")

    result = await scheduling_service.augment_with_availability("Hallo!")

    assert result == _empty()


@pytest.mark.anyio
async def test_augment_returns_empty_when_classification_call_fails(scheduling_service, mock_llm):
    mock_llm.chat = AsyncMock(side_effect=LlmServiceError("RAG down"))

    result = await scheduling_service.augment_with_availability("Koennen wir uns treffen?")

    assert result == _empty()


@pytest.mark.anyio
async def test_augment_returns_empty_when_calendar_not_authenticated(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(return_value='{"is_meeting_request": true, "duration_minutes": 30}')
    mock_calendar.get_availability = AsyncMock(
        side_effect=CalendarServiceError("Not authenticated with Microsoft Graph.")
    )

    result = await scheduling_service.augment_with_availability("Koennen wir uns treffen?")

    assert result == _empty()


@pytest.mark.anyio
async def test_augment_returns_empty_when_auth_error_raised_directly(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(return_value='{"is_meeting_request": true, "duration_minutes": 30}')
    mock_calendar.get_availability = AsyncMock(side_effect=GraphAuthError("not configured"))

    result = await scheduling_service.augment_with_availability("Koennen wir uns treffen?")

    assert result == _empty()


@pytest.mark.anyio
async def test_augment_returns_empty_when_no_free_slots(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(return_value='{"is_meeting_request": true, "duration_minutes": 30}')
    mock_calendar.get_availability = AsyncMock(return_value=[])

    result = await scheduling_service.augment_with_availability("Koennen wir uns treffen?")

    assert result == _empty()


@pytest.mark.anyio
async def test_augment_returns_slots_as_context(scheduling_service, mock_llm, mock_calendar):
    mock_llm.chat = AsyncMock(return_value='{"is_meeting_request": true, "duration_minutes": 30}')
    mock_calendar.get_availability = AsyncMock(return_value=[SLOT])

    result = await scheduling_service.augment_with_availability("Koennen wir uns treffen?")

    assert "Verfuegbare Termine" in result.context
    # SLOT is 09:00-09:30 UTC; August is CEST (UTC+2) -> 11:00-11:30 local.
    assert "11:00" in result.context
    assert "11:30" in result.context


@pytest.mark.anyio
async def test_augment_builds_proposal_from_first_slot(scheduling_service, mock_llm, mock_calendar):
    mock_llm.chat = AsyncMock(return_value='{"is_meeting_request": true, "duration_minutes": 30}')
    mock_calendar.get_availability = AsyncMock(return_value=[SLOT, SLOT_2])

    result = await scheduling_service.augment_with_availability("Koennen wir uns treffen?")

    assert result.proposal is not None
    assert result.proposal.start == SLOT.start
    assert result.proposal.end == SLOT.end
    assert result.proposal.subject == "Termin"
    assert result.proposal.body == ""
    assert result.proposal.attendees == []


@pytest.mark.anyio
async def test_augment_proposal_uses_extracted_subject_and_description(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(
        return_value=(
            '{"is_meeting_request": true, "duration_minutes": 30, '
            '"subject": "Budget-Review", "description": "Wir besprechen Q3."}'
        )
    )
    mock_calendar.get_availability = AsyncMock(return_value=[SLOT])

    result = await scheduling_service.augment_with_availability("Koennen wir uns treffen?")

    assert result.proposal is not None
    assert result.proposal.subject == "Budget-Review"
    assert result.proposal.body == "Wir besprechen Q3."


@pytest.mark.anyio
async def test_augment_handles_markdown_fenced_json_reply(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(
        return_value='```json\n{"is_meeting_request": true, "duration_minutes": 45}\n```'
    )
    mock_calendar.get_availability = AsyncMock(return_value=[SLOT])

    result = await scheduling_service.augment_with_availability("Lass uns 45 Minuten reden.")

    mock_calendar.get_availability.assert_called_once()
    call_args = mock_calendar.get_availability.call_args[0]
    assert call_args[2] == 45
    assert "Verfuegbare Termine" in result.context


@pytest.mark.anyio
async def test_augment_falls_back_to_default_duration_when_invalid(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(
        return_value='{"is_meeting_request": true, "duration_minutes": "invalid"}'
    )
    mock_calendar.get_availability = AsyncMock(return_value=[SLOT])

    await scheduling_service.augment_with_availability("Koennen wir uns treffen?")

    call_args = mock_calendar.get_availability.call_args[0]
    assert call_args[2] == 30


@pytest.mark.anyio
async def test_augment_returns_empty_when_classification_reply_is_json_array(
    scheduling_service, mock_llm
):
    mock_llm.chat = AsyncMock(return_value="[1, 2, 3]")

    result = await scheduling_service.augment_with_availability("Hallo!")

    assert result == _empty()


@pytest.mark.anyio
async def test_augment_uses_find_meeting_times_when_attendees_given(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(return_value='{"is_meeting_request": true, "duration_minutes": 30}')
    mock_calendar.find_meeting_times = AsyncMock(return_value=[SUGGESTION])

    result = await scheduling_service.augment_with_availability(
        "Koennen wir uns treffen?", attendees=["alice@example.com"]
    )

    mock_calendar.find_meeting_times.assert_called_once()
    call_args = mock_calendar.find_meeting_times.call_args[0]
    assert call_args[0] == ["alice@example.com"]
    assert call_args[3] == 30
    mock_calendar.get_availability.assert_not_called()
    assert "alle Empfaenger" in result.context
    # SUGGESTION starts 11:00 UTC; August is CEST (UTC+2) -> 13:00 local.
    assert "13:00" in result.context
    assert result.proposal is not None
    assert result.proposal.attendees == ["alice@example.com"]


@pytest.mark.anyio
async def test_augment_extracts_email_addresses_from_text(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(return_value='{"is_meeting_request": true, "duration_minutes": 30}')
    mock_calendar.find_meeting_times = AsyncMock(return_value=[SUGGESTION])

    result = await scheduling_service.augment_with_availability(
        "Koennen wir uns mit Anna@Example.com treffen?"
    )

    mock_calendar.find_meeting_times.assert_called_once()
    call_args = mock_calendar.find_meeting_times.call_args[0]
    assert call_args[0] == ["anna@example.com"]
    assert result.proposal is not None
    assert result.proposal.attendees == ["anna@example.com"]


@pytest.mark.anyio
async def test_augment_merges_explicit_attendees_with_emails_in_text(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(return_value='{"is_meeting_request": true, "duration_minutes": 30}')
    mock_calendar.find_meeting_times = AsyncMock(return_value=[SUGGESTION])

    await scheduling_service.augment_with_availability(
        "Koennen wir mit bob@example.com treffen?", attendees=["alice@example.com"]
    )

    call_args = mock_calendar.find_meeting_times.call_args[0]
    assert call_args[0] == ["alice@example.com", "bob@example.com"]


@pytest.mark.anyio
async def test_augment_deduplicates_attendees_case_insensitively(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(return_value='{"is_meeting_request": true, "duration_minutes": 30}')
    mock_calendar.find_meeting_times = AsyncMock(return_value=[SUGGESTION])

    await scheduling_service.augment_with_availability(
        "Koennen wir mit Alice@Example.com treffen?", attendees=["alice@example.com"]
    )

    call_args = mock_calendar.find_meeting_times.call_args[0]
    assert call_args[0] == ["alice@example.com"]


@pytest.mark.anyio
async def test_augment_falls_back_to_solo_when_no_attendees(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(return_value='{"is_meeting_request": true, "duration_minutes": 30}')
    mock_calendar.get_availability = AsyncMock(return_value=[SLOT])

    result = await scheduling_service.augment_with_availability(
        "Koennen wir uns treffen?", attendees=[]
    )

    mock_calendar.get_availability.assert_called_once()
    mock_calendar.find_meeting_times.assert_not_called()
    assert "Verfuegbare Termine im Kalender" in result.context


@pytest.mark.anyio
async def test_augment_slot_lines_use_german_weekday_names(
    scheduling_service, mock_llm, mock_calendar
):
    """SLOT.start (2026-08-03) is a Monday; must render as 'Montag', not the
    locale-dependent (and on this system English) strftime('%A') output."""
    mock_llm.chat = AsyncMock(return_value='{"is_meeting_request": true, "duration_minutes": 30}')
    mock_calendar.get_availability = AsyncMock(return_value=[SLOT])

    result = await scheduling_service.augment_with_availability("Koennen wir uns treffen?")

    # SLOT starts 09:00 UTC; August is CEST (UTC+2) -> 11:00 local.
    assert "Montag, 03.08.2026 11:00" in result.context
    assert "Monday" not in result.context


@pytest.mark.anyio
async def test_augment_returns_empty_when_find_meeting_times_fails(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(return_value='{"is_meeting_request": true, "duration_minutes": 30}')
    mock_calendar.find_meeting_times = AsyncMock(
        side_effect=CalendarServiceError("Failed to find meeting times")
    )

    result = await scheduling_service.augment_with_availability(
        "Koennen wir uns treffen?", attendees=["alice@example.com"]
    )

    assert result == _empty()


FIXED_NOW = datetime(2026, 8, 3, 9, 0, tzinfo=UTC)


def _patch_now():
    patcher = patch("app.services.scheduling_service.datetime")
    mock_dt = patcher.start()
    mock_dt.now.return_value = FIXED_NOW
    mock_dt.fromisoformat = datetime.fromisoformat
    return patcher


@pytest.mark.anyio
async def test_augment_uses_earliest_date_from_classification_as_window_start(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(
        return_value=(
            '{"is_meeting_request": true, "duration_minutes": 30, "earliest_date": "2026-08-10"}'
        )
    )
    mock_calendar.get_availability = AsyncMock(return_value=[SLOT])

    patcher = _patch_now()
    try:
        await scheduling_service.augment_with_availability(
            "Koennen wir uns naechste Woche treffen?"
        )
    finally:
        patcher.stop()

    call_args = mock_calendar.get_availability.call_args[0]
    assert call_args[0] == datetime(2026, 8, 10, 9, 0, tzinfo=UTC)


@pytest.mark.anyio
async def test_augment_falls_back_to_now_when_earliest_date_in_past(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(
        return_value=(
            '{"is_meeting_request": true, "duration_minutes": 30, "earliest_date": "2026-07-01"}'
        )
    )
    mock_calendar.get_availability = AsyncMock(return_value=[SLOT])

    patcher = _patch_now()
    try:
        await scheduling_service.augment_with_availability("Koennen wir uns treffen?")
    finally:
        patcher.stop()

    call_args = mock_calendar.get_availability.call_args[0]
    assert call_args[0] == FIXED_NOW


@pytest.mark.anyio
async def test_augment_falls_back_to_now_when_earliest_date_is_invalid(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(
        return_value=(
            '{"is_meeting_request": true, "duration_minutes": 30, '
            '"earliest_date": "naechste Woche"}'
        )
    )
    mock_calendar.get_availability = AsyncMock(return_value=[SLOT])

    patcher = _patch_now()
    try:
        await scheduling_service.augment_with_availability("Koennen wir uns treffen?")
    finally:
        patcher.stop()

    call_args = mock_calendar.get_availability.call_args[0]
    assert call_args[0] == FIXED_NOW


@pytest.mark.anyio
async def test_augment_context_mentions_requested_start_when_different_from_now(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(
        return_value=(
            '{"is_meeting_request": true, "duration_minutes": 30, "earliest_date": "2026-08-10"}'
        )
    )
    mock_calendar.get_availability = AsyncMock(return_value=[SLOT])

    patcher = _patch_now()
    try:
        result = await scheduling_service.augment_with_availability(
            "Koennen wir uns naechste Woche treffen?"
        )
    finally:
        patcher.stop()

    assert "wie angefragt" in result.context


@pytest.mark.anyio
async def test_augment_context_omits_requested_start_note_when_no_earliest_date(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(return_value='{"is_meeting_request": true, "duration_minutes": 30}')
    mock_calendar.get_availability = AsyncMock(return_value=[SLOT])

    result = await scheduling_service.augment_with_availability("Koennen wir uns treffen?")

    assert "wie angefragt" not in result.context


@pytest.mark.anyio
async def test_augment_uses_time_of_day_from_classification_as_daily_window(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(
        return_value=(
            '{"is_meeting_request": true, "duration_minutes": 30, "time_of_day": "vormittags"}'
        )
    )
    mock_calendar.get_availability = AsyncMock(return_value=[SLOT])

    await scheduling_service.augment_with_availability("Koennen wir uns vormittags treffen?")

    _, kwargs = mock_calendar.get_availability.call_args
    assert kwargs["daily_window"] == (8, 12)


@pytest.mark.anyio
async def test_augment_defaults_daily_window_when_no_time_of_day_given(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(return_value='{"is_meeting_request": true, "duration_minutes": 30}')
    mock_calendar.get_availability = AsyncMock(return_value=[SLOT])

    await scheduling_service.augment_with_availability("Koennen wir uns treffen?")

    _, kwargs = mock_calendar.get_availability.call_args
    assert kwargs["daily_window"] == (8, 20)


@pytest.mark.anyio
async def test_augment_defaults_daily_window_when_time_of_day_unrecognized(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(
        return_value=(
            '{"is_meeting_request": true, "duration_minutes": 30, "time_of_day": "irgendwann"}'
        )
    )
    mock_calendar.get_availability = AsyncMock(return_value=[SLOT])

    await scheduling_service.augment_with_availability("Koennen wir uns treffen?")

    _, kwargs = mock_calendar.get_availability.call_args
    assert kwargs["daily_window"] == (8, 20)


@pytest.mark.anyio
async def test_augment_passes_daily_window_to_find_meeting_times(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(
        return_value=(
            '{"is_meeting_request": true, "duration_minutes": 30, "time_of_day": "abends"}'
        )
    )
    mock_calendar.find_meeting_times = AsyncMock(return_value=[SUGGESTION])

    await scheduling_service.augment_with_availability(
        "Koennen wir uns abends treffen?", attendees=["alice@example.com"]
    )

    _, kwargs = mock_calendar.find_meeting_times.call_args
    assert kwargs["daily_window"] == (18, 21)


@pytest.mark.anyio
async def test_augment_context_mentions_time_of_day_when_requested(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(
        return_value=(
            '{"is_meeting_request": true, "duration_minutes": 30, "time_of_day": "vormittags"}'
        )
    )
    mock_calendar.get_availability = AsyncMock(return_value=[SLOT])

    result = await scheduling_service.augment_with_availability(
        "Koennen wir uns vormittags treffen?"
    )

    assert "vormittags" in result.context


@pytest.mark.anyio
async def test_augment_context_omits_time_of_day_note_when_not_requested(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(return_value='{"is_meeting_request": true, "duration_minutes": 30}')
    mock_calendar.get_availability = AsyncMock(return_value=[SLOT])

    result = await scheduling_service.augment_with_availability("Koennen wir uns treffen?")

    assert "wie gewuenscht" not in result.context


@pytest.mark.anyio
async def test_augment_omits_unknown_attendee_note_when_backend_has_no_such_capability(
    scheduling_service, mock_llm, mock_calendar
):
    """Graph (and mock) calendar services have no `unknown_attendees` method -
    the note must simply not appear, not crash."""
    mock_llm.chat = AsyncMock(return_value='{"is_meeting_request": true, "duration_minutes": 30}')
    mock_calendar.find_meeting_times = AsyncMock(return_value=[SUGGESTION])

    result = await scheduling_service.augment_with_availability(
        "Koennen wir uns treffen?", attendees=["alice@example.com"]
    )

    assert "Kalender-Link bekannt" not in result.context


@pytest.mark.anyio
async def test_augment_mentions_unknown_attendees_when_backend_reports_them(mock_llm):
    ics_calendar = MagicMock(spec=IcsCalendarService)
    ics_calendar.find_meeting_times = AsyncMock(return_value=[SUGGESTION])
    ics_calendar.unknown_attendees = MagicMock(return_value=["bob@example.com"])
    scheduling_service = SchedulingService(llm_service=mock_llm, calendar_service=ics_calendar)
    mock_llm.chat = AsyncMock(return_value='{"is_meeting_request": true, "duration_minutes": 30}')

    result = await scheduling_service.augment_with_availability(
        "Koennen wir uns treffen?", attendees=["alice@example.com", "bob@example.com"]
    )

    ics_calendar.unknown_attendees.assert_called_once_with(
        ["alice@example.com", "bob@example.com"]
    )
    assert "bob@example.com" in result.context
    assert "Kalender-Link bekannt" in result.context


@pytest.mark.anyio
async def test_augment_does_not_check_unknown_attendees_when_none_given(mock_llm):
    ics_calendar = MagicMock(spec=IcsCalendarService)
    ics_calendar.get_availability = AsyncMock(return_value=[SLOT])
    ics_calendar.unknown_attendees = MagicMock(return_value=[])
    scheduling_service = SchedulingService(llm_service=mock_llm, calendar_service=ics_calendar)
    mock_llm.chat = AsyncMock(return_value='{"is_meeting_request": true, "duration_minutes": 30}')

    await scheduling_service.augment_with_availability("Koennen wir uns treffen?")

    ics_calendar.unknown_attendees.assert_not_called()


EVENT_1 = CalendarEventSchema(
    id="event-1",
    subject="Sprint Planning",
    start=datetime(2026, 8, 3, 9, 0, tzinfo=UTC),
    end=datetime(2026, 8, 3, 9, 30, tzinfo=UTC),
    organizer="Alice",
    is_organizer=True,
)
EVENT_2 = CalendarEventSchema(
    id="event-2",
    subject="1:1 mit Bob",
    start=datetime(2026, 8, 3, 14, 0, tzinfo=UTC),
    end=datetime(2026, 8, 3, 14, 30, tzinfo=UTC),
    organizer=None,
    is_organizer=False,
)


@pytest.mark.anyio
async def test_augment_lists_calendar_events_when_query_detected(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(return_value='{"is_calendar_query": true}')
    mock_calendar.list_events = AsyncMock(return_value=[EVENT_2, EVENT_1])

    result = await scheduling_service.augment_with_availability(
        "Was steht in meinem Kalender?"
    )

    assert result.proposal is None
    # Sorted chronologically even though the mock returned them out of order.
    assert result.context.index("Sprint Planning") < result.context.index("1:1 mit Bob")
    # Events are UTC 09:00/14:00; August is CEST (UTC+2) -> 11:00/16:00 local.
    assert "11:00" in result.context
    assert "16:00" in result.context


@pytest.mark.anyio
async def test_augment_calendar_listing_defaults_to_todays_local_midnight(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(return_value='{"is_calendar_query": true}')
    mock_calendar.list_events = AsyncMock(return_value=[])

    patcher = _patch_now()
    try:
        await scheduling_service.augment_with_availability("Was steht heute an?")
    finally:
        patcher.stop()

    call_args = mock_calendar.list_events.call_args[0]
    # FIXED_NOW is 2026-08-03 09:00 UTC = 11:00 local (CEST) -> local midnight
    # of that same day is 2026-08-02 22:00 UTC.
    assert call_args[0] == datetime(2026, 8, 2, 22, 0, tzinfo=UTC)


@pytest.mark.anyio
async def test_augment_calendar_listing_uses_earliest_date_without_clamping(
    scheduling_service, mock_llm, mock_calendar
):
    """Unlike the meeting-proposal path, a listing query for a day that has

    already started (or even passed) must NOT be clamped to `now` - asking
    about "today" this afternoon must still show the whole day.
    """
    mock_llm.chat = AsyncMock(
        return_value='{"is_calendar_query": true, "earliest_date": "2026-07-01"}'
    )
    mock_calendar.list_events = AsyncMock(return_value=[])

    patcher = _patch_now()
    try:
        await scheduling_service.augment_with_availability("Was war am 1. Juli los?")
    finally:
        patcher.stop()

    call_args = mock_calendar.list_events.call_args[0]
    assert call_args[0] == datetime(2026, 6, 30, 22, 0, tzinfo=UTC)


@pytest.mark.anyio
async def test_augment_calendar_listing_falls_back_to_today_when_earliest_date_invalid(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(
        return_value='{"is_calendar_query": true, "earliest_date": "naechste Woche"}'
    )
    mock_calendar.list_events = AsyncMock(return_value=[])

    patcher = _patch_now()
    try:
        await scheduling_service.augment_with_availability("Was steht naechste Woche an?")
    finally:
        patcher.stop()

    call_args = mock_calendar.list_events.call_args[0]
    assert call_args[0] == datetime(2026, 8, 2, 22, 0, tzinfo=UTC)


@pytest.mark.anyio
async def test_augment_calendar_listing_returns_explicit_empty_message(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(return_value='{"is_calendar_query": true}')
    mock_calendar.list_events = AsyncMock(return_value=[])

    result = await scheduling_service.augment_with_availability("Was steht an?")

    assert "keine Termine" in result.context
    assert result.proposal is None


@pytest.mark.anyio
async def test_augment_calendar_listing_returns_empty_when_calendar_unavailable(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(return_value='{"is_calendar_query": true}')
    mock_calendar.list_events = AsyncMock(
        side_effect=CalendarServiceError("Kein eigener Kalender-Link hinterlegt.")
    )

    result = await scheduling_service.augment_with_availability("Was steht an?")

    assert result == _empty()


@pytest.mark.anyio
async def test_augment_calendar_listing_caps_events_with_note(
    scheduling_service, mock_llm, mock_calendar
):
    many_events = [
        CalendarEventSchema(
            id=f"event-{i}",
            subject=f"Termin {i}",
            start=datetime(2026, 8, 3, 8, tzinfo=UTC) + (i * timedelta(hours=1)),
            end=datetime(2026, 8, 3, 8, 30, tzinfo=UTC) + (i * timedelta(hours=1)),
        )
        for i in range(12)
    ]
    mock_llm.chat = AsyncMock(return_value='{"is_calendar_query": true}')
    mock_calendar.list_events = AsyncMock(return_value=many_events)

    result = await scheduling_service.augment_with_availability("Was steht an?")

    assert result.context.count("Termin ") == 10  # capped at MAX_LISTED_EVENTS
    assert "2 weitere Termine" in result.context


@pytest.mark.anyio
async def test_augment_returns_empty_when_neither_meeting_nor_calendar_query(
    scheduling_service, mock_llm, mock_calendar
):
    mock_llm.chat = AsyncMock(
        return_value='{"is_meeting_request": false, "is_calendar_query": false}'
    )

    result = await scheduling_service.augment_with_availability("Danke fuer die Info.")

    assert result == _empty()
    mock_calendar.list_events.assert_not_called()
