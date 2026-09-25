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
from app.api.schemas.email_schema import (
    EmailSuggestionRequestSchema,
    HealthResponseSchema,
    ReviseReplyRequestSchema,
    ReviseReplyResponseSchema,
    ThreadSummaryRequestSchema,
    ThreadSummaryResponseSchema,
)
from app.api.schemas.knowledge_schema import (
    KnowledgeDocumentListSchema,
    KnowledgeSearchResponseSchema,
    KnowledgeUploadResponseSchema,
)
from app.api.schemas.pipeline_schema import DoneEvent
from app.api.schemas.pipeline_settings_schema import (
    CreateSavedPromptRequestSchema,
    ModelOptionListSchema,
    ModelOptionSchema,
    PipelineSettingsSchema,
    SavedPromptListSchema,
    SavedPromptSchema,
    UpdatePipelineSettingsRequestSchema,
    UpdateSavedPromptRequestSchema,
)
from app.api.schemas.style_rules_schema import (
    CorrectionResponseSchema,
    CreateCorrectionRequestSchema,
    StyleRuleSchema,
    StyleRulesSchema,
    UpdateStyleRulesSettingsRequestSchema,
)
from app.core.dependencies import (
    GraphAuthServiceDep,
    GraphCalendarServiceDep,
    LlmServiceDep,
    PipelineSettingsServiceDep,
    SchedulingServiceDep,
    StyleRulesServiceDep,
    VectorStoreServiceDep,
)
from app.core.model_catalog import MODEL_CATALOG, ModelChoice, get_model_choice
from app.pipeline import run_pipeline, summarize_thread
from app.pipeline.llm_client import LlmClientError
from app.pipeline.prompt_builder import build_style_rules_instruction, build_tone_instruction
from app.pipeline.reply_revision import revise_reply
from app.pipeline.style_learning import derive_style_rule
from app.services.availability import CalendarServiceError
from app.services.graph_auth_service import GraphAuthError
from app.services.ics_calendar_service import IcsCalendarService
from app.services.llm_service import LlmServiceError
from app.services.pipeline_settings_service import (
    DEFAULT_PROMPT_ID,
    PipelineSettingsStore,
    SavedPromptNotFoundError,
)
from app.services.style_rules_service import StyleRuleNotFoundError, StyleRulesStore

api_router = APIRouter()


def _resolve_model_choice(pipeline_settings_service: PipelineSettingsStore) -> ModelChoice:
    """Resolve the project-wide model choice for the currently configured id."""
    return get_model_choice(pipeline_settings_service.get_model_id())


def _build_system_prompt(
    pipeline_settings_service: PipelineSettingsStore, style_rules_service: StyleRulesStore
) -> str:
    """System prompt for reply generation: base prompt + tone + learned style rules."""
    tone_instruction = build_tone_instruction(
        pipeline_settings_service.get_tone(),
        pipeline_settings_service.get_custom_tone_text(),
    )
    style_rules_instruction = build_style_rules_instruction(style_rules_service.active_rules())
    return "\n\n".join(
        part
        for part in (
            pipeline_settings_service.get_prompt(),
            tone_instruction,
            style_rules_instruction,
        )
        if part
    )


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
    pipeline_settings_service: PipelineSettingsServiceDep,
) -> ChatResponseSchema:
    """Provide a classical chat interface with history and RAG context.

    If the latest user message contains a meeting request, the reply is
    augmented with real calendar availability and a concrete meeting proposal.
    """
    latest_user_message = next(
        (m.content for m in reversed(payload.messages) if m.role == "user"), ""
    )
    model = _resolve_model_choice(pipeline_settings_service).rag_model
    try:
        augmentation = await scheduling_service.augment_with_availability(
            latest_user_message, model=model
        )
        reply = await service.chat(
            payload.messages, extra_context=augmentation.context, model=model
        )
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
    pipeline_settings_service: PipelineSettingsServiceDep,
    style_rules_service: StyleRulesServiceDep,
) -> StreamingResponse:
    """Generate a reply suggestion, streaming each pipeline step as it completes.

    If the email contains a meeting request and the calendar is connected, the
    pipeline is augmented with real availability, and the final `done` event
    carries a concrete meeting proposal.

    The system prompt, tone and whether the pipeline may ask a clarifying question
    before answering come from the user-configurable pipeline settings; style
    rules learned from earlier user corrections are appended to the prompt.
    """
    model_choice = _resolve_model_choice(pipeline_settings_service)
    augmentation = await scheduling_service.augment_with_availability(
        payload.email_content, payload.attendees, model=model_choice.rag_model
    )

    system_prompt = _build_system_prompt(pipeline_settings_service, style_rules_service)

    async def event_stream() -> AsyncIterator[str]:
        async for event in run_pipeline(
            payload.email_content,
            extra_context=augmentation.context,
            system_prompt=system_prompt,
            allow_clarifying_questions=pipeline_settings_service.get_allow_clarifying_questions(),
            clarification_answer=payload.clarification_answer,
            model=model_choice.dgx_model,
        ):
            if isinstance(event, DoneEvent):
                event = DoneEvent(
                    final_reply=event.final_reply,
                    meeting_proposal=augmentation.proposal_matching_reply(
                        event.final_reply, payload.clarification_answer
                    ),
                )
            yield f"data: {event.model_dump_json(by_alias=True)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@api_router.post(
    "/email/suggestion/revise",
    response_model=ReviseReplyResponseSchema,
    summary="Revise an already suggested reply according to user feedback",
    responses={503: {"model": ErrorResponseSchema, "description": "LLM unavailable"}},
    tags=["email"],
    operation_id="postReplyRevision",
)
async def revise_email_suggestion(
    payload: ReviseReplyRequestSchema,
    pipeline_settings_service: PipelineSettingsServiceDep,
    style_rules_service: StyleRulesServiceDep,
) -> ReviseReplyResponseSchema:
    """Rewrite the previous reply with a single LLM call, applying the feedback.

    Uses the same system prompt as a fresh suggestion (base prompt, tone and
    learned style rules) but skips the multi-step pipeline. The feedback applies
    to this one reply only; it is not stored.
    """
    system_prompt = _build_system_prompt(pipeline_settings_service, style_rules_service)
    model = _resolve_model_choice(pipeline_settings_service).dgx_model
    try:
        final_reply = await revise_reply(
            system_prompt,
            payload.email_content,
            payload.previous_reply,
            payload.feedback,
            model=model,
        )
    except LlmClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return ReviseReplyResponseSchema(final_reply=final_reply)


