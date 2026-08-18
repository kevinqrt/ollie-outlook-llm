import logging
from typing import Annotated

from fastapi import Depends

from app.core.config import settings
from app.services.calendar_mock_service import MockCalendarService, MockGraphAuthService
from app.services.graph_auth_service import GraphAuthService
from app.services.graph_calendar_service import GraphCalendarService
from app.services.ics_calendar_service import IcsCalendarService, IcsCalendarStore
from app.services.llm_service import LlmService
from app.services.prompt_service import PromptService
from app.services.scheduling_service import SchedulingService
from app.services.vector_store_service import VectorStoreService

logger = logging.getLogger(__name__)

CalendarService = GraphCalendarService | IcsCalendarService | MockCalendarService


class ServiceContainer:
    """A container for global application services."""

    def __init__(self) -> None:
        self.vector_store: VectorStoreService | None = None
        self.prompt_service: PromptService | None = None
        self.llm_service: LlmService | None = None
        self.graph_auth_service: GraphAuthService | None = None
        self.graph_calendar_service: CalendarService | None = None
        self.scheduling_service: SchedulingService | None = None

    def init_services(self) -> None:
        """Initialize all global services."""
        logger.info("Initializing application services in container...")
        self.vector_store = VectorStoreService()
        self.prompt_service = PromptService()
        self.llm_service = LlmService(
            vector_store=self.vector_store, prompt_service=self.prompt_service
        )
        if settings.calendar_mock_mode:
            logger.warning(
                "CALENDAR_MOCK_MODE is active - calendar endpoints/MCP tools return fake data."
            )
            self.graph_auth_service = MockGraphAuthService()
            self.graph_calendar_service = MockCalendarService(self.graph_auth_service)
        elif settings.calendar_backend == "graph":
            self.graph_auth_service = GraphAuthService()
            self.graph_calendar_service = GraphCalendarService(self.graph_auth_service)
        else:
            self.graph_calendar_service = IcsCalendarService(
                IcsCalendarStore(settings.ics_store_path)
            )
        self.scheduling_service = SchedulingService(
            llm_service=self.llm_service, calendar_service=self.graph_calendar_service
        )
        logger.info("Services initialized successfully.")

    async def close_services(self) -> None:
        """Clean up services during shutdown."""
        logger.info("Cleaning up services in container...")
        if self.graph_calendar_service is not None:
            await self.graph_calendar_service.aclose()
        self.vector_store = None
        self.prompt_service = None
        self.llm_service = None
        self.graph_auth_service = None
        self.graph_calendar_service = None
        self.scheduling_service = None


# Global instance of the container
container = ServiceContainer()


# Dependency Getters
def get_vector_store_service() -> VectorStoreService:
    """Dependency to retrieve the Vector Store service."""
    if container.vector_store is None:
        raise RuntimeError("VectorStoreService is not initialized.")
    return container.vector_store


def get_llm_service() -> LlmService:
    """Dependency to retrieve the LLM service."""
    if container.llm_service is None:
        raise RuntimeError("LlmService is not initialized.")
    return container.llm_service


def get_graph_auth_service() -> GraphAuthService:
    """Dependency to retrieve the Graph auth service."""
    if container.graph_auth_service is None:
        raise RuntimeError("GraphAuthService is not initialized.")
    return container.graph_auth_service


def get_graph_calendar_service() -> CalendarService:
    """Dependency to retrieve the active calendar service (ICS, Graph, or mock)."""
    if container.graph_calendar_service is None:
        raise RuntimeError("Calendar service is not initialized.")
    return container.graph_calendar_service


def get_scheduling_service() -> SchedulingService:
    """Dependency to retrieve the scheduling service."""
    if container.scheduling_service is None:
        raise RuntimeError("SchedulingService is not initialized.")
    return container.scheduling_service


# Annotated Dependency Aliases
VectorStoreServiceDep = Annotated[VectorStoreService, Depends(get_vector_store_service)]
LlmServiceDep = Annotated[LlmService, Depends(get_llm_service)]
GraphAuthServiceDep = Annotated[GraphAuthService, Depends(get_graph_auth_service)]
GraphCalendarServiceDep = Annotated[CalendarService, Depends(get_graph_calendar_service)]
SchedulingServiceDep = Annotated[SchedulingService, Depends(get_scheduling_service)]
