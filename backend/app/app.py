import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.dependencies import container

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Handles startup and shutdown events for the FastAPI application."""
    container.init_services()
    yield
    container.close_services()


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
        allow_origins=["*"],  # TODO: Adjust for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        """Ensures every error reaches the frontend as JSON, never Starlette's
        default plain-text 500 page, which the generated API client can't parse.
        """
        logger.exception("Unhandled exception while processing request: %s", exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})

    # Include API routes
    app.include_router(api_router)

    return app


app = create_app()
