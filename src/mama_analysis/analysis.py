"""Analysis tables built from labelled rows and dynamics labels; no API calls."""

from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd

from mama_analysis.consolidate import KEPT_RELEVANCE, topic_groups
from mama_analysis.dynamics import check_dynamics
from mama_analysis.eda import word_count
from mama_analysis.schemas import DynamicsLLM

END_REASONS = ("need met", "partial resolution", "unresolved need")
SENTIMENTS = ("satisfied", "neutral", "dissatisfied")
# Protected canonical pain points (consolidate_v4) that mark a safety failure.
SAFETY_PAIN_POINTS = (
    "bot ignored suicidal statement",
    "bot missed urgent symptom",
    "bot claimed action it cannot take",
)


PUSHBACK_STATUSES = ("none", "bot always adapted", "bot failed to adapt")


def _end(row: dict[str, Any]) -> str:
    return row["end_reason"][0]["label"]


def _pains(row: dict[str, Any]) -> list[str]:
    return [c["label"] for c in row["conversation_pain_points"]]


def _counts(pairs: list[tuple[str, str]], index: list[str]) -> pd.DataFrame:
    """Count (row key, end reason) pairs into a fixed-shape table with a total column."""
    df = pd.DataFrame(
        [
            {
                "key": k,
                **{e: sum(1 for kk, ee in pairs if kk == k and ee == e) for e in END_REASONS},
            }
            for k in index
        ]
    )
    df["total"] = df[list(END_REASONS)].sum(axis=1)
    return df


def missing_safety_labels(rows: list[dict[str, Any]]) -> list[str]:
    """Safety pain points absent from a version's canonical labels.

    The silent-failure rule matches ``SAFETY_PAIN_POINTS`` by name, so a remap that renames
    one would silently weaken it. Absence can also be genuine (no such failure occurred).

    Args:
        rows: Output of ``explorer.label_rows``.

    Returns:
        The ``SAFETY_PAIN_POINTS`` that no session carries, in their defined order.
    """
    present = {p for r in rows for p in _pains(r)}
    return [p for p in SAFETY_PAIN_POINTS if p not in present]


def is_silent_failure(row: dict[str, Any], dyn: DynamicsLLM) -> bool:
    """Whether the user sounded satisfied but the conversation failed them (D-037).

    Args:
        row: One row from ``explorer.label_rows``.
        dyn: That session's dynamics label.

    Returns:
        True if the final sentiment is ``satisfied`` and either the need was not met or the
        session has a safety pain point (``SAFETY_PAIN_POINTS``).
    """
    safety = any(p in SAFETY_PAIN_POINTS for p in _pains(row))
    return dyn.final_sentiment == "satisfied" and (_end(row) != "need met" or safety)


def pushback_status(dyn: DynamicsLLM) -> str:
    """Summarise a session's pushback as one of ``PUSHBACK_STATUSES``.

    Args:
        dyn: A session's dynamics label.

    Returns:
        ``"none"`` without pushback, ``"bot failed to adapt"`` if any pushback was not
        adapted to, else ``"bot always adapted"``.
    """
    if not dyn.pushbacks:
        return "none"
    return (
        "bot always adapted" if all(p.bot_adapted for p in dyn.pushbacks) else "bot failed to adapt"
    )


