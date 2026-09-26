import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from app.api.schemas.mail_schema import MailMessageSchema
from app.services.graph_auth_service import GraphAuthError, GraphAuthService
from app.services.graph_calendar_service import GRAPH_BASE_URL

logger = logging.getLogger(__name__)

_LIST_FIELDS = "id,subject,from,receivedDateTime,bodyPreview,webLink,isRead"
_BODY_FIELDS = f"{_LIST_FIELDS},body"
# Per-mail cap for full bodies, so a long thread doesn't overflow the prompt.
MAX_BODY_CHARS = 1500


class MailServiceError(RuntimeError):
    pass


def _escape_odata(value: str) -> str:
    return value.replace("'", "''")


def _parse_message(item: dict[str, Any]) -> MailMessageSchema:
    sender = (item.get("from") or {}).get("emailAddress") or {}
    body = (item.get("body") or {}).get("content")
    if body is not None:
        body = body.strip()
        if len(body) > MAX_BODY_CHARS:
            body = body[:MAX_BODY_CHARS].rstrip() + " [...]"
    return MailMessageSchema(
        id=item["id"],
        subject=item.get("subject") or "(Kein Betreff)",
        sender_name=sender.get("name"),
        sender_address=sender.get("address"),
        received=datetime.fromisoformat(item["receivedDateTime"].replace("Z", "+00:00")),
        preview=(item.get("bodyPreview") or "").strip(),
        body=body,
        web_link=item.get("webLink"),
        is_read=bool(item.get("isRead", True)),
    )


class GraphMailService:
    """Read-only access to the user's mailbox via Microsoft Graph (Mail.Read)."""

    def __init__(self, auth_service: GraphAuthService) -> None:
        self._auth_service = auth_service
        self._client = httpx.AsyncClient(base_url=GRAPH_BASE_URL, timeout=httpx.Timeout(30.0))
        self._own_address: str | None = None

    async def aclose(self) -> None:
        await self._client.aclose()

    def _auth_headers(self, with_text_body: bool = False) -> dict[str, str]:
        try:
            token = self._auth_service.get_valid_access_token()
        except GraphAuthError as exc:
            raise MailServiceError(str(exc)) from exc
        headers = {"Authorization": f"Bearer {token}"}
        if with_text_body:
            headers["Prefer"] = 'outlook.body-content-type="text"'
        return headers

    async def _get_messages(
        self, url: str, params: dict[str, str], with_text_body: bool = False
    ) -> list[MailMessageSchema]:
        headers = self._auth_headers(with_text_body)
        try:
            response = await self._client.get(url, params=params, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Graph mail request failed: %s", exc)
            raise MailServiceError(f"Failed to read mails: {exc}") from exc
        return [_parse_message(item) for item in response.json().get("value", [])]

    async def get_own_address(self) -> str | None:
        """The signed-in user's address (cached), to tell own mails apart."""
        if self._own_address is None:
            headers = self._auth_headers()
            try:
                response = await self._client.get(
                    "/me", params={"$select": "mail,userPrincipalName"}, headers=headers
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.error("Graph /me request failed: %s", exc)
                raise MailServiceError(f"Failed to read own profile: {exc}") from exc
            data = response.json()
            # Personal accounts often have no `mail`, only the UPN (= address).
            address = data.get("mail") or data.get("userPrincipalName")
            self._own_address = address.lower() if address else None
        return self._own_address

    async def search_messages(self, query: str, top: int = 10) -> list[MailMessageSchema]:
        """Full-text search across all folders (subject, body, sender, ...).

        Graph returns $search results by relevance and doesn't allow
        $orderby together with $search.
        """
        cleaned = query.replace('"', " ").strip()
        return await self._get_messages(
            "/me/messages",
            {"$search": f'"{cleaned}"', "$top": str(top), "$select": _LIST_FIELDS},
        )

    async def list_recent(self, since: datetime, top: int = 15) -> list[MailMessageSchema]:
        """Newest inbox mails received at or after `since`, newest first."""
        since_utc = since.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        return await self._get_messages(
            "/me/mailFolders/inbox/messages",
            {
                "$filter": f"receivedDateTime ge {since_utc}",
                "$orderby": "receivedDateTime desc",
                "$top": str(top),
                "$select": _LIST_FIELDS,
            },
        )

    async def thread_messages(self, conversation_id: str, top: int = 6) -> list[MailMessageSchema]:
        """Mails of one conversation, with plain-text bodies, oldest first."""
        messages = await self._get_messages(
            "/me/messages",
            {
                "$filter": f"conversationId eq '{_escape_odata(conversation_id)}'",
                "$top": str(top),
                "$select": _BODY_FIELDS,
            },
            with_text_body=True,
        )
        return sorted(messages, key=lambda m: m.received)

    async def messages_from(self, address: str, top: int = 5) -> list[MailMessageSchema]:
        """Latest mails from one sender, with plain-text bodies, oldest first."""
        messages = await self._get_messages(
            "/me/messages",
            {
                # Graph only accepts $orderby with $filter when the sort
                # property also appears first in the filter.
                "$filter": (
                    "receivedDateTime ge 1900-01-01T00:00:00Z and "
                    f"from/emailAddress/address eq '{_escape_odata(address)}'"
                ),
                "$orderby": "receivedDateTime desc",
                "$top": str(top),
                "$select": _BODY_FIELDS,
            },
            with_text_body=True,
        )
        return sorted(messages, key=lambda m: m.received)
