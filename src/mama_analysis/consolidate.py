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

# Fields whose free-text labels the LLM consolidates. ``reason_for_conversation`` and
# ``end_reason`` are fixed vocabularies (see ``schemas.SummaryLLM``), so their labels are
# already canonical.
CONSOLIDATED_FIELDS = ("main_topics", "conversation_pain_points")

# Display names for fixed-vocabulary values. The model returns the short value; outputs and
# the explorer show the name, keeping the short value as the raw label.
DISPLAY_NAMES = {
    "reason_for_conversation": {
        "informational": "understand my condition",
        "decisional": "decide on treatment",
        "emotional": "emotional support",
        "access": "get access to care",
    },
}

# Human merges applied on top of the model's mapping (D-039): any canonical label starting
# with a prefix becomes that prefix's target. The model keeps splitting one failure mode by
# subject or by whether pushback is mentioned, despite the prompt.
CANONICAL_MERGES = {
    "conversation_pain_points": {"bot repeated ": "bot repeated advice"},
}

# Human grouping of canonical topics into ten broad topic groups (D-042), applied on top of the
# model's mapping. Keyed by the canonical labels of the committed mapping, so a remap or relabel
# that renames topics leaves them "(ungrouped)" until this table is updated.
TOPIC_GROUPS = {
    "Physical symptoms": (
        "symptom management",
        "gastrointestinal symptoms",
        "pain management",
        "skin conditions",
        "hair and scalp health",
        "hormonal health",
    ),
    "Treatment choice": (
        "treatment decisions",
        "medication options",
        "surgery decisions",
        "treatment response",
        "supplements and alternative therapies",
        "endometriosis care",
    ),
    "Understanding the condition & outlook": (
        "disease education",
        "disease prognosis",
        "cancer risk",
        "diabetes risk",
    ),
    "Fatigue, sleep, diet & activity": (
        "fatigue and cognition",
        "sleep problems",
        "exercise and pacing",
        "diet and food triggers",
    ),
    "Tests & monitoring": (
        "disease monitoring",
        "diagnostic testing",
        "lab results interpretation",
        "blood glucose management",
    ),
    "Access to care": (
        "specialist access",
        "care access barriers",
        "medication access",
        "travel and care logistics",
    ),
    "Taking medication safely": (
        "medication dosing",
        "medication use",
        "medication safety",
        "medication side effects",
    ),
    "Work & life plans": ("work impact", "fertility and pregnancy"),
    "Emotional wellbeing": ("emotional distress", "suicidal thoughts", "relationship strain"),
    "Working with clinicians": (
        "medical communication",
        "appointment preparation",
        "health information management",
    ),
}
UNGROUPED = "(ungrouped)"
_GROUP_OF = {topic: group for group, topics in TOPIC_GROUPS.items() for topic in topics}

# Every topic is consolidated, but only topics at this relevance become chips, counts and
# graph nodes.
KEPT_RELEVANCE = "strong"

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


def field_labels(summary: SummaryLLM, field: str) -> list[str]:
    """All raw labels of one field; these are what consolidation must map.

    Args:
        summary: A model summary.
        field: One of ``FIELDS``.

    Returns:
        The field's labels; for ``main_topics``, every scored topic, whatever its relevance.
    """
    value = getattr(summary, field)
    if field == "main_topics":
        return [t.topic for t in value]
    return as_list(value)


def shown_labels(summary: SummaryLLM, field: str) -> list[str]:
    """The raw labels of one field that become chips, counts and graph nodes.

    Args:
        summary: A model summary.
        field: One of ``FIELDS``.

    Returns:
        As ``field_labels``, but for ``main_topics`` only topics scored ``KEPT_RELEVANCE``.
    """
    if field == "main_topics":
        return [t.topic for t in summary.main_topics if t.relevance == KEPT_RELEVANCE]
    return field_labels(summary, field)


def raw_labels(summaries: Iterable[SummaryLLM], field: str) -> list[str]:
    """Collect the unique raw labels for a field across summaries.

    Args:
        summaries: Model summaries.
        field: One of ``FIELDS``.

    Returns:
        Sorted unique labels, verbatim (see ``field_labels``).
    """
    return sorted({label for s in summaries for label in field_labels(s, field)})


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


def topic_groups(topics: list[str]) -> list[str]:
    """Map canonical topics to their ``TOPIC_GROUPS`` group.

    Args:
        topics: Canonical topic labels.

    Returns:
        The groups, in first-seen order without duplicates; a topic in no group gives
        ``UNGROUPED``.
    """
    return list(dict.fromkeys(_GROUP_OF.get(t, UNGROUPED) for t in topics))


def merge_canonicals(field: str, mapping: dict[str, str]) -> dict[str, str]:
    """Apply the human merges in ``CANONICAL_MERGES`` to one field's mapping.

    Args:
        field: Field the mapping belongs to.
        mapping: Raw-to-canonical dict from the model.

    Returns:
        The mapping with every canonical label that starts with a merge prefix replaced by
        that prefix's target.
    """
    merges = CANONICAL_MERGES.get(field, {})
    return {
        raw: next((t for p, t in merges.items() if canon.startswith(p)), canon)
        for raw, canon in mapping.items()
    }


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
    """Ask the model for a raw-to-canonical mapping for each consolidated field and cache it.

    Args:
        summaries: Model summaries whose labels to consolidate.
        labeller: Model to call; the same model that wrote the summaries.
        prompt: Consolidation system prompt.
        out_dir: Directory for ``<field>.json`` cache files.
        concurrency: Maximum calls in flight after the warm-up.

    Returns:
        Cache entries keyed by field in ``CONSOLIDATED_FIELDS``; each ``output`` is
        ``{"mapping": {raw: canonical}}``.

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

    return dict(await warm_then_parallel(list(CONSOLIDATED_FIELDS), one, concurrency))
