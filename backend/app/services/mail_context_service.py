import json
import logging
import re
from datetime import datetime
from typing import Any

from app.api.schemas.chat_schema import ChatMessageSchema
from app.api.schemas.mail_schema import MailMessageSchema
from app.core.datetime_utils import LOCAL_TZ, format_datetime_de
from app.services.graph_mail_service import GraphMailService, MailServiceError
from app.services.llm_service import LlmService, LlmServiceError
from app.services.scheduling_service import _extract_json

logger = logging.getLogger(__name__)

# Cheap pre-filter: only messages mentioning mails at all get the extra LLM
# classification call, so ordinary chat questions stay as fast as before.
_MAIL_KEYWORDS = re.compile(
    r"mail|nachricht|geschrieben|schrieb|posteingang|inbox|reingekommen|eingegangen"
    r"|gemeldet|geantwortet|postfach",
    re.IGNORECASE,
)

# Whether the user wants an overview of new mails is decided by these words,
# not by the LLM - the small chat model mixed up "what did X write" with
# "what came in today", which loaded the wrong mails.
_OVERVIEW_KEYWORDS = re.compile(
    r"reingekommen|eingegangen|neue[nr]? (e-)?mails|neue nachrichten|posteingang|ungelesen",
    re.IGNORECASE,
)

# Words that are never useful search terms, for both the LLM's suggestion and
# the capitalized-word fallback.
_STOPWORDS = {
    "was",
    "wer",
    "wann",
    "wie",
    "wo",
    "welche",
    "welcher",
    "hat",
    "haben",
    "habe",
    "hast",
    "ist",
    "sind",
    "gibt",
    "es",
    "ich",
    "du",
    "mir",
    "mich",
    "sich",
    "mein",
    "meine",
    "bitte",
    "kannst",
    "zeig",
    "zeige",
    "mail",
    "mails",
    "e-mail",
    "e-mails",
    "email",
    "emails",
    "nachricht",
    "nachrichten",
    "postfach",
    "posteingang",
    "inbox",
    "heute",
    "gestern",
    "neu",
    "neue",
    "neuen",
    "zuletzt",
    "letzte",
    "letzten",
    "geschrieben",
    "geschickt",
    "gemeldet",
    "von",
    "an",
    "zu",
    "der",
    "die",
    "das",
    "den",
    "dem",
    "ein",
    "eine",
    "und",
}

# Time words are capitalized too but never a search term.
_STOPWORDS |= {
    "montag",
    "dienstag",
    "mittwoch",
    "donnerstag",
    "freitag",
    "samstag",
    "sonntag",
    "woche",
    "wochenende",
    "morgen",
    "vormittag",
    "nachmittag",
    "abend",
    "seit",
}

_CAPITALIZED_WORD = re.compile(r"\b[A-ZÄÖÜ][\wÄÖÜäöüß-]+")

_CLASSIFICATION_PROMPT = (
    "Extrahiere aus der Chat-Nachricht Suchbegriffe fuer eine E-Mail-Postfachsuche. "
    'Antworte AUSSCHLIESSLICH mit JSON der Form {{"search_query": <1-4 Suchbegriffe oder '
    'null>, "since_date": <JJJJ-MM-TT oder null>}} ohne weiteren Text. search_query sind '
    "Namen von Personen oder Firmen und Themen - OHNE Woerter wie Mail, geschrieben, heute. "
    "since_date ist der frueheste gemeinte Tag relativ zum oben genannten heutigen Datum.\n"
    "Beispiele:\n"
    'Nachricht: Was hat Max Muster mir zuletzt geschrieben? -> {{"search_query": '
    '"Max Muster", "since_date": null}}\n'
    'Nachricht: Hat sich die Sparkasse wegen dem Kredit gemeldet? -> {{"search_query": '
    '"Sparkasse Kredit", "since_date": null}}\n'
    'Nachricht: Was ist heute reingekommen? -> {{"search_query": null, "since_date": '
    '"<heutiges Datum>"}}\n\n'
    "Nachricht: {text}"
)

MAX_PREVIEW_CHARS = 200


def _sender_label(message: MailMessageSchema) -> str:
    return message.sender_name or message.sender_address or "Unbekannt"


def _clean_query(words: list[str]) -> str:
    return " ".join(w for w in words if w.lower() not in _STOPWORDS).strip()


def _fallback_query(text: str) -> str:
    """Capitalized words of the question that aren't stopwords, e.g. names."""
    return _clean_query(_CAPITALIZED_WORD.findall(text))


