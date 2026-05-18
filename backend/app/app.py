import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.core.runtime import get_resource_root

logger = logging.getLogger(__name__)
FRONTEND_DIST_DIR = get_resource_root() / "frontend" / "dist"


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
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")

    if FRONTEND_DIST_DIR.is_dir():
        # Serve the built Outlook add-in UI and assets from the same host as the API.
        app.mount("/", StaticFiles(directory=FRONTEND_DIST_DIR, html=True), name="frontend")
    else:
        logger.warning("Frontend build directory not found: %s", FRONTEND_DIST_DIR)

    return app


app = create_app()
logger.info("OLLIE Backend initialized successfully.")
