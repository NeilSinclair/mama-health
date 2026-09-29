"""Reading and writing cached LLM results, and the warm-then-parallel call pattern."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from mama_analysis.config import ModelSpec
from mama_analysis.labellers import Labeller, Prompt
from mama_analysis.schemas import CacheEntry, Usage


def make_entry(labeller: Labeller, prompt: Prompt, usage: Usage, output: BaseModel) -> CacheEntry:
    """Wrap an LLM output with its provenance.

    Args:
        labeller: Labeller that produced the output.
        prompt: Prompt used.
        usage: Token usage of the call.
        output: Parsed output.

    Returns:
        A cache entry timestamped now (UTC).
    """
    return CacheEntry(
        version=labeller.version,
        provider=labeller.spec.provider,
        model_id=labeller.spec.model_id,
        prompt_version=prompt.version,
        prompt_sha256=prompt.sha256,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        usage=usage,
        output=output.model_dump(mode="json"),
    )


def write_entry(entry: CacheEntry, path: Path) -> None:
    """Write a cache entry as stable, sorted JSON.

    Args:
        entry: Entry to write.
        path: Destination file; parent directories are created.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(entry.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")


def read_entries(directory: Path) -> dict[str, CacheEntry]:
    """Read every cache entry in a directory.

    Args:
        directory: Directory of ``<key>.json`` files; may not exist.

    Returns:
        Entries keyed by file stem, sorted by key; empty if the directory is missing.
    """
    if not directory.is_dir():
        return {}
    return {
        p.stem: CacheEntry.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted(directory.glob("*.json"))
    }


def stale_keys(entries: dict[str, CacheEntry], spec: ModelSpec, prompt: Prompt) -> list[str]:
    """Find entries produced by a different model or prompt than the current config.

    Args:
        entries: Cached entries by key.
        spec: Currently configured model.
        prompt: Current prompt.

    Returns:
        Sorted keys whose model ID or prompt hash differs.
    """
    return sorted(
        k
        for k, e in entries.items()
        if e.model_id != spec.model_id or e.prompt_sha256 != prompt.sha256
    )


async def warm_then_parallel[X, Y](
    items: Sequence[X], call: Callable[[X], Awaitable[Y]], concurrency: int
) -> list[Y]:
    """Await the first call alone so it writes the prompt cache, then run the rest concurrently.

    Args:
        items: Inputs, in order.
        call: Async function applied to each input.
        concurrency: Maximum calls in flight after the warm-up.

    Returns:
        Results in input order.
    """
    if not items:
        return []
    first = await call(items[0])
    sem = asyncio.Semaphore(concurrency)

    async def guarded(item: X) -> Y:
        async with sem:
            return await call(item)

    rest = await asyncio.gather(*(guarded(i) for i in items[1:]))
    return [first, *rest]
