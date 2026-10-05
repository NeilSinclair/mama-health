"""Label-stability experiment: how much do Claude Sonnet 5.5's labels vary between runs?

Exploratory, not part of the pipeline: it writes only under ``data/labels_stability/sonnet/``
and never touches ``data/labels/`` or ``outputs/``. It labels with the pipeline's ``sonnet``
version (D-055).

Unlike ``label_stability.py`` (GPT Luna, frozen at ``summary_v7``), this uses the current
summary and consolidation prompts, so topic groups are compared too.

- ``run``: three fresh summary runs over all 50 sessions, then one consolidation call over
  the raw labels of all three runs, so every run shares one vocabulary. Needs
  ``ANTHROPIC_API_KEY`` in ``.env``. Resumable: finished steps are skipped.
- ``analyse``: offline. Agreement tables, a comparison with GPT Luna and cost, written to
  ``data/labels_stability/sonnet/results/``.

Usage:
    uv run python scripts/sonnet_label_stability.py run
    uv run python scripts/sonnet_label_stability.py analyse
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from label_stability import RELEVANCE_RANK, fleiss_kappa, jaccard, majority

from mama_analysis.cache import make_entry, read_entries, write_entry
from mama_analysis.cli import DEFAULT_GOLD_PATH
from mama_analysis.config import DEFAULT_LABELS_DIR
from mama_analysis.consolidate import (
    CONSOLIDATE_PROMPT,
    CONSOLIDATED_FIELDS,
    DISPLAY_NAMES,
    raw_labels,
    render_labels,
)
from mama_analysis.data import DEFAULT_DATA_PATH, load_sessions
from mama_analysis.labellers import Labeller, Prompt, load_prompt, make_labeller
from mama_analysis.schemas import CacheEntry, LabelMapping, SummaryLLM
from mama_analysis.summarise import SUMMARY_PROMPT, label_sessions, summary_dir

VERSION = "sonnet"
ROOT = Path("data/labels_stability/sonnet")
RESULTS = ROOT / "results"
RUNS = ("run1", "run2", "run3")

# Claude Sonnet 5.5, USD per million tokens (checked 2026-10-05; not in the repo).
PRICE_IN, PRICE_CACHE_READ, PRICE_CACHE_WRITE, PRICE_OUT = 2.00, 0.20, 2.50, 10.00

CATEGORICAL = ("reason_for_conversation", "issue_resolved", "end_reason")
SETS = ("strong_topics", "strong_topic_groups", "conversation_pain_points")


def load_summaries(run: str) -> dict[str, CacheEntry]:
    """Cached summary entries of one run, keyed by session ID."""
    return read_entries(ROOT / "runs" / run)


async def _consolidate(
    summaries: list[SummaryLLM], labeller: Labeller, prompt: Prompt, out_dir: Path
) -> None:
    """One mapping call per consolidated field; raw labels the model skips map to themselves.

    ``consolidate.consolidate_all`` rejects a mapping with any raw label missing. Over three
    runs Sonnet names ~750 distinct topics and drops a couple from each answer, so here the
    gaps are kept as their own labels and counted in the cache entry instead.
    """
    for field in CONSOLIDATED_FIELDS:
        raws = raw_labels(summaries, field)
        proposed, usage = await labeller.complete(
            prompt.text, render_labels(field, raws), LabelMapping
        )
        mapping = {p.raw: p.canonical.strip() for p in proposed.mappings if p.raw in set(raws)}
        missing = sorted(set(raws) - mapping.keys())
        print(f"{field}: {len(raws)} raw labels, {len(missing)} left unmapped by the model")
        entry = make_entry(labeller, prompt, usage, proposed)
        entry.output = {
            "mapping": dict(sorted((mapping | {m: m for m in missing}).items())),
            "unmapped": missing,
        }
        write_entry(entry, out_dir / f"{field}.json")


async def _run(records: list[dict[str, Any]]) -> None:
    labeller = make_labeller(VERSION)
    try:
        for run in RUNS:
            if len(load_summaries(run)) == len(records):
                print(f"{run}: cached, skipping")
                continue
            print(f"{run}: summarising {len(records)} sessions")
            await label_sessions(
                records, labeller, load_prompt(SUMMARY_PROMPT), SummaryLLM, ROOT / "runs" / run
            )

        joint = ROOT / "joint_mappings"
        if not all((joint / f"{f}.json").exists() for f in CONSOLIDATED_FIELDS):
            print("joint mapping over 3 runs")
            summaries = [
                SummaryLLM.model_validate(e.output)
                for run in RUNS
                for e in load_summaries(run).values()
            ]
            await _consolidate(summaries, labeller, load_prompt(CONSOLIDATE_PROMPT), joint)
    finally:
        await labeller.aclose()


def session_labels(s: SummaryLLM, topic_map: dict[str, str], pain_map: dict[str, str]) -> dict:
    """One run's labels for one session, in the shared vocabulary."""
    relevance: dict[str, str] = {}
    for t in s.main_topics:
        canon = topic_map[t.topic]
        if RELEVANCE_RANK[t.relevance] > RELEVANCE_RANK.get(relevance.get(canon, ""), 0):
            relevance[canon] = t.relevance
    return {
        "reason_for_conversation": DISPLAY_NAMES["reason_for_conversation"][
            s.reason_for_conversation
        ],
        "issue_resolved": s.issue_resolved,
        "end_reason": s.end_reason,
        "strong_topics": frozenset(k for k, v in relevance.items() if v == "strong"),
        "strong_topic_groups": frozenset(
            t.topic_group for t in s.main_topics if t.relevance == "strong"
        ),
        "conversation_pain_points": frozenset(pain_map[p] for p in s.conversation_pain_points),
    }


