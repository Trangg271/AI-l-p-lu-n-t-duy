# backend/app/models/ws.py
"""
WebSocket message frame models for the real-time debate stream.

Server → Client frame types:
    ``token``         — a single streamed token from the AI response
    ``fallacy``       — a detected logical fallacy (FallacyResult)
    ``score``         — post-session rubric score (SessionScore)
    ``contradiction`` — a contradiction alert string
    ``error``         — an error message

Client → Server message types:
    ``user_message``  — the user's debate argument
    ``end_session``   — request to end the session and trigger grading
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

# ─── Server → Client ─────────────────────────────────────────────────────────


class WSFrameType(str, Enum):
    """Discriminator for server-to-client WebSocket frames."""

    TOKEN = "token"
    FALLACY = "fallacy"
    SCORE = "score"
    CONTRADICTION = "contradiction"
    ERROR = "error"
    SYNC = "sync"
    TURN_DONE = "turn_done"
    SESSION_ENDED = "session_ended"
    GRADING = "grading"


class WSFrame(BaseModel):
    """Envelope for all server-to-client WebSocket frames.

    The ``type`` field is the discriminator; ``data`` carries the
    payload whose shape depends on the type:

    - ``token``: ``str`` (a single token or chunk of text)
    - ``fallacy``: ``FallacyResult`` dict
    - ``score``: ``SessionScore`` dict
    - ``contradiction``: ``str`` (alert message)
    - ``error``: ``str`` (error description)
    """

    type: WSFrameType = Field(..., description="Frame type discriminator.")
    data: Any = Field(..., description="Payload — shape depends on type.")


# ─── Client → Server ─────────────────────────────────────────────────────────


class WSClientMessageType(str, Enum):
    """Discriminator for client-to-server WebSocket messages."""

    USER_MESSAGE = "user_message"
    END_SESSION = "end_session"
    PING = "ping"


class WSClientMessage(BaseModel):
    """Envelope for all client-to-server WebSocket messages.

    ``user_message`` payload: ``{"content": str, "language": str}``
    ``end_session``  payload: ``{"reason": str | None}``
    ``ping``         payload: ``{}``
    """

    type: Literal["user_message", "end_session", "ping"] = Field(
        ...,
        description="Message type discriminator.",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Message payload.",
    )
