from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rag_service_api import HTTPValidationError

from app.api.schemas.chat_schema import ChatMessageSchema
from app.services.llm_service import LlmService, LlmServiceError
from app.services.prompt_service import PromptService
from app.services.vector_store_service import VectorStoreService


@pytest.mark.anyio
async def test_generate_suggestion_success():
    """Tests successful suggestion generation from RAG service"""
    # GIVEN
    service = LlmService()
    email_text = "Hello"
    mock_response = MagicMock()
    mock_response.additional_properties = {"reply": "Mocked AI reply"}

    with patch("app.services.llm_service.direct_query.asyncio") as mock_direct_query:
        mock_direct_query.return_value = mock_response

        # WHEN
        result = await service.generate_suggestion(email_text)

        # THEN
        assert result == "Mocked AI reply"


@pytest.mark.anyio
async def test_generate_suggestion_no_response():
    """Tests handling when RAG service returns None"""
    # GIVEN
    service = LlmService()

    with patch("app.services.llm_service.direct_query.asyncio") as mock_direct_query:
        mock_direct_query.return_value = None

        # WHEN / THEN
        with pytest.raises(LlmServiceError, match="RAG Service returned no response"):
            await service.generate_suggestion("Hello")


@pytest.mark.anyio
async def test_generate_suggestion_validation_error():
    """Tests handling when RAG service returns a validation error"""
    # GIVEN
    service = LlmService()
    mock_error = HTTPValidationError(
        detail=[{"msg": "Invalid request", "type": "value_error", "loc": []}]
    )

    with patch("app.services.llm_service.direct_query.asyncio") as mock_direct_query:
        mock_direct_query.return_value = mock_error

        # WHEN / THEN
        with pytest.raises(LlmServiceError, match="RAG Service validation error"):
            await service.generate_suggestion("Hello")


@pytest.mark.anyio
async def test_generate_suggestion_general_exception():
    """Tests handling of general exceptions during RAG service call"""
    # GIVEN
    service = LlmService()

    with patch("app.services.llm_service.direct_query.asyncio") as mock_direct_query:
        mock_direct_query.side_effect = Exception("Connection error")

        # WHEN / THEN
        with pytest.raises(LlmServiceError, match="RAG Service request failed: Connection error"):
            await service.generate_suggestion("Hello")


@pytest.fixture
def properly_constructed_llm_service() -> LlmService:
    """A correctly constructed LlmService (see memory: the `LlmService()` calls
    above pre-date the `vector_store`/`prompt_service` constructor args and are
    a known, pre-existing, out-of-scope failure - don't copy that pattern)."""
    vector_store = MagicMock(spec=VectorStoreService)
    vector_store.search = AsyncMock(return_value=[])
    prompt_service = MagicMock(spec=PromptService)
    prompt_service.get_reply_prompt.return_value = "ANTWORT:"
    return LlmService(vector_store=vector_store, prompt_service=prompt_service)


@pytest.mark.anyio
async def test_chat_always_includes_today_anchor(properly_constructed_llm_service):
    """Regression test: the model must always know today's date, not only when
    a meeting request happens to be detected - otherwise a plain "what day is
    it?" question gets a "no real-time data" refusal."""
    mock_response = MagicMock()
    mock_response.additional_properties = {"reply": "Hallo!"}

    fixed_now = datetime(2026, 8, 6, 14, 22, tzinfo=UTC)  # a Thursday
    with (
        patch("app.services.llm_service.direct_query.asyncio") as mock_direct_query,
        patch("app.services.llm_service.datetime") as mock_dt,
    ):
        mock_dt.now.return_value = fixed_now
        mock_direct_query.return_value = mock_response

        await properly_constructed_llm_service.chat(
            [ChatMessageSchema(role="user", content="Welcher Tag ist heute?")]
        )

    _, kwargs = mock_direct_query.call_args
    assert kwargs["body"].documents_text.startswith("Heute ist Donnerstag, 06.08.2026 16:22 Uhr.")


@pytest.mark.anyio
async def test_generate_suggestion_always_includes_today_anchor(
    properly_constructed_llm_service,
):
    mock_response = MagicMock()
    mock_response.additional_properties = {"reply": "Antwort"}

    fixed_now = datetime(2026, 8, 6, 14, 22, tzinfo=UTC)  # a Thursday
    with (
        patch("app.services.llm_service.direct_query.asyncio") as mock_direct_query,
        patch("app.services.llm_service.datetime") as mock_dt,
    ):
        mock_dt.now.return_value = fixed_now
        mock_direct_query.return_value = mock_response

        await properly_constructed_llm_service.generate_suggestion("Koennen wir uns treffen?")

    _, kwargs = mock_direct_query.call_args
    assert kwargs["body"].documents_text.startswith("Heute ist Donnerstag, 06.08.2026 16:22 Uhr.")
