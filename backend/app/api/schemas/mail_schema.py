from datetime import datetime

from app.api.schemas.base_schema import BaseSchema


class MailMessageSchema(BaseSchema):
    id: str
    subject: str
    sender_name: str | None = None
    sender_address: str | None = None
    received: datetime
    preview: str = ""
    body: str | None = None
    web_link: str | None = None
    is_read: bool = True
