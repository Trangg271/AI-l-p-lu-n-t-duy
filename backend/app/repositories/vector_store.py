# backend/app/repositories/vector_store.py
"""
Backward-compatibility shim.

The ``VectorStoreRepository`` has been replaced by ``QdrantRepository``
in ``app.repositories.qdrant_repo``.

.. deprecated::
    Import from ``app.repositories.qdrant_repo`` instead.
"""

from __future__ import annotations

from app.repositories.qdrant_repo import QdrantRepository  # noqa: F401
