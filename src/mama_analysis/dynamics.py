"""Conversation dynamics: pushback, whether the bot adapted, and the user's final stance."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from mama_analysis.config import CONCURRENCY
from mama_analysis.labellers import Labeller, Prompt
from mama_analysis.schemas import CacheEntry, DynamicsLLM
from mama_analysis.summarise import label_sessions

DYNAMICS_PROMPT = "dynamics_v1"


def dynamics_dir(labels_dir: Path, version: str) -> Path:
    """Directory holding one cached dynamics label per session for a model version.

    Args:
        labels_dir: Root of the label cache.
        version: Model version key.

    Returns:
        ``labels_dir / "dynamics" / version``.
    """
    return labels_dir / "dynamics" / version


def _normalise(text: str) -> str:
    """Lower-case, unify quotes and ellipses, and collapse whitespace for quote matching."""
    text = text.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("…", "...").strip().strip("\"'").strip(".").strip()
    return re.sub(r"\s+", " ", text)


def quote_in(quote: str, text: str) -> bool:
    """Whether a model quote appears in a turn, ignoring case, quote style and spacing.

    Args:
        quote: Words the model says it copied.
        text: The turn's text.

    Returns:
        True if the normalised quote is a substring of the normalised text.
    """
    q = _normalise(quote)
    return bool(q) and q in _normalise(text)


def check_dynamics(record: dict[str, Any], dyn: DynamicsLLM) -> dict[str, Any]:
    """Check a dynamics label against its transcript.

    Args:
        record: Raw session record.
        dyn: The model's dynamics label for it.

    Returns:
        ``final_quote_found`` (the final-sentiment quote is in some user turn) and
        ``pushback_ok``, one bool per pushback: its turn is a user turn containing its quote.
    """
    user_turns = {t["turn"]: t["text"] for t in record["conversation"] if t["role"] == "user"}
    return {
        "final_quote_found": any(
            quote_in(dyn.final_sentiment_quote, t) for t in user_turns.values()
        ),
        "pushback_ok": [
            p.turn in user_turns and quote_in(p.quote, user_turns[p.turn]) for p in dyn.pushbacks
        ],
    }


async def dynamics_all(
    records: list[dict[str, Any]],
    labeller: Labeller,
    prompt: Prompt,
    out_dir: Path,
    concurrency: int = CONCURRENCY,
) -> dict[str, CacheEntry]:
    """Label every session's dynamics and cache each result.

    Args:
        records: Raw session records.
        labeller: Model to call.
        prompt: Dynamics system prompt.
        out_dir: Directory for ``<session_id>.json`` cache files.
        concurrency: Maximum calls in flight after the warm-up.

    Returns:
        Cache entries keyed by session ID.
    """
    return await label_sessions(records, labeller, prompt, DynamicsLLM, out_dir, concurrency)
