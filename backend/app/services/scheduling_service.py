import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.api.schemas.calendar_schema import MeetingProposalSchema
from app.api.schemas.chat_schema import ChatMessageSchema
from app.core.datetime_utils import LOCAL_TZ, format_datetime_de
from app.services.availability import CalendarServiceError
from app.services.calendar_mock_service import MockCalendarService
from app.services.graph_auth_service import GraphAuthError
from app.services.graph_calendar_service import GraphCalendarService
from app.services.ics_calendar_service import IcsCalendarService
from app.services.llm_service import LlmService, LlmServiceError

logger = logging.getLogger(__name__)

CalendarService = GraphCalendarService | IcsCalendarService | MockCalendarService

_CLASSIFICATION_PROMPT = (
    "Analysiere die folgende Nachricht. Enthaelt sie eine Terminanfrage oder den Wunsch "
    "nach einem Meeting/Gespraech (ein NEUER Termin soll vereinbart werden)? Oder fragt sie "
    "nach BESTEHENDEN Terminen im Kalender (z.B. 'was steht in meinem Kalender', 'welche "
    "Termine habe ich diese Woche'), ohne einen neuen Termin vereinbaren zu wollen? Antworte "
    'AUSSCHLIESSLICH mit einem JSON-Objekt der Form {{"is_meeting_request": true|false, '
    '"is_calendar_query": true|false, "duration_minutes": <Zahl>, '
    '"subject": <kurzer Betreff oder null>, "description": <kurze Beschreibung oder null>, '
    '"earliest_date": <Datum im Format JJJJ-MM-TT oder null>, '
    '"time_of_day": <"vormittags"|"mittags"|"nachmittags"|"abends"|null>}} '
    "ohne weiteren Text. Falls keine Dauer erkennbar ist, verwende 30. Setze subject/description "
    "nur, wenn sie explizit im Text stehen - sonst null. Setze earliest_date auf den fruehesten "
    "Tag, um den es in der Nachricht geht (bei einem neuen Termin: ab wann er stattfinden soll; "
    "bei einer Abfrage bestehender Termine: fuer welchen Tag/Zeitraum), abgeleitet aus "
    'Zeitangaben in der Nachricht (z.B. "naechste Woche" -> Montag der Folgewoche, "Freitag" -> '
    'naechster Freitag, "in 3 Tagen" -> entsprechendes Datum, "heute" -> heutiges Datum) relativ '
    "zum oben genannten heutigen Datum - oder null, wenn keine Zeitangabe erkennbar ist. Setze "
    'time_of_day, wenn die Nachricht eine Tageszeit nennt (z.B. "vormittags", "am Nachmittag", '
    '"abends") - sonst null.\n\nNachricht:\n{text}'
)

_EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

LOOKAHEAD_DAYS = 7
DEFAULT_DURATION_MINUTES = 30
DEFAULT_SUBJECT = "Termin"
MAX_SUGGESTED_SLOTS = 3
MAX_LISTED_EVENTS = 10
BUSINESS_HOURS_START = 9

# Local (Europe/Berlin) hour-of-day ranges for each recognized time-of-day label.
TIME_OF_DAY_RANGES: dict[str, tuple[int, int]] = {
    "vormittags": (8, 12),
    "mittags": (12, 14),
    "nachmittags": (14, 18),
    "abends": (18, 21),
}
# Applies when no time-of-day was requested - keeps suggestions within sensible
# waking hours instead of e.g. literal midnight.
DEFAULT_DAILY_WINDOW: tuple[int, int] = (8, 20)


