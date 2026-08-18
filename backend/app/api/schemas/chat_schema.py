from pydantic import Field

from app.api.schemas.base_schema import BaseSchema
from app.api.schemas.calendar_schema import MeetingProposalSchema


class ChatMessageSchema(BaseSchema):
    role: str = Field(..., description="The role of the message sender (e.g., 'user', 'assistant')")
    content: str = Field(..., description="The content of the message")


class ChatRequestSchema(BaseSchema):
    messages: list[ChatMessageSchema] = Field(..., description="The history of the conversation")


class ChatResponseSchema(BaseSchema):
    reply: str = Field(..., description="The AI-generated reply")
    meeting_proposal: MeetingProposalSchema | None = Field(
        default=None,
        description="A concrete meeting suggestion, if the message contained a meeting request.",
    )
