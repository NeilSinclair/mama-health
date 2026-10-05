"""Versioned prompts and provider adapters that return pydantic structured outputs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from importlib.resources import files
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from mama_analysis.config import (
    MAX_OUTPUT_TOKENS,
    MAX_RETRIES,
    MAX_STREAMED_OUTPUT_TOKENS,
    MODELS,
    ModelSpec,
)
from mama_analysis.schemas import Usage

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class Prompt:
    """A versioned system prompt.

    Attributes:
        version: Prompt file stem, e.g. ``"summary_v1"``.
        text: Prompt text.
        sha256: Hash of the text, stored with every cached label to detect staleness.
    """

    version: str
    text: str
    sha256: str


def load_prompt(version: str) -> Prompt:
    """Load a prompt from ``src/mama_analysis/prompts/<version>.md``.

    Args:
        version: Prompt file stem.

    Returns:
        The prompt with its hash.
    """
    text = (files("mama_analysis") / "prompts" / f"{version}.md").read_text(encoding="utf-8")
    return Prompt(version, text, hashlib.sha256(text.encode("utf-8")).hexdigest())


class Labeller(Protocol):
    """An LLM that returns a validated pydantic object for a system and user message."""

    version: str
    spec: ModelSpec

    async def complete(self, system: str, user: str, schema: type[T]) -> tuple[T, Usage]:
        """Run one structured-output call."""
        ...

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        ...


class AnthropicLabeller:
    """Claude via the Messages API, with the system prompt marked for prompt caching."""

    def __init__(self, version: str, spec: ModelSpec, client: Any = None) -> None:
        """Create the adapter.

        Args:
            version: Key into ``config.MODELS``.
            spec: Model spec for this version.
            client: An ``anthropic.AsyncAnthropic`` client; created from the environment if omitted.
        """
        if client is None:
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(max_retries=MAX_RETRIES)
        self.version = version
        self.spec = spec
        self.client = client

    async def complete(self, system: str, user: str, schema: type[T]) -> tuple[T, Usage]:
        """Run one structured-output call with the model's default thinking and effort.

        Streamed so the large token cap cannot hit an HTTP timeout. No fallback model is
        configured: a refusal fails the call rather than mixing in another model's labels.

        Args:
            system: System prompt; cached across calls.
            user: User message.
            schema: Pydantic model the output must satisfy.

        Returns:
            The parsed output and token usage.

        Raises:
            ValueError: If the response has no parsed output (e.g. refusal or truncation).
        """
        async with self.client.messages.stream(
            model=self.spec.model_id,
            max_tokens=MAX_STREAMED_OUTPUT_TOKENS,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_format=schema,
        ) as stream:
            msg = await stream.get_final_message()
        if msg.stop_reason != "end_turn" or msg.parsed_output is None:
            raise ValueError(f"no parsed output (stop_reason={msg.stop_reason})")
        u = msg.usage
        return msg.parsed_output, Usage(
            input_tokens=u.input_tokens,
            output_tokens=u.output_tokens,
            cache_read_tokens=u.cache_read_input_tokens or 0,
            cache_write_tokens=u.cache_creation_input_tokens or 0,
        )

    async def aclose(self) -> None:
        """Close the underlying HTTP client inside the running event loop."""
        await self.client.close()


class OpenAILabeller:
    """An OpenAI model via the Responses API; prompt caching is automatic on shared prefixes."""

    def __init__(self, version: str, spec: ModelSpec, client: Any = None) -> None:
        """Create the adapter.

        Args:
            version: Key into ``config.MODELS``.
            spec: Model spec for this version.
            client: An ``openai.AsyncOpenAI`` client; created from the environment if omitted.
        """
        if client is None:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(max_retries=MAX_RETRIES)
        self.version = version
        self.spec = spec
        self.client = client

    async def complete(self, system: str, user: str, schema: type[T]) -> tuple[T, Usage]:
        """Run one structured-output call.

        Args:
            system: System prompt (instructions); the shared, cacheable prefix.
            user: User message.
            schema: Pydantic model the output must satisfy.

        Returns:
            The parsed output and token usage.

        Raises:
            ValueError: If the response has no parsed output.
        """
        resp = await self.client.responses.parse(
            model=self.spec.model_id,
            instructions=system,
            input=user,
            text_format=schema,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            # Routes calls sharing this prompt to the same cache.
            prompt_cache_key=hashlib.sha256(system.encode("utf-8")).hexdigest()[:32],
        )
        parsed = resp.output_parsed
        if parsed is None:
            raise ValueError(f"no parsed output (status={resp.status})")
        u = resp.usage
        return parsed, Usage(
            input_tokens=u.input_tokens,
            output_tokens=u.output_tokens,
            cache_read_tokens=u.input_tokens_details.cached_tokens or 0,
        )

    async def aclose(self) -> None:
        """Close the underlying HTTP client inside the running event loop."""
        await self.client.close()


def make_labeller(version: str) -> Labeller:
    """Build the labeller for a configured version.

    Args:
        version: Key into ``config.MODELS``.

    Returns:
        A labeller for that model, using API keys from the environment.
    """
    spec = MODELS[version]
    cls = AnthropicLabeller if spec.provider == "anthropic" else OpenAILabeller
    return cls(version, spec)
