"""Pipeline entry point: `uv run mama-pipeline`."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import ValidationError

from mama_analysis import eda
from mama_analysis.cache import read_entries, stale_keys
from mama_analysis.config import DEFAULT_LABELS_DIR, MODELS
from mama_analysis.consolidate import (
    CONSOLIDATE_PROMPT,
    FIELDS,
    consolidate_all,
    mapping_dir,
    raw_labels,
)
from mama_analysis.data import DEFAULT_DATA_PATH, load_sessions, sessions_frame, turns_frame
from mama_analysis.explorer import (
    cooccurrence_table,
    explorer_payload,
    label_counts,
    label_graph,
    label_rows,
    render_explorer,
    summaries_table,
)
from mama_analysis.labellers import Labeller, load_prompt, make_labeller
from mama_analysis.schemas import CacheEntry, SummaryLLM
from mama_analysis.summarise import (
    SUMMARY_PROMPT,
    merge_deterministic,
    summarise_all,
    summary_dir,
)

META_COLUMNS = ["gender", "age_group", "country", "disease", "session_ended_by"]


def run_eda(data_path: Path, out_dir: Path) -> dict[str, Path]:
    """Compute EDA tables and write them as CSVs.

    Args:
        data_path: Path to the conversations JSON file.
        out_dir: Output root; tables are written to ``out_dir / "eda"``.

    Returns:
        Mapping from table name to the CSV path written.
    """
    records = load_sessions(data_path)
    sessions = sessions_frame(records)
    turns = turns_frame(records)
    turns = turns.assign(
        words=turns["text"].map(eda.word_count),
        non_ascii_share=turns["text"].map(eda.non_ascii_share),
    )

    features = eda.session_features(sessions, turns)
    volume_cols = ["n_turns", "user_words", "assistant_words", "assistant_to_user_words"]

    target = out_dir / "eda"
    target.mkdir(parents=True, exist_ok=True)
    tables = {
        "session_features": features,
        "timing_summary": eda.timing_summary(features),
        "volume_summary": eda.numeric_summary(features, volume_cols),
        "ending_crosstab": eda.cross_counts(features, "last_role", "session_ended_by"),
        "country_by_end_state": eda.cross_counts(features, "country", "session_ended_by"),
        "medians_by_end_state": eda.medians_by(features, "session_ended_by", volume_cols),
        "non_ascii_turns": eda.non_ascii_turns(turns),
        "metadata_counts": eda.categorical_counts(sessions, META_COLUMNS),
        "integrity_issues": eda.integrity_issues(sessions, turns),
        "assistant_repeats": eda.cross_session_repeats(turns, "assistant"),
        "user_repeats": eda.cross_session_repeats(turns, "user"),
        "assistant_openings": eda.opening_phrases(turns, "assistant"),
        "turns": turns,
    }
    written = {}
    for name, df in tables.items():
        path = target / f"{name}.csv"
        df.to_csv(path, index=False)
        written[name] = path
    return written


def load_version(
    records: list[dict[str, Any]], labels_dir: Path, version: str
) -> tuple[list[dict[str, Any]] | None, str]:
    """Build labelled rows for one model version from the cache.

    Args:
        records: Raw session records.
        labels_dir: Root of the label cache.
        version: Key into ``config.MODELS``.

    Returns:
        The rows from ``explorer.label_rows`` (``None`` unless every session and every
        field mapping is cached) and the model ID(s) recorded in the cache.

    Raises:
        ValueError: If cached summaries don't fit the current schema, or a cached mapping
            doesn't cover their raw labels (e.g. after a relabel that failed mid-way).
    """
    spec = MODELS[version]
    summaries = read_entries(summary_dir(labels_dir, version))
    mappings = read_entries(mapping_dir(labels_dir, version))
    model_ids = ", ".join(sorted({e.model_id for e in summaries.values()})) or spec.model_id
    ids = {r["session_id"] for r in records}
    if not ids <= summaries.keys() or not set(FIELDS) <= mappings.keys():
        return None, model_ids
    stale = stale_keys(summaries, spec, load_prompt(SUMMARY_PROMPT))
    stale += stale_keys(mappings, spec, load_prompt(CONSOLIDATE_PROMPT))
    if stale:
        print(f"warning: {version}: {len(stale)} cached labels predate the current model/prompt")
    try:
        merged = [
            merge_deterministic(r, SummaryLLM.model_validate(summaries[r["session_id"]].output))
            for r in records
        ]
    except ValidationError as err:
        raise ValueError(
            f"{version}: cached summaries don't match the current schema; "
            f"run: uv run mama-pipeline --relabel {version}"
        ) from err
    field_maps = {f: mappings[f].output["mapping"] for f in FIELDS}
    for field, mapping in field_maps.items():
        unmapped = set(raw_labels(merged, field)) - mapping.keys()
        if unmapped:
            raise ValueError(
                f"{version}: {len(unmapped)} {field} labels have no cached mapping; "
                f"run: uv run mama-pipeline --remap {version}"
            )
    return label_rows(merged, field_maps), model_ids


def run_summaries(data_path: Path, labels_dir: Path, out_dir: Path) -> dict[str, Path]:
    """Write summary tables and the explorer page from cached labels; makes no API calls.

    Args:
        data_path: Path to the conversations JSON file.
        labels_dir: Root of the label cache.
        out_dir: Output root.

    Returns:
        Mapping from output name to the path written.
    """
    records = load_sessions(data_path)
    versions = {}
    written = {}
    for version, spec in MODELS.items():
        rows, model_ids = load_version(records, labels_dir, version)
        versions[version] = {"label": spec.label, "model_id": model_ids, "rows": rows}
        if rows is None:
            print(f"note: no complete cached labels for {version}; skipping its tables")
            continue
        target = out_dir / "summaries" / version
        target.mkdir(parents=True, exist_ok=True)
        for name, df in (
            ("summaries", summaries_table(rows)),
            ("label_counts", label_counts(rows)),
            ("label_cooccurrence", cooccurrence_table(label_graph(rows))),
        ):
            path = target / f"{name}.csv"
            df.to_csv(path, index=False)
            written[f"{version}/{name}"] = path
    path = out_dir / "explorer.html"
    path.write_text(render_explorer(explorer_payload(records, versions)), encoding="utf-8")
    written["explorer"] = path
    return written


def _print_usage(label: str, entries: dict[str, CacheEntry]) -> None:
    for key, e in entries.items():
        u = e.usage
        print(
            f"  {label} {key}: in={u.input_tokens} out={u.output_tokens} "
            f"cache_read={u.cache_read_tokens} cache_write={u.cache_write_tokens}"
        )


async def _consolidate(
    labeller: Labeller, summaries: dict[str, CacheEntry], labels_dir: Path
) -> None:
    mappings = await consolidate_all(
        [SummaryLLM.model_validate(e.output) for e in summaries.values()],
        labeller,
        load_prompt(CONSOLIDATE_PROMPT),
        mapping_dir(labels_dir, labeller.version),
    )
    _print_usage("mapping", mappings)


async def _relabel(version: str, records: list[dict[str, Any]], labels_dir: Path) -> None:
    labeller = make_labeller(version)
    print(f"relabelling {version} with {labeller.spec.model_id}")
    try:
        summaries = await summarise_all(
            records, labeller, load_prompt(SUMMARY_PROMPT), summary_dir(labels_dir, version)
        )
        _print_usage("summary", summaries)
        await _consolidate(labeller, summaries, labels_dir)
    finally:
        await labeller.aclose()


async def _remap(version: str, labels_dir: Path) -> None:
    summaries = read_entries(summary_dir(labels_dir, version))
    if not summaries:
        raise SystemExit(f"no cached summaries for {version}; run --relabel {version} first")
    labeller = make_labeller(version)
    print(f"re-consolidating {version} labels with {labeller.spec.model_id}")
    try:
        await _consolidate(labeller, summaries, labels_dir)
    finally:
        await labeller.aclose()


def relabel(version: str, data_path: Path, labels_dir: Path) -> None:
    """Regenerate one version's summaries and label mappings via the API.

    Reads API keys from ``.env``. Overwrites that version's cache in ``labels_dir``.

    Args:
        version: Key into ``config.MODELS``.
        data_path: Path to the conversations JSON file.
        labels_dir: Root of the label cache.
    """
    load_dotenv()
    asyncio.run(_relabel(version, load_sessions(data_path), labels_dir))


def remap(version: str, labels_dir: Path) -> None:
    """Regenerate one version's label mappings from its cached summaries via the API.

    Reads API keys from ``.env``. Overwrites that version's mapping cache.

    Args:
        version: Key into ``config.MODELS``.
        labels_dir: Root of the label cache.
    """
    load_dotenv()
    asyncio.run(_remap(version, labels_dir))


def main(argv: list[str] | None = None) -> None:
    """Run the pipeline from the command line.

    Args:
        argv: Command-line arguments; defaults to ``sys.argv[1:]``.
    """
    parser = argparse.ArgumentParser(description="mama health conversation analysis pipeline")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--out", type=Path, default=Path("outputs"))
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS_DIR)
    parser.add_argument(
        "--relabel",
        choices=[*MODELS, "all"],
        help="regenerate cached LLM labels for a model version via the API (needs .env keys)",
    )
    parser.add_argument(
        "--remap",
        choices=[*MODELS, "all"],
        help="regenerate only the label mappings, from cached summaries (needs .env keys)",
    )
    args = parser.parse_args(argv)

    if args.relabel:
        for version in MODELS if args.relabel == "all" else [args.relabel]:
            relabel(version, args.data, args.labels)
    if args.remap:
        for version in MODELS if args.remap == "all" else [args.remap]:
            remap(version, args.labels)

    written = run_eda(args.data, args.out)
    written |= run_summaries(args.data, args.labels, args.out)
    for name, path in written.items():
        print(f"wrote {name}: {path}")


if __name__ == "__main__":
    main()