def cost_table() -> pd.DataFrame:
    """Tokens and USD for every group of calls."""
    groups = {f"summary {r}": load_summaries(r) for r in RUNS}
    groups["mapping joint (3 runs)"] = read_entries(ROOT / "joint_mappings")
    rows = []
    for name, entries in groups.items():
        u = {
            k: sum(getattr(e.usage, k) for e in entries.values())
            for k in ("input_tokens", "cache_read_tokens", "cache_write_tokens", "output_tokens")
        }
        usd = (
            u["input_tokens"] * PRICE_IN
            + u["cache_read_tokens"] * PRICE_CACHE_READ
            + u["cache_write_tokens"] * PRICE_CACHE_WRITE
            + u["output_tokens"] * PRICE_OUT
        ) / 1e6
        rows.append({"calls": name, "n": len(entries)} | u | {"usd": round(usd, 4)})
    return pd.DataFrame(rows)


def run_seconds(entries: dict[str, CacheEntry]) -> float:
    """Seconds between the first and last cache write of one run (8 calls in flight)."""
    times = sorted(datetime.fromisoformat(e.created_at) for e in entries.values())
    return (times[-1] - times[0]).total_seconds()


def comparison_table(labels: dict) -> pd.DataFrame:
    """Sonnet against the hand-labelled outcomes and GPT Luna's cached labels, and run times.

    GPT Luna's labels are whatever is cached in ``data/labels/``; its run times are those of
    the three ``label_stability.py`` runs.
    """
    rows = []
    gold = pd.read_csv(DEFAULT_GOLD_PATH)
    for run in RUNS:
        hits = sum(
            labels[run][sid]["end_reason"] == human
            for sid, human in zip(gold["session_id"], gold["human_end_reason"], strict=True)
        )
        rows.append(
            {"measure": "outcome matches hand label", "who": run, "value": hits, "of": len(gold)}
        )
    gpt = {
        sid: SummaryLLM.model_validate(e.output)
        for sid, e in read_entries(summary_dir(DEFAULT_LABELS_DIR, "gpt_luna")).items()
    }
    for field in CATEGORICAL:
        same = 0
        for sid, s in gpt.items():
            theirs = getattr(s, field)
            if field == "reason_for_conversation":
                theirs = DISPLAY_NAMES[field][theirs]
            same += majority([labels[r][sid][field] for r in RUNS]) == theirs
        rows.append(
            {
                "measure": f"{field}: Sonnet majority matches GPT Luna",
                "who": "sonnet vs gpt_luna",
                "value": same,
                "of": len(gpt),
            }
        )
    for run in RUNS:
        for who, entries in (
            (f"sonnet {run}", load_summaries(run)),
            (f"gpt_luna {run}", read_entries(Path("data/labels_stability/runs") / run)),
        ):
            rows.append(
                {
                    "measure": "seconds to label 50 conversations",
                    "who": who,
                    "value": run_seconds(entries),
                    "of": "",
                }
            )
    return pd.DataFrame(rows)


