"""Pipeline entry point: `uv run mama-pipeline`."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import ValidationError

from mama_analysis import analysis, eda
from mama_analysis.cache import read_entries, stale_keys
from mama_analysis.config import DEFAULT_LABELS_DIR, MODELS
from mama_analysis.consolidate import (
    CONSOLIDATE_PROMPT,
    CONSOLIDATED_FIELDS,
    DISPLAY_NAMES,
    FIELDS,
    UNGROUPED,
    consolidate_all,
    mapping_dir,
    merge_canonicals,
    raw_labels,
    topic_groups,
)
from mama_analysis.data import DEFAULT_DATA_PATH, load_sessions, sessions_frame, turns_frame
from mama_analysis.dynamics import DYNAMICS_PROMPT, check_dynamics, dynamics_all, dynamics_dir
from mama_analysis.explorer import (
    attach_dynamics,
    cooccurrence_table,
    explorer_payload,
    label_counts,
    label_graph,
    label_rows,
    render_explorer,
    summaries_table,
)
from mama_analysis.labellers import Labeller, load_prompt, make_labeller
from mama_analysis.memo import (
    DEFAULT_MEMO_PATH,
    memo_breakdown,
    outcome_table_html,
    pain_points_html,
    render_memo,
)
from mama_analysis.schemas import CacheEntry, DynamicsLLM, SummaryLLM
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
    if not ids <= summaries.keys() or not set(CONSOLIDATED_FIELDS) <= mappings.keys():
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
    field_maps = {
        f: merge_canonicals(f, mappings[f].output["mapping"]) for f in CONSOLIDATED_FIELDS
    }
    # Fixed-vocabulary fields map to their display name, or to themselves.
    field_maps |= {
        f: {x: DISPLAY_NAMES.get(f, {}).get(x, x) for x in raw_labels(merged, f)}
        for f in FIELDS
        if f not in CONSOLIDATED_FIELDS
    }
    for field, mapping in field_maps.items():
        unmapped = set(raw_labels(merged, field)) - mapping.keys()
        if unmapped:
            raise ValueError(
                f"{version}: {len(unmapped)} {field} labels have no cached mapping; "
                f"run: uv run mama-pipeline --remap {version}"
            )
    return label_rows(merged, field_maps), model_ids


def load_dynamics(
    records: list[dict[str, Any]], labels_dir: Path, version: str
) -> dict[str, DynamicsLLM] | None:
    """Load one version's cached dynamics labels.

    Args:
        records: Raw session records.
        labels_dir: Root of the label cache.
        version: Key into ``config.MODELS``.

    Returns:
        Dynamics labels keyed by session ID, or ``None`` unless every session is cached.

    Raises:
        ValueError: If cached dynamics labels don't fit the current schema.
    """
    entries = read_entries(dynamics_dir(labels_dir, version))
    if not {r["session_id"] for r in records} <= entries.keys():
        return None
    stale = stale_keys(entries, MODELS[version], load_prompt(DYNAMICS_PROMPT))
    if stale:
        print(f"warning: {version}: {len(stale)} cached dynamics labels predate the current prompt")
    try:
        dyn = {
            r["session_id"]: DynamicsLLM.model_validate(entries[r["session_id"]].output)
            for r in records
        }
    except ValidationError as err:
        raise ValueError(
            f"{version}: cached dynamics don't match the current schema; "
            f"run: uv run mama-pipeline --dynamics {version}"
        ) from err
    bad = 0
    for r in records:
        check = check_dynamics(r, dyn[r["session_id"]])
        bad += (not check["final_quote_found"]) + check["pushback_ok"].count(False)
    if bad:
        print(f"warning: {version}: {bad} dynamics quotes not found in their transcript turn")
    return dyn


def analysis_tables(
    records: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    dyn: dict[str, DynamicsLLM] | None,
) -> dict[str, Any]:
    """Build the analysis tables for one version.

    Args:
        records: Raw session records.
        rows: Output of ``explorer.label_rows``.
        dyn: Dynamics labels keyed by session ID, or ``None`` if not cached.

    Returns:
        DataFrames keyed by table name; the dynamics tables only when ``dyn`` is given.
    """
    tables = {
        "ending_vs_outcome": analysis.ending_vs_outcome(rows),
        "ending_mismatches": analysis.ending_mismatches(rows),
        "outcome_by_reason": analysis.outcome_by(rows, "reason_for_conversation"),
        "outcome_by_disease": analysis.outcome_by(rows, "disease"),
        "topic_groups": analysis.topic_group_counts(rows),
        "pain_points": analysis.pain_point_list(rows),
    }
    if dyn is not None:
        by_id = {r["session_id"]: r for r in records}
        tables |= {
            "sentiment_vs_outcome": analysis.sentiment_vs_outcome(rows, dyn),
            "silent_failures": analysis.silent_failures(rows, dyn, by_id),
            "pushbacks": analysis.pushbacks_table(rows, dyn, by_id),
            "recovery_by_outcome": analysis.recovery_by_outcome(rows, dyn),
            "friction": analysis.friction(rows, dyn, by_id),
        }
    return tables


def run_summaries(
    data_path: Path, labels_dir: Path, out_dir: Path, memo_path: Path | None = None
) -> dict[str, Path]:
    """Write summary and analysis tables, the explorer page and the memo page from cached labels.

    Makes no API calls.

    Args:
        data_path: Path to the conversations JSON file.
        labels_dir: Root of the label cache.
        out_dir: Output root.
        memo_path: Memo draft in Markdown; ``memo.html`` is written only if it is given,
            exists, and some version has complete labels (the first such version is used).

    Returns:
        Mapping from output name to the path written.

    Raises:
        ValueError: If cached labels don't fit the current schema or mapping (see
            ``load_version``), or the memo draft uses an unknown marker.
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
        missing = analysis.missing_safety_labels(rows)
        if missing:
            print(
                f"note: {version}: no session has safety pain point(s) {missing}; check the mapping"
            )
        topics = sorted({c["label"] for r in rows for c in r["main_topics"]})
        ungrouped = [t for t in topics if topic_groups([t]) == [UNGROUPED]]
        if ungrouped:
            print(f"note: {version}: topics in no TOPIC_GROUPS group: {ungrouped}")
        dyn = load_dynamics(records, labels_dir, version)
        if dyn is None:
            print(f"note: no complete cached dynamics for {version}; skipping those tables")
        target = out_dir / "analysis" / version
        target.mkdir(parents=True, exist_ok=True)
        for name, df in analysis_tables(records, rows, dyn).items():
            path = target / f"{name}.csv"
            df.to_csv(path, index=False)
            written[f"analysis/{version}/{name}"] = path
        by_id = {r["session_id"]: r for r in records}
        versions[version]["rows"] = attach_dynamics(rows, dyn, by_id)
    path = out_dir / "explorer.html"
    path.write_text(render_explorer(explorer_payload(records, versions)), encoding="utf-8")
    written["explorer"] = path
    memo_version = next((k for k, v in versions.items() if v["rows"] is not None), None)
    if memo_path and memo_path.exists() and memo_version:
        rows = versions[memo_version]["rows"]
        blocks = {
            name: outcome_table_html(
                analysis.outcome_by(rows, field),
                field,
                f"outputs/analysis/{memo_version}/{name}.csv",
            )
            for name, field in (
                ("outcome_by_reason", "reason_for_conversation"),
                ("outcome_by_disease", "disease"),
            )
        }
        blocks["pain_points"] = pain_points_html(
            analysis.pain_point_list(rows), f"outputs/analysis/{memo_version}/pain_points.csv"
        )
        path = out_dir / "memo.html"
        text = memo_path.read_text(encoding="utf-8")
        path.write_text(render_memo(text, blocks, memo_breakdown(rows)), encoding="utf-8")
        written["memo"] = path
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


