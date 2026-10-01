"""Per-conversation LLM summaries."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from mama_analysis.cache import make_entry, warm_then_parallel, write_entry
from mama_analysis.config import CONCURRENCY
from mama_analysis.labellers import Labeller, Prompt
from mama_analysis.schemas import CacheEntry, SessionSummary, SummaryLLM

SUMMARY_PROMPT = "summary_v9"


def summary_dir(labels_dir: Path, version: str) -> Path:
    """Directory holding one cached summary per session for a model version.

    Args:
        labels_dir: Root of the label cache.
        version: Model version key.

    Returns:
        ``labels_dir / "summaries" / version``.
    """
    return labels_dir / "summaries" / version


def render_conversation(record: dict[str, Any]) -> str:
    """Render a session transcript as the user message for the model.

    Metadata is deliberately left out: demographics and disease are copied, not inferred.

    Args:
        record: One raw session record.

    Returns:
        A header line with the session ID, then one ``[t<turn>] <role>: <text>`` line per turn.
    """
    lines = [f"session_id: {record['session_id']}"]
    lines += [f"[t{t['turn']}] {t['role']}: {t['text']}" for t in record["conversation"]]
    return "\n".join(lines)


async def label_sessions(
    records: list[dict[str, Any]],
    labeller: Labeller,
    prompt: Prompt,
    schema: type[BaseModel],
    out_dir: Path,
    concurrency: int = CONCURRENCY,
) -> dict[str, CacheEntry]:
    """Run one structured-output call per session, writing each cache entry as it arrives.

    The first call runs alone to warm the prompt cache; the rest run concurrently.

    Args:
        records: Raw session records.
        labeller: Model to call.
        prompt: System prompt.
        schema: Pydantic model each output must satisfy.
        out_dir: Directory for ``<session_id>.json`` cache files.
        concurrency: Maximum calls in flight after the warm-up.

    Returns:
        Cache entries keyed by session ID.
    """

    async def one(record: dict[str, Any]) -> tuple[str, CacheEntry]:
        output, usage = await labeller.complete(prompt.text, render_conversation(record), schema)
        entry = make_entry(labeller, prompt, usage, output)
        write_entry(entry, out_dir / f"{record['session_id']}.json")
        return record["session_id"], entry

    return dict(await warm_then_parallel(records, one, concurrency))


async def summarise_all(
    records: list[dict[str, Any]],
    labeller: Labeller,
    prompt: Prompt,
    out_dir: Path,
    concurrency: int = CONCURRENCY,
) -> dict[str, CacheEntry]:
    """Summarise every session (``label_sessions`` with the ``SummaryLLM`` schema).

    Args:
        records: Raw session records.
        labeller: Model to call.
        prompt: Summary system prompt.
        out_dir: Directory for ``<session_id>.json`` cache files.
        concurrency: Maximum calls in flight after the warm-up.

    Returns:
        Cache entries keyed by session ID.
    """
    return await label_sessions(records, labeller, prompt, SummaryLLM, out_dir, concurrency)


def merge_deterministic(record: dict[str, Any], llm: SummaryLLM) -> SessionSummary:
    """Combine an LLM summary with metadata copied from the session record.

    Args:
        record: Raw session record; the source of truth for demographics and end state.
        llm: The model's summary of the conversation.

    Returns:
        The full session summary.
    """
    return SessionSummary(
        session_id=record["session_id"],
        **{k: record["user_meta"][k] for k in ("disease", "age_group", "gender", "country")},
        session_ended_by=record["session_meta"]["session_ended_by"],
        **llm.model_dump(),
    )
