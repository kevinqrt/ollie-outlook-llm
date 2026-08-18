from unittest.mock import patch

import pytest
from fastapi import status


def test_security_headers(client):
    """Checks if important security headers are present in the response."""
    # WHEN
    response = client.get("/health")

    # THEN
    # FastAPI/Uvicorn defaults + potential additions
    assert response.status_code == status.HTTP_200_OK
    # Content-Type is a basic security requirement to prevent MIME sniffing
    assert "content-type" in response.headers


def test_input_validation_security(client):
    """Tests if extremely large input is handled or if it causes a crash."""
    # GIVEN
    large_input = "A" * 1_000_000  # 1MB of text

    with patch("app.api.router.LlmService.generate_suggestion") as mock_gen:
        mock_gen.return_value = "Reply"

        # WHEN
        response = client.post("/email/suggestion", json={"email_content": large_input})

        # THEN
        # System should handle it (either 200 or 413/422 depending on config, here 200 is expected if not limited)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_413_CONTENT_TOO_LARGE]


def test_llm_service_timeout_handling():
    """Verifies that the LlmService has a timeout configured for RAG requests."""
    from app.services.llm_service import LlmService

    # WHEN
    service = LlmService()

    # THEN
    assert service.client._timeout.read == 60.0
    assert service.client._timeout.connect == 60.0


@pytest.mark.anyio
async def test_reliability_health_check(client):
    """Ensures the health check is reliable and returns the correct schema."""
    # WHEN
    response = client.get("/health")

    # THEN
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}
