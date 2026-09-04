from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.schemas.base_schema import ErrorResponseSchema
from app.api.schemas.calendar_schema import (
    AuthCallbackRequestSchema,
    AuthStatusSchema,
    AuthUrlSchema,
    CalendarEventListSchema,
    FindMeetingTimesRequestSchema,
    IcsStatusSchema,
    KnownCalendarListSchema,
    KnownCalendarSchema,
    MeetingTimeSuggestionListSchema,
    SetKnownIcsUrlRequestSchema,
    SetSelfIcsUrlRequestSchema,
)
from app.api.schemas.chat_schema import ChatRequestSchema, ChatResponseSchema
from app.api.schemas.email_schema import EmailSuggestionRequestSchema, HealthResponseSchema
from app.api.schemas.knowledge_schema import (
    KnowledgeDocumentListSchema,
    KnowledgeSearchResponseSchema,
    KnowledgeUploadResponseSchema,
)
from app.api.schemas.pipeline_schema import DoneEvent
from app.core.dependencies import (
    GraphAuthServiceDep,
    GraphCalendarServiceDep,
    LlmServiceDep,
    SchedulingServiceDep,
    VectorStoreServiceDep,
)
from app.pipeline import run_pipeline
from app.services.availability import CalendarServiceError
from app.services.graph_auth_service import GraphAuthError
from app.services.ics_calendar_service import IcsCalendarService
from app.services.llm_service import LlmServiceError

api_router = APIRouter()


@api_router.get(
    "/health",
    response_model=HealthResponseSchema,
    summary="Check service availability",
    tags=["health"],
    operation_id="getHealth",
)
async def health_check() -> HealthResponseSchema:
    """Returns 'ok' status if the API service is running correctly."""
    return HealthResponseSchema(status="ok")


@api_router.post(
    "/chat",
    response_model=ChatResponseSchema,
    summary="Classical LLM chat",
    responses={503: {"model": ErrorResponseSchema, "description": "RAG Service unavailable"}},
    tags=["chat"],
    operation_id="postChat",
)
async def post_chat(
    payload: ChatRequestSchema,
    service: LlmServiceDep,
    scheduling_service: SchedulingServiceDep,
) -> ChatResponseSchema:
    """Provide a classical chat interface with history and RAG context.

    If the latest user message contains a meeting request, the reply is
    augmented with real calendar availability and a concrete meeting proposal.
    """
    latest_user_message = next(
        (m.content for m in reversed(payload.messages) if m.role == "user"), ""
    )
    try:
        augmentation = await scheduling_service.augment_with_availability(latest_user_message)
        reply = await service.chat(payload.messages, extra_context=augmentation.context)
        return ChatResponseSchema(reply=reply, meeting_proposal=augmentation.proposal)
    except LlmServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@api_router.post(
    "/email/suggestion/stream",
    response_class=StreamingResponse,
    summary="Generate AI email suggestion with live pipeline progress",
    response_description="SSE stream of pipeline steps, ending in a done or error event",
    responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},
    tags=["email"],
    operation_id="streamEmailSuggestion",
)
async def stream_email_suggestion(
    payload: EmailSuggestionRequestSchema,
    scheduling_service: SchedulingServiceDep,
) -> StreamingResponse:
    """Generate a reply suggestion, streaming each pipeline step as it completes.

    If the email contains a meeting request and the calendar is connected, the
    pipeline is augmented with real availability, and the final `done` event
    carries a concrete meeting proposal.
    """
    augmentation = await scheduling_service.augment_with_availability(
        payload.email_content, payload.attendees
    )

    async def event_stream() -> AsyncIterator[str]:
        async for event in run_pipeline(payload.email_content, extra_context=augmentation.context):
            if isinstance(event, DoneEvent):
                event = DoneEvent(
                    final_reply=event.final_reply, meeting_proposal=augmentation.proposal
                )
            yield f"data: {event.model_dump_json(by_alias=True)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@api_router.post(
    "/knowledge/pdf",
    response_model=KnowledgeUploadResponseSchema,
    summary="Upload and index a PDF document",
    tags=["knowledge"],
)
async def upload_pdf(
    file: Annotated[UploadFile, File()],
    service: VectorStoreServiceDep,
) -> KnowledgeUploadResponseSchema:
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    content = await file.read()
    try:
        filename = await service.ingest_pdf(content, file.filename)
        return KnowledgeUploadResponseSchema(filename=filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@api_router.get(
    "/knowledge/search",
    response_model=KnowledgeSearchResponseSchema,
    summary="Search in the knowledge base",
    tags=["knowledge"],
)
async def search_knowledge(
    query: str,
    service: VectorStoreServiceDep,
) -> KnowledgeSearchResponseSchema:
    results = await service.search(query)
    return KnowledgeSearchResponseSchema(results=results)


@api_router.get(
    "/knowledge/documents",
    response_model=KnowledgeDocumentListSchema,
    summary="List all indexed documents",
    tags=["knowledge"],
)
async def list_documents(
    service: VectorStoreServiceDep,
) -> KnowledgeDocumentListSchema:
    docs = await service.list_documents()
    return KnowledgeDocumentListSchema(documents=docs)


@api_router.delete(
    "/knowledge/documents/{filename}",
    summary="Delete a document from the knowledge base",
    tags=["knowledge"],
)
async def delete_document(
    filename: str,
    service: VectorStoreServiceDep,
) -> dict[str, str]:
    success = await service.delete_document(filename)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"status": "deleted", "filename": filename}


