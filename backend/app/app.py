import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    # Configure logging within the app lifecycle
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
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app


app = create_app()
logger.info("OLLIE Backend initialized successfully.")
