from typing import Literal, TypedDict, cast

from langchain_openai import ChatOpenAI
from openai import OpenAIError
from pydantic import SecretStr

from app.core.config import settings


class LlmClientError(RuntimeError):
    pass


class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


# Das DGX-Modell hinter MODEL_API_BASE_URL ist unabhängig vom RAG-Service-Modell
# (settings.llm_model), das dort nicht im Katalog steht.
PIPELINE_MODEL = "openai/gpt-oss-120b"


def build_chat_model() -> ChatOpenAI:
    if not settings.model_api_base_url:
        raise LlmClientError(
            "MODEL_API_BASE_URL ist nicht gesetzt. Bitte in der .env bzw. im "
            "Ollie Desktop Host unter 'Model API Base URL' konfigurieren."
        )

    return ChatOpenAI(
        base_url=settings.model_api_base_url,
        # Der DGX-Tunnel hinter MODEL_API_BASE_URL prüft keinen Key.
        api_key=SecretStr("not-needed"),
        model=PIPELINE_MODEL,
        max_completion_tokens=settings.llm_max_tokens,
        timeout=120.0,
    )


async def invoke_chat(model: ChatOpenAI, messages: list[ChatMessage]) -> str:
    """Ruft das LLM auf und gibt den Antworttext zurück.

    Manche Modelle (z. B. Reasoning-Modelle wie gpt-oss) füllen `max_tokens` zuerst
    mit ihrem internen 'reasoning'-Feld, bevor sie den eigentlichen 'content'
    schreiben. Wird das Limit dabei ausgeschöpft, bleibt `content` leer - das
    behandeln wir als Fehler statt stillschweigend einen leeren String zurückzugeben.
    """
    try:
        response = await model.ainvoke(cast(list[dict[str, str]], messages))
    except OpenAIError as exc:
        raise LlmClientError(f"DGX-Anfrage fehlgeschlagen: {exc}") from exc

    content = response.content
    if not isinstance(content, str) or not content:
        finish_reason = response.response_metadata.get("finish_reason")
        raise LlmClientError(
            f"DGX-Modell hat keine Antwort geliefert (finish_reason={finish_reason}). "
            "Vermutlich hat 'reasoning' das gesamte max_tokens-Budget verbraucht."
        )

    return content
