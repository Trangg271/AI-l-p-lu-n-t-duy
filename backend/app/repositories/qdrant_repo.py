# backend/app/repositories/qdrant_repo.py
"""
QdrantRepository — async Qdrant client wrapper using the Repository Pattern.

Provides a clean interface for:
  - Collection bootstrapping (idempotent ``initialize_collection``)
  - Point upsert with pre-computed embeddings
  - Filtered similarity search (top-k retrieval)

All methods are async and I/O-bound — they live in the Imperative Shell
layer and are called from LangGraph nodes via dependency injection.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from app.config import get_settings

logger = structlog.get_logger(__name__)


class QdrantRepository:
    """Thin async wrapper around the Qdrant vector database client.

    Instantiate once at app startup and share across the application.
    The underlying ``AsyncQdrantClient`` manages its own connection pool.
    """

    def __init__(self, url: str | None = None) -> None:
        """Initialise the Qdrant client.

        Args:
            url: Qdrant REST endpoint.  Falls back to ``settings.qdrant_url``
                 if not provided.
        """
        settings = get_settings()
        self._client = AsyncQdrantClient(url=url or settings.qdrant_url)
        self._default_collection = settings.qdrant_collection_name
        self._vector_size = settings.qdrant_vector_size

    async def initialize_collection(self, name: str | None = None) -> None:
        """Create a vector collection if it does not already exist.

        Args:
            name: Collection name.  Defaults to the configured collection.

        This operation is idempotent — safe to call on every startup.
        """
        collection = name or self._default_collection
        log = logger.bind(collection=collection)

        exists = await self._client.collection_exists(collection)
        if not exists:
            await self._client.create_collection(
                collection_name=collection,
                vectors_config=qmodels.VectorParams(
                    size=self._vector_size,
                    distance=qmodels.Distance.COSINE,
                ),
            )
            log.info("qdrant_collection_created")
        else:
            log.debug("qdrant_collection_already_exists")

    async def upsert_points(
        self,
        points: list[dict[str, Any]],
        collection: str | None = None,
    ) -> None:
        """Upsert a batch of points into the specified collection.

        Each point dict must contain:
          - ``vector``: ``list[float]`` — the dense embedding
          - ``payload``: ``dict`` — arbitrary metadata (session_id, claim_text, etc.)
          - ``id`` (optional): ``str`` — point ID; auto-generated if absent

        Args:
            points: List of point dicts to upsert.
            collection: Target collection name.  Defaults to the configured collection.
        """
        target = collection or self._default_collection
        qdrant_points = [
            qmodels.PointStruct(
                id=p.get("id", str(uuid4())),
                vector=p["vector"],
                payload=p.get("payload", {}),
            )
            for p in points
        ]
        await self._client.upsert(
            collection_name=target,
            points=qdrant_points,
        )
        logger.info(
            "qdrant_points_upserted",
            count=len(qdrant_points),
            collection=target,
        )

    async def search(
        self,
        vector: list[float],
        collection: str | None = None,
        filter_: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Perform a similarity search and return the top-k results.

        Args:
            vector: The query embedding vector.
            collection: Collection to search.  Defaults to the configured collection.
            filter_: Optional Qdrant filter dict (converted to ``Filter`` internally).
                     Expected shape: ``{"session_id": "..."}`` for session-scoped search.
            top_k: Number of nearest neighbours to return.

        Returns:
            List of dicts with ``id``, ``score``, and ``payload`` keys.
        """
        target = collection or self._default_collection

        query_filter = None
        if filter_:
            must_conditions = []
            for key, value in filter_.items():
                must_conditions.append(
                    qmodels.FieldCondition(
                        key=key,
                        match=qmodels.MatchValue(value=value),
                    )
                )
            query_filter = qmodels.Filter(must=must_conditions)

        results = await self._client.query_points(
            collection_name=target,
            query=vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )

        return [
            {
                "id": str(hit.id),
                "score": hit.score,
                "payload": hit.payload or {},
            }
            for hit in results.points
        ]

    async def close(self) -> None:
        """Close the underlying Qdrant client connection."""
        await self._client.close()
