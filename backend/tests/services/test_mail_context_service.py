from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.schemas.mail_schema import MailMessageSchema
from app.services.graph_mail_service import GraphMailService, MailServiceError
from app.services.llm_service import LlmService, LlmServiceError
from app.services.mail_context_service import MailContextService

MESSAGE = MailMessageSchema(
    id="msg-1",
    subject="Projektstand",
    sender_name="Max Muster",
    sender_address="max@example.com",
    received=datetime(2026, 9, 22, 12, 3, tzinfo=UTC),
    preview="Hallo, hier der aktuelle Stand.",
    is_read=False,
)


@pytest.fixture
def mock_llm() -> MagicMock:
    return MagicMock(spec=LlmService)


@pytest.fixture
def mock_mail() -> MagicMock:
    mail = MagicMock(spec=GraphMailService)
    mail.get_own_address = AsyncMock(return_value="ich@example.com")
    return mail


@pytest.fixture
def service(mock_llm, mock_mail) -> MailContextService:
    return MailContextService(llm_service=mock_llm, mail_service=mock_mail)


@pytest.mark.anyio
async def test_chat_context_skips_classification_without_mail_keywords(service, mock_llm):
    mock_llm.chat = AsyncMock()

    assert await service.build_chat_context("Wie spaet ist es?") == ""
    mock_llm.chat.assert_not_called()


@pytest.mark.anyio
async def test_chat_context_searches_mailbox(service, mock_llm, mock_mail):
    mock_llm.chat = AsyncMock(return_value='{"search_query": "Max Projekt", "since_date": null}')
    mock_mail.search_messages = AsyncMock(return_value=[MESSAGE])

    context = await service.build_chat_context("Was hat Max mir wegen dem Projekt geschrieben?")

    mock_mail.search_messages.assert_awaited_once_with("Max Projekt")
    assert "zur Suche 'Max Projekt', neueste zuerst" in context
    assert (
        "- Dienstag, 22.09.2026 14:03 Uhr - Max Muster: Projektstand [ungelesen] - "
        "Hallo, hier der aktuelle Stand." in context
    )


@pytest.mark.anyio
async def test_chat_context_inbox_overview_since_date(service, mock_llm, mock_mail):
    mock_llm.chat = AsyncMock(
        return_value='```json\n{"search_query": null, "since_date": "2026-09-21"}\n```'
    )
    mock_mail.list_recent = AsyncMock(return_value=[])

    context = await service.build_chat_context("Was ist seit Montag reingekommen?")

    since = mock_mail.list_recent.await_args.args[0]
    assert since.date().isoformat() == "2026-09-21"
    assert "keine passenden E-Mails gefunden" in context


@pytest.mark.anyio
async def test_chat_context_empty_when_mailbox_unavailable(service, mock_llm, mock_mail):
    mock_llm.chat = AsyncMock(return_value='{"search_query": "Bank", "since_date": null}')
    mock_mail.search_messages = AsyncMock(side_effect=MailServiceError("Not authenticated."))

    assert await service.build_chat_context("Hat die Bank sich gemeldet?") == ""


@pytest.mark.anyio
async def test_chat_context_overview_without_llm_when_classification_fails(
    service, mock_llm, mock_mail
):
    mock_llm.chat = AsyncMock(side_effect=LlmServiceError("down"))
    mock_mail.list_recent = AsyncMock(return_value=[MESSAGE])

    context = await service.build_chat_context("Habe ich neue Mails?")

    mock_mail.list_recent.assert_awaited_once()
    assert "Neu eingegangene E-Mails" in context


@pytest.mark.anyio
async def test_chat_context_empty_when_not_about_mails(service, mock_llm):
    mock_llm.chat = AsyncMock(return_value='{"search_query": null, "since_date": null}')

    assert await service.build_chat_context("schreib mir eine nachricht bitte") == ""


@pytest.mark.anyio
async def test_reply_context_prefers_thread(service, mock_mail):
    thread_message = MESSAGE.model_copy(update={"body": "Voller Text der alten Mail."})
    mock_mail.thread_messages = AsyncMock(return_value=[thread_message])
    mock_mail.messages_from = AsyncMock()

    context = await service.build_reply_context("conv-1", "max@example.com")

    mock_mail.messages_from.assert_not_called()
    assert "--- Dienstag, 22.09.2026 14:03 Uhr, von Max Muster, Betreff: Projektstand" in context
    assert "Voller Text der alten Mail." in context


@pytest.mark.anyio
async def test_reply_context_falls_back_to_sender(service, mock_mail):
    mock_mail.thread_messages = AsyncMock(return_value=[])
    mock_mail.messages_from = AsyncMock(return_value=[MESSAGE])

    context = await service.build_reply_context("conv-1", "max@example.com")

    mock_mail.messages_from.assert_awaited_once_with("max@example.com")
    assert "Hallo, hier der aktuelle Stand." in context


@pytest.mark.anyio
async def test_reply_context_empty_without_ids_or_on_error(service, mock_mail):
    assert await service.build_reply_context(None, None) == ""

    mock_mail.thread_messages = AsyncMock(side_effect=MailServiceError("down"))
    assert await service.build_reply_context("conv-1", None) == ""


@pytest.mark.anyio
async def test_chat_context_searches_names_even_if_llm_suggests_overview(
    service, mock_llm, mock_mail
):
    # The small chat model once answered this with an inbox overview for today.
    mock_llm.chat = AsyncMock(
        return_value='{"is_inbox_overview": true, "search_query": null, "since_date": "2026-09-25"}'
    )
    mock_mail.search_messages = AsyncMock(return_value=[MESSAGE])
    mock_mail.list_recent = AsyncMock()

    await service.build_chat_context("Was hat Sören Mars zuletzt geschrieben?")

    mock_mail.search_messages.assert_awaited_once_with("Sören Mars")
    mock_mail.list_recent.assert_not_called()


@pytest.mark.anyio
async def test_chat_context_drops_filler_words_from_llm_query(service, mock_llm, mock_mail):
    mock_llm.chat = AsyncMock(
        return_value='{"search_query": "Mail von Sparkasse heute", "since_date": null}'
    )
    mock_mail.search_messages = AsyncMock(return_value=[])

    await service.build_chat_context("Hat die Sparkasse heute eine Mail geschickt?")

    mock_mail.search_messages.assert_awaited_once_with("Sparkasse")


@pytest.mark.anyio
async def test_chat_context_sorts_newest_first_and_marks_own_mails(service, mock_llm, mock_mail):
    own_reply = MESSAGE.model_copy(
        update={
            "id": "msg-2",
            "sender_name": "Ich",
            "sender_address": "Ich@Example.com",
            "received": datetime(2026, 9, 23, 8, 0, tzinfo=UTC),
            "subject": "AW: Projektstand",
        }
    )
    mock_llm.chat = AsyncMock(return_value='{"search_query": "Max", "since_date": null}')
    mock_mail.search_messages = AsyncMock(return_value=[MESSAGE, own_reply])

    context = await service.build_chat_context("Was hat Max geschrieben?")

    lines = [line for line in context.splitlines() if line.startswith("- ")]
    assert lines[0].startswith("- Mittwoch, 23.09.2026 10:00 Uhr - Ich (von dir): AW: Projektstand")
    assert lines[1].startswith("- Dienstag, 22.09.2026 14:03 Uhr - Max Muster: Projektstand")
