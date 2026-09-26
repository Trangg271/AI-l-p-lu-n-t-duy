# backend/app/main.py
"""
SocraticAI FastAPI application entry point.

Endpoints
---------
WebSocket
    /ws/debate/{session_id}          Real-time streaming debate

REST
    POST   /session/create           Create a new debate session
    GET    /session/{session_id}     Retrieve session metadata
    POST   /session/{session_id}/end Gracefully end a session
    GET    /health                   Liveness probe

Run locally (without Docker):
    uv run uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError

from app.config import get_settings
from app.graph.nodes import _get_qdrant_repo
from app.routers import debate_ws, sessions
from app.services.session_service import _get_redis_repo

# ─── Structured logging setup ─────────────────────────────────────────────────


def _configure_logging(log_level: str = "INFO") -> None:
    """Wire structlog to the standard library logging handler."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.ExceptionRenderer(),
            structlog.dev.ConsoleRenderer()
            if log_level == "DEBUG"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )


logger = structlog.get_logger(__name__)


# ─── Lifespan ─────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown hooks.

    Startup:
      - Configure structured logging
      - Initialise Qdrant collection (idempotent)
      - Ping Redis to verify connectivity

    Shutdown:
      - Close repository connections
    """
    settings = get_settings()
    _configure_logging(settings.log_level)

    logger.info(
        "socratic_ai_starting",
        environment=settings.environment,
        version="0.1.0",
    )

    # ── Initialise Qdrant collection ──────────────────────────────────────
    qdrant_repo = _get_qdrant_repo()
    try:
        await qdrant_repo.initialize_collection()
        logger.info("qdrant_initialized")
    except Exception as exc:
        logger.warning("qdrant_init_failed", error=str(exc))

    # ── Ping Redis ────────────────────────────────────────────────────────
    redis_repo = _get_redis_repo()
    try:
        is_alive = await redis_repo.ping()
        if is_alive:
            logger.info("redis_connected")
        else:
            logger.warning("redis_ping_returned_false")
    except Exception as exc:
        logger.warning("redis_ping_failed", error=str(exc))

    yield  # ← application runs here

    # ── Cleanup ───────────────────────────────────────────────────────────
    try:
        await qdrant_repo.close()
    except Exception:
        pass
    try:
        await redis_repo.close()
    except Exception:
        pass

    logger.info("socratic_ai_shutting_down")


# ─── App factory ──────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title="SocraticAI",
        description=(
            "Bilingual (EN/VI) AI-powered debate training platform. "
            "Trains critical thinking via the Socratic method and steelmanning."
        ),
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    @application.exception_handler(RedisError)
    async def storage_unavailable(request: Request, exc: RedisError) -> JSONResponse:
        logger.error("storage_unavailable", error=type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={"detail": "Session storage is unavailable. Please try again shortly."},
        )

    # ── CORS ──────────────────────────────────────────────────────────────────
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    application.include_router(sessions.router, prefix="/session", tags=["sessions"])
    application.include_router(debate_ws.router, tags=["debate-ws"])

    # ── Health ────────────────────────────────────────────────────────────────
    @application.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "socratic-ai-backend"}

    return application


app = create_app()


# ─── Dev runner ───────────────────────────────────────────────────────────────


def run() -> None:
    """Entry point for ``uv run socratic-backend``."""
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["app"],
        log_level="info",
    )


if __name__ == "__main__":
    run()
