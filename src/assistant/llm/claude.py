"""Anthropic Claude API client."""

from collections.abc import Iterator
from typing import ClassVar

import anthropic

from assistant.exceptions import LLMError


class ClaudeClient:
    """Wraps the Anthropic SDK so no other layer imports anthropic directly."""

    DEFAULT_MODEL: ClassVar[str] = "claude-opus-4-6"
    DEFAULT_MAX_TOKENS: ClassVar[int] = 4096

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def stream_response(self, system_prompt: str, user_message: str) -> Iterator[str]:
        """Stream text chunks from Claude.

        Yields:
            Text delta strings as they arrive.

        Raises:
            LLMError: On Anthropic API failure.
        """
        try:
            with self._client.messages.stream(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            ) as stream:
                yield from stream.text_stream
        except anthropic.APIError as e:
            raise LLMError(f"Claude API error: {e}") from e
