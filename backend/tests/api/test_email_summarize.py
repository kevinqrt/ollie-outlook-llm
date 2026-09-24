from unittest.mock import patch

from fastapi import status
from fastapi.testclient import TestClient

from app.pipeline.llm_client import LlmClientError


def test_summarize_email_thread_success(client: TestClient) -> None:
    with patch("app.api.router.summarize_thread") as mock_summarize:
        mock_summarize.return_value = "Kurze Zusammenfassung des Verlaufs."

        response = client.post(
            "/email/summarize", json={"thread_text": "Hallo,\n\nkoennen wir uns treffen?"}
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"summary": "Kurze Zusammenfassung des Verlaufs."}
    mock_summarize.assert_called_once_with(
        "Hallo,\n\nkoennen wir uns treffen?", model="openai/gpt-oss-120b"
    )


def test_summarize_email_thread_empty_content(client: TestClient) -> None:
    response = client.post("/email/summarize", json={"thread_text": ""})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_summarize_email_thread_service_error(client: TestClient) -> None:
    with patch("app.api.router.summarize_thread") as mock_summarize:
        mock_summarize.side_effect = LlmClientError("DGX-Anfrage fehlgeschlagen")

        response = client.post("/email/summarize", json={"thread_text": "Testmail"})

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "DGX-Anfrage fehlgeschlagen" in response.json()["detail"]