def _format_list_line(message: MailMessageSchema, own_address: str | None = None) -> str:
    preview = message.preview.replace("\n", " ").replace("\r", " ")
    if len(preview) > MAX_PREVIEW_CHARS:
        preview = preview[:MAX_PREVIEW_CHARS].rstrip() + "..."
    unread = " [ungelesen]" if not message.is_read else ""
    own = (
        " (von dir)"
        if own_address and (message.sender_address or "").lower() == own_address
        else ""
    )
    return (
        f"- {format_datetime_de(message.received)} Uhr - {_sender_label(message)}{own}: "
        f"{message.subject}{unread} - {preview}"
    )


def _format_thread_entry(message: MailMessageSchema) -> str:
    text = message.body if message.body is not None else message.preview
    return (
        f"--- {format_datetime_de(message.received)} Uhr, von {_sender_label(message)}, "
        f"Betreff: {message.subject}\n{text}"
    )


class MailContextService:
    """Adds mails from the user's mailbox as prompt context.

    Like `SchedulingService`, this is deterministic orchestration rather than
    tool calling (the RAG service has no function calling): classify the
    message, fetch matching mails via Graph, hand them back as extra context.
    """

    def __init__(self, llm_service: LlmService, mail_service: GraphMailService) -> None:
        self._llm_service = llm_service
        self._mail_service = mail_service

    async def build_chat_context(self, text: str, model: str | None = None) -> str:
        """Mail search results or an inbox overview for a chat message, else ""."""
        if not text.strip() or not _MAIL_KEYWORDS.search(text):
            return ""
        detection = await self._classify(text, model) or {}

        llm_query = detection.get("search_query")
        query = _clean_query(llm_query.split()) if isinstance(llm_query, str) else ""
        if not query:
            query = _fallback_query(text)

        try:
            if query:
                messages = await self._mail_service.search_messages(query)
                messages.sort(key=lambda m: m.received, reverse=True)
                header = (
                    f"E-Mails im Postfach des Nutzers zur Suche '{query}', neueste zuerst "
                    "(die erste Zeile ist die aktuellste Mail)"
                )
            elif _OVERVIEW_KEYWORDS.search(text):
                since = self._resolve_since(detection.get("since_date"))
                messages = await self._mail_service.list_recent(since)
                header = (
                    f"Neu eingegangene E-Mails seit {format_datetime_de(since)} Uhr, neueste zuerst"
                )
            else:
                return ""
            own_address = await self._own_address()
        except MailServiceError:
            logger.info("Skipping mail context: mailbox unavailable.")
            return ""

        if not messages:
            return f"\n\n{header}: keine passenden E-Mails gefunden."
        lines = "\n".join(_format_list_line(m, own_address) for m in messages)
        return (
            f"\n\n{header} - nutze sie, um die Frage zu beantworten. Mit '(von dir)' "
            f"markierte Mails hat der Nutzer selbst geschrieben:\n{lines}"
        )

    async def _own_address(self) -> str | None:
        try:
            return await self._mail_service.get_own_address()
        except MailServiceError:
            return None

    async def build_reply_context(self, conversation_id: str | None, sender: str | None) -> str:
        """Earlier mails of the same conversation (or from the same sender)."""
        try:
            messages: list[MailMessageSchema] = []
            if conversation_id:
                messages = await self._mail_service.thread_messages(conversation_id)
            if not messages and sender:
                messages = await self._mail_service.messages_from(sender)
        except MailServiceError:
            logger.info("Skipping reply mail context: mailbox unavailable.")
            return ""

        if not messages:
            return ""
        entries = "\n".join(_format_thread_entry(m) for m in messages)
        return (
            "\n\nFruehere E-Mails in diesem Verlauf bzw. mit diesem Absender, aelteste zuerst "
            "(nur als Hintergrund fuer eine passende Antwort verwenden):\n" + entries
        )

    @staticmethod
    def _resolve_since(since_date: Any) -> datetime:
        today = datetime.now(LOCAL_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        if isinstance(since_date, str):
            try:
                parsed = datetime.fromisoformat(since_date).replace(tzinfo=LOCAL_TZ)
            except ValueError:
                return today
            if parsed <= today:
                return parsed
        return today

    async def _classify(self, text: str, model: str | None) -> dict[str, Any] | None:
        try:
            raw_reply = await self._llm_service.chat(
                [ChatMessageSchema(role="user", content=_CLASSIFICATION_PROMPT.format(text=text))],
                model=model,
            )
        except LlmServiceError:
            logger.info("Skipping mail context: classification request failed.")
            return None
        try:
            parsed = json.loads(_extract_json(raw_reply))
        except ValueError:
            logger.info("Skipping mail context: could not parse classification reply.")
            return None
        return parsed if isinstance(parsed, dict) else None