@api_router.get(
    "/calendar/auth/login",
    response_model=AuthUrlSchema,
    summary="Get the Microsoft login URL to connect the calendar",
    responses={503: {"model": ErrorResponseSchema, "description": "Graph not configured"}},
    tags=["calendar"],
    operation_id="getCalendarAuthLogin",
)
async def get_calendar_auth_login(service: GraphAuthServiceDep) -> AuthUrlSchema:
    try:
        return AuthUrlSchema(auth_url=service.get_auth_url())
    except GraphAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@api_router.post(
    "/calendar/auth/callback",
    response_model=AuthStatusSchema,
    summary="Exchange an OAuth authorization code for Graph tokens",
    responses={503: {"model": ErrorResponseSchema, "description": "Token exchange failed"}},
    tags=["calendar"],
    operation_id="postCalendarAuthCallback",
)
async def post_calendar_auth_callback(
    payload: AuthCallbackRequestSchema,
    service: GraphAuthServiceDep,
) -> AuthStatusSchema:
    try:
        service.acquire_token_by_code(payload.code)
    except GraphAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return AuthStatusSchema(authenticated=service.is_authenticated())


@api_router.get(
    "/calendar/auth/status",
    response_model=AuthStatusSchema,
    summary="Check whether the calendar is connected",
    tags=["calendar"],
    operation_id="getCalendarAuthStatus",
)
async def get_calendar_auth_status(service: GraphAuthServiceDep) -> AuthStatusSchema:
    return AuthStatusSchema(authenticated=service.is_authenticated())


@api_router.get(
    "/calendar/events",
    response_model=CalendarEventListSchema,
    summary="List calendar events in a date range",
    responses={503: {"model": ErrorResponseSchema, "description": "Graph API unavailable"}},
    tags=["calendar"],
    operation_id="getCalendarEvents",
)
async def get_calendar_events(
    start: datetime,
    end: datetime,
    service: GraphCalendarServiceDep,
) -> CalendarEventListSchema:
    try:
        events = await service.list_events(start, end)
        return CalendarEventListSchema(events=events)
    except CalendarServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@api_router.post(
    "/calendar/meeting-times",
    response_model=MeetingTimeSuggestionListSchema,
    summary="Find meeting times that work for all given attendees",
    responses={503: {"model": ErrorResponseSchema, "description": "Graph API unavailable"}},
    tags=["calendar"],
    operation_id="postCalendarMeetingTimes",
)
async def post_calendar_meeting_times(
    payload: FindMeetingTimesRequestSchema,
    service: GraphCalendarServiceDep,
) -> MeetingTimeSuggestionListSchema:
    """Find slots where every given attendee (plus the signed-in user) is free.

    Only works for attendees within the same Microsoft 365 tenant, since
    Microsoft Graph has no visibility into external/private calendars.
    """
    try:
        now = datetime.now(UTC)
        window_end = now + timedelta(days=payload.lookahead_days)
        suggestions = await service.find_meeting_times(
            payload.attendees, now, window_end, payload.duration_minutes
        )
        return MeetingTimeSuggestionListSchema(suggestions=suggestions)
    except CalendarServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


