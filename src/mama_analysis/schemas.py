"""Pydantic models for LLM structured outputs and the label cache."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ScoredTopic(BaseModel):
    """One topic the user raised, scored for how central it is to the conversation.

    ``reason`` comes before ``relevance`` so the model justifies the score before giving it.
    """

    topic: str = Field(description="Something the user talks about; a short generic label.")
    reason: str = Field(
        description="One short sentence, grounded in the transcript, for the score."
    )
    relevance: Literal["strong", "medium", "low"] = Field(
        description="How central the topic is to this conversation."
    )


class SummaryLLM(BaseModel):
    """Fields the model extracts from one conversation (structured output)."""

    main_topics: list[ScoredTopic] = Field(
        description="Every topic the user talks about, incl. their health issues, each scored."
    )
    summary: str = Field(description="Two or three short sentences summarising the conversation.")
    reason_for_conversation: str = Field(
        description="Why the user started the conversation; a short generic label."
    )
    conversation_pain_points: list[str] = Field(
        description="Problems the user had with this conversation itself; short labels."
    )
    issue_resolved: bool = Field(description="Whether the user's issue was resolved.")
    end_reason: Literal["need met", "partial resolution", "unresolved need"] = Field(
        description="How the user's need stood when the conversation ended."
    )


class Pushback(BaseModel):
    """One user turn that resists the bot's previous reply, and whether the bot adapted."""

    turn: int = Field(description="The user turn number [t<n>] where the pushback happens.")
    kind: Literal["correction", "objection", "repeated question", "frustration"] = Field(
        description="The dominant kind of pushback in that turn."
    )
    quote: str = Field(description="Words copied verbatim from that user turn.")
    reason: str = Field(description="One sentence: why the bot's next reply did or did not adapt.")
    bot_adapted: bool = Field(description="Whether the bot's next reply changed approach.")


class DynamicsLLM(BaseModel):
    """How a conversation moved: pushback and the user's final stance (structured output).

    Evidence fields come before the judgements they support.
    """

    final_sentiment_quote: str = Field(
        description="The user's last substantive words, copied verbatim."
    )
    final_sentiment: Literal["satisfied", "neutral", "dissatisfied"] = Field(
        description="How the user sounded at the end; not whether their need was met."
    )
    pushbacks: list[Pushback] = Field(description="Every user turn that pushes back on the bot.")


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
