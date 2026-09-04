from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.schemas.chat_schema import ChatMessageSchema
from app.services.llm_service import LlmService
from app.services.vector_store_service import VectorStoreService


@pytest.fixture
def properly_constructed_llm_service() -> LlmService:
    """An LlmService with a mocked vector_store constructor arg."""
    vector_store = MagicMock(spec=VectorStoreService)
    vector_store.search = AsyncMock(return_value=[])
    return LlmService(vector_store=vector_store)


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
