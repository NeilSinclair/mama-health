"""Build a blind outcome-labelling page: ten conversations for the human to label by hand.

Exploratory, not part of the pipeline: it reads the cached labels only to pick the sample and
writes ``docs/outcome_check.html``. The page holds the transcripts and no model label.

The sample is five conversations the model labelled "need met" and five it labelled
"partial resolution" or "unresolved need", in shuffled order. Conversations the human has
already read with their label in view (those named in the memo draft, plus s008) are used
only when a group has too few others.

Usage:
    uv run python scripts/make_outcome_check.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from mama_analysis.cache import read_entries
from mama_analysis.config import DEFAULT_LABELS_DIR
from mama_analysis.data import load_sessions
from mama_analysis.explorer import PAYLOAD_MARKER
from mama_analysis.summarise import summary_dir

VERSION = "gpt_luna"
SEED = 20261002
PER_GROUP = 5
OUT_PATH = Path("docs/outcome_check.html")
TEMPLATE_PATH = Path(__file__).with_name("outcome_check_template.html")

# Read by the human with the model's label in view, so a blind label is not possible.
ALREADY_SEEN = frozenset(
    {
        "s005",
        "s008",
        "s014",
        "s018",
        "s022",
        "s024",
        "s026",
        "s038",
        "s042",
        "s043",
        "s046",
        "s048",
        "s049",
    }
)


def pick(end_reasons: dict[str, str]) -> list[str]:
    """Choose the sample: ``PER_GROUP`` need-met and ``PER_GROUP`` other sessions, shuffled.

    Args:
        end_reasons: The model's end reason per session ID.

    Returns:
        Session IDs in the order the page shows them.
    """
    rng = random.Random(SEED)
    chosen: list[str] = []
    for met in (True, False):
        group = sorted(sid for sid, end in end_reasons.items() if (end == "need met") == met)
        fresh = [sid for sid in group if sid not in ALREADY_SEEN]
        seen = [sid for sid in group if sid in ALREADY_SEEN]
        picked = rng.sample(fresh, min(PER_GROUP, len(fresh)))
        picked += rng.sample(seen, PER_GROUP - len(picked))
        chosen += picked
    rng.shuffle(chosen)
    return chosen


def main() -> None:
    """Write the labelling page."""
    entries = read_entries(summary_dir(DEFAULT_LABELS_DIR, VERSION))
    records = {r["session_id"]: r for r in load_sessions()}
    items = [
        {
            "item": i,
            "session_id": sid,
            "turns": [
                {"turn": t["turn"], "role": t["role"], "text": t["text"]}
                for t in records[sid]["conversation"]
            ],
        }
        for i, sid in enumerate(pick({k: e.output["end_reason"] for k, e in entries.items()}), 1)
    ]
    # Escaping every "<" keeps transcript text from closing the script.
    data = json.dumps(items, ensure_ascii=False).replace("<", "\\u003c")
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    OUT_PATH.write_text(template.replace(PAYLOAD_MARKER, data), encoding="utf-8")
    print(f"wrote {OUT_PATH}: {len(items)} conversations")


if __name__ == "__main__":
    main()