def _require_ics_service(service: object) -> IcsCalendarService:
    if not isinstance(service, IcsCalendarService):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ICS-Kalendermodus ist nicht aktiv (CALENDAR_BACKEND ist nicht 'ics').",
        )
    return service


def _known_calendars_response(ics_service: IcsCalendarService) -> KnownCalendarListSchema:
    return KnownCalendarListSchema(
        calendars=[
            KnownCalendarSchema(email=email, url=url)
            for email, url in ics_service.store.list_known().items()
        ]
    )


@api_router.get(
    "/calendar/ics/status",
    response_model=IcsStatusSchema,
    summary="Check whether an own ICS calendar link is configured",
    responses={503: {"model": ErrorResponseSchema, "description": "ICS backend not active"}},
    tags=["calendar"],
    operation_id="getCalendarIcsStatus",
)
async def get_calendar_ics_status(service: GraphCalendarServiceDep) -> IcsStatusSchema:
    ics_service = _require_ics_service(service)
    return IcsStatusSchema(configured=ics_service.store.get_self_url() is not None)


@api_router.post(
    "/calendar/ics/self",
    response_model=IcsStatusSchema,
    summary="Set the signed-in user's own published-calendar ICS URL",
    responses={
        422: {"model": ErrorResponseSchema, "description": "URL not reachable/parseable"},
        503: {"model": ErrorResponseSchema, "description": "ICS backend not active"},
    },
    tags=["calendar"],
    operation_id="postCalendarIcsSelf",
)
async def post_calendar_ics_self(
    payload: SetSelfIcsUrlRequestSchema,
    service: GraphCalendarServiceDep,
) -> IcsStatusSchema:
    """Validate the given ICS feed URL by fetching it, then store it as "my calendar"."""
    ics_service = _require_ics_service(service)
    try:
        await ics_service.validate_feed(payload.url)
    except CalendarServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    ics_service.store.set_self_url(payload.url)
    return IcsStatusSchema(configured=True)


@api_router.get(
    "/calendar/ics/known",
    response_model=KnownCalendarListSchema,
    summary="List known calendar links of other people",
    responses={503: {"model": ErrorResponseSchema, "description": "ICS backend not active"}},
    tags=["calendar"],
    operation_id="getCalendarIcsKnown",
)
async def get_calendar_ics_known(service: GraphCalendarServiceDep) -> KnownCalendarListSchema:
    return _known_calendars_response(_require_ics_service(service))


@api_router.post(
    "/calendar/ics/known",
    response_model=KnownCalendarListSchema,
    summary="Save another person's published-calendar ICS URL",
    responses={
        422: {"model": ErrorResponseSchema, "description": "URL not reachable/parseable"},
        503: {"model": ErrorResponseSchema, "description": "ICS backend not active"},
    },
    tags=["calendar"],
    operation_id="postCalendarIcsKnown",
)
async def post_calendar_ics_known(
    payload: SetKnownIcsUrlRequestSchema,
    service: GraphCalendarServiceDep,
) -> KnownCalendarListSchema:
    ics_service = _require_ics_service(service)
    try:
        await ics_service.validate_feed(payload.url)
    except CalendarServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    ics_service.store.set_known_url(payload.email, payload.url)
    return _known_calendars_response(ics_service)


@api_router.delete(
    "/calendar/ics/known/{email}",
    response_model=KnownCalendarListSchema,
    summary="Remove a saved calendar link",
    responses={503: {"model": ErrorResponseSchema, "description": "ICS backend not active"}},
    tags=["calendar"],
    operation_id="deleteCalendarIcsKnown",
)
async def delete_calendar_ics_known(
    email: str, service: GraphCalendarServiceDep
) -> KnownCalendarListSchema:
    ics_service = _require_ics_service(service)
    ics_service.store.remove_known_url(email)
    return _known_calendars_response(ics_service)
