from datetime import UTC, datetime
from unittest.mock import patch

from fastapi import status
from fastapi.testclient import TestClient

from app.api.schemas.calendar_schema import MeetingProposalSchema
from app.services.llm_service import LlmServiceError
from app.services.scheduling_service import AvailabilityAugmentation


def test_post_chat_success_without_meeting_proposal(client: TestClient) -> None:
    with (
        patch("app.services.llm_service.LlmService.chat") as mock_chat,
        patch(
            "app.services.scheduling_service.SchedulingService.augment_with_availability"
        ) as mock_augment,
    ):
        mock_augment.return_value = AvailabilityAugmentation()
        mock_chat.return_value = "Hallo, wie kann ich helfen?"

        response = client.post("/chat", json={"messages": [{"role": "user", "content": "Hallo"}]})

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "reply": "Hallo, wie kann ich helfen?",
        "meetingProposal": None,
    }
    mock_augment.assert_called_once_with("Hallo")
    mock_chat.assert_called_once()


def test_post_chat_returns_meeting_proposal(client: TestClient) -> None:
    proposal = MeetingProposalSchema(
        subject="Termin",
        body="",
        start=datetime(2026, 8, 3, 9, 0, tzinfo=UTC),
        end=datetime(2026, 8, 3, 9, 30, tzinfo=UTC),
        attendees=[],
    )

    with (
        patch("app.services.llm_service.LlmService.chat") as mock_chat,
        patch(
            "app.services.scheduling_service.SchedulingService.augment_with_availability"
        ) as mock_augment,
    ):
        mock_augment.return_value = AvailabilityAugmentation(
            context="\n\nVerfuegbare Termine im Kalender:\n- Mo 09:00-09:30 Uhr",
            proposal=proposal,
        )
        mock_chat.return_value = "Wie waere es am Montag um 09:00 Uhr?"

        response = client.post(
            "/chat",
            json={
                "messages": [
                    {"role": "user", "content": "Koennen wir uns treffen?"},
                ]
            },
        )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["reply"] == "Wie waere es am Montag um 09:00 Uhr?"
    assert body["meetingProposal"]["subject"] == "Termin"
    mock_chat.assert_called_once()
    call_args, call_kwargs = mock_chat.call_args
    assert call_args[0][0].content == "Koennen wir uns treffen?"
    assert (
        call_kwargs["extra_context"] == "\n\nVerfuegbare Termine im Kalender:\n- Mo 09:00-09:30 Uhr"
    )


def test_post_chat_uses_latest_user_message_for_scheduling(client: TestClient) -> None:
    with (
        patch("app.services.llm_service.LlmService.chat") as mock_chat,
        patch(
            "app.services.scheduling_service.SchedulingService.augment_with_availability"
        ) as mock_augment,
    ):
        mock_augment.return_value = AvailabilityAugmentation()
        mock_chat.return_value = "Ok."

        client.post(
            "/chat",
            json={
                "messages": [
                    {"role": "user", "content": "Erste Nachricht"},
                    {"role": "assistant", "content": "Antwort"},
                    {"role": "user", "content": "Zweite Nachricht"},
                ]
            },
        )

    mock_augment.assert_called_once_with("Zweite Nachricht")


def test_post_chat_service_error(client: TestClient) -> None:
    with (
        patch("app.services.llm_service.LlmService.chat") as mock_chat,
        patch(
            "app.services.scheduling_service.SchedulingService.augment_with_availability"
        ) as mock_augment,
    ):
        mock_augment.return_value = AvailabilityAugmentation()
        mock_chat.side_effect = LlmServiceError("RAG Service request failed")

        response = client.post("/chat", json={"messages": [{"role": "user", "content": "Hallo"}]})

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "RAG Service request failed" in response.json()["detail"]
