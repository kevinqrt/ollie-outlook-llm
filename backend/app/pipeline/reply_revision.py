from app.pipeline.llm_client import PIPELINE_MODEL, build_chat_model, invoke_chat
from app.pipeline.prompt_builder import build_revision_prompt


async def revise_reply(
    system_prompt: str,
    email_content: str,
    previous_reply: str,
    feedback: str,
    model: str = PIPELINE_MODEL,
) -> str:
    """Überarbeitet eine bereits vorgeschlagene Antwort nach Nutzerfeedback.

    Bewusst ein einzelner Modellaufruf statt der mehrstufigen Pipeline: schneller
    und der Inhalt der bisherigen Antwort bleibt erhalten. Modellfehler
    (`LlmClientError`, auch bei leerer Antwort) werden nicht verschluckt.
    """
    answer = await invoke_chat(
        build_chat_model(model),
        [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": build_revision_prompt(email_content, previous_reply, feedback),
            },
        ],
    )
    return answer.strip()