def _extract_json(text: str) -> str:
    """Strip an optional markdown code fence the LLM may wrap its JSON answer in."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[len("json") :]
    return stripped.strip()


def _resolve_window_start(detection: dict[str, Any], now: datetime) -> datetime:
    """Resolve the earliest date the user asked for (e.g. "naechste Woche") into

    a concrete search-window start, falling back to `now` if the classification
    didn't extract a date, extracted an invalid one, or extracted one in the past
    (we never search backwards). Anchored to the start of business hours rather
    than midnight, since a slot search starting at 00:00 would otherwise propose
    meetings at literal midnight.
    """
    earliest_date = detection.get("earliest_date")
    if not earliest_date or not isinstance(earliest_date, str):
        return now

    try:
        parsed = datetime.fromisoformat(earliest_date).replace(
            hour=BUSINESS_HOURS_START, minute=0, second=0, microsecond=0, tzinfo=UTC
        )
    except ValueError:
        return now

    return parsed if parsed > now else now


def _resolve_listing_day(detection: dict[str, Any], now: datetime) -> datetime:
    """Local midnight of the day calendar-listing should start from.

    Unlike `_resolve_window_start` (used for proposing a NEW meeting), this
    does NOT clamp to `now` - asking "was ist heute los" is valid even after
    today's midnight has already passed, whereas proposing a new meeting in
    the past never makes sense.
    """
    earliest_date = detection.get("earliest_date")
    if isinstance(earliest_date, str):
        try:
            parsed_date = datetime.fromisoformat(earliest_date)
        except ValueError:
            parsed_date = None
        if parsed_date is not None:
            return parsed_date.replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=LOCAL_TZ
            ).astimezone(UTC)

    return (
        now.astimezone(LOCAL_TZ).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
    )


def _resolve_daily_window(detection: dict[str, Any]) -> tuple[int, int]:
    """Resolve the time-of-day the user asked for (e.g. "vormittags") into a

    local hour-of-day range, falling back to `DEFAULT_DAILY_WINDOW` if the
    classification didn't extract one or extracted an unrecognized value.
    """
    time_of_day = detection.get("time_of_day")
    if not isinstance(time_of_day, str):
        return DEFAULT_DAILY_WINDOW
    return TIME_OF_DAY_RANGES.get(time_of_day, DEFAULT_DAILY_WINDOW)


def _merge_attendees(explicit: list[str] | None, text: str) -> list[str]:
    """Combine explicitly given attendees with real email addresses found in `text`."""
    found = _EMAIL_REGEX.findall(text)
    combined = [a.lower() for a in (explicit or [])] + [e.lower() for e in found]

    seen: set[str] = set()
    merged: list[str] = []
    for address in combined:
        if address not in seen:
            seen.add(address)
            merged.append(address)
    return merged


@dataclass
class AvailabilityAugmentation:
    """Result of checking calendar availability for a piece of text.

    `context` is extra prompt context to fold into the LLM request; `proposal`
    is a concrete, ready-to-open meeting suggestion (or None if not applicable).
    """

    context: str = ""
    proposal: MeetingProposalSchema | None = None


class SchedulingService:
    """Detects meeting requests in text and augments replies with real availability.

    Since the external RAG service only exposes a plain query/answer interface
    (no function-calling), the orchestration here is deterministic: classify,
    then look up availability, then hand the result back as extra prompt
    context and a structured proposal — rather than letting the LLM call tools
    itself or freely pick a time in prose.
    """

    def __init__(self, llm_service: LlmService, calendar_service: CalendarService) -> None:
        self._llm_service = llm_service
        self._calendar_service = calendar_service

    async def augment_with_availability(
        self, text: str, attendees: list[str] | None = None
    ) -> AvailabilityAugmentation:
        """Check `text` for a meeting request or a query about existing events

        and augment accordingly - a request for a NEW meeting gets a proposal
        built from real free slots; a question about EXISTING events gets
        those events listed. If a message were somehow both, the meeting
        request takes priority (a rare edge case, not otherwise handled).
        """
        if not text.strip():
            return AvailabilityAugmentation()

        detection = await self._detect_meeting_request(text)
        if detection is None:
            return AvailabilityAugmentation()

        if detection.get("is_meeting_request"):
            return await self._augment_with_meeting_proposal(text, detection, attendees)
        if detection.get("is_calendar_query"):
            return await self._augment_with_calendar_listing(detection)
        return AvailabilityAugmentation()

    async def _augment_with_meeting_proposal(
        self, text: str, detection: dict[str, Any], attendees: list[str] | None
    ) -> AvailabilityAugmentation:
        """Look up real availability for a NEW meeting request and build a proposal.

        Attendees are the union of explicitly passed addresses (e.g. To/Cc) and
        any real email addresses found in `text` itself. If any attendees are
        given, availability is checked for everyone via Graph's
        `findMeetingTimes`; otherwise only the user's own calendar is checked.
        """
        try:
            duration_minutes = int(detection.get("duration_minutes") or DEFAULT_DURATION_MINUTES)
        except (TypeError, ValueError):
            duration_minutes = DEFAULT_DURATION_MINUTES

        all_attendees = _merge_attendees(attendees, text)
        now = datetime.now(UTC)
        window_start = _resolve_window_start(detection, now)
        window_end = window_start + timedelta(days=LOOKAHEAD_DAYS)
        daily_window = _resolve_daily_window(detection)
        time_of_day = detection.get("time_of_day")

        try:
            if all_attendees:
                suggestions = await self._calendar_service.find_meeting_times(
                    all_attendees,
                    window_start,
                    window_end,
                    duration_minutes,
                    daily_window=daily_window,
                )
                slots = [(s.start, s.end) for s in suggestions]
            else:
                solo_slots = await self._calendar_service.get_availability(
                    window_start, window_end, duration_minutes, daily_window=daily_window
                )
                slots = [(s.start, s.end) for s in solo_slots]
        except (CalendarServiceError, GraphAuthError):
            logger.info("Skipping calendar augmentation: calendar unavailable.")
            return AvailabilityAugmentation()

        if not slots:
            return AvailabilityAugmentation()

        slot_lines = "\n".join(
            f"- {format_datetime_de(slot_start)}"
            f"-{slot_end.astimezone(LOCAL_TZ).strftime('%H:%M')} Uhr"
            for slot_start, slot_end in slots[:MAX_SUGGESTED_SLOTS]
        )
        intro = (
            "Verfuegbare Termine, an denen alle Empfaenger Zeit haben"
            if all_attendees
            else "Verfuegbare Termine im Kalender"
        )
        if window_start != now:
            intro += f" ab {format_datetime_de(window_start)} Uhr, wie angefragt"
        if isinstance(time_of_day, str) and time_of_day in TIME_OF_DAY_RANGES:
            intro += f" ({time_of_day}, wie gewuenscht)"
        context = (
            f"\n\n{intro} (nutze diese fuer einen konkreten "
            f"Terminvorschlag in der Antwort):\n{slot_lines}"
        )

        unknown_attendees = self._unknown_attendees(all_attendees)
        if unknown_attendees:
            context += (
                "\n\nHinweis: Fuer " + ", ".join(unknown_attendees) + " ist noch kein "
                "Kalender-Link bekannt - deren Verfuegbarkeit ist hier NICHT beruecksichtigt. "
                "Bitte in der Antwort darum bitten, den Kalender-Link zu teilen."
            )

        first_start, first_end = slots[0]
        proposal = MeetingProposalSchema(
            subject=str(detection.get("subject") or DEFAULT_SUBJECT),
            body=str(detection.get("description") or ""),
            start=first_start,
            end=first_end,
            attendees=all_attendees,
        )
        return AvailabilityAugmentation(context=context, proposal=proposal)

    async def _augment_with_calendar_listing(
        self, detection: dict[str, Any]
    ) -> AvailabilityAugmentation:
        """Answer "what's on my calendar" style questions by listing real,

        EXISTING events - as opposed to `_augment_with_meeting_proposal`,
        which searches for FREE slots to propose a new meeting. Never
        produces a `MeetingProposalSchema` (nothing is being proposed).
        """
        now = datetime.now(UTC)
        window_start = _resolve_listing_day(detection, now)
        window_end = window_start + timedelta(days=LOOKAHEAD_DAYS)

        try:
            events = await self._calendar_service.list_events(window_start, window_end)
        except (CalendarServiceError, GraphAuthError):
            logger.info("Skipping calendar listing: calendar unavailable.")
            return AvailabilityAugmentation()

        range_label = (
            f"{format_datetime_de(window_start)} Uhr und {format_datetime_de(window_end)} Uhr"
        )
        if not events:
            return AvailabilityAugmentation(
                context=f"\n\nDer Kalender enthaelt zwischen {range_label} keine Termine."
            )

        sorted_events = sorted(events, key=lambda e: e.start)
        event_lines = "\n".join(
            f"- {format_datetime_de(event.start)}"
            f"-{event.end.astimezone(LOCAL_TZ).strftime('%H:%M')} Uhr: {event.subject}"
            for event in sorted_events[:MAX_LISTED_EVENTS]
        )
        remaining = len(sorted_events) - MAX_LISTED_EVENTS
        if remaining > 0:
            event_lines += f"\n- (und {remaining} weitere Termine in diesem Zeitraum)"

        context = (
            f"\n\nTermine im Kalender zwischen {range_label} "
            f"(nutze diese, um die Frage zu beantworten):\n{event_lines}"
        )
        return AvailabilityAugmentation(context=context)

    def _unknown_attendees(self, attendees: list[str]) -> list[str]:
        """Which of `attendees` the calendar service has no link/data for.

        `unknown_attendees` isn't part of the calendar-service interface used
        by every backend - Graph doesn't need it (it can look anyone in the
        tenant up), only the ICS backend exposes it, since it depends on
        someone having shared a calendar link for it to know anything at all.
        """
        if not attendees:
            return []
        checker: Callable[[list[str]], list[str]] | None = getattr(
            self._calendar_service, "unknown_attendees", None
        )
        if checker is None:
            return []
        result: list[str] = checker(attendees)
        return result

    async def _detect_meeting_request(self, text: str) -> dict[str, Any] | None:
        try:
            raw_reply = await self._llm_service.chat(
                [
                    ChatMessageSchema(
                        role="user",
                        content=_CLASSIFICATION_PROMPT.format(text=text),
                    )
                ]
            )
        except LlmServiceError:
            logger.info("Skipping calendar augmentation: classification request failed.")
            return None

        try:
            parsed = json.loads(_extract_json(raw_reply))
        except ValueError:
            logger.info("Skipping calendar augmentation: could not parse classification reply.")
            return None

        if not isinstance(parsed, dict):
            return None
        return parsed
