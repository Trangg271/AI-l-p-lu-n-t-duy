"""Provider-neutral async chat clients used by the debate graph."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from google import genai
from google.genai.types import GenerateContentConfig
from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.shared_params import ResponseFormatJSONObject


class ChatClient(Protocol):
    async def complete(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        json_output: bool = False,
    ) -> str: ...

    def stream(
        self, prompt: str, *, system_instruction: str | None = None
    ) -> AsyncIterator[str]: ...

    async def aclose(self) -> None: ...


class OpenAIChatClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key, timeout=60.0)
        self._model = model

    def _messages(
        self, prompt: str, system_instruction: str | None
    ) -> list[ChatCompletionMessageParam]:
        messages: list[ChatCompletionMessageParam] = []
        if system_instruction:
            system_message: ChatCompletionSystemMessageParam = {
                "role": "system",
                "content": system_instruction,
            }
            messages.append(system_message)
        user_message: ChatCompletionUserMessageParam = {"role": "user", "content": prompt}
        messages.append(user_message)
        return messages

    async def complete(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        json_output: bool = False,
    ) -> str:
        if json_output:
            response_format: ResponseFormatJSONObject = {"type": "json_object"}
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=self._messages(prompt, system_instruction),
                response_format=response_format,
            )
        else:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=self._messages(prompt, system_instruction),
            )
        return response.choices[0].message.content or ""

    async def stream(
        self, prompt: str, *, system_instruction: str | None = None
    ) -> AsyncIterator[str]:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=self._messages(prompt, system_instruction),
            stream=True,
        )
        async for chunk in response:
            if chunk.choices:
                content = chunk.choices[0].delta.content
                if content:
                    yield content

    async def aclose(self) -> None:
        await self._client.close()


class GeminiChatClient:
    def __init__(self, client: genai.Client, model: str) -> None:
        self._client = client
        self._model = model

    async def complete(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        json_output: bool = False,
    ) -> str:
        config = GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json" if json_output else None,
        )
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config if system_instruction or json_output else None,
        )
        return response.text or ""

    async def stream(
        self, prompt: str, *, system_instruction: str | None = None
    ) -> AsyncIterator[str]:
        config = (
            GenerateContentConfig(system_instruction=system_instruction)
            if system_instruction
            else None
        )
        response = await self._client.aio.models.generate_content_stream(
            model=self._model,
            contents=prompt,
            config=config,
        )
        async for chunk in response:
            if chunk.text:
                yield chunk.text

    async def aclose(self) -> None:
        await self._client.aio.aclose()
        self._client.close()
