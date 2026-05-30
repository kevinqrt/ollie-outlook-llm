from pydantic import BaseModel, Field


class ChatMessageSchema(BaseModel):
    role: str = Field(..., description="The role of the message sender (e.g., 'user', 'assistant')")
    content: str = Field(..., description="The content of the message")


class ChatRequestSchema(BaseModel):
    messages: list[ChatMessageSchema] = Field(..., description="The history of the conversation")


class ChatResponseSchema(BaseModel):
    reply: str = Field(..., description="The AI-generated reply")
