"""Exploratory descriptive statistics and data-integrity checks."""

from __future__ import annotations

import re
from collections import Counter

import pandas as pd

_WORD_RE = re.compile(r"\b\w+\b")


def word_count(text: str) -> int:
    """Count word tokens in a text.

    Args:
        text: Text to count; an empty string counts as zero.

    Returns:
        Number of word tokens (runs of letters, digits or underscores).
    """
    return len(_WORD_RE.findall(text or ""))


def non_ascii_share(text: str) -> float:
    """Compute the share of letters that are non-ASCII.

    A crude signal of non-English text.

    Args:
        text: Text to inspect.

    Returns:
        Fraction of alphabetic characters that are non-ASCII, or 0.0 if there are none.
    """
    letters = [c for c in text or "" if c.isalpha()]
    if not letters:
        return 0.0
    return sum(not c.isascii() for c in letters) / len(letters)


def session_features(sessions: pd.DataFrame, turns: pd.DataFrame) -> pd.DataFrame:
    """Build per-session shape features: turn counts, word volumes and duration.

    Args:
        sessions: One row per session, as returned by ``data.sessions_frame``.
        turns: One row per turn, as returned by ``data.turns_frame``.

    Returns:
        ``sessions`` with added columns ``n_turns``, ``n_user``, ``n_assistant``,
        ``first_role``, ``last_role``, ``user_words``, ``assistant_words``,
        ``assistant_to_user_words``, ``duration_min``, ``seconds_per_turn`` and
        ``starts_on_hour``.
    """
    t = turns.assign(words=turns["text"].map(word_count))
    agg = (
        t.groupby("session_id")
        .agg(
            n_turns=("position", "size"),
            n_user=("role", lambda r: int((r == "user").sum())),
            n_assistant=("role", lambda r: int((r == "assistant").sum())),
            first_role=("role", "first"),
            last_role=("role", "last"),
        )
        .reset_index()
    )
    words = t.pivot_table(
        index="session_id", columns="role", values="words", aggfunc="sum", fill_value=0
    )
    words = words.reindex(columns=["user", "assistant"], fill_value=0)
    words.columns = [f"{c}_words" for c in words.columns]
    out = sessions.merge(agg, on="session_id", how="left").merge(
        words.reset_index(), on="session_id", how="left"
    )
    out["assistant_to_user_words"] = out["assistant_words"] / out["user_words"].where(
        out["user_words"] > 0
    )
    out["duration_min"] = (out["ended_at"] - out["started_at"]).dt.total_seconds() / 60
    out["seconds_per_turn"] = out["duration_min"] * 60 / out["n_turns"]
    started = out["started_at"]
    out["starts_on_hour"] = (started.dt.minute == 0) & (started.dt.second == 0)
    return out


def timing_summary(features: pd.DataFrame) -> pd.DataFrame:
    """Summarise whether session timestamps look generated rather than observed.

    Args:
        features: Output of ``session_features``.

    Returns:
        DataFrame with columns ``metric`` and ``value``: session count, sessions
        starting exactly on the hour, the number of distinct seconds-per-turn values
        (rounded to 0.01 s), and the min and max seconds per turn.
    """
    spt = features["seconds_per_turn"].round(2)
    rows = [
        ("n_sessions", len(features)),
        ("n_starts_on_hour", int(features["starts_on_hour"].sum())),
        ("n_distinct_seconds_per_turn", int(spt.nunique())),
        ("min_seconds_per_turn", float(spt.min())),
        ("max_seconds_per_turn", float(spt.max())),
    ]
    return pd.DataFrame(rows, columns=["metric", "value"], dtype=object)


def ending_crosstab(features: pd.DataFrame) -> pd.DataFrame:
    """Cross-tabulate who spoke last against the recorded end state.

    Args:
        features: Output of ``session_features``.

    Returns:
        DataFrame with columns ``last_role``, ``session_ended_by`` and ``n_sessions``,
        one row per observed combination.
    """
    return (
        features.groupby(["last_role", "session_ended_by"])
        .size()
        .reset_index(name="n_sessions")
        .sort_values(["last_role", "session_ended_by"], ignore_index=True)
    )


def medians_by(features: pd.DataFrame, by: str, columns: list[str]) -> pd.DataFrame:
    """Compute per-group medians and group sizes.

    Args:
        features: Output of ``session_features``.
        by: Column to group by.
        columns: Numeric columns to take medians of.

    Returns:
        DataFrame with ``by``, ``n_sessions`` and the median of each column.
    """
    grouped = features.groupby(by)
    out = grouped[columns].median()
    out.insert(0, "n_sessions", grouped.size())
    return out.reset_index()


def non_ascii_turns(turns: pd.DataFrame) -> pd.DataFrame:
    """List turns containing any non-ASCII letters, a crude flag for non-English text.

    Misses non-English text written without accents; every hit needs reading.

    Args:
        turns: One row per turn with a ``non_ascii_share`` column.

    Returns:
        The matching turns (``session_id``, ``turn``, ``role``, ``non_ascii_share``,
        ``text``), highest share first.
    """
    hits = turns[turns["non_ascii_share"] > 0]
    cols = ["session_id", "turn", "role", "non_ascii_share", "text"]
    return hits.sort_values(
        ["non_ascii_share", "session_id", "turn"], ascending=[False, True, True]
    )[cols].reset_index(drop=True)