@api_router.get(
    "/pipeline/settings",
    response_model=PipelineSettingsSchema,
    summary="Get the current auto-reply pipeline settings",
    tags=["pipeline"],
    operation_id="getPipelineSettings",
)
async def get_pipeline_settings(
    service: PipelineSettingsServiceDep,
) -> PipelineSettingsSchema:
    return PipelineSettingsSchema(
        prompt=service.get_prompt(),
        allow_clarifying_questions=service.get_allow_clarifying_questions(),
        tone=service.get_tone(),
        custom_tone_text=service.get_custom_tone_text(),
        model=service.get_model_id(),
    )


@api_router.put(
    "/pipeline/settings",
    response_model=PipelineSettingsSchema,
    summary="Update the auto-reply pipeline settings (system prompt, clarifying questions)",
    tags=["pipeline"],
    operation_id="putPipelineSettings",
)
async def put_pipeline_settings(
    payload: UpdatePipelineSettingsRequestSchema,
    service: PipelineSettingsServiceDep,
) -> PipelineSettingsSchema:
    service.update(
        prompt=payload.prompt,
        allow_clarifying_questions=payload.allow_clarifying_questions,
        tone=payload.tone,
        custom_tone_text=payload.custom_tone_text,
        model=payload.model,
    )
    return PipelineSettingsSchema(
        prompt=service.get_prompt(),
        allow_clarifying_questions=service.get_allow_clarifying_questions(),
        tone=service.get_tone(),
        custom_tone_text=service.get_custom_tone_text(),
        model=service.get_model_id(),
    )


@api_router.get(
    "/pipeline/models",
    response_model=ModelOptionListSchema,
    summary="List selectable AI models",
    tags=["pipeline"],
    operation_id="getPipelineModels",
)
async def get_pipeline_models() -> ModelOptionListSchema:
    return ModelOptionListSchema(
        models=[ModelOptionSchema(id=choice.id, label=choice.label) for choice in MODEL_CATALOG]
    )


@api_router.get(
    "/pipeline/settings/prompts",
    response_model=SavedPromptListSchema,
    summary="List saved prompt templates",
    tags=["pipeline"],
    operation_id="getSavedPrompts",
)
async def get_saved_prompts(service: PipelineSettingsServiceDep) -> SavedPromptListSchema:
    """List saved prompt templates, with the built-in default prompt always first.

    The default entry is synthesized here (not stored in "saved_prompts") so it can
    never be deleted or overwritten, but is always available to re-select - fixing
    the case where a user edits the prompt field and saves over the original default.
    """
    default_entry = SavedPromptSchema(
        id=DEFAULT_PROMPT_ID, text=service.get_default_prompt(), is_default=True
    )
    saved_entries = [
        SavedPromptSchema(id=entry["id"], text=entry["text"])
        for entry in service.list_saved_prompts()
    ]
    return SavedPromptListSchema(prompts=[default_entry, *saved_entries])


@api_router.post(
    "/pipeline/settings/prompts",
    response_model=SavedPromptSchema,
    summary="Save a new prompt template",
    tags=["pipeline"],
    operation_id="postSavedPrompt",
)
async def post_saved_prompt(
    payload: CreateSavedPromptRequestSchema,
    service: PipelineSettingsServiceDep,
) -> SavedPromptSchema:
    entry = service.add_saved_prompt(payload.text)
    return SavedPromptSchema(id=entry["id"], text=entry["text"])


