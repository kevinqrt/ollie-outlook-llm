from app.pipeline.llm_client import PIPELINE_MODEL, ChatMessage, build_chat_model, invoke_chat

SUMMARY_SYSTEM_PROMPT = (
    "Du bist ein Text-Zusammenfassungs-Tool für E-Mail-Verläufe. Fasse den vom Nutzer "
    "bereitgestellten E-Mail-Verlauf prägnant auf Deutsch zusammen: wer schreibt was, worum "
    "geht es, und was ist ggf. zu tun oder offen. Gib ausschließlich die Zusammenfassung "
    "aus, ohne Einleitung oder Kommentare."
)


async def summarize_thread(thread_text: str, model: str = PIPELINE_MODEL) -> str:
    """Summarize an email thread (including quoted history) in a few sentences.

    Uses the DGX pipeline model (same backend as `/email/suggestion/stream`)
    instead of the RAG-service `direct_query` path - a plain system+user chat
    call, no `documents_text`/`query` split to fight with.
    """
    chat_model = build_chat_model(model)
    messages: list[ChatMessage] = [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": thread_text},
    ]
    return await invoke_chat(chat_model, messages)
