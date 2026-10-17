"""Opt-in live smoke test. Makes short AI requests and an isolated Redis write."""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings
from app.repositories.qdrant_repo import QdrantRepository
from app.repositories.redis_repo import RedisRepository


async def main():
    settings = get_settings()
    redis = RedisRepository()
    qdrant = QdrantRepository()
    key = f"socratic:audit:{uuid4()}"
    try:
        assert await redis.ping(), "Redis unavailable"
        await redis.set(key, "ok", ttl=60)
        assert await redis.get(key) == "ok"
        async with redis.session_lock(key) as acquired:
            assert acquired
        print("Redis read/write/lock: PASS", flush=True)
        await qdrant.initialize_collection()
        results = await qdrant.search(
            [0.1] * settings.qdrant_vector_size,
            filter_={"session_id": "audit-nonexistent"},
            top_k=1,
        )
        assert results == []
        print("Qdrant collection/search: PASS", flush=True)
        for task in ["fast", "complex"]:
            client, model = settings.get_ai_client(task)
            try:
                response = await client.complete("Reply with OK only.")
                assert response
                print(f"{settings.selected_ai_provider} {task} ({model}): PASS", flush=True)
            except Exception as exc:
                # Do not expose API keys or provider response bodies in output.
                print(
                    f"{settings.selected_ai_provider} {task} ({model}): FAIL {type(exc).__name__}",
                    flush=True,
                )
            finally:
                await client.aclose()
    finally:
        await redis.delete(key)
        await redis.close()
        await qdrant.close()


asyncio.run(main())
