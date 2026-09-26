# backend/app/services/session_service.py
"""
SessionService — manages session lifecycle (create, get, end).

All session metadata is stored in Redis via ``RedisRepository`` with
a configurable TTL.  This is the Imperative Shell for session I/O.
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from uuid import UUID

import structlog

from app.config import get_settings
from app.models.session import (
    CreateSessionRequest,
    DebateConfig,
    EndSessionRequest,
    SessionMetadata,
)
from app.repositories.redis_repo import RedisRepository

logger = structlog.get_logger(__name__)

# ── Redis repository singleton ────────────────────────────────────────────────
_redis_repo: RedisRepository | None = None


def _get_redis_repo() -> RedisRepository:
    """Lazy-initialise the Redis repository singleton."""
    global _redis_repo
    if _redis_repo is None:
        _redis_repo = RedisRepository()
    return _redis_repo


def _session_key(session_id: UUID) -> str:
    """Build the Redis key for a session.

    Args:
        session_id: The session UUID.

    Returns:
        A namespaced Redis key string.
    """
    return f"socratic:session:{session_id}"


class SessionService:
    """Manages the full session lifecycle: create → get → end.

    All state is stored in Redis.  This service is stateless — safe
    to instantiate multiple times.
    """

    def lock_session(self, session_id: UUID) -> AbstractAsyncContextManager[bool]:
        return _get_redis_repo().session_lock(_session_key(session_id))

    async def create_session(self, request: CreateSessionRequest) -> SessionMetadata:
        """Create a new debate session and persist it to Redis.

        Builds a ``DebateConfig`` from the request, auto-assigns the AI
        position as the opposite of the user's, and stores the full
        ``SessionMetadata`` in Redis.

        Args:
            request: The session creation request body.

        Returns:
            The newly created ``SessionMetadata`` with a generated ``session_id``.
        """
        settings = get_settings()
        log = logger.bind(topic=request.topic, language=request.language)

        # Auto-assign AI position as opposite of user
        ai_position = "con" if request.user_position.lower() in ("pro", "for") else "pro"

        config = DebateConfig(
            topic=request.topic,
            topic_description=request.topic_description,
            language=request.language,
            difficulty=request.difficulty,
            ai_position=ai_position,
            user_position=request.user_position,
        )

        session = SessionMetadata(
            config=config,
            status="active",
            max_turns=request.max_turns or settings.max_debate_turns,
        )

        repo = _get_redis_repo()
        key = _session_key(session.session_id)

        await repo.set(
            key=key,
            value=session.model_dump_json(),
            ttl=settings.redis_session_ttl_seconds,
        )

        log.info("session_created", session_id=str(session.session_id))
        return session

    async def get_session(self, session_id: UUID) -> SessionMetadata | None:
        """Retrieve session metadata from Redis.

        Args:
            session_id: The session UUID to look up.

        Returns:
            The ``SessionMetadata`` if found, ``None`` otherwise.
        """
        repo = _get_redis_repo()
        key = _session_key(session_id)

        data = await repo.get(key)
        if data is None:
            logger.bind(session_id=str(session_id)).warning("session_not_found")
            return None

        return SessionMetadata.model_validate_json(data)

    async def update_session(self, session: SessionMetadata) -> None:
        """Persist updated session metadata back to Redis.

        Args:
            session: The session metadata to save.
        """
        settings = get_settings()
        repo = _get_redis_repo()
        key = _session_key(session.session_id)

        await repo.set(
            key=key,
            value=session.model_dump_json(),
            ttl=settings.redis_session_ttl_seconds,
        )

    async def end_session(
        self,
        session_id: UUID,
        request: EndSessionRequest,
    ) -> SessionMetadata | None:
        """Mark a session as ended and persist the update.

        Args:
            session_id: The session UUID to end.
            request: The end session request body with optional reason.

        Returns:
            The updated ``SessionMetadata`` if found, ``None`` otherwise.
        """
        log = logger.bind(session_id=str(session_id))

        session = await self.get_session(session_id)
        if session is None:
            return None

        if session.status in ("ended", "graded"):
            return session

        session.status = "ended"
        session.ended_at = datetime.now(UTC)

        await self.update_session(session)

        log.info("session_ended", reason=request.reason)
        return session
