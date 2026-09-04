from typing import Any

from pydantic import Field

from app.api.schemas.base_schema import BaseSchema


class KnowledgeSearchResultSchema(BaseSchema):
    content: str = Field(description="The content snippet from the document.")
    metadata: dict[str, Any] = Field(description="Additional metadata for the result.")


class KnowledgeSearchResponseSchema(BaseSchema):
    results: list[KnowledgeSearchResultSchema] = Field(
        description="Search results from the vector store."
    )


class KnowledgeDocumentSchema(BaseSchema):
    source: str = Field(description="The source filename of the document.")


class KnowledgeDocumentListSchema(BaseSchema):
    documents: list[KnowledgeDocumentSchema] = Field(description="List of all indexed documents.")


class KnowledgeUploadResponseSchema(BaseSchema):
    filename: str = Field(description="The name of the successfully uploaded and indexed file.")
    status: str = Field(default="indexed")
