import json
import logging
import threading
import uuid
from pathlib import Path
from typing import Any

from app.api.schemas.pipeline_settings_schema import ToneOption
from app.core.model_catalog import DEFAULT_MODEL_ID

logger = logging.getLogger(__name__)


class SavedPromptNotFoundError(Exception):
    pass


# Reserved id for the built-in default prompt entry synthesized by the API (never
# stored in "saved_prompts") - see PipelineSettingsStore.get_default_prompt().
DEFAULT_PROMPT_ID = "default"


class PipelineSettingsStore:
    """Persists the (optionally user-customized) pipeline system prompt,

    whether the pipeline may ask clarifying questions before answering, and a
    small library of saved prompt templates the user can reuse, in a local
    JSON file (analogous to `IcsCalendarStore`).
    """

    def __init__(self, path: str, default_prompt: str) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._default_prompt = default_prompt
        self._data = self._load()
        self._log_active_prompt()

    def _load(self) -> dict[str, Any]:
        """Lädt die Einstellungsdatei, mit robustem Fallback statt Absturz.

        Prüft bei jedem Start, ob ein eigener Prompt gespeichert ist: ist die
        Datei fehlend, leer oder beschädigt (z. B. durch einen Absturz beim
        Schreiben), wird mit dem Standard-Prompt gestartet statt den
        gesamten Server-Start mit einer unbehandelten Exception abzubrechen.
        """
        if self._path.exists():
            try:
                data: dict[str, Any] = json.loads(self._path.read_text(encoding="utf-8"))
                return data
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "Pipeline-Einstellungen (%s) konnten nicht gelesen werden (%s) - "
                    "starte mit dem Standard-Prompt statt abzustürzen.",
                    self._path,
                    exc,
                )
        return {
            "prompt": None,
            "allow_clarifying_questions": False,
            "saved_prompts": [],
            "tone": "friendly",
            "custom_tone_text": None,
            "model": DEFAULT_MODEL_ID,
        }

    def _log_active_prompt(self) -> None:
        if self._data.get("prompt"):
            logger.info("Pipeline-Prompt: zuletzt gespeicherter, benutzerdefinierter Prompt aktiv.")
        else:
            logger.info("Pipeline-Prompt: kein eigener gespeichert, nutze den Standard-Prompt.")

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def get_prompt(self) -> str:
        return self._data.get("prompt") or self._default_prompt

    def get_default_prompt(self) -> str:
        return self._default_prompt

    def get_allow_clarifying_questions(self) -> bool:
        return bool(self._data.get("allow_clarifying_questions", False))

    def get_tone(self) -> ToneOption:
        return self._data.get("tone") or "friendly"

    def get_custom_tone_text(self) -> str | None:
        return self._data.get("custom_tone_text")

    def get_model_id(self) -> str:
        return self._data.get("model") or DEFAULT_MODEL_ID

    def update(
        self,
        *,
        prompt: str,
        allow_clarifying_questions: bool,
        tone: str = "friendly",
        custom_tone_text: str | None = None,
        model: str = DEFAULT_MODEL_ID,
    ) -> None:
        with self._lock:
            self._data["prompt"] = prompt
            self._data["allow_clarifying_questions"] = allow_clarifying_questions
            self._data["tone"] = tone
            self._data["custom_tone_text"] = custom_tone_text
            self._data["model"] = model
            self._save()

    def list_saved_prompts(self) -> list[dict[str, str]]:
        prompts: list[dict[str, str]] = self._data.get("saved_prompts", [])
        return list(prompts)

    def add_saved_prompt(self, text: str) -> dict[str, str]:
        with self._lock:
            entry = {"id": str(uuid.uuid4()), "text": text}
            self._data.setdefault("saved_prompts", []).append(entry)
            self._save()
            return entry

    def update_saved_prompt(self, prompt_id: str, text: str) -> dict[str, str]:
        if prompt_id == DEFAULT_PROMPT_ID:
            raise SavedPromptNotFoundError(prompt_id)
        with self._lock:
            entries: list[dict[str, str]] = self._data.setdefault("saved_prompts", [])
            for entry in entries:
                if entry["id"] == prompt_id:
                    entry["text"] = text
                    self._save()
                    return entry
            raise SavedPromptNotFoundError(prompt_id)

    def delete_saved_prompt(self, prompt_id: str) -> None:
        if prompt_id == DEFAULT_PROMPT_ID:
            raise SavedPromptNotFoundError(prompt_id)
        with self._lock:
            entries: list[dict[str, str]] = self._data.setdefault("saved_prompts", [])
            remaining = [entry for entry in entries if entry["id"] != prompt_id]
            if len(remaining) == len(entries):
                raise SavedPromptNotFoundError(prompt_id)
            self._data["saved_prompts"] = remaining
            self._save()
