import logging
from collections.abc import AsyncIterator

from app.api.schemas.pipeline_schema import (
    DoneEvent,
    ErrorEvent,
    PipelineEvent,
    PlanReadyEvent,
    StepCompletedEvent,
    StepStartedEvent,
)
from app.pipeline.llm_client import ChatMessage, build_client, chat_complete
from app.pipeline.plan_parser import parse_plan
from app.pipeline.prompt_builder import build_planning_prompt, build_step_prompt

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "Du bist ein professioneller E-Mail-Assistent."


async def run_pipeline(email_text: str) -> AsyncIterator[PipelineEvent]:
    """Zerlegt die Antwort-Generierung in nachvollziehbare Teilschritte.

    Lässt das LLM die Aufgabe zunächst planen und arbeitet die geplanten
    Teilschritte nacheinander ab. Der Konversationsverlauf (E-Mail, Plan,
    bisherige Zwischenergebnisse) wird als `messages`-Verlauf mitgeschickt,
    sodass jeder Teilschritt Zugriff auf den bisherigen Kontext hat.
    """
    messages: list[ChatMessage] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Eingegangene E-Mail:\n{email_text.strip()}"},
    ]

    async with build_client() as client:
        try:
            messages.append({"role": "user", "content": build_planning_prompt()})
            plan_answer = await chat_complete(client, messages)
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
                result = await chat_complete(client, messages)
                messages.append({"role": "assistant", "content": result})

                final_reply = result
                yield StepCompletedEvent(index=index, label=step, result=result)

            yield DoneEvent(final_reply=final_reply)
        except Exception as exc:
            logger.error("Pipeline failed: %s", exc)
            yield ErrorEvent(detail=str(exc))
