"""Label-stability experiment: how much do GPT Luna's labels vary between identical runs?

Exploratory, not part of the pipeline: it writes only under ``data/labels_stability/`` and
never touches ``data/labels/`` or ``outputs/``.

- ``run``: three fresh ``summary_v7`` runs over all 50 sessions; one ``consolidate_v3`` call
  over the raw labels of all four runs (committed + three fresh), so every run shares one
  vocabulary; and three ``consolidate_v3`` reruns on the committed summaries. Needs
  ``OPENAI_API_KEY`` in ``.env``. Resumable: finished steps are skipped.
- ``analyse``: offline. Agreement tables, majority-vote comparison, consolidation
  agreement and cost, written to ``data/labels_stability/results/``.

Usage:
    uv run python scripts/label_stability.py run
    uv run python scripts/label_stability.py analyse
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from mama_analysis import labellers
from mama_analysis.cache import read_entries
from mama_analysis.config import DEFAULT_LABELS_DIR
from mama_analysis.consolidate import (
    CONSOLIDATE_PROMPT,
    CONSOLIDATED_FIELDS,
    DISPLAY_NAMES,
    consolidate_all,
    mapping_dir,
)
from mama_analysis.data import DEFAULT_DATA_PATH, load_sessions
from mama_analysis.labellers import load_prompt, make_labeller
from mama_analysis.schemas import CacheEntry, SummaryLLM
from mama_analysis.summarise import SUMMARY_PROMPT, summarise_all, summary_dir

VERSION = "gpt_luna"
ROOT = Path("data/labels_stability")
RESULTS = ROOT / "results"
RUNS = ("run1", "run2", "run3")
REPS = ("rep1", "rep2", "rep3")
COMMITTED = "committed"

# GPT-6 Luna standard tier, USD per million tokens (checked 2026-10-01; not in the repo).
PRICE_IN, PRICE_CACHED, PRICE_OUT = 0.10, 0.01, 0.50

# The joint mapping covers ~4x the usual raw labels, so allow a longer answer.
JOINT_MAX_OUTPUT_TOKENS = 64_000

RELEVANCE_RANK = {"strong": 3, "medium": 2, "low": 1}
PROTECTED = (
    "bot ignored suicidal statement",
    "bot missed urgent symptom",
    "bot claimed action it cannot take",
)


def run_dir(run: str) -> Path:
    """Cache directory for one summary run (the committed run lives in ``data/labels``)."""
    if run == COMMITTED:
        return summary_dir(DEFAULT_LABELS_DIR, VERSION)
    return ROOT / "runs" / run


def load_summaries(run: str) -> dict[str, CacheEntry]:
    """Cached summary entries of one run, keyed by session ID."""
    return read_entries(run_dir(run))


# --------------------------------------------------------------------------- API calls


async def _run(records: list[dict[str, Any]]) -> None:
    labeller = make_labeller(VERSION)
    try:
        for run in RUNS:
            if len(load_summaries(run)) == len(records):
                print(f"{run}: cached, skipping")
                continue
            print(f"{run}: summarising {len(records)} sessions")
            await summarise_all(records, labeller, load_prompt(SUMMARY_PROMPT), run_dir(run))

        prompt = load_prompt(CONSOLIDATE_PROMPT)
        joint = ROOT / "joint_mappings"
        if not all((joint / f"{f}.json").exists() for f in CONSOLIDATED_FIELDS):
            print("joint mapping over committed + 3 runs")
            summaries = [
                SummaryLLM.model_validate(e.output)
                for run in (COMMITTED, *RUNS)
                for e in load_summaries(run).values()
            ]
            labellers.MAX_OUTPUT_TOKENS = JOINT_MAX_OUTPUT_TOKENS
            await consolidate_all(summaries, labeller, prompt, joint)

        committed = [
            SummaryLLM.model_validate(e.output) for e in load_summaries(COMMITTED).values()
        ]
        for rep in REPS:
            out = ROOT / "consolidation_reruns" / rep
            if all((out / f"{f}.json").exists() for f in CONSOLIDATED_FIELDS):
                print(f"{rep}: cached, skipping")
                continue
            print(f"{rep}: re-consolidating committed summaries")
            await consolidate_all(committed, labeller, prompt, out)
    finally:
        await labeller.aclose()


# --------------------------------------------------------------------------- analysis


def session_labels(s: SummaryLLM, topic_map: dict[str, str], pain_map: dict[str, str]) -> dict:
    """One run's labels for one session, in the shared vocabulary."""
    relevance: dict[str, str] = {}
    for t in s.main_topics:
        canon = topic_map[t.topic]
        if RELEVANCE_RANK[t.relevance] > RELEVANCE_RANK.get(relevance.get(canon, ""), 0):
            relevance[canon] = t.relevance
    reason = DISPLAY_NAMES["reason_for_conversation"][s.reason_for_conversation]
    return {
        "reason_for_conversation": reason,
        "issue_resolved": s.issue_resolved,
        "end_reason": s.end_reason,
        "strong_topics": frozenset(k for k, v in relevance.items() if v == "strong"),
        # Sensitivity check: is the strong/medium boundary what moves?
        "medium_plus_topics": frozenset(k for k, v in relevance.items() if v != "low"),
        "topic_relevance": relevance,
        "conversation_pain_points": frozenset(pain_map[p] for p in s.conversation_pain_points),
    }


