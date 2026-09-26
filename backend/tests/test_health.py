# backend/tests/test_health.py
"""Smoke tests for the health and session endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_ok(test_client: AsyncClient) -> None:
    response = await test_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "socratic-ai-backend"


@pytest.mark.asyncio
async def test_create_session_returns_201(test_client: AsyncClient) -> None:
    payload = {
        "topic": "Artificial intelligence will eliminate more jobs than it creates.",
        "language": "en",
        "user_stance": "pro",
    }
    response = await test_client.post("/session/create", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert "session_id" in body
    assert body["status"] == "active"


@pytest.mark.asyncio
async def test_get_nonexistent_session_returns_404(test_client: AsyncClient) -> None:
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await test_client.get(f"/session/{fake_id}")
    assert response.status_code == 404
