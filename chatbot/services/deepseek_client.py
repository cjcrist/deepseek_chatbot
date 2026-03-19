"""DeepSeek client backed by DeepInfra's OpenAI-compatible API."""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx


class DeepSeekError(RuntimeError):
    """Raised when the DeepSeek API request fails."""


class DeepSeekClient:
    """Async client for DeepInfra chat completions (buffered and streaming)."""

    def __init__(
        self,
        *,
        token: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
    ) -> None:
        self._model = model
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_seconds, connect=30.0),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )

    async def generate_response(self, messages: list[dict[str, str]]) -> str:
        """Send a chat completion request and return assistant content."""
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }

        try:
            response = await self._client.post("/openai/chat/completions", json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DeepSeekError("Failed to call the DeepSeek API.") from exc

        data = response.json()

        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, AttributeError) as exc:
            raise DeepSeekError("DeepSeek API returned an unexpected response shape.") from exc

    async def stream_chat_completion(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        """Yield assistant text deltas from a streaming chat completion."""
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
        }

        try:
            async with self._client.stream(
                "POST",
                "/openai/chat/completions",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        break
                    try:
                        obj = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    try:
                        choices = obj.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        piece = delta.get("content")
                        if piece:
                            yield piece
                    except (KeyError, IndexError, TypeError):
                        continue
        except httpx.HTTPError as exc:
            raise DeepSeekError("Failed to call the DeepSeek API.") from exc

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