def analyse() -> None:
    """Write every results table and print the headline numbers."""
    joint = read_entries(ROOT / "joint_mappings")
    topic_map = joint["main_topics"].output["mapping"]
    pain_map = joint["conversation_pain_points"].output["mapping"]
    labels = {
        run: {
            sid: session_labels(SummaryLLM.model_validate(e.output), topic_map, pain_map)
            for sid, e in load_summaries(run).items()
        }
        for run in RUNS
    }
    sids = sorted(labels[RUNS[0]])
    RESULTS.mkdir(parents=True, exist_ok=True)

    agreement = []
    for field in CATEGORICAL:
        per = pd.DataFrame(
            [{"session_id": sid} | {r: labels[r][sid][field] for r in RUNS} for sid in sids]
        )
        per["n_distinct"] = per[list(RUNS)].nunique(axis=1)
        per.to_csv(RESULTS / f"{field}_by_session.csv", index=False)
        agreement.append(
            {
                "field": field,
                "sessions_unanimous": int((per["n_distinct"] == 1).sum()),
                "sessions_2_vs_1": int((per["n_distinct"] == 2).sum()),
                "sessions_3_way": int((per["n_distinct"] == 3).sum()),
                "fleiss_kappa": round(fleiss_kappa(per[list(RUNS)].values.tolist()), 3),
            }
        )
    for field in SETS:
        pairs, sessions = [], []
        for sid in sids:
            sets = {r: labels[r][sid][field] for r in RUNS}
            for label in sorted(set().union(*sets.values())):
                row = {"session_id": sid, "label": label}
                row |= {r: label in sets[r] for r in RUNS}
                pairs.append(row | {"n_runs": sum(label in sets[r] for r in RUNS)})
            jac = [jaccard(sets[a], sets[b]) for a, b in itertools.combinations(RUNS, 2)]
            sessions.append(
                {
                    "session_id": sid,
                    "identical_3_runs": len(set(sets.values())) == 1,
                    "mean_pairwise_jaccard": round(sum(jac) / 3, 3),
                    "n_labels_per_run": "/".join(str(len(sets[r])) for r in RUNS),
                }
            )
        pair_df, sess = pd.DataFrame(pairs), pd.DataFrame(sessions)
        pair_df.to_csv(RESULTS / f"{field}_by_label.csv", index=False)
        sess.to_csv(RESULTS / f"{field}_by_session.csv", index=False)
        agreement.append(
            {
                "field": field,
                "sessions_unanimous": int(sess["identical_3_runs"].sum()),
                "sessions_not_identical": int((~sess["identical_3_runs"]).sum()),
                "mean_pairwise_jaccard": round(sess["mean_pairwise_jaccard"].mean(), 3),
                "label_occurrences_3_of_3": int((pair_df["n_runs"] == 3).sum()),
                "label_occurrences_2_of_3": int((pair_df["n_runs"] == 2).sum()),
                "label_occurrences_1_of_3": int((pair_df["n_runs"] == 1).sum()),
            }
        )
    summary = pd.DataFrame(agreement)
    summary.to_csv(RESULTS / "agreement_summary.csv", index=False)
    comparison = comparison_table(labels)
    comparison.to_csv(RESULTS / "model_comparison.csv", index=False)
    print(comparison.to_string(index=False))
    cost = cost_table()
    cost.to_csv(RESULTS / "cost.csv", index=False)
    print(summary.to_string(index=False))
    print(cost.to_string(index=False))


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=["run", "analyse"])
    args = parser.parse_args()
    if args.step == "run":
        load_dotenv()
        asyncio.run(_run(load_sessions(DEFAULT_DATA_PATH)))
    else:
        analyse()


if __name__ == "__main__":
    main()
