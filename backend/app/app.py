import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.dependencies import container

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Handles startup and shutdown events for the FastAPI application."""
    container.init_services()
    yield
    await container.close_services()


def create_app() -> FastAPI:
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    app = FastAPI(
        title="OLLIE - Outlook Local Language Inference Engine",
        description="""
        Intelligent bridge orchestrating communication with the
        [Universal RAG Service](https://github.com/detti97/universal-rag-service)
        to provide context-aware AI email suggestions.
        """,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
        root_path=os.getenv("ROOT_PATH", ""),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(api_router)

    return app


app = create_app()
