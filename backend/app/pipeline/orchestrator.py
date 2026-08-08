import logging
from collections.abc import AsyncIterator

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
from app.pipeline.llm_client import ChatMessage, LlmClientError, build_chat_model, invoke_chat
from app.pipeline.plan_parser import parse_plan
from app.pipeline.prompt_builder import build_planning_prompt, build_step_prompt
from app.pipeline.tools import build_search_tool

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "Du bist ein professioneller E-Mail-Assistent."


async def run_pipeline(email_text: str) -> AsyncIterator[PipelineEvent]:
    """Zerlegt die Antwort-Generierung in nachvollziehbare Teilschritte.

    Lässt das LLM die Aufgabe zunächst planen und arbeitet die geplanten
    Teilschritte nacheinander ab. Jeder Teilschritt läuft als Tool-Calling-Agent
    (`create_react_agent`) mit Zugriff auf eine RAG-Session über den Inhalt der
    E-Mail, damit das Modell Fakten nachschlagen kann statt sie zu erfinden. Der
    Konversationsverlauf (E-Mail, Plan, bisherige Zwischenergebnisse) wird als
    `messages`-Verlauf mitgeschickt, sodass jeder Teilschritt Zugriff auf den
    bisherigen Kontext hat.
    """
    messages: list[ChatMessage] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Eingegangene E-Mail:\n{email_text.strip()}"},
    ]

    chat_model = build_chat_model()

    async with rag_client.build_client() as rag_http_client:
        session_id: str | None = None
        try:
            session_id = await rag_client.create_rag_session(
                rag_http_client, email_text.strip()
            )
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
                agent_state = await step_agent.ainvoke({"messages": messages})
                result = agent_state["messages"][-1].content
                if not isinstance(result, str) or not result:
                    raise LlmClientError(
                        "DGX-Modell hat für einen Teilschritt keine Antwort geliefert."
                    )
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
