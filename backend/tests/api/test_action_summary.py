from unittest.mock import patch

from fastapi import status
from fastapi.testclient import TestClient

from app.api.schemas.action_schema import (
    ActionCategory,
    ActionType,
    EmailActionResponseSchema,
    MeetingDetailsSchema,
)


def test_get_action_summary_meeting(client: TestClient) -> None:
    """Tests that a meeting request is classified and extracted as such."""
    # GIVEN
    payload = {
        "emailContent": "Können wir uns Donnerstag um 14 Uhr treffen?",
        "emailLinks": [],
        "sender": "Herr Schmidt",
        "subject": "Termin",
    }
    expected = EmailActionResponseSchema(
        category=ActionCategory.ACTION,
        action_type=ActionType.MEETING,
        action_summary="Termin mit Herrn Schmidt vereinbaren: Vorschlag Do 14 Uhr",
        link_index=None,
        meeting=MeetingDetailsSchema(
            subject="Termin",
            proposed_time="Donnerstag 14 Uhr",
            attendees=["Herr Schmidt"],
        ),
    )

    with patch("app.services.llm_service.LlmService.extract_action") as mock_extract:
        mock_extract.return_value = expected

        # WHEN
        response = client.post("/email/action-summary", json=payload)

        # THEN
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["category"] == "action"
        assert body["actionType"] == "meeting"
        assert body["meeting"]["proposedTime"] == "Donnerstag 14 Uhr"
        mock_extract.assert_called_once_with(
            payload["emailContent"], payload["emailLinks"], payload["sender"], payload["subject"]
        )


def test_get_action_summary_newsletter(client: TestClient) -> None:
    """Tests that a non-actionable email is classified without action fields."""
    # GIVEN
    payload = {"emailContent": "Unser Newsletter im Februar.", "emailLinks": []}
    expected = EmailActionResponseSchema(category=ActionCategory.NEWSLETTER)

    with patch("app.services.llm_service.LlmService.extract_action") as mock_extract:
        mock_extract.return_value = expected

        # WHEN
        response = client.post("/email/action-summary", json=payload)

        # THEN
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["category"] == "newsletter"
        assert body["actionType"] is None


def test_get_action_summary_service_unavailable(client: TestClient) -> None:
    """Tests that a RAG service failure is surfaced as 503."""
    from app.services.llm_service import LlmServiceError

    with patch("app.services.llm_service.LlmService.extract_action") as mock_extract:
        mock_extract.side_effect = LlmServiceError("RAG Service returned invalid JSON")

        response = client.post("/email/action-summary", json={"emailContent": "Hallo"})

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "invalid JSON" in response.json()["detail"]
