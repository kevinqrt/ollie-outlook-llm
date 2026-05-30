import logging
from typing import Annotated

from fastapi import Depends

from app.services.llm_service import LlmService
from app.services.prompt_service import PromptService
from app.services.vector_store_service import VectorStoreService

logger = logging.getLogger(__name__)


class ServiceContainer:
    """A container for global application services."""

    def __init__(self) -> None:
        self.vector_store: VectorStoreService | None = None
        self.prompt_service: PromptService | None = None
        self.llm_service: LlmService | None = None

    def init_services(self) -> None:
        """Initialize all global services."""
        logger.info("Initializing application services in container...")
        self.vector_store = VectorStoreService()
        self.prompt_service = PromptService()
        self.llm_service = LlmService(
            vector_store=self.vector_store, prompt_service=self.prompt_service
        )
        logger.info("Services initialized successfully.")

    def close_services(self) -> None:
        """Clean up services during shutdown."""
        logger.info("Cleaning up services in container...")
        self.vector_store = None
        self.prompt_service = None
        self.llm_service = None


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


# Annotated Dependency Aliases
VectorStoreServiceDep = Annotated[VectorStoreService, Depends(get_vector_store_service)]
LlmServiceDep = Annotated[LlmService, Depends(get_llm_service)]
