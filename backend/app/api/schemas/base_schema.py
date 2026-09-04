from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class ErrorResponseSchema(BaseSchema):
    detail: str = Field(
        description="A detailed error message explaining what went wrong.",
        examples=["RAG Service request failed: connection timeout"],
    )
