import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import patch

from fastapi import status
from fastapi.testclient import TestClient

from app.api.schemas.calendar_schema import MeetingProposalSchema
from app.api.schemas.pipeline_schema import DoneEvent, ErrorEvent, PipelineEvent, PlanReadyEvent
from app.services.scheduling_service import AvailabilityAugmentation


async def _fake_pipeline_success(_email_text: str, **_kwargs: str) -> AsyncIterator[PipelineEvent]:
    yield PlanReadyEvent(steps=["Kernfragen identifizieren"])
    yield DoneEvent(final_reply="Fertige Antwort")


async def _fake_pipeline_error(_email_text: str, **_kwargs: str) -> AsyncIterator[PipelineEvent]:
    yield PlanReadyEvent(steps=["Kernfragen identifizieren"])
    yield ErrorEvent(detail="RAG Service request failed")


def _read_events(client: TestClient, payload: dict[str, str]) -> list[dict]:
    with client.stream("POST", "/email/suggestion/stream", json=payload) as response:
        assert response.status_code == status.HTTP_200_OK
        lines = [line for line in response.iter_lines() if line.startswith("data: ")]
    return [json.loads(line.removeprefix("data: ")) for line in lines]


def test_stream_email_suggestion_success(client: TestClient) -> None:
    """Tests that a successful pipeline run streams events ending in 'done'."""
    with patch("app.api.router.run_pipeline", _fake_pipeline_success):
        events = _read_events(client, {"emailContent": "Können wir das Meeting verschieben?"})

    assert [e["type"] for e in events] == ["plan_ready", "done"]
    assert events[0]["steps"] == ["Kernfragen identifizieren"]
    assert events[-1]["finalReply"] == "Fertige Antwort"


def test_stream_email_suggestion_error(client: TestClient) -> None:
    """Tests that a pipeline failure surfaces as an 'error' event, not an HTTP error."""
    with patch("app.api.router.run_pipeline", _fake_pipeline_error):
        events = _read_events(client, {"emailContent": "Testmail"})

    assert [e["type"] for e in events] == ["plan_ready", "error"]
    assert events[-1]["detail"] == "RAG Service request failed"


def test_stream_email_suggestion_includes_meeting_proposal(client: TestClient) -> None:
    """Tests that attendees are checked for availability and a resulting meeting

    proposal is attached to the final 'done' event, even though the pipeline
    itself has no knowledge of calendars.
    """
    proposal = MeetingProposalSchema(
        subject="Sprint Planning",
        start=datetime(2026, 8, 10, 9, 0, tzinfo=UTC),
        end=datetime(2026, 8, 10, 9, 30, tzinfo=UTC),
        attendees=["alice@example.com"],
    )
    augmentation = AvailabilityAugmentation(context="\n\nAlice ist frei.", proposal=proposal)

    with (
        patch("app.api.router.run_pipeline", _fake_pipeline_success),
        patch(
            "app.services.scheduling_service.SchedulingService.augment_with_availability"
        ) as mock_augment,
    ):
        mock_augment.return_value = augmentation
        events = _read_events(
            client,
            {
                "emailContent": "Können wir das Meeting verschieben?",
                "attendees": ["alice@example.com"],
            },
        )

    mock_augment.assert_called_once_with(
        "Können wir das Meeting verschieben?", ["alice@example.com"]
    )
    done_event = events[-1]
    assert done_event["type"] == "done"
    assert done_event["meetingProposal"]["subject"] == "Sprint Planning"
