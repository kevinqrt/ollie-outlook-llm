from fastapi import APIRouter

from app.api.routes.email import router as email_router
from app.api.routes.health import router as health_router
from app.api.routes.rag import router as rag_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(email_router, tags=["email"])
api_router.include_router(rag_router, tags=["rag"])
