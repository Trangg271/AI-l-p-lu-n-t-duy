# backend/app/repositories/redis_repo.py
"""
RedisRepository — generic async Redis client wrapper using the Repository Pattern.

Provides a minimal key-value interface for:
  - Session metadata storage (JSON-serialised Pydantic models)
  - LangGraph checkpointer backing store
  - Generic caching with configurable TTL

All methods are async.  The underlying ``redis.asyncio.Redis`` connection
pool is managed internally; call ``close()`` on shutdown.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from redis.asyncio import Redis

from app.config import get_settings

logger = structlog.get_logger(__name__)


class RedisRepository:
    """Async Redis key-value repository.

    Instantiate once at app startup.  The connection pool is lazily
    created and reused across all calls.
    """

    def __init__(self, url: str | None = None) -> None:
        """Initialise the Redis client.

        Args:
            url: Redis connection URL.  Falls back to ``settings.redis_url``
                 if not provided.
        """
        settings = get_settings()
        self._redis = Redis.from_url(
            url or settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=5,
        )

    async def get(self, key: str) -> str | None:
        """Retrieve a value by key.

        Args:
            key: The Redis key to look up.

        Returns:
            The stored string value, or ``None`` if the key does not exist.
        """
        value = await self._redis.get(key)
        if value is None:
            logger.debug("redis_key_miss", key=key)
        return value

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        """Store a value with an optional TTL.

        Args:
            key: The Redis key.
            value: The string value to store.
            ttl: Time-to-live in seconds.  If ``None``, the key persists
                 until explicitly deleted.
        """
        if ttl is not None:
            await self._redis.setex(name=key, time=ttl, value=value)
        else:
            await self._redis.set(name=key, value=value)
        logger.debug("redis_key_set", key=key, ttl=ttl)

    async def delete(self, key: str) -> None:
        """Delete a key from Redis.

        Args:
            key: The Redis key to delete.  No-op if key does not exist.
        """
        await self._redis.delete(key)
        logger.debug("redis_key_deleted", key=key)

    async def ping(self) -> bool:
        """Check if Redis is reachable.

        Returns:
            ``True`` if the server responds to PING, ``False`` otherwise.
        """
        try:
            return bool(await self._redis.ping())
        except Exception as exc:
            logger.error("redis_ping_failed", error=str(exc))
            return False

    @asynccontextmanager
    async def session_lock(self, key: str) -> AsyncIterator[bool]:
        lock = self._redis.lock(f"{key}:lock", timeout=300, blocking=False)
        acquired = await lock.acquire()
        try:
            yield acquired
        finally:
            if acquired:
                await lock.release()

    async def close(self) -> None:
        """Close the Redis connection pool.

        Call this during application shutdown.
        """
        await self._redis.aclose()  # type: ignore[attr-defined]
        logger.info("redis_connection_closed")