def fleiss_kappa(ratings: list[list[Any]]) -> float:
    """Fleiss' kappa for items each rated by the same number of raters."""
    n = len(ratings[0])
    cats = sorted({r for item in ratings for r in item}, key=str)
    counts = [[item.count(c) for c in cats] for item in ratings]
    p_i = [(sum(x * x for x in row) - n) / (n * (n - 1)) for row in counts]
    p_j = [sum(row[j] for row in counts) / (len(ratings) * n) for j in range(len(cats))]
    p_bar, p_e = sum(p_i) / len(p_i), sum(p * p for p in p_j)
    return (p_bar - p_e) / (1 - p_e) if p_e < 1 else 1.0


def majority(values: list[Any]) -> Any:
    """Value given by at least two of three runs, else ``None`` (a three-way tie)."""
    value, n = Counter(values).most_common(1)[0]
    return value if n >= 2 else None


def jaccard(a: frozenset, b: frozenset) -> float:
    """Jaccard similarity; two empty sets count as identical."""
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def categorical_tables(labels: dict, field: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per-session values of a single-valued field, and per-run value counts."""
    rows = []
    for sid in sorted(labels[COMMITTED]):
        vals = [labels[r][sid][field] for r in RUNS]
        maj = majority(vals)
        rows.append(
            {"session_id": sid}
            | dict(zip(RUNS, vals, strict=True))
            | {
                COMMITTED: labels[COMMITTED][sid][field],
                "n_distinct": len(set(vals)),
                "majority": maj,
                "committed_matches_majority": labels[COMMITTED][sid][field] == maj,
            }
        )
    per_session = pd.DataFrame(rows)
    counts = (
        pd.DataFrame({r: per_session[r].value_counts() for r in (*RUNS, COMMITTED, "majority")})
        .fillna(0)
        .astype(int)
    )
    counts.index.name = "value"
    return per_session, counts.reset_index()


def set_tables(labels: dict, field: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Per (session, label) presence, per-session agreement, and per-run label counts."""
    pairs, sessions = [], []
    for sid in sorted(labels[COMMITTED]):
        sets = {r: labels[r][sid][field] for r in (*RUNS, COMMITTED)}
        for label in sorted(set().union(*sets.values())):
            n = sum(label in sets[r] for r in RUNS)
            row = {"session_id": sid, "label": label, "n_runs": n}
            row |= {r: label in sets[r] for r in (*RUNS, COMMITTED)}
            row["majority"] = n >= 2
            if field == "strong_topics":
                # Where not strong, was the topic still there at a lower relevance?
                row |= {
                    f"{r}_relevance": labels[r][sid]["topic_relevance"].get(label, "absent")
                    for r in (*RUNS, COMMITTED)
                }
            pairs.append(row)
        jac = [jaccard(sets[a], sets[b]) for a, b in itertools.combinations(RUNS, 2)]
        maj = frozenset(
            lbl
            for lbl in set().union(*(sets[r] for r in RUNS))
            if sum(lbl in sets[r] for r in RUNS) >= 2
        )
        sessions.append(
            {
                "session_id": sid,
                "identical_3_runs": sets["run1"] == sets["run2"] == sets["run3"],
                "mean_pairwise_jaccard": round(sum(jac) / 3, 3),
                "n_labels_per_run": "/".join(str(len(sets[r])) for r in RUNS),
                "committed_matches_majority": sets[COMMITTED] == maj,
            }
        )
    pair_df = pd.DataFrame(pairs)
    counts = pd.DataFrame(
        {r: pair_df.groupby("label")[r].sum() for r in (*RUNS, COMMITTED, "majority")}
    ).astype(int)
    counts["run_range"] = counts[list(RUNS)].max(axis=1) - counts[list(RUNS)].min(axis=1)
    counts = counts.sort_values("majority", ascending=False)
    counts.index.name = "label"
    return pair_df, pd.DataFrame(sessions), counts.reset_index()


def ari(a: list[str], b: list[str]) -> float:
    """Adjusted Rand index between two labellings of the same items."""

    def c2(x: int) -> float:
        return x * (x - 1) / 2

    n = len(a)
    sum_ij = sum(c2(v) for v in Counter(zip(a, b, strict=True)).values())
    sum_a = sum(c2(v) for v in Counter(a).values())
    sum_b = sum(c2(v) for v in Counter(b).values())
    expected = sum_a * sum_b / c2(n)
    top = (sum_a + sum_b) / 2
    return 1.0 if top == expected else (sum_ij - expected) / (top - expected)


def consolidation_tables(committed: list[SummaryLLM]) -> pd.DataFrame:
    """Agreement between the committed mapping and three reruns on the same raw labels."""
    maps = {COMMITTED: read_entries(mapping_dir(DEFAULT_LABELS_DIR, VERSION))}
    maps |= {rep: read_entries(ROOT / "consolidation_reruns" / rep) for rep in REPS}
    rows = []
    for field in CONSOLIDATED_FIELDS:
        m = {k: v[field].output["mapping"] for k, v in maps.items()}
        raws = sorted(m[COMMITTED])
        # Occurrence-weighted items: every time a raw label is shown (strong topics only).
        occ = (
            [t.topic for s in committed for t in s.main_topics if t.relevance == "strong"]
            if field == "main_topics"
            else [p for s in committed for p in s.conversation_pain_points]
        )
        for a, b in itertools.combinations(m, 2):
            rows.append(
                {
                    "field": field,
                    "mapping_a": a,
                    "mapping_b": b,
                    "n_canonical_a": len(set(m[a].values())),
                    "n_canonical_b": len(set(m[b].values())),
                    "ari_raw_labels": round(
                        ari([m[a][r] for r in raws], [m[b][r] for r in raws]), 3
                    ),
                    "ari_shown_occurrences": round(
                        ari([m[a][r] for r in occ], [m[b][r] for r in occ]), 3
                    ),
                }
            )
        if field == "conversation_pain_points":
            for k, mp in m.items():
                for p in PROTECTED:
                    sids = sorted(
                        sid
                        for sid, e in load_summaries(COMMITTED).items()
                        if any(mp[x] == p for x in e.output["conversation_pain_points"])
                    )
                    rows.append(
                        {
                            "field": "protected",
                            "mapping_a": k,
                            "label": p,
                            "sessions": " ".join(sids),
                        }
                    )
    return pd.DataFrame(rows)


def cost_table() -> pd.DataFrame:
    """Tokens and USD for every group of calls (committed run included for reference)."""
    groups = {f"summary {r}": load_summaries(r) for r in (COMMITTED, *RUNS)}
    groups["mapping committed"] = read_entries(mapping_dir(DEFAULT_LABELS_DIR, VERSION))
    groups["mapping joint (4 runs)"] = read_entries(ROOT / "joint_mappings")
    groups |= {f"mapping {rep}": read_entries(ROOT / "consolidation_reruns" / rep) for rep in REPS}
    rows = []
    for name, entries in groups.items():
        u_in = sum(e.usage.input_tokens for e in entries.values())
        u_cached = sum(e.usage.cache_read_tokens for e in entries.values())
        u_out = sum(e.usage.output_tokens for e in entries.values())
        usd = ((u_in - u_cached) * PRICE_IN + u_cached * PRICE_CACHED + u_out * PRICE_OUT) / 1e6
        rows.append(
            {
                "calls": name,
                "n_calls": len(entries),
                "input_tokens": u_in,
                "cached_tokens": u_cached,
                "output_tokens": u_out,
                "usd": round(usd, 4),
            }
        )
    return pd.DataFrame(rows)


def analyse(records: list[dict[str, Any]]) -> None:
    """Write every results table and print the headline numbers."""
    joint = read_entries(ROOT / "joint_mappings")
    topic_map = joint["main_topics"].output["mapping"]
    pain_map = joint["conversation_pain_points"].output["mapping"]
    labels = {
        run: {
            sid: session_labels(SummaryLLM.model_validate(e.output), topic_map, pain_map)
            for sid, e in load_summaries(run).items()
        }
        for run in (COMMITTED, *RUNS)
    }
    RESULTS.mkdir(parents=True, exist_ok=True)

    def write(name: str, df: pd.DataFrame) -> None:
        df.to_csv(RESULTS / f"{name}.csv", index=False)

    agreement = []
    instability = {sid: [] for sid in labels[COMMITTED]}
    for field in ("reason_for_conversation", "issue_resolved", "end_reason"):
        per, counts = categorical_tables(labels, field)
        write(f"{field}_by_session", per)
        write(f"{field}_counts", counts)
        agreement.append(
            {
                "field": field,
                "sessions_unanimous": int((per["n_distinct"] == 1).sum()),
                "sessions_2_vs_1": int((per["n_distinct"] == 2).sum()),
                "sessions_3_way": int((per["n_distinct"] == 3).sum()),
                "fleiss_kappa": round(fleiss_kappa(per[list(RUNS)].values.tolist()), 3),
                "committed_vs_majority_differs": int((~per["committed_matches_majority"]).sum()),
            }
        )
        for sid in per.loc[per["n_distinct"] > 1, "session_id"]:
            instability[sid].append(field)
    for field in ("strong_topics", "medium_plus_topics", "conversation_pain_points"):
        pairs, sess, counts = set_tables(labels, field)
        write(f"{field}_by_label", pairs)
        write(f"{field}_by_session", sess)
        write(f"{field}_counts", counts)
        agreement.append(
            {
                "field": field,
                "sessions_unanimous": int(sess["identical_3_runs"].sum()),
                "sessions_not_identical": int((~sess["identical_3_runs"]).sum()),
                "mean_pairwise_jaccard": round(sess["mean_pairwise_jaccard"].mean(), 3),
                "label_occurrences_3_of_3": int((pairs["n_runs"] == 3).sum()),
                "label_occurrences_2_of_3": int((pairs["n_runs"] == 2).sum()),
                "label_occurrences_1_of_3": int((pairs["n_runs"] == 1).sum()),
                "committed_vs_majority_differs": int((~sess["committed_matches_majority"]).sum()),
            }
        )
        if field == "medium_plus_topics":
            continue
        for sid in sess.loc[~sess["identical_3_runs"], "session_id"]:
            instability[sid].append(field)
        if field == "strong_topics":
            # For each strong topic missing from a run: was it demoted or dropped?
            flips = Counter(
                row[f"{r}_relevance"]
                for _, row in pairs[pairs["n_runs"].between(1, 2)].iterrows()
                for r in RUNS
                if not row[r]
            )
            write(
                "strong_topic_misses",
                pd.DataFrame(
                    [{"relevance_in_missing_run": k, "count": v} for k, v in sorted(flips.items())]
                ),
            )
    write("agreement_summary", pd.DataFrame(agreement))

    by_id = {r["session_id"]: r for r in records}
    write(
        "session_instability",
        pd.DataFrame(
            [
                {
                    "session_id": sid,
                    "n_unstable_fields": len(f),
                    "unstable_fields": " ".join(f),
                    "n_turns": len(by_id[sid]["conversation"]),
                    "user_words": sum(
                        len(t["text"].split())
                        for t in by_id[sid]["conversation"]
                        if t["role"] == "user"
                    ),
                    "disease": by_id[sid]["user_meta"]["disease"],
                    "session_ended_by": by_id[sid]["session_meta"]["session_ended_by"],
                }
                for sid, f in sorted(instability.items())
            ]
        ),
    )
    committed = [SummaryLLM.model_validate(e.output) for e in load_summaries(COMMITTED).values()]
    write("consolidation_agreement", consolidation_tables(committed))
    write("cost", cost_table())
    vocab = pd.DataFrame(
        [
            {
                "field": f,
                "n_raw": len(joint[f].output["mapping"]),
                "n_canonical": len(set(joint[f].output["mapping"].values())),
            }
            for f in CONSOLIDATED_FIELDS
        ]
    )
    write("joint_vocabulary", vocab)
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(pd.DataFrame(agreement).to_string(index=False))
        print(vocab.to_string(index=False))
        print(cost_table().to_string(index=False))
    print(f"wrote {RESULTS}/")


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=["run", "analyse"])
    args = parser.parse_args()
    records = load_sessions(DEFAULT_DATA_PATH)
    if args.step == "run":
        load_dotenv()
        asyncio.run(_run(records))
    else:
        analyse(records)


if __name__ == "__main__":
    main()
