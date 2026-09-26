"""Stream debate turns and persist complete session snapshots in Redis."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

import structlog

from app.graph.graph import build_debate_graph
from app.models.session import SessionMetadata, SessionScore, SessionState, Turn
from app.models.ws import WSFrame, WSFrameType
from app.services.session_service import SessionService

logger = structlog.get_logger(__name__)
_DEBATE_GRAPH = build_debate_graph()
_session_service = SessionService()


class DebateService:
    def _state(self, session: SessionMetadata) -> SessionState:
        return {
            "session_id": str(session.session_id),
            "config": session.config,
            "turns": session.turns,
            "extracted_claims": session.claims,
            "contradiction_alerts": session.contradiction_alerts,
            "current_user_message": "",
            "ai_response": "",
            "fallacy_analysis": [],
            "session_score": session.grade,
            "is_ended": False,
        }

    async def process_user_turn(
        self,
        session: SessionMetadata,
        user_input: str,
    ) -> AsyncGenerator[WSFrame, None]:
        state = self._state(session)
        state["turns"] = session.turns + [
            Turn(
                turn_number=len(session.turns),
                speaker="user",
                content=user_input,
            )
        ]
        state["current_user_message"] = user_input
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def run_graph() -> dict[str, Any]:
            try:
                async with asyncio.timeout(180):
                    result: dict[str, Any] = await _DEBATE_GRAPH.ainvoke(
                        state,
                        config={"configurable": {"token_queue": queue}},
                    )
                    return result
            finally:
                # Always unblock the consumer, including errors before the first token.
                queue.put_nowait(None)

        task = asyncio.create_task(run_graph())
        try:
            while (chunk := await queue.get()) is not None:
                yield WSFrame(type=WSFrameType.TOKEN, data=chunk)
            result = await task
            turns = [Turn.model_validate(turn) for turn in result["turns"]]
            fallacies = result.get("fallacy_analysis") or []
            turns[-2].fallacies_detected = fallacies
            claims = result.get("extracted_claims", [])
            for turn in turns[-2:]:
                turn.claims_extracted = [c for c in claims if c.turn_number == turn.turn_number]
            updated = session.model_copy(deep=True)
            updated.turns = turns
            updated.claims = claims
            updated.contradiction_alerts += result.get("contradiction_alerts", [])
            updated.turn_count += 1
            await _session_service.update_session(updated)
            for fallacy in fallacies:
                yield WSFrame(type=WSFrameType.FALLACY, data=fallacy.model_dump(mode="json"))
            for alert in result.get("contradiction_alerts", []):
                yield WSFrame(type=WSFrameType.CONTRADICTION, data=alert)
            yield WSFrame(type=WSFrameType.TURN_DONE, data=self._snapshot(updated))
        except Exception:
            logger.exception("debate_turn_failed", session_id=str(session.session_id))
            yield WSFrame(
                type=WSFrameType.ERROR,
                data=(
                    "Unable to complete this turn. Please try again. / "
                    "Không thể hoàn thành lượt này. Vui lòng thử lại."
                ),
            )
            yield await self.get_sync_frame(session)
        finally:
            if not task.done():
                task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task

    async def end_session(self, session: SessionMetadata) -> AsyncGenerator[WSFrame, None]:
        if session.grade:
            yield WSFrame(type=WSFrameType.SCORE, data=session.grade.model_dump(mode="json"))
            return
        if not session.turns:
            yield WSFrame(type=WSFrameType.ERROR, data="Complete at least one turn before scoring.")
            return
        session.status = "ended"
        session.ended_at = session.ended_at or datetime.now(UTC)
        await _session_service.update_session(session)
        yield WSFrame(type=WSFrameType.GRADING, data={})
        state = self._state(session)
        state["is_ended"] = True
        try:
            async with asyncio.timeout(120):
                result = await _DEBATE_GRAPH.ainvoke(state)
            score = result.get("session_score")
            if score is None:
                raise RuntimeError("No score returned")
            session.grade = SessionScore.model_validate(score)
            session.status = "graded"
            await _session_service.update_session(session)
            yield WSFrame(type=WSFrameType.SCORE, data=session.grade.model_dump(mode="json"))
        except Exception:
            logger.exception("session_grading_failed", session_id=str(session.session_id))
            yield WSFrame(
                type=WSFrameType.ERROR,
                data=(
                    "Scoring failed. Your debate is saved; select End & Score to retry. / "
                    "Chấm điểm thất bại. Hội thoại đã lưu; chọn End & Score để thử lại."
                ),
            )
        yield WSFrame(type=WSFrameType.SESSION_ENDED, data={"status": session.status})

    def _snapshot(self, session: SessionMetadata) -> dict[str, Any]:
        return {
            "turns": [t.model_dump(mode="json") for t in session.turns],
            "extracted_claims": [c.model_dump(mode="json") for c in session.claims],
            "fallacy_analysis": [
                f.model_dump(mode="json") for t in session.turns for f in t.fallacies_detected
            ],
            "contradiction_alerts": session.contradiction_alerts,
            "session_score": session.grade.model_dump(mode="json") if session.grade else None,
            "status": session.status,
            "turn_count": session.turn_count,
            "max_turns": session.max_turns,
            "config": session.config.model_dump(mode="json"),
        }

    async def get_sync_frame(self, session: SessionMetadata) -> WSFrame:
        return WSFrame(type=WSFrameType.SYNC, data=self._snapshot(session))
