from typing import Annotated, Literal

from pydantic import Field

from app.api.schemas.base_schema import BaseSchema
from app.api.schemas.calendar_schema import MeetingProposalSchema


class PlanReadyEvent(BaseSchema):
    type: Literal["plan_ready"] = "plan_ready"
    steps: list[str] = Field(description="Teilschritte, die das LLM für die Aufgabe geplant hat.")


class StepStartedEvent(BaseSchema):
    type: Literal["step_started"] = "step_started"
    index: int = Field(description="0-basierter Index des Teilschritts.")
    label: str = Field(description="Beschreibung des gestarteten Teilschritts.")


class StepCompletedEvent(BaseSchema):
    type: Literal["step_completed"] = "step_completed"
    index: int
    label: str
    result: str = Field(description="Zwischenergebnis dieses Teilschritts.")


class DoneEvent(BaseSchema):
    type: Literal["done"] = "done"
    final_reply: str = Field(description="Die finale, formatierte Antwort.")
    meeting_proposal: MeetingProposalSchema | None = Field(
        default=None,
        description="Ein konkreter Terminvorschlag, falls die E-Mail eine Terminanfrage enthielt.",
    )


class ErrorEvent(BaseSchema):
    type: Literal["error"] = "error"
    detail: str


PipelineEvent = Annotated[
    PlanReadyEvent | StepStartedEvent | StepCompletedEvent | DoneEvent | ErrorEvent,
    Field(discriminator="type"),
]
