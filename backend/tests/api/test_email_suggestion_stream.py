import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

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


def _capture_system_prompt(client: TestClient) -> str:
    captured: dict[str, str] = {}

    async def _capturing_pipeline(_email: str, **kwargs: str) -> AsyncIterator[PipelineEvent]:
        captured["system_prompt"] = kwargs["system_prompt"]
        yield DoneEvent(final_reply="Fertige Antwort")

    with patch("app.api.router.run_pipeline", _capturing_pipeline):
        _read_events(client, {"emailContent": "Testmail"})
    return captured["system_prompt"]


def test_stream_email_suggestion_appends_learned_style_rules(client: TestClient) -> None:
    with patch("app.api.router.derive_style_rule", AsyncMock(return_value="Duze den Empfänger.")):
        client.post("/pipeline/corrections", json={"originalReply": "Antwort", "feedback": "duzen"})

    system_prompt = _capture_system_prompt(client)

    assert "GELERNTE STILVORGABEN" in system_prompt
    assert "- Duze den Empfänger." in system_prompt


def test_stream_email_suggestion_ignores_style_rules_when_learning_is_off(
    client: TestClient,
) -> None:
    with patch("app.api.router.derive_style_rule", AsyncMock(return_value="Duze den Empfänger.")):
        client.post("/pipeline/corrections", json={"originalReply": "Antwort", "feedback": "duzen"})
    client.put("/pipeline/style-rules/settings", json={"enabled": False})

    assert "GELERNTE STILVORGABEN" not in _capture_system_prompt(client)


def test_stream_email_suggestion_without_rules_has_no_style_section(client: TestClient) -> None:
    assert "GELERNTE STILVORGABEN" not in _capture_system_prompt(client)
