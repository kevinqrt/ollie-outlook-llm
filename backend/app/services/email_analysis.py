import os

from ollama import ChatResponse, chat

from app.api.schemas.email import EmailAnalyzeRequest, EmailAnalyzeResponse


OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")


class OllamaError(RuntimeError):
    pass


def analyze_email_request(payload: EmailAnalyzeRequest) -> EmailAnalyzeResponse:
    return EmailAnalyzeResponse(text=_generate_reply(payload.text))


def _generate_reply(email_text: str) -> str:
    try:
        response: ChatResponse = chat(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Schreibe genau eine fertige E-Mail-Antwort auf Basis dieses Textes. "
                        "Gib nur den finalen Antworttext zurueck.\n\n"
                        f"{email_text.strip()}"
                    ),
                }
            ],
        )
        text = response.message.content.strip()
        if not text:
            raise ValueError("Ollama returned no text.")
        return text
    except Exception as exc:
        raise OllamaError(f"Ollama request failed: {exc}") from exc
