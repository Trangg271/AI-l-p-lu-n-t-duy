# backend/app/utils/logging.py
"""
Structured logging utilities for SocraticAI.

Provides:
  - ``get_logger``  — thin re-export of structlog.get_logger (use this everywhere)
  - ``log_duration`` — async context manager that logs execution time of any block
  - ``bind_request_context`` — FastAPI middleware helper that binds request IDs
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from uuid import uuid4

import structlog

# Re-export so the rest of the codebase only imports from app.utils.logging
get_logger = structlog.get_logger


@asynccontextmanager
async def log_duration(
    logger: structlog.stdlib.BoundLogger,
    operation: str,
    **extra: object,
) -> AsyncGenerator[None, None]:
    """
    Async context manager that logs the wall-clock duration of a block.

    Usage::

        async with log_duration(log, "qdrant_search", collection="socratic_claims"):
            results = await client.search(...)
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(f"{operation}_duration_ms", elapsed_ms=round(elapsed_ms, 2), **extra)


def generate_request_id() -> str:
    """Generate a short request-scoped correlation ID."""
    return uuid4().hex[:12]
