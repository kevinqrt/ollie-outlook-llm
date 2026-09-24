from app.pipeline.llm_client import PIPELINE_MODEL, build_chat_model, invoke_chat
from app.pipeline.prompt_builder import build_style_rule_distill_prompt

MAX_RULE_LENGTH = 200
# Anführungszeichen, die das Modell um die Regel setzen könnte (gerade, deutsche, typografische).
QUOTE_CHARS = "\"'\u201e\u201c\u201d\u201a\u2018\u2019"
NO_RULE_MARKER = "KEINE"


def normalize_rule(raw: str) -> str | None:
    """Bereinigt die Modellausgabe zu einer einzeiligen Regel, oder None ohne Regel."""
    lines = [line.strip() for line in raw.strip().splitlines() if line.strip()]
    if not lines:
        return None
    rule = lines[0].lstrip("-*\u2022 ").strip().strip(QUOTE_CHARS).strip()
    if not rule or rule.upper().rstrip(".") == NO_RULE_MARKER:
        return None
    return rule[:MAX_RULE_LENGTH]


async def derive_style_rule(
    original_reply: str,
    feedback: str | None,
    corrected_reply: str | None,
    model: str = PIPELINE_MODEL,
) -> str | None:
    """Lässt das LLM aus einer Nutzerkorrektur eine allgemeine Stilregel ableiten.

    Gibt None zurück, wenn die Korrektur nur den Inhalt der einen Antwort betraf.
    Fehler des Modells (`LlmClientError`) werden bewusst nicht verschluckt.
    """
    answer = await invoke_chat(
        build_chat_model(model),
        [
            {
                "role": "user",
                "content": build_style_rule_distill_prompt(
                    original_reply, feedback, corrected_reply
                ),
            }
        ],
    )
    return normalize_rule(answer)
