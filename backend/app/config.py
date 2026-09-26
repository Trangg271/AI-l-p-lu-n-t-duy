# backend/app/config.py
"""
Application configuration via pydantic-settings.

All settings are read from environment variables (or a .env file).
Use `get_settings()` everywhere — it is LRU-cached so the .env is parsed once.

Usage:
    from app.config import get_settings

    settings = get_settings()
    model = settings.get_gemini_model("fast")
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Literal

import structlog
from google import genai
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger(__name__)

# Model defaults can be overridden using GEMINI_FAST_MODEL / GEMINI_COMPLEX_MODEL.
_MODEL_MAP: dict[str, str] = {
    "fast": "gemini-3.5-flash-lite",
    "complex": "gemini-3.1-flash-lite",
}


class Settings(BaseSettings):
    """Central configuration for SocraticAI backend."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Google AI Studio ───────────────────────────────────────────────────────
    google_api_key: SecretStr = Field(..., description="Google AI Studio API key")

    gemini_fast_model: str = _MODEL_MAP["fast"]
    gemini_complex_model: str = _MODEL_MAP["complex"]

    # ── Qdrant ────────────────────────────────────────────────────────────────
    qdrant_url: str = Field(
        default="http://localhost:6333",
        description="Qdrant REST endpoint",
    )
    qdrant_collection_name: str = Field(
        default="socratic_claims",
        description="Qdrant collection for debate claim vectors",
    )
    qdrant_vector_size: int = Field(
        default=768,
        description="Embedding dimension (must match the chosen sentence-transformer model)",
    )
    qdrant_embedding_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        description="HuggingFace model used for claim embeddings (English + Vietnamese)",
    )

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL",
    )
    redis_session_ttl_seconds: int = Field(
        default=3600,
        description="TTL for session keys in Redis (seconds)",
    )

    # ── CORS / Frontend ────────────────────────────────────────────────────────
    cors_origins: str | list[str] = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins",
    )

    # ── Application ────────────────────────────────────────────────────────────
    environment: Literal["development", "staging", "production"] = Field(default="development")
    log_level: str = Field(default="INFO")

    # ── Debate engine ─────────────────────────────────────────────────────────
    max_debate_turns: int = Field(
        default=20,
        description="Maximum number of turns before a session is force-ended",
    )
    memory_top_k: int = Field(
        default=5,
        description="Top-k similar claims to retrieve from Qdrant per turn",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, v: str | list[str]) -> list[str]:
        """Allow a comma-separated string from the env file."""
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    # ── Gemini model factory ──────────────────────────────────────────────────

    def get_gemini_model(self, task: Literal["fast", "complex"]) -> tuple["genai.Client", str]:
        """
        Return a ``(client, model_name)`` tuple for the given task tier.

        Callers should use::

            client, model_name = settings.get_gemini_model("fast")
            response = await client.aio.models.generate_content(
                model=model_name, contents=[...]
            )
        """
        model_name = self.gemini_fast_model if task == "fast" else self.gemini_complex_model

        client = genai.Client(
            api_key=self.google_api_key.get_secret_value(),
            http_options={"timeout": 60_000},
        )

        logger.info(
            "gemini_model_selected",
            task=task,
            model=model_name,
            environment=self.environment,
        )

        return client, model_name

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached :class:`Settings` singleton.

    The first call reads from the environment / .env file.
    Subsequent calls return the cached instance — zero I/O overhead.

    To reset in tests::

        get_settings.cache_clear()
    """
    settings = Settings()
    logger.info(
        "settings_loaded",
        environment=settings.environment,
        qdrant_url=settings.qdrant_url,
        redis_url=settings.redis_url,
    )
    return settings
