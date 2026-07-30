from typing import Literal, TypedDict

import httpx

from app.core.config import settings


class LlmClientError(RuntimeError):
    pass


class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


def build_client() -> httpx.AsyncClient:
    if not settings.model_api_base_url:
        raise LlmClientError(
            "MODEL_API_BASE_URL ist nicht gesetzt. Bitte in der .env bzw. im "
            "Ollie Desktop Host unter 'Model API Base URL' konfigurieren."
        )

    headers = {}
    if settings.model_api_key:
        headers["Authorization"] = f"Bearer {settings.model_api_key}"

    return httpx.AsyncClient(
        base_url=settings.model_api_base_url, headers=headers, timeout=120.0
    )


async def chat_complete(client: httpx.AsyncClient, messages: list[ChatMessage]) -> str:
    """Ruft die OpenAI-kompatible Chat-Completions-API auf und gibt den Antworttext zurück.

    Manche Modelle (z. B. Reasoning-Modelle wie gpt-oss) füllen `max_tokens` zuerst
    mit ihrem internen 'reasoning'-Feld, bevor sie den eigentlichen 'content'
    schreiben. Wird das Limit dabei ausgeschöpft, bleibt `content` leer - das
    behandeln wir als Fehler statt stillschweigend einen leeren String zurückzugeben.
    """
    try:
        response = await client.post(
            "/chat/completions",
            json={
                "model": settings.llm_model,
                "messages": messages,
                "max_tokens": settings.llm_max_tokens,
            },
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise LlmClientError(f"DGX-Anfrage fehlgeschlagen: {exc}") from exc

    body = response.json()
    try:
        choice = body["choices"][0]
        content = choice["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise LlmClientError(f"Unerwartetes Antwortformat vom DGX-Server: {body}") from exc

    if not isinstance(content, str) or not content:
        finish_reason = body.get("choices", [{}])[0].get("finish_reason")
        raise LlmClientError(
            f"DGX-Modell hat keine Antwort geliefert (finish_reason={finish_reason}). "
            "Vermutlich hat 'reasoning' das gesamte max_tokens-Budget verbraucht."
        )

    return content
