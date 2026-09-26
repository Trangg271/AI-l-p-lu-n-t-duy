# backend/app/models/debate.py
"""
Backward-compatibility re-exports.

All domain models have been consolidated into ``app.models.session``
and ``app.models.ws``.  This module re-exports commonly used names
so that existing imports continue to work during the migration.

.. deprecated::
    Import directly from ``app.models.session`` or ``app.models.ws`` instead.
"""

from __future__ import annotations

# Re-export domain models from session.py
from app.models.session import (  # noqa: F401
    Claim,
    DebateConfig,
    FallacyResult,
    SessionScore,
    SessionState,
    Turn,
)

# Re-export WS models from ws.py
from app.models.ws import (  # noqa: F401
    WSClientMessage,
    WSFrame,
    WSFrameType,
)
