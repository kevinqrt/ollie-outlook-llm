import json
from collections.abc import AsyncIterator
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status

from app.api.schemas.pipeline_schema import DoneEvent, PipelineEvent


def test_security_headers(client):
    """Checks if important security headers are present in the response."""
    # WHEN
    response = client.get("/health")

    # THEN
    # FastAPI/Uvicorn defaults + potential additions
    assert response.status_code == status.HTTP_200_OK
    # Content-Type is a basic security requirement to prevent MIME sniffing
    assert "content-type" in response.headers


async def _fake_pipeline(_email_text: str, **_kwargs: str) -> AsyncIterator[PipelineEvent]:
    yield DoneEvent(final_reply="Reply")


def test_input_validation_security(client):
    """Tests if extremely large input is handled or if it causes a crash."""
    # GIVEN
    large_input = "A" * 1_000_000  # 1MB of text

    with (
        patch("app.api.router.run_pipeline", _fake_pipeline),
        client.stream(
            "POST", "/email/suggestion/stream", json={"email_content": large_input}
        ) as response,
    ):
        # THEN
        # System should handle it (200 expected here; 413/422 also acceptable if limited)
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_413_CONTENT_TOO_LARGE,
        ]
        if response.status_code == status.HTTP_200_OK:
            lines = [line for line in response.iter_lines() if line.startswith("data: ")]
            events = [json.loads(line.removeprefix("data: ")) for line in lines]
            assert events[-1]["type"] == "done"


def test_llm_service_timeout_handling():
    """Verifies that the LlmService has a timeout configured for RAG requests."""
    from app.services.llm_service import LlmService
    from app.services.vector_store_service import VectorStoreService

    # WHEN
    service = LlmService(vector_store=MagicMock(spec=VectorStoreService))

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
