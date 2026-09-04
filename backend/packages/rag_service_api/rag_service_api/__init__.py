"""Universal RAG Service API Package."""

from .generated.client import Client
from .generated.models.create_session_request import CreateSessionRequest
from .generated.models.direct_query_request import DirectQueryRequest
from .generated.models.http_validation_error import HTTPValidationError
from .generated.models.query_session_request import QuerySessionRequest
from .generated.api.default import direct_query_query_post as direct_query
from .generated.api.default import create_session_sessions_post as create_session
from .generated.api.default import (
    delete_session_sessions_session_id_delete as delete_session,
)
from .generated.api.default import (
    query_session_sessions_session_id_query_post as query_session,
)

__all__ = [
    "Client",
    "CreateSessionRequest",
    "DirectQueryRequest",
    "HTTPValidationError",
    "QuerySessionRequest",
    "create_session",
    "delete_session",
    "direct_query",
    "query_session",
]
