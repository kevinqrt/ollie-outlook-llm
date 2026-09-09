import json
import re
from dataclasses import dataclass
from typing import Any

MAX_OPTIONS = 3

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class ClarificationCheckResult:
    needs_clarification: bool
    question: str
    options: list[str]


def parse_clarification_check(raw_answer: str) -> ClarificationCheckResult | None:
    """Parst die JSON-Antwort der Rückfrage-Prüfung.

    Fail-open: ein unerwartetes Modell-Format wird als "keine Rückfrage nötig"
    behandelt (None), damit ein Parse-Fehler die Pipeline nicht blockiert.
    """
    parsed = _try_parse_json_object(raw_answer.strip())

    if parsed is None:
        match = _JSON_OBJECT_RE.search(raw_answer)
        if match:
            parsed = _try_parse_json_object(match.group(0))

    if parsed is None:
        return None

    needs_clarification = bool(parsed.get("needs_clarification"))
    question = str(parsed.get("question") or "").strip()
    raw_options = parsed.get("options")
    options = [str(o).strip() for o in raw_options if str(o).strip()] if isinstance(
        raw_options, list
    ) else []

    if not needs_clarification or not question:
        return ClarificationCheckResult(needs_clarification=False, question="", options=[])

    return ClarificationCheckResult(
        needs_clarification=True, question=question, options=options[:MAX_OPTIONS]
    )


def _try_parse_json_object(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None
