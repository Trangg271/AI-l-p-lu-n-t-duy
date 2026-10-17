from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from app.config import Settings
from app.utils.llm import GeminiChatClient, OpenAIChatClient


def test_openai_is_selected_when_its_key_is_configured():
    settings = Settings(
        _env_file=None,
        ai_provider=None,
        openai_api_key=SecretStr("test-openai-key"),
        google_api_key=SecretStr("test-google-key"),
    )

    client, model = settings.get_ai_client("fast")

    assert settings.selected_ai_provider == "openai"
    assert model == "gpt-4.1-mini"
    assert isinstance(client, OpenAIChatClient)


def test_explicit_provider_requires_its_own_key():
    settings = Settings(_env_file=None, ai_provider="openai")

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        _ = settings.selected_ai_provider


async def test_gemini_remains_available_when_only_its_key_is_configured():
    settings = Settings(
        _env_file=None,
        ai_provider=None,
        google_api_key=SecretStr("test-google-key"),
    )

    client, model = settings.get_ai_client("complex")

    assert settings.selected_ai_provider == "gemini"
    assert model == settings.gemini_complex_model
    assert isinstance(client, GeminiChatClient)
    await client.aclose()


async def test_openai_adapter_sends_system_prompt_and_json_mode():
    create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))]
        )
    )
    close = AsyncMock()
    adapter = OpenAIChatClient.__new__(OpenAIChatClient)
    adapter._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
        close=close,
    )
    adapter._model = "test-model"

    response = await adapter.complete(
        "Return JSON",
        system_instruction="You are a test assistant",
        json_output=True,
    )
    await adapter.aclose()

    assert response == '{"ok":true}'
    assert create.await_args.kwargs == {
        "model": "test-model",
        "messages": [
            {"role": "system", "content": "You are a test assistant"},
            {"role": "user", "content": "Return JSON"},
        ],
        "response_format": {"type": "json_object"},
    }
    close.assert_awaited_once()


async def test_openai_adapter_streams_only_text_deltas():
    async def stream_chunks():
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Hello"))])
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=" world"))])
        yield SimpleNamespace(choices=[])

    create = AsyncMock(return_value=stream_chunks())
    adapter = OpenAIChatClient.__new__(OpenAIChatClient)
    adapter._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
        close=AsyncMock(),
    )
    adapter._model = "test-model"

    chunks = [chunk async for chunk in adapter.stream("Hi", system_instruction="Be concise")]

    assert chunks == ["Hello", " world"]
    assert create.await_args.kwargs["stream"] is True
    assert create.await_args.kwargs["messages"][0] == {
        "role": "system",
        "content": "Be concise",
    }