@api_router.put(
    "/pipeline/settings/prompts/{prompt_id}",
    response_model=SavedPromptSchema,
    summary="Update a saved prompt template",
    responses={404: {"model": ErrorResponseSchema, "description": "Prompt not found"}},
    tags=["pipeline"],
    operation_id="putSavedPrompt",
)
async def put_saved_prompt(
    prompt_id: str,
    payload: UpdateSavedPromptRequestSchema,
    service: PipelineSettingsServiceDep,
) -> SavedPromptSchema:
    try:
        entry = service.update_saved_prompt(prompt_id, payload.text)
        return SavedPromptSchema(id=entry["id"], text=entry["text"])
    except SavedPromptNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Prompt nicht gefunden."
        ) from exc


@api_router.delete(
    "/pipeline/settings/prompts/{prompt_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a saved prompt template",
    responses={404: {"model": ErrorResponseSchema, "description": "Prompt not found"}},
    tags=["pipeline"],
    operation_id="deleteSavedPrompt",
)
async def delete_saved_prompt(
    prompt_id: str,
    service: PipelineSettingsServiceDep,
) -> None:
    try:
        service.delete_saved_prompt(prompt_id)
    except SavedPromptNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Prompt nicht gefunden."
        ) from exc


@api_router.get(
    "/pipeline/style-rules",
    response_model=StyleRulesSchema,
    summary="List the style rules learned from user corrections",
    tags=["pipeline"],
    operation_id="getStyleRules",
)
async def get_style_rules(service: StyleRulesServiceDep) -> StyleRulesSchema:
    return StyleRulesSchema(
        enabled=service.is_enabled(),
        rules=[StyleRuleSchema(id=r["id"], text=r["text"]) for r in service.list_rules()],
    )


@api_router.put(
    "/pipeline/style-rules/settings",
    response_model=StyleRulesSchema,
    summary="Switch learning from user corrections on or off",
    tags=["pipeline"],
    operation_id="putStyleRulesSettings",
)
async def put_style_rules_settings(
    payload: UpdateStyleRulesSettingsRequestSchema,
    service: StyleRulesServiceDep,
) -> StyleRulesSchema:
    service.set_enabled(payload.enabled)
    return await get_style_rules(service)


@api_router.post(
    "/pipeline/corrections",
    response_model=CorrectionResponseSchema,
    summary="Learn a style rule from a user correction of a suggested reply",
    responses={
        409: {"model": ErrorResponseSchema, "description": "Learning is switched off"},
        503: {"model": ErrorResponseSchema, "description": "LLM unavailable"},
    },
    tags=["pipeline"],
    operation_id="postCorrection",
)
async def post_correction(
    payload: CreateCorrectionRequestSchema,
    service: StyleRulesServiceDep,
    pipeline_settings_service: PipelineSettingsServiceDep,
) -> CorrectionResponseSchema:
    """Derive one short, general style rule from the correction and store it.

    Only the rule text is stored, never the reply or the e-mail it came from.
    """
    if not service.is_enabled():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Lernen aus Korrekturen ist ausgeschaltet.",
        )
    model = _resolve_model_choice(pipeline_settings_service).dgx_model
    try:
        rule_text = await derive_style_rule(
            payload.original_reply, payload.feedback, payload.corrected_reply, model=model
        )
    except LlmClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    entry = service.add_rule(rule_text) if rule_text else None
    if entry is None:
        return CorrectionResponseSchema(learned=False)
    return CorrectionResponseSchema(
        learned=True, rule=StyleRuleSchema(id=entry["id"], text=entry["text"])
    )


@api_router.delete(
    "/pipeline/style-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one learned style rule",
    responses={404: {"model": ErrorResponseSchema, "description": "Rule not found"}},
    tags=["pipeline"],
    operation_id="deleteStyleRule",
)
async def delete_style_rule(rule_id: str, service: StyleRulesServiceDep) -> None:
    try:
        service.delete_rule(rule_id)
    except StyleRuleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Regel nicht gefunden."
        ) from exc


@api_router.delete(
    "/pipeline/style-rules",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete all learned style rules",
    tags=["pipeline"],
    operation_id="deleteAllStyleRules",
)
async def delete_all_style_rules(service: StyleRulesServiceDep) -> None:
    service.clear()


@api_router.post(
    "/email/summarize",
    response_model=ThreadSummaryResponseSchema,
    summary="Summarize an email thread",
    responses={503: {"model": ErrorResponseSchema, "description": "DGX model unavailable"}},
    tags=["email"],
    operation_id="summarizeEmailThread",
)
async def summarize_email_thread(
    payload: ThreadSummaryRequestSchema,
    pipeline_settings_service: PipelineSettingsServiceDep,
) -> ThreadSummaryResponseSchema:
    """Summarize an email thread, including quoted history, in a few sentences."""
    model = _resolve_model_choice(pipeline_settings_service).dgx_model
    try:
        summary = await summarize_thread(payload.thread_text, model=model)
        return ThreadSummaryResponseSchema(summary=summary)
    except LlmClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


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
