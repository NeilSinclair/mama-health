"""Pinned model configuration and paths for LLM labelling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DEFAULT_LABELS_DIR = Path("data/labels")

# Cap on output tokens per call. Generous because reasoning models count reasoning tokens here.
MAX_OUTPUT_TOKENS = 16_000

# Parallel calls after the cache warm-up call.
CONCURRENCY = 8

# SDK-level retries on rate limits and transient errors.
MAX_RETRIES = 5


@dataclass(frozen=True)
class ModelSpec:
    """A labelling model version.

    Attributes:
        provider: API provider that serves the model.
        model_id: Exact, pinned API model ID.
        label: Human-readable name for the explorer UI.
    """

    provider: Literal["openai"]
    model_id: str
    label: str


MODELS: dict[str, ModelSpec] = {
    "gpt_luna": ModelSpec("openai", "gpt-6-luna", "GPT Luna"),
}
