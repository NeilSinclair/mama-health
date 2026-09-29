"""Consolidating free-text labels into a smaller canonical vocabulary."""

from __future__ import annotations

import warnings
from collections.abc import Iterable
from pathlib import Path

from mama_analysis.cache import make_entry, warm_then_parallel, write_entry
from mama_analysis.config import CONCURRENCY
from mama_analysis.labellers import Labeller, Prompt
from mama_analysis.schemas import CacheEntry, LabelMapping, SummaryLLM, Usage

CONSOLIDATE_PROMPT = "consolidate_v3"

FIELDS = ("main_topics", "conversation_pain_points", "reason_for_conversation", "end_reason")

# Attempts per field when the model's mapping fails validation.
MAX_ATTEMPTS = 3


def mapping_dir(labels_dir: Path, version: str) -> Path:
    """Directory holding one cached mapping per field for a model version.

    Args:
        labels_dir: Root of the label cache.
        version: Model version key.

    Returns:
        ``labels_dir / "mappings" / version``.
    """
    return labels_dir / "mappings" / version


def as_list(value: str | list[str]) -> list[str]:
    """Treat a scalar label field and a list label field alike.

    Args:
        value: A label or list of labels.

    Returns:
        The labels as a list.
    """
    return [value] if isinstance(value, str) else list(value)


def raw_labels(summaries: Iterable[SummaryLLM], field: str) -> list[str]:
    """Collect the unique raw labels for a field across summaries.

    Args:
        summaries: Model summaries.
        field: One of ``FIELDS``.

    Returns:
        Sorted unique labels, verbatim.
    """
    return sorted({label for s in summaries for label in as_list(getattr(s, field))})


def render_labels(field: str, labels: list[str]) -> str:
    """Render the user message for one consolidation call.

    Args:
        field: Field the labels come from.
        labels: Unique raw labels.

    Returns:
        A header naming the field, then one label per line.
    """
    return "\n".join([f"field: {field}", "labels:", *labels])


def validate_mapping(raws: list[str], mapping: LabelMapping) -> dict[str, str]:
    """Check that a proposed mapping covers every raw label exactly once.

    Args:
        raws: Raw labels that must be mapped.
        mapping: The model's proposed mapping.

    Returns:
        Raw-to-canonical dict restricted to ``raws``, sorted by raw label.

    Raises:
        ValueError: If a raw label is unmapped, mapped to an empty label, or mapped
            inconsistently.
    """
    wanted = set(raws)
    result: dict[str, str] = {}
    extras = []
    for pair in mapping.mappings:
        if pair.raw not in wanted:
            extras.append(pair.raw)
            continue
        canonical = pair.canonical.strip()
        if not canonical:
            raise ValueError(f"empty canonical label for {pair.raw!r}")
        if result.get(pair.raw, canonical) != canonical:
            raise ValueError(f"conflicting canonical labels for {pair.raw!r}")
        result[pair.raw] = canonical
    missing = sorted(wanted - result.keys())
    if missing:
        raise ValueError(f"{len(missing)} raw labels unmapped, e.g. {missing[:3]}")
    if extras:
        warnings.warn(f"dropped {len(extras)} labels not in the input", stacklevel=2)
    return dict(sorted(result.items()))


def apply_mapping(value: str | list[str], mapping: dict[str, str]) -> str | list[str]:
    """Map a label field to canonical labels.

    Args:
        value: A raw label, or a list of raw labels.
        mapping: Raw-to-canonical dict.

    Returns:
        The canonical label, or canonical labels in first-seen order without duplicates.
    """
    if isinstance(value, str):
        return mapping[value]
    return list(dict.fromkeys(mapping[v] for v in value))


async def consolidate_all(
    summaries: Iterable[SummaryLLM],
    labeller: Labeller,
    prompt: Prompt,
    out_dir: Path,
    concurrency: int = CONCURRENCY,
) -> dict[str, CacheEntry]:
    """Ask the model for a raw-to-canonical mapping for each field and cache it.

    Args:
        summaries: Model summaries whose labels to consolidate.
        labeller: Model to call; the same model that wrote the summaries.
        prompt: Consolidation system prompt.
        out_dir: Directory for ``<field>.json`` cache files.
        concurrency: Maximum calls in flight after the warm-up.

    Returns:
        Cache entries keyed by field; each ``output`` is ``{"mapping": {raw: canonical}}``.

    Raises:
        ValueError: If a field's mapping still fails validation after ``MAX_ATTEMPTS``.
    """
    summaries = list(summaries)

    async def one(field: str) -> tuple[str, CacheEntry]:
        raws = raw_labels(summaries, field)
        total = Usage()
        for attempt in range(1, MAX_ATTEMPTS + 1):
            proposed, usage = await labeller.complete(
                prompt.text, render_labels(field, raws), LabelMapping
            )
            # Record the tokens of failed attempts too, so the cache reflects the real cost.
            total = Usage(**{k: v + getattr(usage, k) for k, v in total.model_dump().items()})
            try:
                mapping = validate_mapping(raws, proposed)
                break
            except ValueError as err:
                if attempt == MAX_ATTEMPTS:
                    raise ValueError(f"{field}: {err}") from err
        entry = make_entry(labeller, prompt, total, proposed)
        entry.output = {"mapping": mapping}
        write_entry(entry, out_dir / f"{field}.json")
        return field, entry

    return dict(await warm_then_parallel(list(FIELDS), one, concurrency))
