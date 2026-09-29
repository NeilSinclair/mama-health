"""Pydantic models for LLM structured outputs and the label cache."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SummaryLLM(BaseModel):
    """Fields the model extracts from one conversation (structured output)."""

    main_topics: list[str] = Field(
        description="What the user talks about, incl. their health issues; short generic labels."
    )
    summary: str = Field(description="Two or three short sentences summarising the conversation.")
    reason_for_conversation: str = Field(
        description="Why the user started the conversation; a short generic label."
    )
    conversation_pain_points: list[str] = Field(
        description="Problems the user had with this conversation itself; short labels."
    )
    issue_resolved: bool = Field(description="Whether the user's issue was resolved.")
    end_reason: str = Field(
        description="Interpretation of why the conversation ended; a short generic label."
    )


class SessionSummary(SummaryLLM):
    """A conversation summary with metadata copied deterministically from the dataset."""

    session_id: str
    disease: str
    age_group: str
    gender: str
    country: str
    session_ended_by: str


class LabelPair(BaseModel):
    """One raw label and the canonical label it maps to."""

    raw: str = Field(description="A raw label, copied verbatim from the input list.")
    canonical: str = Field(description="The consolidated label for it.")


class LabelMapping(BaseModel):
    """Consolidation of raw labels (structured output).

    A list of pairs rather than a dict, because strict structured-output schemas reject
    objects with arbitrary keys.
    """

    mappings: list[LabelPair]


class Usage(BaseModel):
    """Token usage for one API call, normalised across providers."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class CacheEntry(BaseModel):
    """One cached LLM result with the provenance needed to detect stale labels."""

    version: str
    provider: str
    model_id: str
    prompt_version: str
    prompt_sha256: str
    created_at: str
    usage: Usage
    output: dict[str, Any]
