from pydantic import Field, model_validator

from app.api.schemas.base_schema import BaseSchema


class StyleRuleSchema(BaseSchema):
    id: str
    text: str = Field(description="Kurze, allgemeine Stilregel, abgeleitet aus einer Korrektur.")


class StyleRulesSchema(BaseSchema):
    enabled: bool = Field(
        description="Ob gelernte Regeln bei neuen Antwortvorschlägen berücksichtigt "
        "(und neue Korrekturen gelernt) werden."
    )
    rules: list[StyleRuleSchema]


class UpdateStyleRulesSettingsRequestSchema(BaseSchema):
    enabled: bool


class CreateCorrectionRequestSchema(BaseSchema):
    original_reply: str = Field(description="Der von Ollie vorgeschlagene Antworttext.")
    feedback: str | None = Field(
        default=None,
        description="Freitext-Anweisung, was künftig anders sein soll (z. B. 'kürzer').",
    )
    corrected_reply: str | None = Field(
        default=None, description="Optional: die vom Nutzer korrigierte Fassung der Antwort."
    )

    @model_validator(mode="after")
    def _require_feedback_or_corrected_reply(self) -> "CreateCorrectionRequestSchema":
        if not (self.feedback or "").strip() and not (self.corrected_reply or "").strip():
            raise ValueError("feedback oder corrected_reply ist erforderlich.")
        return self


class CorrectionResponseSchema(BaseSchema):
    learned: bool = Field(
        description="Ob aus der Korrektur eine neue Stilregel entstanden ist. False, wenn nur "
        "der Inhalt geändert wurde oder die Regel bereits bekannt ist."
    )
    rule: StyleRuleSchema | None = None
