import json
import re

MAX_STEPS = 5

FALLBACK_STEPS = [
    "Kernfragen der E-Mail identifizieren",
    "Antwortpunkte zu jeder Frage entwerfen",
    "Antwort professionell formulieren",
]

_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def parse_plan(raw_answer: str) -> list[str]:
    """Parst die vom LLM gelieferte Teilschritt-Liste, mit robustem Fallback.

    Das LLM hält Formatvorgaben nicht immer exakt ein, daher wird zuerst direkt
    geparst, dann per Regex ein JSON-Array aus umgebendem Text extrahiert, und
    im Fehlerfall auf eine feste Schrittfolge zurückgefallen statt abzustürzen.
    """
    steps = _try_parse_json_array(raw_answer.strip())

    if steps is None:
        match = _JSON_ARRAY_RE.search(raw_answer)
        if match:
            steps = _try_parse_json_array(match.group(0))

    if not steps:
        return FALLBACK_STEPS

    return steps[:MAX_STEPS]


def _try_parse_json_array(text: str) -> list[str] | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, list):
        return None

    cleaned = [item.strip() for item in parsed if isinstance(item, str) and item.strip()]
    return cleaned or None
