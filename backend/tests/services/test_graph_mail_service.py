from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.graph_auth_service import GraphAuthError, GraphAuthService
from app.services.graph_mail_service import MAX_BODY_CHARS, GraphMailService, MailServiceError

RAW_MESSAGE = {
    "id": "msg-1",
    "subject": "Projektstand",
    "from": {"emailAddress": {"name": "Max Muster", "address": "max@example.com"}},
    "receivedDateTime": "2026-09-22T12:03:00Z",
    "bodyPreview": "Hallo, hier der aktuelle Stand...",
    "webLink": "https://outlook.live.com/mail/id/msg-1",
    "isRead": False,
}


def _json_response(data: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = data
    response.raise_for_status.return_value = None
    return response


@pytest.fixture
def mock_auth() -> MagicMock:
    auth = MagicMock(spec=GraphAuthService)
    auth.get_valid_access_token.return_value = "test-access-token"
    return auth


@pytest.fixture
def mail_service(mock_auth: MagicMock) -> GraphMailService:
    service = GraphMailService(mock_auth)
    service._client.get = AsyncMock(return_value=_json_response({"value": [RAW_MESSAGE]}))
    return service


@pytest.mark.anyio
async def test_search_messages_parses_response(mail_service):
    messages = await mail_service.search_messages('Projekt "Alpha"')

    assert len(messages) == 1
    message = messages[0]
    assert message.subject == "Projektstand"
    assert message.sender_name == "Max Muster"
    assert message.sender_address == "max@example.com"
    assert message.received == datetime(2026, 9, 22, 12, 3, tzinfo=UTC)
    assert message.is_read is False
    assert message.body is None
    args, kwargs = mail_service._client.get.call_args
    assert args[0] == "/me/messages"
    # Inner quotes would break the KQL phrase, so they are dropped.
    assert kwargs["params"]["$search"] == '"Projekt  Alpha"'
    assert "$orderby" not in kwargs["params"]


@pytest.mark.anyio
async def test_list_recent_filters_inbox_by_date(mail_service):
    await mail_service.list_recent(datetime(2026, 9, 22, 0, 0, tzinfo=UTC))

    args, kwargs = mail_service._client.get.call_args
    assert args[0] == "/me/mailFolders/inbox/messages"
    assert kwargs["params"]["$filter"] == "receivedDateTime ge 2026-09-22T00:00:00Z"
    assert kwargs["params"]["$orderby"] == "receivedDateTime desc"


@pytest.mark.anyio
async def test_thread_messages_requests_text_bodies_and_sorts_oldest_first(mail_service):
    newer = {**RAW_MESSAGE, "id": "msg-2", "receivedDateTime": "2026-09-23T08:00:00Z"}
    long_body = {**RAW_MESSAGE, "body": {"content": "x" * (MAX_BODY_CHARS + 50)}}
    mail_service._client.get = AsyncMock(return_value=_json_response({"value": [newer, long_body]}))

    messages = await mail_service.thread_messages("conv'1")

    assert [m.id for m in messages] == ["msg-1", "msg-2"]
    assert messages[0].body is not None
    assert messages[0].body.endswith("[...]")
    _, kwargs = mail_service._client.get.call_args
    assert kwargs["params"]["$filter"] == "conversationId eq 'conv''1'"
    assert kwargs["headers"]["Prefer"] == 'outlook.body-content-type="text"'


@pytest.mark.anyio
async def test_messages_from_filters_by_sender(mail_service):
    await mail_service.messages_from("max@example.com")

    _, kwargs = mail_service._client.get.call_args
    assert kwargs["params"]["$filter"].endswith("from/emailAddress/address eq 'max@example.com'")
    assert kwargs["params"]["$orderby"] == "receivedDateTime desc"


@pytest.mark.anyio
async def test_auth_failure_raises_mail_error(mock_auth):
    mock_auth.get_valid_access_token.side_effect = GraphAuthError("Not authenticated.")
    service = GraphMailService(mock_auth)

    with pytest.raises(MailServiceError, match="Not authenticated"):
        await service.search_messages("Projekt")


@pytest.mark.anyio
async def test_http_error_raises_mail_error(mail_service):
    mail_service._client.get = AsyncMock(side_effect=httpx.ConnectTimeout("timed out"))

    with pytest.raises(MailServiceError, match="Failed to read mails"):
        await mail_service.list_recent(datetime(2026, 9, 22, tzinfo=UTC))


@pytest.mark.anyio
async def test_get_own_address_uses_upn_and_caches(mail_service):
    mail_service._client.get = AsyncMock(
        return_value=_json_response({"mail": None, "userPrincipalName": "Ich@Outlook.de"})
    )

    assert await mail_service.get_own_address() == "ich@outlook.de"
    assert await mail_service.get_own_address() == "ich@outlook.de"
    mail_service._client.get.assert_called_once()
