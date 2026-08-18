import httpx
from rag_service_api import (
    Client,
    CreateSessionRequest,
    HTTPValidationError,
    QuerySessionRequest,
    create_session,
    delete_session,
    query_session,
)

from app.core.config import settings


class RagClientError(RuntimeError):
    pass


def build_client() -> Client:
    return Client(
        base_url=settings.rag_service_url,
        timeout=httpx.Timeout(120.0),
        raise_on_unexpected_status=True,
    )


async def create_rag_session(client: Client, documents_text: str) -> str:
    response = await create_session.asyncio(
        client=client,
        body=CreateSessionRequest(documents_text=documents_text, llm_model=settings.llm_model),
    )

    if response is None:
        raise RagClientError("RAG Service returned no response while creating the session.")
    if isinstance(response, HTTPValidationError):
        raise RagClientError(f"RAG Service validation error: {response.detail}")

    session_id = response.additional_properties.get("session_id")
    if not isinstance(session_id, str):
        raise RagClientError("RAG Service response is missing 'session_id'.")
    return session_id


async def query_rag_session(client: Client, session_id: str, query: str) -> str:
    response = await query_session.asyncio(
        session_id=session_id,
        client=client,
        body=QuerySessionRequest(query=query),
    )

    if response is None:
        raise RagClientError("RAG Service returned no response for the query.")
    if isinstance(response, HTTPValidationError):
        raise RagClientError(f"RAG Service validation error: {response.detail}")

    answer = response.additional_properties.get("answer")
    if not isinstance(answer, str):
        raise RagClientError("RAG Service response is missing 'answer'.")
    return answer


async def delete_rag_session(client: Client, session_id: str) -> None:
    await delete_session.asyncio(session_id=session_id, client=client)