async def _run_dynamics(
    labeller: Labeller, records: list[dict[str, Any]], labels_dir: Path
) -> None:
    entries = await dynamics_all(
        records, labeller, load_prompt(DYNAMICS_PROMPT), dynamics_dir(labels_dir, labeller.version)
    )
    _print_usage("dynamics", entries)


async def _relabel(version: str, records: list[dict[str, Any]], labels_dir: Path) -> None:
    labeller = make_labeller(version)
    print(f"relabelling {version} with {labeller.spec.model_id}")
    try:
        summaries = await summarise_all(
            records, labeller, load_prompt(SUMMARY_PROMPT), summary_dir(labels_dir, version)
        )
        _print_usage("summary", summaries)
        await _consolidate(labeller, summaries, labels_dir)
        await _run_dynamics(labeller, records, labels_dir)
    finally:
        await labeller.aclose()


async def _dynamics(version: str, records: list[dict[str, Any]], labels_dir: Path) -> None:
    labeller = make_labeller(version)
    print(f"labelling {version} conversation dynamics with {labeller.spec.model_id}")
    try:
        await _run_dynamics(labeller, records, labels_dir)
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
    """Regenerate one version's summaries, label mappings and dynamics via the API.

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


def dynamics(version: str, data_path: Path, labels_dir: Path) -> None:
    """Regenerate only one version's conversation-dynamics labels via the API.

    Reads API keys from ``.env``. Overwrites that version's dynamics cache.

    Args:
        version: Key into ``config.MODELS``.
        data_path: Path to the conversations JSON file.
        labels_dir: Root of the label cache.
    """
    load_dotenv()
    asyncio.run(_dynamics(version, load_sessions(data_path), labels_dir))


def main(argv: list[str] | None = None) -> None:
    """Run the pipeline from the command line.

    Args:
        argv: Command-line arguments; defaults to ``sys.argv[1:]``.
    """
    parser = argparse.ArgumentParser(description="mama health conversation analysis pipeline")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--out", type=Path, default=Path("outputs"))
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS_DIR)
    parser.add_argument("--memo", type=Path, default=DEFAULT_MEMO_PATH)
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
    parser.add_argument(
        "--dynamics",
        choices=[*MODELS, "all"],
        help="regenerate only the conversation-dynamics labels (needs .env keys)",
    )
    args = parser.parse_args(argv)

    if args.relabel:
        for version in MODELS if args.relabel == "all" else [args.relabel]:
            relabel(version, args.data, args.labels)
    if args.remap:
        for version in MODELS if args.remap == "all" else [args.remap]:
            remap(version, args.labels)
    if args.dynamics:
        for version in MODELS if args.dynamics == "all" else [args.dynamics]:
            dynamics(version, args.data, args.labels)

    written = run_eda(args.data, args.out)
    written |= run_summaries(args.data, args.labels, args.out, args.memo)
    for name, path in written.items():
        print(f"wrote {name}: {path}")


if __name__ == "__main__":
    main()
