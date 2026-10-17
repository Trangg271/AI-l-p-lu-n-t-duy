# backend/app/routers/sessions.py
"""
REST router for session lifecycle management.

Routes (all mounted under /session in main.py):
    POST   /session/create
    GET    /session/{session_id}
    POST   /session/{session_id}/end
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.models.session import (
    CreateSessionRequest,
    EndSessionRequest,
    EndSessionResponse,
    SessionHistoryEntry,
    SessionHistoryRequest,
    SessionHistoryResponse,
    SessionMetadata,
)
from app.models.ws import WSFrameType
from app.services.debate_service import DebateService
from app.services.session_service import SessionService

router = APIRouter()
_session_service = SessionService()


@router.post(
    "/create",
    response_model=SessionMetadata,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new debate session",
)
async def create_session(request: CreateSessionRequest) -> SessionMetadata:
    """Initialise a new debate session.

    Returns the full ``SessionMetadata`` including the generated ``session_id``
    which should be used for subsequent WebSocket connections and REST calls.
    """
    return await _session_service.create_session(request)


@router.get(
    "/{session_id}",
    response_model=SessionMetadata,
    summary="Get session metadata",
)
async def get_session(session_id: UUID) -> SessionMetadata:
    """Retrieve current metadata for an existing session."""
    session = await _session_service.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    return session


@router.post(
    "/history",
    response_model=SessionHistoryResponse,
    summary="Load compact practice-history summaries",
)
async def get_session_history(request: SessionHistoryRequest) -> SessionHistoryResponse:
    """Load up to 100 browser-recorded sessions without returning full transcripts."""
    sessions = await asyncio.gather(
        *(_session_service.get_session(session_id) for session_id in request.session_ids)
    )
    found: list[SessionHistoryEntry] = []
    missing: list[UUID] = []
    for session_id, session in zip(request.session_ids, sessions, strict=True):
        if session is None:
            missing.append(session_id)
            continue
        found.append(
            SessionHistoryEntry(
                session_id=session.session_id,
                topic=session.config.topic,
                user_position=session.config.user_position,
                status=session.status,
                turn_count=session.turn_count,
                created_at=session.created_at,
                ended_at=session.ended_at,
                grade=session.grade,
            )
        )
    return SessionHistoryResponse(sessions=found, missing_session_ids=missing)


@router.post(
    "/{session_id}/end",
    response_model=EndSessionResponse,
    summary="End a debate session",
)
async def end_session(
    session_id: UUID,
    request: EndSessionRequest,
) -> EndSessionResponse:
    """Gracefully terminate a session.

    Waits for grading, persists the result, and marks the session as graded.
    """
    async with _session_service.lock_session(session_id) as acquired:
        if not acquired:
            raise HTTPException(status_code=409, detail="Session is busy. Try again shortly.")
        session = await _session_service.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        async for frame in DebateService().end_session(session):
            if frame.type == WSFrameType.ERROR:
                raise HTTPException(status_code=503 if session.turns else 409, detail=frame.data)
    return EndSessionResponse(
        session_id=session.session_id,
        status=session.status,
        message="Session ended and scored successfully.",
    )
