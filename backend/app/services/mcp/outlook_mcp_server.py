import logging
import os
import sys
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import httpx
from mcp.server.fastmcp import FastMCP
from msal import ConfidentialClientApplication  # type: ignore[import-untyped]

# Setup logging to stderr since stdout is used for JSON-RPC communication in stdio transport
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("outlook_mcp_server")

# Initialize FastMCP Server
mcp = FastMCP("Outlook Calendar Server")


class MicrosoftGraphError(Exception):
    """Raised when Microsoft Graph API requests fail."""

    pass


class NoCredentialsError(Exception):
    """Raised when Microsoft credentials are not configured."""

    pass


class MicrosoftGraphClient:
    """Helper client to authenticate and communicate with Microsoft Graph API."""

    def __init__(self) -> None:
        self.access_token = os.getenv("MICROSOFT_GRAPH_ACCESS_TOKEN")
        self.client_id = os.getenv("MICROSOFT_CLIENT_ID")
        self.client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
        self.tenant_id = os.getenv("MICROSOFT_TENANT_ID", "common")
        # For client credentials flow, we need a specific user mailbox
        self.user_email = os.getenv("MICROSOFT_USER_EMAIL")

        self._token_expires_at: datetime | None = None
        self._cached_token: str | None = None

    def get_token(self) -> str:
        """Acquires a Microsoft Graph access token."""
        # 1. Check for manual developer token
        if self.access_token:
            logger.info("Using manually provided MICROSOFT_GRAPH_ACCESS_TOKEN.")
            return self.access_token

        # 2. Check for App registration credentials (OBO or Client Credentials)
        if not (self.client_id and self.client_secret):
            raise NoCredentialsError(
                "Microsoft Graph API credentials not configured. Please define "
                "MICROSOFT_GRAPH_ACCESS_TOKEN or MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET."
            )

        # Token caching logic
        if (
            self._cached_token
            and self._token_expires_at
            and datetime.now(UTC) < self._token_expires_at
        ):
            return self._cached_token

        try:
            logger.info("Requesting access token via MSAL Client Credentials Flow.")
            authority = f"https://login.microsoftonline.com/{self.tenant_id}"
            app = ConfidentialClientApplication(
                client_id=self.client_id, client_credential=self.client_secret, authority=authority
            )

            # Scopes for client credentials flow must be application permissions
            scopes = ["https://graph.microsoft.com/.default"]
            result = app.acquire_token_for_client(scopes=scopes)

            if "access_token" in result:
                self._cached_token = result["access_token"]
                expires_in = result.get("expires_in", 3599)
                self._token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in - 60)
                return self._cached_token
            else:
                error_msg = result.get("error_description", result.get("error", "Unknown error"))
                raise MicrosoftGraphError(f"Token acquisition failed: {error_msg}")
        except Exception as e:
            if not isinstance(e, MicrosoftGraphError):
                raise MicrosoftGraphError(f"MSAL authentication exception: {e}") from e
            raise

    def get_headers(self) -> dict[str, str]:
        token = self.get_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def _get_base_url(self) -> str:
        # If user_email is specified, we query that user's endpoint, otherwise default to '/me'
        # Note: client credentials flow requires user-specific path e.g. /users/{id_or_email}
        if self.user_email:
            return f"https://graph.microsoft.com/v1.0/users/{self.user_email}"
        return "https://graph.microsoft.com/v1.0/me"

    async def list_events(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Fetch events from Microsoft Graph API."""
        url = f"{self._get_base_url()}/calendarView"
        params = {
            "startDateTime": start_date,
            "endDateTime": end_date,
            "$select": "id,subject,bodyPreview,start,end,location,attendees",
            "$orderby": "start/dateTime",
            "$top": "50",
        }

        async with httpx.AsyncClient() as client:
            headers = self.get_headers()
            response = await client.get(url, headers=headers, params=params, timeout=15.0)

            if response.status_code != 200:
                raise MicrosoftGraphError(
                    f"Failed to fetch calendar events: {response.status_code} - {response.text}"
                )

            val = response.json().get("value", [])
            return cast(list[dict[str, Any]], val)

    async def create_event(self, event_data: dict[str, Any]) -> dict[str, Any]:
        """Create a new event in Microsoft Graph Calendar."""
        url = f"{self._get_base_url()}/events"

        async with httpx.AsyncClient() as client:
            headers = self.get_headers()
            response = await client.post(url, headers=headers, json=event_data, timeout=15.0)

            if response.status_code != 201:
                raise MicrosoftGraphError(
                    f"Failed to create event: {response.status_code} - {response.text}"
                )

            return cast(dict[str, Any], response.json())


# Initialize Graph Client
graph_client = MicrosoftGraphClient()

# --- MOCK DATA FOR TESTING WITHOUT CREDENTIALS ---
MOCK_EVENTS: list[dict[str, Any]] = [
    {
        "id": "mock-event-1",
        "subject": "Daily Standup Meeting",
        "bodyPreview": "Short team sync on project status.",
        "start": {"dateTime": "2026-07-13T09:00:00", "timeZone": "Europe/Berlin"},
        "end": {"dateTime": "2026-07-13T09:30:00", "timeZone": "Europe/Berlin"},
        "location": {"displayName": "Microsoft Teams"},
        "attendees": [
            {"emailAddress": {"name": "Kevin", "address": "kevin@example.com"}},
            {"emailAddress": {"name": "Ben", "address": "ben@example.com"}},
            {"emailAddress": {"name": "Ollie Assistant", "address": "ollie@example.com"}},
        ],
    },
    {
        "id": "mock-event-2",
        "subject": "Lunch with Kevin",
        "bodyPreview": "Discussing upcoming features and calendar integration details.",
        "start": {"dateTime": "2026-07-13T12:00:00", "timeZone": "Europe/Berlin"},
        "end": {"dateTime": "2026-07-13T13:00:00", "timeZone": "Europe/Berlin"},
        "location": {"displayName": "Local Restaurant"},
        "attendees": [
            {"emailAddress": {"name": "Kevin", "address": "kevin@example.com"}},
            {"emailAddress": {"name": "Ben", "address": "ben@example.com"}},
        ],
    },
    {
        "id": "mock-event-3",
        "subject": "Ollie Project Sync & Review",
        "bodyPreview": "Weekly review of LLM and Vector Store capabilities.",
        "start": {"dateTime": "2026-07-14T14:00:00", "timeZone": "Europe/Berlin"},
        "end": {"dateTime": "2026-07-14T15:00:00", "timeZone": "Europe/Berlin"},
        "location": {"displayName": "Meeting Room Berlin"},
        "attendees": [
            {"emailAddress": {"name": "Kevin", "address": "kevin@example.com"}},
            {"emailAddress": {"name": "Ben", "address": "ben@example.com"}},
            {"emailAddress": {"name": "Sarah", "address": "sarah@example.com"}},
        ],
    },
]


def format_event_for_llm(event: dict[str, Any]) -> str:
    """Utility to pretty format event info for the LLM response."""
    start_time = event.get("start", {}).get("dateTime", "")
    end_time = event.get("end", {}).get("dateTime", "")
    location = event.get("location", {}).get("displayName", "N/A")
    attendees_list = [
        att.get("emailAddress", {}).get("name", att.get("emailAddress", {}).get("address", ""))
        for att in event.get("attendees", [])
    ]
    attendees_str = ", ".join(filter(None, attendees_list)) or "None"

    return (
        f"📅 Subject: {event.get('subject')}\n"
        f"   Time: {start_time} to {end_time}\n"
        f"   Location: {location}\n"
        f"   Attendees: {attendees_str}\n"
        f"   Description: {event.get('bodyPreview', 'No description')}\n"
    )


# --- MCP TOOLS ---


@mcp.tool()
async def list_calendar_events(start_date: str | None = None, end_date: str | None = None) -> str:
    """Lists calendar events for the user within a given date range.

    Args:
        start_date: The start ISO datetime string (e.g. '2026-07-13T00:00:00Z').
            Defaults to today.
        end_date: The end ISO datetime string (e.g. '2026-07-14T23:59:59Z').
            Defaults to 7 days from today.
    """
    # Defaults
    now = datetime.now(UTC)
    if not start_date:
        start_date = now.strftime("%Y-%m-%dT00:00:00Z")
    if not end_date:
        end_date = (now + timedelta(days=7)).strftime("%Y-%m-%dT23:59:59Z")

    logger.info(f"Listing calendar events from {start_date} to {end_date}")

    try:
        events = await graph_client.list_events(start_date, end_date)
        if not events:
            return f"No events found between {start_date} and {end_date}."

        formatted_events = [format_event_for_llm(e) for e in events]
        return "Here are the calendar events found:\n\n" + "\n".join(formatted_events)

    except (NoCredentialsError, MicrosoftGraphError) as e:
        logger.warning("Graph API connection failed (%s). Falling back to Mock Calendar Data.", e)
        # Filter mock events based on simple datetime string comparison
        # (This mock parsing is simple since mock dates are hardcoded for 13.07.2026 and 14.07.2026)
        fallback_msg = (
            "⚠️ [MOCK MODE] Graph API Credentials not configured. "
            "Showing simulated calendar events:\n\n"
        )
        formatted_events = [format_event_for_llm(e) for e in MOCK_EVENTS]
        return fallback_msg + "\n".join(formatted_events)


@mcp.tool()
async def create_calendar_event(
    subject: str,
    start_time: str,
    end_time: str,
    body: str = "",
    location: str = "",
    attendees: list[str] | None = None,
) -> str:
    """Creates a new event in the user's Outlook calendar.

    Args:
        subject: The title of the meeting / calendar event.
        start_time: ISO start datetime string (e.g., '2026-07-13T14:00:00' in local time).
        end_time: ISO end datetime string (e.g., '2026-07-13T15:00:00' in local time).
        body: Optional description or meeting agenda.
        location: Optional meeting location or online meeting link.
        attendees: Optional list of email addresses of attendees to invite.
    """
    logger.info(f"Creating calendar event: '{subject}' from {start_time} to {end_time}")

    # Construct MS Graph API compatible body
    formatted_attendees = []
    if attendees:
        for email in attendees:
            formatted_attendees.append({"emailAddress": {"address": email}, "type": "required"})

    event_payload = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": body},
        "start": {
            "dateTime": start_time,
            "timeZone": "Europe/Berlin",  # Customize or dynamically infer
        },
        "end": {"dateTime": end_time, "timeZone": "Europe/Berlin"},
        "location": {"displayName": location},
        "attendees": formatted_attendees,
    }

    try:
        created_event = await graph_client.create_event(event_payload)
        return (
            f"Successfully created event in Outlook!\n"
            f"ID: {created_event.get('id')}\n"
            f"Subject: {created_event.get('subject')}\n"
            f"Start: {created_event.get('start', {}).get('dateTime')}\n"
            f"End: {created_event.get('end', {}).get('dateTime')}"
        )
    except (NoCredentialsError, MicrosoftGraphError) as ex:
        logger.warning(
            f"Graph API event creation failed ({ex}). Falling back to Mock Event Simulation."
        )
        # Simulate successful creation
        simulated_id = f"mock-created-{int(datetime.now(UTC).timestamp())}"
        mock_event = {
            "id": simulated_id,
            "subject": subject,
            "bodyPreview": body,
            "start": {"dateTime": start_time, "timeZone": "Europe/Berlin"},
            "end": {"dateTime": end_time, "timeZone": "Europe/Berlin"},
            "location": {"displayName": location},
            "attendees": [
                {"emailAddress": {"name": email.split("@")[0].capitalize(), "address": email}}
                for email in (attendees or [])
            ],
        }

        # Add to mock events in memory so user can list it in the same run
        MOCK_EVENTS.append(mock_event)

        return (
            "⚠️ [MOCK MODE] Graph API Credentials not configured. "
            "Simulated calendar event creation:\n\n"
            "Successfully simulated event creation!\n"
            f"ID: {simulated_id}\n"
            f"Subject: {subject}\n"
            f"Start: {start_time}\n"
            f"End: {end_time}\n"
            f"Attendees: {', '.join(attendees) if attendees else 'None'}\n"
            f"Location: {location}"
        )


@mcp.tool()
async def check_calendar_availability(start_time: str, end_time: str) -> str:
    """Checks if the user has any events during a specific time window.

    Args:
        start_time: ISO start datetime string (e.g., '2026-07-13T09:00:00').
        end_time: ISO end datetime string (e.g., '2026-07-13T10:00:00').
    """
    logger.info(f"Checking availability from {start_time} to {end_time}")

    try:
        events = await graph_client.list_events(start_time, end_time)
        if events:
            conflicts = "\n".join(
                [
                    f"- {e.get('subject')} ({e.get('start', {}).get('dateTime')} "
                    f"bis {e.get('end', {}).get('dateTime')})"
                    for e in events
                ]
            )
            return f"The time slot is BUSY. Found conflicts:\n{conflicts}"
        return "The time slot is FREE. No conflicts found."
    except (NoCredentialsError, MicrosoftGraphError) as ex:
        logger.warning(
            "Graph API availability check failed (%s). Falling back to Mock Check.", ex
        )

        # Mock checking: Simple datetime overlap check for mock events
        try:
            check_start = datetime.fromisoformat(start_time.replace("Z", ""))
            check_end = datetime.fromisoformat(end_time.replace("Z", ""))
        except Exception:
            return "Error: Invalid datetime format. Please use ISO format e.g. YYYY-MM-DDTHH:MM:SS"

        mock_conflicts = []
        for event in MOCK_EVENTS:
            # We cast these because they are inside a dict[str, Any]
            start_dict = cast(dict[str, Any], event.get("start", {}))
            end_dict = cast(dict[str, Any], event.get("end", {}))
            e_start_str = str(start_dict.get("dateTime", ""))
            e_end_str = str(end_dict.get("dateTime", ""))
            e_start = datetime.fromisoformat(e_start_str)
            e_end = datetime.fromisoformat(e_end_str)

            # Check overlap
            if max(check_start, e_start) < min(check_end, e_end):
                mock_conflicts.append(
                    f"- {event['subject']} ({e_start_str} bis {e_end_str})"
                )

        if mock_conflicts:
            return "⚠️ [MOCK MODE] The time slot is BUSY. Simulated conflicts:\n" + "\n".join(
                mock_conflicts
            )
        return "⚠️ [MOCK MODE] The time slot is FREE. No simulated conflicts found."


if __name__ == "__main__":
    # Start the FastMCP server over stdio transport (stdin/stdout)
    mcp.run()
