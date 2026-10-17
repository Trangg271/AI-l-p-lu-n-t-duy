# backend/app/config.py
"""
Application configuration via pydantic-settings.

All settings are read from environment variables (or a .env file).
Use `get_settings()` everywhere — it is LRU-cached so the .env is parsed once.

Usage:
    from app.config import get_settings

    settings = get_settings()
    client, model = settings.get_ai_client("fast")
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Literal

import structlog
from google import genai
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.utils.llm import ChatClient, GeminiChatClient, OpenAIChatClient

logger = structlog.get_logger(__name__)


class Settings(BaseSettings):
    """Central configuration for SocraticAI backend."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── AI providers ─────────────────────────────────────────────────────────
    ai_provider: Literal["openai", "gemini"] | None = Field(
        default=None,
        description="AI provider; when unset, use OpenAI if configured, otherwise Gemini.",
    )
    openai_api_key: SecretStr | None = Field(
        default=None, description="OpenAI API key; supply through the environment."
    )
    openai_fast_model: str = "gpt-4.1-mini"
    openai_complex_model: str = "gpt-4.1"
    google_api_key: SecretStr | None = Field(
        default=None, description="Optional Google AI Studio API key for Gemini."
    )
    gemini_fast_model: str = "gemini-3.5-flash-lite"
    gemini_complex_model: str = "gemini-3.1-flash-lite"

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
        default=90 * 24 * 60 * 60,
        description="TTL for session keys in Redis (seconds); defaults to 90 days for practice history",
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

    @property
    def selected_ai_provider(self) -> Literal["openai", "gemini"]:
        if self.ai_provider is not None:
            provider = self.ai_provider
        elif self.openai_api_key and self.openai_api_key.get_secret_value().strip():
            provider = "openai"
        else:
            provider = "gemini"

        key = self.openai_api_key if provider == "openai" else self.google_api_key
        if key is None or not key.get_secret_value().strip():
            variable = "OPENAI_API_KEY" if provider == "openai" else "GOOGLE_API_KEY"
            raise ValueError(f"AI_PROVIDER={provider} requires {variable} to be configured.")
        return provider

    def get_ai_client(self, task: Literal["fast", "complex"]) -> tuple[ChatClient, str]:
        provider = self.selected_ai_provider
        client: ChatClient
        if provider == "openai":
            model_name = self.openai_fast_model if task == "fast" else self.openai_complex_model
            client = OpenAIChatClient(
                api_key=self._required_api_key(self.openai_api_key, "OPENAI_API_KEY"),
                model=model_name,
            )
        else:
            model_name = self.gemini_fast_model if task == "fast" else self.gemini_complex_model
            client = GeminiChatClient(
                genai.Client(
                    api_key=self._required_api_key(self.google_api_key, "GOOGLE_API_KEY"),
                    http_options={"timeout": 60_000},
                ),
                model=model_name,
            )

        logger.info(
            "ai_model_selected",
            provider=provider,
            task=task,
            model=model_name,
            environment=self.environment,
        )
        return client, model_name

    @staticmethod
    def _required_api_key(key: SecretStr | None, variable: str) -> str:
        if key is None or not key.get_secret_value().strip():
            raise ValueError(f"{variable} is required for the selected AI provider.")
        return key.get_secret_value()

    def get_gemini_model(self, task: Literal["fast", "complex"]) -> tuple["genai.Client", str]:
        """
        Return a native Gemini client for integrations that need Gemini-specific APIs.

        Callers should use::

            client, model_name = settings.get_gemini_model("fast")
            response = await client.aio.models.generate_content(
                model=model_name, contents=[...]
            )
        """
        if self.google_api_key is None or not self.google_api_key.get_secret_value().strip():
            raise ValueError("GOOGLE_API_KEY is required for direct Gemini access.")
        model_name = self.gemini_fast_model if task == "fast" else self.gemini_complex_model
        client = genai.Client(
            api_key=self.google_api_key.get_secret_value(),
            http_options={"timeout": 60_000},
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
    ai_provider = settings.selected_ai_provider
    logger.info(
        "settings_loaded",
        environment=settings.environment,
        ai_provider=ai_provider,
        qdrant_url=settings.qdrant_url,
        redis_url=settings.redis_url,
    )
    return settings
