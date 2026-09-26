"""Tests run without network, storage servers, or real API keys."""

import os
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

os.environ["GOOGLE_API_KEY"] = "test-key-placeholder"
os.environ["ENVIRONMENT"] = "development"

from app.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services import session_service  # noqa: E402


class MemoryRepository:
    def __init__(self):
        self.values = {}
        self.locks = set()

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ttl=None):
        self.values[key] = value

    @asynccontextmanager
    async def session_lock(self, key):
        if key in self.locks:
            yield False
            return
        self.locks.add(key)
        try:
            yield True
        finally:
            self.locks.remove(key)


@pytest.fixture(autouse=True)
def memory_repo(monkeypatch):
    get_settings.cache_clear()
    repo = MemoryRepository()
    monkeypatch.setattr(session_service, "_redis_repo", repo)
    yield repo
    get_settings.cache_clear()


@pytest.fixture
async def test_client():
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
def score_data():
    return dict(
        argument_depth=20,
        logical_consistency=21,
        evidence_quality=19,
        rebuttal_effectiveness=22,
        total=82,
        grade="B",
    )
