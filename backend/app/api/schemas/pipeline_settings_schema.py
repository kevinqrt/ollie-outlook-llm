from typing import Literal

from pydantic import Field, model_validator

from app.api.schemas.base_schema import BaseSchema

ToneOption = Literal["friendly", "formal", "casual", "custom"]


class PipelineSettingsSchema(BaseSchema):
    prompt: str = Field(description="System-Prompt, der die Antwort-Pipeline steuert.")
    allow_clarifying_questions: bool = Field(
        default=False,
        description="Ob die Pipeline vor der Antwort-Generierung Rückfragen an den Nutzer "
        "stellen darf, statt Fehlendes zu erfinden oder zu übergehen.",
    )
    tone: ToneOption = Field(
        default="friendly",
        description="Tonalität, die der finalen Antwort-E-Mail zusätzlich zum System-Prompt "
        "vorgegeben wird.",
    )
    custom_tone_text: str | None = Field(
        default=None,
        description="Freitext-Tonvorgabe, nur relevant wenn tone == 'custom'.",
    )


class UpdatePipelineSettingsRequestSchema(BaseSchema):
    prompt: str = Field(min_length=1)
    allow_clarifying_questions: bool = False
    tone: ToneOption = "friendly"
    custom_tone_text: str | None = None

    @model_validator(mode="after")
    def _require_custom_tone_text_when_custom(self) -> "UpdatePipelineSettingsRequestSchema":
        if self.tone == "custom" and not (self.custom_tone_text or "").strip():
            raise ValueError("custom_tone_text ist erforderlich, wenn tone 'custom' ist.")
        return self


class SavedPromptSchema(BaseSchema):
    id: str
    text: str
    is_default: bool = Field(
        default=False,
        description="Ob dies der eingebaute Standard-Prompt ist - immer vorhanden, nicht "
        "bearbeitbar oder löschbar, aber jederzeit erneut auswählbar.",
    )


class SavedPromptListSchema(BaseSchema):
    prompts: list[SavedPromptSchema]


class CreateSavedPromptRequestSchema(BaseSchema):
    text: str = Field(min_length=1)


class UpdateSavedPromptRequestSchema(BaseSchema):
    text: str = Field(min_length=1)
