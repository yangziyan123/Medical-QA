from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers.auth import router as auth_router
from app.api.routers.chat import router as chat_router
from app.api.routers.knowledge import router as knowledge_router
from app.api.routers.sessions import router as sessions_router
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(knowledge_router)
    app.include_router(sessions_router)

    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True, "env": settings.app_env, "name": settings.app_name}

    return app


app = create_app()
