"""Load and flatten the conversations dataset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_DATA_PATH = Path("data/conversations.json")

REQUIRED_KEYS = ("session_id", "user_meta", "session_meta", "conversation")


def load_sessions(path: Path | str = DEFAULT_DATA_PATH) -> list[dict[str, Any]]:
    """Read the raw JSON list of session records.

    Args:
        path: Path to the conversations JSON file.

    Returns:
        List of session records as dictionaries.

    Raises:
        ValueError: If the file isn't a JSON list, or a record lacks a required key.
    """
    with open(path, encoding="utf-8") as f:
        records = json.load(f)
    if not isinstance(records, list):
        raise ValueError(f"expected a list of sessions, got {type(records).__name__}")
    for i, rec in enumerate(records):
        missing = [k for k in REQUIRED_KEYS if k not in rec]
        if missing:
            raise ValueError(f"record {i} missing keys: {missing}")
    return records


def sessions_frame(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Flatten session records to one row per session.

    Args:
        records: Session records from ``load_sessions``.

    Returns:
        DataFrame with ``session_id``, the user and session metadata fields, and
        ``started_at``/``ended_at`` parsed as UTC timestamps.
    """
    rows = []
    for rec in records:
        rows.append(
            {
                "session_id": rec["session_id"],
                **rec["user_meta"],
                **rec["session_meta"],
            }
        )
    df = pd.DataFrame(rows)
    for col in ("started_at", "ended_at"):
        if col in df:
            df[col] = pd.to_datetime(df[col], utc=True)
    return df


def turns_frame(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Flatten session records to one row per conversation turn.

    Args:
        records: Session records from ``load_sessions``.

    Returns:
        DataFrame with columns ``session_id``, ``position`` (0-based index in the
        conversation), ``turn``, ``role`` and ``text``.
    """
    rows = []
    for rec in records:
        for pos, t in enumerate(rec["conversation"]):
            rows.append(
                {
                    "session_id": rec["session_id"],
                    "position": pos,
                    "turn": t.get("turn"),
                    "role": t.get("role"),
                    "text": t.get("text", ""),
                }
            )
    return pd.DataFrame(rows, columns=["session_id", "position", "turn", "role", "text"])