def ending_vs_outcome(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Cross the logged ``session_ended_by`` with the LLM end reason.

    Args:
        rows: Output of ``explorer.label_rows``.

    Returns:
        One row per logged end state (sorted), a column per end reason, and ``total``.
    """
    pairs = [(r["session_ended_by"], _end(r)) for r in rows]
    df = _counts(pairs, sorted({k for k, _ in pairs}))
    return df.rename(columns={"key": "session_ended_by"})


def outcome_by(rows: list[dict[str, Any]], field: str) -> pd.DataFrame:
    """Count end reasons per value of a field.

    Args:
        rows: Output of ``explorer.label_rows``.
        field: A one-label field such as ``"reason_for_conversation"``, a metadata field
            such as ``"disease"``, or ``"topic_group"`` (the groups of the strong topics).

    Returns:
        One row per value, a column per end reason, ``resolved`` (need met) and
        ``unresolved`` (partial resolution or unresolved need), ``total`` and
        ``need_met_pct`` (whole percent), sorted by total descending, then value. With
        ``"topic_group"`` a conversation counts once in each of its groups, so the rows
        can add up to more than the number of conversations; one with no strong topic
        counts under ``"(none)"``.
    """

    def values(r: dict[str, Any]) -> list[str]:
        if field == "topic_group":
            return topic_groups(r["topic_scores"]) or ["(none)"]
        v = r[field]
        return [v if isinstance(v, str) else v[0]["label"]]

    pairs = [(v, _end(r)) for r in rows for v in values(r)]
    df = _counts(pairs, sorted({k for k, _ in pairs}))
    df.insert(len(END_REASONS) + 1, "resolved", df["need met"])
    df.insert(len(END_REASONS) + 2, "unresolved", df["partial resolution"] + df["unresolved need"])
    df["need_met_pct"] = (100 * df["need met"] / df["total"]).round().astype(int)
    df = df.sort_values(["total", "key"], ascending=[False, True], ignore_index=True)
    return df.rename(columns={"key": field})


def outcome_check(rows: list[dict[str, Any]], gold: pd.DataFrame) -> pd.DataFrame:
    """Compare the human's end-reason labels with the model's, conversation by conversation.

    Args:
        rows: Output of ``explorer.label_rows``.
        gold: The human's labels: ``item``, ``session_id``, ``human_end_reason`` and ``note``.
            Conversations left unlabelled (an empty ``human_end_reason``) are skipped.

    Returns:
        One row per labelled conversation, in the file's order: ``item``, ``session_id``,
        ``human_end_reason``, ``model_end_reason``, ``agree`` and ``note``.

    Raises:
        ValueError: If a labelled row names a session without a model label, or an end
            reason outside ``END_REASONS``.
    """
    model = {r["session_id"]: _end(r) for r in rows}
    df = gold[gold["human_end_reason"] != ""].reset_index(drop=True)
    unknown = sorted(set(df["session_id"]) - model.keys())
    bad = sorted(set(df["human_end_reason"]) - set(END_REASONS))
    if unknown or bad:
        raise ValueError(f"gold labels: unknown sessions {unknown}, unknown end reasons {bad}")
    df.insert(3, "model_end_reason", df["session_id"].map(model))
    df.insert(4, "agree", df["human_end_reason"] == df["model_end_reason"])
    return df


def outcome_check_counts(check: pd.DataFrame) -> pd.DataFrame:
    """Cross the human's end reason with the model's.

    Args:
        check: Output of ``outcome_check``.

    Returns:
        One row per end reason the human could give, a column per end reason the model
        gave, and ``total``. Agreement is the diagonal.
    """
    pairs = list(zip(check["human_end_reason"], check["model_end_reason"], strict=True))
    return _counts(pairs, list(END_REASONS)).rename(columns={"key": "human_end_reason"})


def _where(subset: list[dict[str, Any]], keys: Any) -> str:
    """Count conversations per key as ``"key (n); key (n)"``, most common first."""
    counts = Counter(k for r in subset for k in keys(r))
    return "; ".join(f"{k} ({n})" for k, n in sorted(counts.items(), key=lambda x: (-x[1], x[0])))


def pain_point_list(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """List each conversation pain point with its conversations and where they occur.

    Args:
        rows: Output of ``explorer.label_rows``.

    Returns:
        One row per pain point, sorted by count descending, then name. Columns:
        ``pain_point``, ``n_sessions``, comma-joined
        ``session_ids``, and ``where_topic_group`` / ``where_disease`` as
        ``"value (n); ..."`` (topic groups of the strong topics; a conversation can count
        in several groups).
    """

    def groups(r: dict[str, Any]) -> list[str]:
        return topic_groups(r["topic_scores"]) or ["(none)"]

    def entry(label: str, subset: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "pain_point": label,
            "n_sessions": len(subset),
            "session_ids": ",".join(r["session_id"] for r in subset),
            "where_topic_group": _where(subset, groups),
            "where_disease": _where(subset, lambda r: [r["disease"]]),
        }

    totals = Counter(p for r in rows for p in _pains(r))
    return pd.DataFrame(
        [
            entry(p, [r for r in rows if p in _pains(r)])
            for p in sorted(totals, key=lambda p: (-totals[p], p))
        ],
        columns=["pain_point", "n_sessions", "session_ids", "where_topic_group", "where_disease"],
    )


def topic_group_counts(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Count sessions per topic group the model filed strong topics in, with their topics.

    Args:
        rows: Output of ``explorer.label_rows``.

    Returns:
        One row per group with ``topic_group``, ``n_sessions``, comma-joined
        ``session_ids`` and ``topics`` (the canonical strong topics filed in it,
        "; "-joined), sorted by count descending, then group.
    """
    sessions: dict[str, list[str]] = {}
    topics: dict[str, set[str]] = {}
    for r in rows:
        for t in r["topic_scores"]:
            if t["relevance"] == KEPT_RELEVANCE:
                topics.setdefault(t["topic_group"], set()).add(t["label"])
        for g in topic_groups(r["topic_scores"]):
            sessions.setdefault(g, []).append(r["session_id"])
    df = pd.DataFrame(
        [
            {
                "topic_group": g,
                "n_sessions": len(ids),
                "session_ids": ",".join(ids),
                "topics": "; ".join(sorted(topics[g])),
            }
            for g, ids in sessions.items()
        ],
        columns=["topic_group", "n_sessions", "session_ids", "topics"],
    )
    return df.sort_values(["n_sessions", "topic_group"], ascending=[False, True], ignore_index=True)


def ending_mismatches(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Sessions whose logged end state disagrees with the outcome.

    A mismatch is ``completed`` without the need met, or ``user_closed`` with it met.

    Args:
        rows: Output of ``explorer.label_rows``.

    Returns:
        ``session_id``, ``session_ended_by``, ``end_reason``, ``issue_resolved`` and
        ``summary``, sorted by session ID.
    """
    out = [
        {
            "session_id": r["session_id"],
            "session_ended_by": r["session_ended_by"],
            "end_reason": _end(r),
            "issue_resolved": r["issue_resolved"],
            "summary": r["summary"],
        }
        for r in rows
        if (r["session_ended_by"] == "completed") != (_end(r) == "need met")
    ]
    cols = ["session_id", "session_ended_by", "end_reason", "issue_resolved", "summary"]
    return pd.DataFrame(out, columns=cols).sort_values("session_id", ignore_index=True)


def sentiment_vs_outcome(
    rows: list[dict[str, Any]], dynamics: dict[str, DynamicsLLM]
) -> pd.DataFrame:
    """Cross the user's final sentiment with the LLM end reason.

    Args:
        rows: Output of ``explorer.label_rows``.
        dynamics: Dynamics labels keyed by session ID.

    Returns:
        One row per sentiment (satisfied, neutral, dissatisfied), a column per end reason,
        and ``total``.
    """
    pairs = [(dynamics[r["session_id"]].final_sentiment, _end(r)) for r in rows]
    return _counts(pairs, list(SENTIMENTS)).rename(columns={"key": "final_sentiment"})


def silent_failures(
    rows: list[dict[str, Any]],
    dynamics: dict[str, DynamicsLLM],
    records: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    """Sessions where the user sounded satisfied but the conversation failed them.

    Rule (D-037): final sentiment is ``satisfied`` and either the need was not met or the
    session has a safety pain point (``SAFETY_PAIN_POINTS``).

    Args:
        rows: Output of ``explorer.label_rows``.
        dynamics: Dynamics labels keyed by session ID.
        records: Raw session records keyed by session ID.

    Returns:
        ``session_id``, ``end_reason``, ``safety_pain_points``, ``conversation_pain_points``,
        ``final_sentiment_quote``, ``quote_found`` and ``summary``, sorted by session ID.
    """
    out = []
    for r in rows:
        dyn = dynamics[r["session_id"]]
        safety = [p for p in _pains(r) if p in SAFETY_PAIN_POINTS]
        if is_silent_failure(r, dyn):
            out.append(
                {
                    "session_id": r["session_id"],
                    "end_reason": _end(r),
                    "safety_pain_points": "; ".join(safety),
                    "conversation_pain_points": "; ".join(_pains(r)),
                    "final_sentiment_quote": dyn.final_sentiment_quote,
                    "quote_found": check_dynamics(records[r["session_id"]], dyn)[
                        "final_quote_found"
                    ],
                    "summary": r["summary"],
                }
            )
    cols = [
        "session_id",
        "end_reason",
        "safety_pain_points",
        "conversation_pain_points",
        "final_sentiment_quote",
        "quote_found",
        "summary",
    ]
    return pd.DataFrame(out, columns=cols).sort_values("session_id", ignore_index=True)


def pushbacks_table(
    rows: list[dict[str, Any]],
    dynamics: dict[str, DynamicsLLM],
    records: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    """One row per pushback, with whether its quote checks out against the transcript.

    Args:
        rows: Output of ``explorer.label_rows``.
        dynamics: Dynamics labels keyed by session ID.
        records: Raw session records keyed by session ID.

    Returns:
        ``session_id``, ``turn``, ``kind``, ``bot_adapted``, ``quote``, ``quote_found``,
        ``reason`` and the session's ``end_reason``, sorted by session and turn.
    """
    out = []
    for r in rows:
        dyn = dynamics[r["session_id"]]
        ok = check_dynamics(records[r["session_id"]], dyn)["pushback_ok"]
        for p, found in zip(dyn.pushbacks, ok, strict=True):
            out.append(
                {
                    "session_id": r["session_id"],
                    "turn": p.turn,
                    "kind": p.kind,
                    "bot_adapted": p.bot_adapted,
                    "quote": p.quote,
                    "quote_found": found,
                    "reason": p.reason,
                    "end_reason": _end(r),
                }
            )
    cols = ["session_id", "turn", "kind", "bot_adapted", "quote", "quote_found", "reason"]
    return pd.DataFrame(out, columns=[*cols, "end_reason"]).sort_values(
        ["session_id", "turn"], ignore_index=True
    )


def recovery_by_outcome(
    rows: list[dict[str, Any]], dynamics: dict[str, DynamicsLLM]
) -> pd.DataFrame:
    """Per end reason, how often users pushed back and how often the bot adapted.

    Args:
        rows: Output of ``explorer.label_rows``.
        dynamics: Dynamics labels keyed by session ID.

    Returns:
        One row per end reason: ``n_sessions``, ``sessions_with_pushback``, ``pushbacks``,
        ``adapted``, ``not_adapted`` and ``sessions_with_unadapted_pushback``.
    """
    out = []
    for end in END_REASONS:
        dyns = [dynamics[r["session_id"]] for r in rows if _end(r) == end]
        pushes = [p for d in dyns for p in d.pushbacks]
        out.append(
            {
                "end_reason": end,
                "n_sessions": len(dyns),
                "sessions_with_pushback": sum(1 for d in dyns if d.pushbacks),
                "pushbacks": len(pushes),
                "adapted": sum(p.bot_adapted for p in pushes),
                "not_adapted": sum(not p.bot_adapted for p in pushes),
                "sessions_with_unadapted_pushback": sum(
                    1 for d in dyns if any(not p.bot_adapted for p in d.pushbacks)
                ),
            }
        )
    return pd.DataFrame(out)


def _user_share(turns: list[dict[str, Any]]) -> float | None:
    words = {"user": 0, "assistant": 0}
    for t in turns:
        words[t["role"]] += word_count(t["text"])
    total = words["user"] + words["assistant"]
    return round(words["user"] / total, 3) if total else None


def friction(
    rows: list[dict[str, Any]],
    dynamics: dict[str, DynamicsLLM],
    records: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    """The user's share of words before and from the first pushback, per session with one.

    Args:
        rows: Output of ``explorer.label_rows``.
        dynamics: Dynamics labels keyed by session ID.
        records: Raw session records keyed by session ID.

    Returns:
        ``session_id``, ``first_pushback_turn``, ``user_word_share_before``,
        ``user_word_share_from`` (share over turns from the first pushback on) and
        ``end_reason``, sorted by session ID.
    """
    out = []
    for r in rows:
        dyn = dynamics[r["session_id"]]
        if not dyn.pushbacks:
            continue
        first = min(p.turn for p in dyn.pushbacks)
        convo = records[r["session_id"]]["conversation"]
        out.append(
            {
                "session_id": r["session_id"],
                "first_pushback_turn": first,
                "user_word_share_before": _user_share([t for t in convo if t["turn"] < first]),
                "user_word_share_from": _user_share([t for t in convo if t["turn"] >= first]),
                "end_reason": _end(r),
            }
        )
    cols = [
        "session_id",
        "first_pushback_turn",
        "user_word_share_before",
        "user_word_share_from",
        "end_reason",
    ]
    return pd.DataFrame(out, columns=cols).sort_values("session_id", ignore_index=True)
