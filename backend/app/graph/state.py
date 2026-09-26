# backend/app/graph/state.py
"""
Backward-compatibility shim.

The ``DebateState`` has been replaced by ``SessionState`` TypedDict
defined in ``app.models.session``.

.. deprecated::
    Import ``SessionState`` from ``app.models.session`` instead.
"""

from __future__ import annotations

from app.models.session import SessionState  # noqa: F401

# Alias for backward compatibility
DebateState = SessionState