def integrity_issues(sessions: pd.DataFrame, turns: pd.DataFrame) -> pd.DataFrame:
    """List structural oddities in the dataset.

    Checks duplicate session IDs, sessions with no turns, turn numbering, unknown
    roles, non-alternating roles, first turn not from the user, empty or null texts,
    repeated texts within a session, and missing or inverted timestamps.

    Args:
        sessions: One row per session, as returned by ``data.sessions_frame``.
        turns: One row per turn, as returned by ``data.turns_frame``.

    Returns:
        DataFrame with columns ``session_id``, ``check`` and ``detail``; empty if clean.
    """
    issues: list[dict[str, object]] = []

    def add(sid: str, check: str, detail: str) -> None:
        issues.append({"session_id": sid, "check": check, "detail": detail})

    dup_ids = sessions["session_id"][sessions["session_id"].duplicated()]
    for sid in dup_ids:
        add(sid, "duplicate_session_id", "")

    for sid in sorted(set(sessions["session_id"]) - set(turns["session_id"])):
        add(sid, "no_turns", "")

    for sid, g in turns.groupby("session_id", sort=True):
        g = g.sort_values("position")
        expected = list(range(1, len(g) + 1))
        if g["turn"].tolist() != expected:
            add(sid, "turn_numbering", f"turns={g['turn'].tolist()}")
        roles = g["role"].tolist()
        bad_roles = sorted(set(roles) - {"user", "assistant"})
        if bad_roles:
            add(sid, "unknown_role", ",".join(map(str, bad_roles)))
        for a, b, pos in zip(roles, roles[1:], g["position"].tolist()[1:], strict=False):
            if a == b:
                add(sid, "role_not_alternating", f"position {pos}: two '{b}' in a row")
        if roles and roles[0] != "user":
            add(sid, "first_turn_not_user", roles[0])
        for pos, text in zip(g["position"], g["text"], strict=True):
            if pd.isna(text) or not str(text).strip():
                add(sid, "empty_text", f"position {pos}")
        texts = g["text"].dropna()
        dupes = [txt for txt, n in Counter(texts).items() if n > 1 and str(txt).strip()]
        for txt in dupes:
            add(sid, "repeated_text_in_session", str(txt)[:80])

    for _, row in sessions.iterrows():
        if pd.notna(row["started_at"]) and pd.notna(row["ended_at"]):
            if row["ended_at"] < row["started_at"]:
                add(row["session_id"], "ends_before_start", "")
        else:
            add(row["session_id"], "missing_timestamp", "")

    return pd.DataFrame(issues, columns=["session_id", "check", "detail"])


def cross_session_repeats(
    turns: pd.DataFrame, role: str = "assistant", min_sessions: int = 2
) -> pd.DataFrame:
    """Find exact texts from one role that recur across different sessions.

    Useful for spotting templated replies.

    Args:
        turns: One row per turn, as returned by ``data.turns_frame``.
        role: Role whose texts to compare (``"assistant"`` or ``"user"``).
        min_sessions: Minimum number of distinct sessions a text must appear in.

    Returns:
        DataFrame with columns ``text``, ``n_sessions`` and ``sessions`` (comma-joined
        IDs), sorted by ``n_sessions`` descending.
    """
    t = turns[turns["role"] == role]
    grouped = t.groupby("text")["session_id"].agg(lambda s: sorted(set(s)))
    grouped = grouped[grouped.map(len) >= min_sessions]
    out = pd.DataFrame(
        {
            "text": grouped.index,
            "n_sessions": grouped.map(len).values,
            "sessions": grouped.map(",".join).values,
        }
    )
    return out.sort_values(["n_sessions", "text"], ascending=[False, True]).reset_index(drop=True)


def opening_phrases(turns: pd.DataFrame, role: str = "assistant", n_words: int = 4) -> pd.DataFrame:
    """Count how often each turn opening occurs for one role.

    A signal of formulaic replies.

    Args:
        turns: One row per turn, as returned by ``data.turns_frame``.
        role: Role whose turns to inspect.
        n_words: Number of leading (lower-cased) words that define an opening.

    Returns:
        DataFrame with columns ``opening`` and ``count``, most frequent first.
    """
    t = turns[turns["role"] == role]
    starts = t["text"].map(lambda s: " ".join(_WORD_RE.findall(s.lower())[:n_words]))
    counts = starts.value_counts()
    return counts.rename_axis("opening").reset_index(name="count")


def categorical_counts(sessions: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Count values of categorical metadata columns in long format.

    Args:
        sessions: One row per session.
        columns: Column names to count.

    Returns:
        DataFrame with columns ``field``, ``value`` and ``count``.
    """
    frames = [
        sessions[col]
        .value_counts()
        .rename_axis("value")
        .reset_index(name="count")
        .assign(field=col)
        for col in columns
    ]
    return pd.concat(frames, ignore_index=True)[["field", "value", "count"]]
