import logging
from collections.abc import AsyncIterator
from typing import Any

from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from app.api.schemas.pipeline_schema import (
    DoneEvent,
    ErrorEvent,
    PipelineEvent,
    PlanReadyEvent,
    StepCompletedEvent,
    StepStartedEvent,
)
from app.pipeline import rag_client
from app.pipeline.llm_client import ChatMessage, build_chat_model, invoke_chat
from app.pipeline.plan_parser import parse_plan
from app.pipeline.prompt_builder import build_planning_prompt, build_step_prompt
from app.pipeline.tools import build_search_tool

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "Du bist ein professioneller E-Mail-Assistent."

MAX_STEP_ATTEMPTS = 2


async def _run_step(
    step_agent: CompiledStateGraph[Any, Any, Any, Any],
    chat_model: ChatOpenAI,
    messages: list[ChatMessage],
) -> str:
    """Führt einen Teilschritt über den Tool-Calling-Agenten aus, mit Fallback.

    Das gpt-oss-Modell liefert über den DGX-Tunnel bei gebundenen Tools gelegentlich
    eine leere Antwort zurück (finish_reason='stop', aber ohne sichtbaren Inhalt) -
    ein reproduzierbares Verhalten dieses Modells/Servings bei Tool-Calling, kein
    Fehler in unserer Logik. Wir versuchen es daher mehrfach und weichen danach auf
    einen normalen Modellaufruf ohne Tool aus, statt den ganzen Lauf abzubrechen.
    """
    for attempt in range(1, MAX_STEP_ATTEMPTS + 1):
        agent_state = await step_agent.ainvoke({"messages": messages})
        result = agent_state["messages"][-1].content
        if isinstance(result, str) and result:
            return result
        logger.warning(
            "Tool-Agent hat leere Antwort geliefert (Versuch %d/%d).",
            attempt,
            MAX_STEP_ATTEMPTS,
        )

    logger.warning("Tool-Agent liefert weiterhin leere Antworten, weiche auf Aufruf ohne Tool aus.")
    return await invoke_chat(chat_model, messages)


async def run_pipeline(email_text: str, *, extra_context: str = "") -> AsyncIterator[PipelineEvent]:
    """Zerlegt die Antwort-Generierung in nachvollziehbare Teilschritte.

    Lässt das LLM die Aufgabe zunächst planen und arbeitet die geplanten
    Teilschritte nacheinander ab. Jeder Teilschritt läuft als Tool-Calling-Agent
    (`create_react_agent`) mit Zugriff auf eine RAG-Session über den Inhalt der
    E-Mail, damit das Modell Fakten nachschlagen kann statt sie zu erfinden. Der
    Konversationsverlauf (E-Mail, Plan, bisherige Zwischenergebnisse) wird als
    `messages`-Verlauf mitgeschickt, sodass jeder Teilschritt Zugriff auf den
    bisherigen Kontext hat.

    `extra_context` (z.B. Kalenderverfügbarkeit) wird der E-Mail unverändert
    angehängt, analog zu `LlmService.chat`.
    """
    messages: list[ChatMessage] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Eingegangene E-Mail:\n{email_text.strip()}{extra_context}",
        },
    ]

    async with rag_client.build_client() as rag_http_client:
        session_id: str | None = None
        try:
            chat_model = build_chat_model()
            session_id = await rag_client.create_rag_session(rag_http_client, email_text.strip())
            search_tool = build_search_tool(rag_http_client, session_id)
            step_agent = create_react_agent(chat_model, tools=[search_tool])

            messages.append({"role": "user", "content": build_planning_prompt()})
            plan_answer = await invoke_chat(chat_model, messages)
            messages.append({"role": "assistant", "content": plan_answer})

            steps = parse_plan(plan_answer)
            yield PlanReadyEvent(steps=steps)

            final_reply = ""
            for index, step in enumerate(steps):
                is_final = index == len(steps) - 1
                yield StepStartedEvent(index=index, label=step)

                messages.append(
                    {"role": "user", "content": build_step_prompt(step, is_final=is_final)}
                )
                result = await _run_step(step_agent, chat_model, messages)
                messages.append({"role": "assistant", "content": result})

                final_reply = result
                yield StepCompletedEvent(index=index, label=step, result=result)

            yield DoneEvent(final_reply=final_reply)
        except Exception as exc:
            logger.error("Pipeline failed: %s", exc)
            yield ErrorEvent(detail=str(exc))
        finally:
            if session_id is not None:
                try:
                    await rag_client.delete_rag_session(rag_http_client, session_id)
                except Exception:
                    logger.warning("RAG-Session %s konnte nicht gelöscht werden.", session_id)
