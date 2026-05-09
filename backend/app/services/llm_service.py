import httpx
from rag_service_api import Client, DirectQueryRequest, HTTPValidationError, direct_query

from app.core.config import settings
from app.services.prompt_service import PromptService
from app.services.vector_store_service import vector_store_service


class LlmServiceError(RuntimeError):
    pass


class LlmService:
    def __init__(self) -> None:
        self.prompt_service = PromptService()
        self.client = Client(
            base_url=settings.rag_service_url,
            timeout=httpx.Timeout(60.0),
            raise_on_unexpected_status=True,
        )

    async def generate_suggestion(self, email_text: str) -> str:
        """Sucht relevantes Wissen und generiert dann einen Antwortvorschlag."""
        
        # 1. Relevantes Wissen aus der Vektordatenbank suchen
        knowledge_results = vector_store_service.search(email_text, k=3)
        context_knowledge = "\n".join([doc.page_content for doc in knowledge_results])
        
        # 2. Den Prompt vorbereiten (Email + Zusatzwissen)
        full_context = f"EMAIL CONTENT:\n{email_text}\n\nADDITIONAL KNOWLEDGE FROM DOCUMENTS:\n{context_knowledge}"
        query_text = self.prompt_service.get_reply_prompt(full_context)

        # 3. Anfrage an den RAG-Service (LLM) stellen
        request_body = DirectQueryRequest(
            documents_text=full_context,
            query=query_text,
            llm_model=settings.llm_model,
        )

        try:
            response = await direct_query.asyncio(
                client=self.client,
                body=request_body,
            )

            if response is None:
                raise LlmServiceError("RAG Service returned no response.")

            if isinstance(response, HTTPValidationError):
                raise LlmServiceError(f"RAG Service validation error: {response.detail}")

            reply = response.additional_properties.get(
                "reply"
            ) or response.additional_properties.get("answer")
            return str(reply or "Keine Antwort vom Modell generiert.")

        except Exception as exc:
            if isinstance(exc, LlmServiceError):
                raise
            print(f"DEBUG: RAG Service Request failed. URL: {self.client._base_url}, Error: {exc}")
            raise LlmServiceError(f"RAG Service request failed: {exc}") from exc
