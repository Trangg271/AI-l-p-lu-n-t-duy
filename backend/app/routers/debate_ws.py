"""Validated, serialized WebSocket operations for a persisted debate session."""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.models.ws import WSClientMessage, WSFrame, WSFrameType
from app.services.debate_service import DebateService
from app.services.session_service import SessionService

logger = structlog.get_logger(__name__)
router = APIRouter()
_session_service = SessionService()
_debate_service = DebateService()


@router.websocket("/ws/debate/{session_id}")
async def debate_websocket(websocket: WebSocket, session_id: UUID) -> None:
    await websocket.accept()
    try:
        session = await _session_service.get_session(session_id)
        if session is None:
            await _send_frame(
                websocket, WSFrame(type=WSFrameType.ERROR, data="Session not found or expired.")
            )
            await websocket.close(code=1008)
            return
        await _send_frame(websocket, await _debate_service.get_sync_frame(session))
        if session.grade:
            await websocket.close(code=1000)
            return
        while True:
            raw = await websocket.receive_text()
            try:
                if len(raw) > 16_000:
                    raise ValueError("Message too large")
                msg = WSClientMessage.model_validate_json(raw)
                content = msg.data.get("content")
                if msg.type == "user_message" and (
                    not isinstance(content, str) or not 1 <= len(content.strip()) <= 1000
                ):
                    raise ValueError("Argument must contain 1–1000 characters")
            except (ValidationError, ValueError):
                await _send_frame(
                    websocket,
                    WSFrame(
                        type=WSFrameType.ERROR,
                        data="Invalid message. Arguments must contain 1–1000 characters.",
                    ),
                )
                continue
            if msg.type == "ping":
                await websocket.send_json({"type": "pong", "data": {}})
                continue
            async with _session_service.lock_session(session_id) as acquired:
                if not acquired:
                    await _send_frame(
                        websocket,
                        WSFrame(
                            type=WSFrameType.ERROR,
                            data="This session is processing another request. Please wait.",
                        ),
                    )
                    continue
                # Refresh metadata so other tabs / REST requests cannot revive an ended session.
                session = await _session_service.get_session(session_id)
                if session is None:
                    await _send_frame(
                        websocket, WSFrame(type=WSFrameType.ERROR, data="Session expired.")
                    )
                    await websocket.close(code=1008)
                    return
                if msg.type == "user_message":
                    if (
                        session.status not in ("pending", "active")
                        or session.turn_count >= session.max_turns
                    ):
                        await _send_frame(
                            websocket,
                            WSFrame(
                                type=WSFrameType.ERROR,
                                data="This debate has ended. Select End & Score to view results.",
                            ),
                        )
                        await _send_frame(websocket, await _debate_service.get_sync_frame(session))
                        continue
                    async for frame in _debate_service.process_user_turn(
                        session, str(content).strip()
                    ):
                        await _send_frame(websocket, frame)
                    session = await _session_service.get_session(session_id)
                    if session is None or session.turn_count < session.max_turns:
                        continue
                async for frame in _debate_service.end_session(session):
                    await _send_frame(websocket, frame)
                if session.grade:
                    await websocket.close(code=1000)
                    return
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("ws_error", session_id=str(session_id))
        try:
            await _send_frame(
                websocket,
                WSFrame(
                    type=WSFrameType.ERROR,
                    data="Service temporarily unavailable. Please reconnect.",
                ),
            )
            await websocket.close(code=1011)
        except Exception:
            pass


async def _send_frame(websocket: WebSocket, frame: WSFrame) -> None:
    await websocket.send_text(frame.model_dump_json())
