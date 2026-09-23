import json
import logging
import threading
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MAX_RULES = 15


class StyleRuleNotFoundError(Exception):
    pass


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


class StyleRulesStore:
    """Persists the style rules learned from user corrections in a local JSON file

    (analogous to `PipelineSettingsStore`).

    Only the short, generic rule text is stored - never the e-mail or the
    reply it was derived from.
    """

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        """Lädt die Regeldatei, mit robustem Fallback statt Absturz.

        Ist die Datei fehlend, leer oder beschädigt (z. B. durch einen Absturz
        beim Schreiben), wird ohne gelernte Regeln gestartet, statt den
        gesamten Server-Start abzubrechen.
        """
        if self._path.exists():
            try:
                data: dict[str, Any] = json.loads(self._path.read_text(encoding="utf-8"))
                return data
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "Stilregeln (%s) konnten nicht gelesen werden (%s) - starte ohne Regeln.",
                    self._path,
                    exc,
                )
        return {"enabled": True, "rules": []}

    def _save(self) -> None:
        self._path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def is_enabled(self) -> bool:
        return bool(self._data.get("enabled", True))

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._data["enabled"] = enabled
            self._save()

    def list_rules(self) -> list[dict[str, str]]:
        rules: list[dict[str, str]] = self._data.get("rules", [])
        return list(rules)

    def active_rules(self) -> list[str]:
        """Rule texts to inject into the prompt - empty while learning is switched off."""
        if not self.is_enabled():
            return []
        return [rule["text"] for rule in self.list_rules()]

    def add_rule(self, text: str) -> dict[str, str] | None:
        """Stores a new rule; returns None if an equivalent rule already exists.

        Once `MAX_RULES` is reached, the oldest rule is dropped.
        """
        with self._lock:
            rules: list[dict[str, str]] = self._data.setdefault("rules", [])
            if any(_normalize(rule["text"]) == _normalize(text) for rule in rules):
                return None
            entry = {"id": str(uuid.uuid4()), "text": text}
            rules.append(entry)
            if len(rules) > MAX_RULES:
                del rules[: len(rules) - MAX_RULES]
            self._save()
            return entry

    def delete_rule(self, rule_id: str) -> None:
        with self._lock:
            rules: list[dict[str, str]] = self._data.setdefault("rules", [])
            remaining = [rule for rule in rules if rule["id"] != rule_id]
            if len(remaining) == len(rules):
                raise StyleRuleNotFoundError(rule_id)
            self._data["rules"] = remaining
            self._save()

    def clear(self) -> None:
        with self._lock:
            self._data["rules"] = []
            self._save()
