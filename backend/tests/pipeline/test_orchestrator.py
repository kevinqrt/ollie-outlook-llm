import asyncio
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from app.api.schemas.pipeline_schema import PipelineEvent
from app.pipeline import orchestrator


class _FakeChatModel(FakeMessagesListChatModel):
    """FakeMessagesListChatModel lehnt bind_tools() standardmäßig ab (NotImplementedError).

    create_react_agent ruft bind_tools() aber immer auf, auch wenn die konkreten
    Tool-Aufrufe hier direkt über kanonische AIMessage(tool_calls=...) vorgegeben
    werden. Also Tool-Bindung einfach als No-Op behandeln.
    """

    def bind_tools(self, _tools: object, **_kwargs: object) -> "_FakeChatModel":
        return self


class _FakeRagHttpClient:
    async def __aenter__(self) -> "_FakeRagHttpClient":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


@dataclass
class Mocks:
    fake_rag_client: _FakeRagHttpClient
    create_session: AsyncMock
    delete_session: AsyncMock
    query_session: AsyncMock


@contextmanager
def patched_pipeline(fake_model: FakeMessagesListChatModel):
    """Patcht LLM- und RAG-Anbindung, damit die Pipeline ohne Netzwerk läuft."""
    fake_rag_client = _FakeRagHttpClient()
    create_session = AsyncMock(return_value="session-123")
    delete_session = AsyncMock()
    query_session = AsyncMock()

    with ExitStack() as stack:
        stack.enter_context(patch.object(orchestrator, "build_chat_model", return_value=fake_model))
        stack.enter_context(
            patch.object(orchestrator.rag_client, "build_client", return_value=fake_rag_client)
        )
        stack.enter_context(
            patch.object(orchestrator.rag_client, "create_rag_session", create_session)
        )
        stack.enter_context(
            patch.object(orchestrator.rag_client, "delete_rag_session", delete_session)
        )
        stack.enter_context(
            patch.object(orchestrator.rag_client, "query_rag_session", query_session)
        )
        yield Mocks(fake_rag_client, create_session, delete_session, query_session)


def _run(email_text: str) -> list[PipelineEvent]:
    async def _collect() -> list[PipelineEvent]:
        return [event async for event in orchestrator.run_pipeline(email_text)]

    return asyncio.run(_collect())


def test_happy_path_without_tool_call():
    fake_model = _FakeChatModel(
        responses=[
            AIMessage(content='["Kernfragen identifizieren", "Antwort formulieren"]'),
            AIMessage(content="Kernfrage: Terminverschiebung auf 14 Uhr"),
            AIMessage(content="Sehr geehrte Damen und Herren,\n\nja, 14 Uhr passt.\n\nMfG"),
        ]
    )

    with patched_pipeline(fake_model) as mocks:
        events = _run("Koennen wir das Meeting auf 14 Uhr verschieben?")

    types = [e.type for e in events]
    assert types == [
        "plan_ready",
        "step_started",
        "step_completed",
        "step_started",
        "step_completed",
        "done",
    ]
    assert events[0].steps == ["Kernfragen identifizieren", "Antwort formulieren"]
    assert events[-1].final_reply.startswith("Sehr geehrte Damen und Herren")
    mocks.create_session.assert_awaited_once_with(
        mocks.fake_rag_client, "Koennen wir das Meeting auf 14 Uhr verschieben?"
    )
    mocks.delete_session.assert_awaited_once_with(mocks.fake_rag_client, "session-123")
    mocks.query_session.assert_not_awaited()


def test_happy_path_with_tool_call():
    fake_model = _FakeChatModel(
        responses=[
            AIMessage(content='["Informationen pruefen"]'),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_email_context",
                        "args": {"query": "Ist der Termin frei?"},
                        "id": "call_1",
                    }
                ],
            ),
            AIMessage(content="Laut Pruefung ist der Termin frei."),
        ]
    )

    with patched_pipeline(fake_model) as mocks:
        mocks.query_session.return_value = "Der Termin ist frei."
        events = _run("Ist der Termin am Montag noch frei?")

    step_completed = [e for e in events if e.type == "step_completed"]
    assert len(step_completed) == 1
    assert step_completed[0].result == "Laut Pruefung ist der Termin frei."

    mocks.query_session.assert_awaited_once_with(
        mocks.fake_rag_client, "session-123", "Ist der Termin frei?"
    )
    mocks.delete_session.assert_awaited_once()


def test_malformed_plan_falls_back_to_default_steps():
    fake_model = _FakeChatModel(
        responses=[
            AIMessage(content="Klar, hier mein Plan: erstens dies, zweitens das."),
            AIMessage(content="Ergebnis 1"),
            AIMessage(content="Ergebnis 2"),
            AIMessage(content="Finale Antwort"),
        ]
    )

    with patched_pipeline(fake_model):
        events = _run("Testmail")

    plan_ready = next(e for e in events if e.type == "plan_ready")
    assert plan_ready.steps == [
        "Kernfragen der E-Mail identifizieren",
        "Antwortpunkte zu jeder Frage entwerfen",
        "Antwort professionell formulieren",
    ]
    assert events[-1].type == "done"
    assert events[-1].final_reply == "Finale Antwort"


def test_step_falls_back_to_plain_call_when_agent_returns_empty_content():
    # gpt-oss liefert über den DGX-Tunnel bei gebundenen Tools manchmal leeren
    # Inhalt zurück (finish_reason='stop', aber kein Text). Nach MAX_STEP_ATTEMPTS
    # erfolglosen Agent-Versuchen soll auf einen Aufruf ohne Tool umgeschaltet werden.
    fake_model = _FakeChatModel(
        responses=[
            AIMessage(content='["Nur ein Schritt"]'),
            AIMessage(content=""),
            AIMessage(content=""),
            AIMessage(content="Fallback-Antwort ohne Tool."),
        ]
    )

    with patched_pipeline(fake_model):
        events = _run("Testmail")

    step_completed = [e for e in events if e.type == "step_completed"]
    assert len(step_completed) == 1
    assert step_completed[0].result == "Fallback-Antwort ohne Tool."
    assert events[-1].type == "done"
    assert events[-1].final_reply == "Fallback-Antwort ohne Tool."


def test_error_mid_pipeline_yields_error_event_and_still_cleans_up_session():
    fake_model = _FakeChatModel(responses=[AIMessage(content='["Nur ein Schritt"]')])

    with (
        patched_pipeline(fake_model) as mocks,
        patch.object(
            orchestrator,
            "create_react_agent",
            return_value=AsyncMock(
                ainvoke=AsyncMock(side_effect=RuntimeError("Simulated backend failure"))
            ),
        ),
    ):
        events = _run("Testmail")

    types = [e.type for e in events]
    assert types == ["plan_ready", "step_started", "error"]
    assert events[-1].detail == "Simulated backend failure"
    mocks.delete_session.assert_awaited_once_with(mocks.fake_rag_client, "session-123")
