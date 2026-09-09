from pydantic import Field

from app.api.schemas.base_schema import BaseSchema


class PipelineSettingsSchema(BaseSchema):
    prompt: str = Field(description="System-Prompt, der die Antwort-Pipeline steuert.")
    allow_clarifying_questions: bool = Field(
        default=False,
        description="Ob die Pipeline vor der Antwort-Generierung Rückfragen an den Nutzer "
        "stellen darf, statt Fehlendes zu erfinden oder zu übergehen.",
    )


class UpdatePipelineSettingsRequestSchema(BaseSchema):
    prompt: str = Field(min_length=1)
    allow_clarifying_questions: bool = False


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
