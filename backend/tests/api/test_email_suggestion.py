from unittest.mock import patch

from fastapi import status
from fastapi.testclient import TestClient

from app.services.scheduling_service import AvailabilityAugmentation


def test_get_email_suggestion_success(client: TestClient) -> None:
    """Tests a successful email suggestion request"""
    # GIVEN
    email_content = "Can we meet tomorrow?"
    expected_reply = "This is a mock reply."

    with (
        patch("app.services.llm_service.LlmService.generate_suggestion") as mock_gen,
        patch(
            "app.services.scheduling_service.SchedulingService.augment_with_availability"
        ) as mock_augment,
    ):
        mock_gen.return_value = expected_reply
        mock_augment.return_value = AvailabilityAugmentation()

        # WHEN
        response = client.post("/email/suggestion", json={"email_content": email_content})

        # THEN
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"suggestedReply": expected_reply, "meetingProposal": None}
        mock_gen.assert_called_once_with(email_content, extra_context="")


def test_get_email_suggestion_empty_content(client):
    """Tests that empty email content returns a 422 validation error"""
    # GIVEN
    email_content = ""

    # WHEN
    response = client.post("/email/suggestion", json={"email_content": email_content})

    # THEN
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_get_email_suggestion_service_error(client):
    """Tests that an LlmServiceError returns a 503 service unavailable error"""
    # GIVEN
    from app.services.llm_service import LlmServiceError

    email_content = "Hello"

    with patch("app.services.llm_service.LlmService.generate_suggestion") as mock_gen:
        mock_gen.side_effect = LlmServiceError("RAG Service request failed")

        # WHEN
        response = client.post("/email/suggestion", json={"email_content": email_content})

        # THEN
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "RAG Service request failed" in response.json()["detail"]
