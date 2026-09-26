# backend/app/repositories/session_store.py
"""
Backward-compatibility shim.

The ``SessionStoreRepository`` has been replaced by ``RedisRepository``
in ``app.repositories.redis_repo``.  Session-specific key formatting
now lives in ``SessionService``.

.. deprecated::
    Import from ``app.repositories.redis_repo`` instead.
"""

from __future__ import annotations

from app.repositories.redis_repo import RedisRepository  # noqa: F401
