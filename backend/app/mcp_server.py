import logging
from datetime import datetime
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.core.config import settings
from app.services.calendar_mock_service import MockCalendarService, MockGraphAuthService
from app.services.graph_auth_service import GraphAuthService
from app.services.graph_calendar_service import GraphCalendarService
from app.services.ics_calendar_service import IcsCalendarService, IcsCalendarStore

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "ollie-calendar",
    instructions=(
        "Tools for reading the authenticated user's calendar, via a published "
        "Outlook ICS feed by default (see CALENDAR_BACKEND) - no Azure AD or "
        "OAuth required in that mode. Falls back to Microsoft Graph if "
        "CALENDAR_BACKEND=graph is configured."
    ),
)

_calendar_service: GraphCalendarService | IcsCalendarService | MockCalendarService

if settings.calendar_mock_mode:
    logger.warning("CALENDAR_MOCK_MODE is active - tools return fake data.")
    _calendar_service = MockCalendarService(MockGraphAuthService())
elif settings.calendar_backend == "graph":
    _calendar_service = GraphCalendarService(GraphAuthService())
else:
    _calendar_service = IcsCalendarService(IcsCalendarStore(settings.ics_store_path))


@mcp.tool()
async def list_events(start: str, end: str) -> list[dict[str, Any]]:
    """List calendar events between two ISO 8601 timestamps."""
    events = await _calendar_service.list_events(
        datetime.fromisoformat(start), datetime.fromisoformat(end)
    )
    return [event.model_dump(mode="json") for event in events]


@mcp.tool()
async def check_availability(
    start: str, end: str, duration_minutes: int = 30
) -> list[dict[str, Any]]:
    """Find free time slots of a given duration between two ISO 8601 timestamps."""
    slots = await _calendar_service.get_availability(
        datetime.fromisoformat(start), datetime.fromisoformat(end), duration_minutes
    )
    return [slot.model_dump(mode="json") for slot in slots]


@mcp.tool()
async def find_meeting_times(
    attendees: list[str],
    start: str,
    end: str,
    duration_minutes: int = 30,
    max_candidates: int = 5,
) -> list[dict[str, Any]]:
    """Find meeting slots where every given attendee (plus the user) is free.

    Only works for attendees within the same Microsoft 365 tenant.
    """
    suggestions = await _calendar_service.find_meeting_times(
        attendees,
        datetime.fromisoformat(start),
        datetime.fromisoformat(end),
        duration_minutes,
        max_candidates,
    )
    return [suggestion.model_dump(mode="json") for suggestion in suggestions]


@mcp.tool()
async def create_event(
    subject: str,
    start: str,
    end: str,
    attendees: list[str] | None = None,
    body: str = "",
) -> dict[str, Any]:
    """Create a new calendar event."""
    event = await _calendar_service.create_event(
        subject=subject,
        start=datetime.fromisoformat(start),
        end=datetime.fromisoformat(end),
        attendees=attendees,
        body=body,
    )
    return event.model_dump(mode="json")


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
