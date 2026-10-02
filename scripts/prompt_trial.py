"""Trial of a new summary prompt against the committed labels and the human's gold labels.

Exploratory, not part of the pipeline: it writes only under ``data/labels_trials/`` and never
touches ``data/labels/`` or ``outputs/``.

- ``run``: label sessions with the given prompt version into
  ``data/labels_trials/<prompt>/run<n>/``. Needs ``OPENAI_API_KEY`` in ``.env``. Resumable:
  sessions already labelled in that run are skipped, so a full run reuses an earlier run on
  the gold set.
- ``compare``: offline. One row per trialled session, with the committed label, each trial
  run's label and the human's label where there is one, written to
  ``data/labels_trials/<prompt>/results/comparison.csv``. Pain points are the model's raw
  labels; they are not consolidated.

The prompts trialled so far (``summary_v10``, ``summary_v11``) were not adopted and are no
longer in ``src/mama_analysis/prompts/``; see D-051 for the commit that holds them.

Usage:
    uv run python scripts/prompt_trial.py run summary_v10 --gold
    uv run python scripts/prompt_trial.py run summary_v10
    uv run python scripts/prompt_trial.py run summary_v10 --run 2 --sessions s001,s002
    uv run python scripts/prompt_trial.py compare summary_v10
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from mama_analysis.cache import read_entries
from mama_analysis.config import DEFAULT_LABELS_DIR
from mama_analysis.data import load_sessions
from mama_analysis.labellers import load_prompt, make_labeller
from mama_analysis.summarise import summarise_all, summary_dir

VERSION = "gpt_luna"
TRIALS_DIR = Path("data/labels_trials")
GOLD_PATH = Path("data/gold/outcome_check.csv")
FIELDS = ("end_reason", "reason_for_conversation")


def load_gold() -> dict[str, str]:
    """The human's end reason per session ID; empty if there is no gold file."""
    if not GOLD_PATH.exists():
        return {}
    gold = pd.read_csv(GOLD_PATH, keep_default_na=False)
    gold = gold[gold["human_end_reason"] != ""]
    return dict(zip(gold["session_id"], gold["human_end_reason"], strict=True))


async def run(prompt_version: str, run_number: int, sessions: set[str] | None) -> None:
    """Label the chosen sessions with one prompt version, skipping those already done.

    Args:
        prompt_version: Prompt file stem, e.g. ``"summary_v10"``.
        run_number: Which repeat this is; each has its own directory.
        sessions: Session IDs to label, or ``None`` for all.
    """
    out_dir = TRIALS_DIR / prompt_version / f"run{run_number}"
    done = set(read_entries(out_dir))
    records = [
        r
        for r in load_sessions()
        if (sessions is None or r["session_id"] in sessions) and r["session_id"] not in done
    ]
    print(f"{prompt_version} run{run_number}: {len(records)} to label, {len(done)} already done")
    if not records:
        return
    labeller = make_labeller(VERSION)
    try:
        await summarise_all(records, labeller, load_prompt(prompt_version), out_dir)
    finally:
        await labeller.aclose()


def compare(prompt_version: str) -> pd.DataFrame:
    """Set the trial labels beside the committed labels and the human's.

    Args:
        prompt_version: Prompt file stem of the trial.

    Returns:
        One row per session labelled in any trial run, sorted by session ID.
    """
    committed = read_entries(summary_dir(DEFAULT_LABELS_DIR, VERSION))
    runs = {
        d.name: read_entries(d) for d in sorted((TRIALS_DIR / prompt_version).glob("run[0-9]*"))
    }
    gold = load_gold()
    rows = []
    for sid in sorted({sid for entries in runs.values() for sid in entries}):
        row = {"session_id": sid, "human_end_reason": gold.get(sid, "")}
        for field in FIELDS:
            row[f"committed_{field}"] = committed[sid].output[field]
            for name, entries in runs.items():
                row[f"{name}_{field}"] = entries[sid].output[field] if sid in entries else ""
        row["committed_pain_points"] = "; ".join(committed[sid].output["conversation_pain_points"])
        for name, entries in runs.items():
            pains = entries[sid].output["conversation_pain_points"] if sid in entries else []
            row[f"{name}_pain_points"] = "; ".join(pains)
        rows.append(row)
    df = pd.DataFrame(rows)
    out = TRIALS_DIR / prompt_version / "results" / "comparison.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"wrote {out}: {len(df)} sessions, runs: {', '.join(runs)}")
    return df


def main() -> None:
    """Run the trial or compare its labels."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["run", "compare"])
    parser.add_argument("prompt", help="prompt version, e.g. summary_v10")
    parser.add_argument("--run", type=int, default=1, help="repeat number (default 1)")
    parser.add_argument("--gold", action="store_true", help="only the human-labelled sessions")
    parser.add_argument("--sessions", help="comma-separated session IDs")
    args = parser.parse_args()
    if args.command == "compare":
        compare(args.prompt)
        return
    load_dotenv()
    sessions = set(load_gold()) if args.gold else None
    if args.sessions:
        sessions = set(args.sessions.split(","))
    asyncio.run(run(args.prompt, args.run, sessions))


if __name__ == "__main__":
    main()
