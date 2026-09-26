# backend/app/utils/embeddings.py
"""
Embedding helper for multilingual text → dense vector conversion.

Uses sentence-transformers with the multilingual MPNet model which
supports both English and Vietnamese out of the box.

The ``EmbeddingService`` instance is module-level to avoid reloading
the model on every call (model loading is slow ~2-4 s).
"""

from __future__ import annotations

from threading import Lock
from typing import TYPE_CHECKING, cast

import structlog

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

from app.config import get_settings

logger = structlog.get_logger(__name__)

# Module-level singleton — loaded once on first import
_model: SentenceTransformer | None = None
_model_lock = Lock()


def _get_model() -> SentenceTransformer:
    global _model
    with _model_lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer

            settings = get_settings()
            logger.info("loading_embedding_model", model=settings.qdrant_embedding_model)
            _model = SentenceTransformer(settings.qdrant_embedding_model)
            logger.info("embedding_model_loaded")
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Convert a list of texts to dense vectors.

    Args:
        texts: List of strings (claims, arguments, queries).

    Returns:
        List of float vectors, one per input text.
        Dimension is determined by ``qdrant_vector_size`` setting (default 768).
    """
    model = _get_model()
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return cast(list[list[float]], embeddings.tolist())


def embed_single(text: str) -> list[float]:
    """Convenience wrapper for a single text."""
    return embed_texts([text])[0]
