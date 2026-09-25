from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.schemas.chat_schema import ChatMessageSchema
from app.api.schemas.knowledge_schema import KnowledgeDocumentSchema, KnowledgeSearchResultSchema
from app.services.llm_service import LlmService
from app.services.vector_store_service import VectorStoreService


@pytest.fixture
def properly_constructed_llm_service() -> LlmService:
    """An LlmService with a mocked vector_store constructor arg."""
    vector_store = MagicMock(spec=VectorStoreService)
    vector_store.search = AsyncMock(return_value=[])
    vector_store.list_documents = AsyncMock(return_value=[])
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


async def _documents_text_for(service: LlmService, question: str) -> str:
    mock_response = MagicMock()
    mock_response.additional_properties = {"reply": "Antwort"}
    with patch("app.services.llm_service.direct_query.asyncio") as mock_direct_query:
        mock_direct_query.return_value = mock_response
        await service.chat([ChatMessageSchema(role="user", content=question)])
    _, kwargs = mock_direct_query.call_args
    return str(kwargs["body"].documents_text)


@pytest.mark.anyio
async def test_chat_lists_knowledge_base_documents_and_sources(properly_constructed_llm_service):
    """Regression test: asking what's in the knowledge base used to only yield a
    few unlabelled excerpts, so the model answered that the context wasn't enough."""
    vector_store = properly_constructed_llm_service.vector_store
    vector_store.list_documents = AsyncMock(
        return_value=[
            KnowledgeDocumentSchema(source="grundgesetz.pdf"),
            KnowledgeDocumentSchema(source="handbuch.pdf"),
        ]
    )
    vector_store.search = AsyncMock(
        return_value=[
            KnowledgeSearchResultSchema(
                content="Die Wuerde des Menschen ist unantastbar.",
                metadata={"source": "grundgesetz.pdf"},
            )
        ]
    )

    documents_text = await _documents_text_for(
        properly_constructed_llm_service, "Was liegt in der Wissensbasis?"
    )

    assert (
        "Dokumente in der Wissensbasis (vom Nutzer hochgeladene PDFs): "
        "grundgesetz.pdf, handbuch.pdf"
    ) in documents_text
    assert "[Quelle: grundgesetz.pdf] Die Wuerde des Menschen ist unantastbar." in documents_text


@pytest.mark.anyio
async def test_chat_says_when_knowledge_base_is_empty(properly_constructed_llm_service):
    documents_text = await _documents_text_for(
        properly_constructed_llm_service, "Was liegt in der Wissensbasis?"
    )

    assert "Die Wissensbasis ist leer" in documents_text
    properly_constructed_llm_service.vector_store.search.assert_not_called()
