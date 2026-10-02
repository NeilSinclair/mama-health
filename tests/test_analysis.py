import pandas as pd

from mama_analysis.analysis import (
    ending_mismatches,
    ending_vs_outcome,
    friction,
    is_silent_failure,
    missing_safety_labels,
    outcome_by,
    outcome_check,
    outcome_check_counts,
    pain_point_list,
    pushback_status,
    pushbacks_table,
    recovery_by_outcome,
    sentiment_vs_outcome,
    silent_failures,
    topic_group_counts,
)
from mama_analysis.schemas import DynamicsLLM, Pushback


def _row(sid, ended_by, end, pains=()):
    return {
        "session_id": sid,
        "session_ended_by": ended_by,
        "end_reason": [{"label": end, "raw": [end]}],
        "conversation_pain_points": [{"label": p, "raw": [p]} for p in pains],
        "issue_resolved": end == "need met",
        "summary": f"summary of {sid}",
    }


def _record(sid, turns):
    return {
        "session_id": sid,
        "conversation": [
            {"turn": i + 1, "role": role, "text": text} for i, (role, text) in enumerate(turns)
        ],
    }


def _dyn(sentiment, final="ok", pushes=()):
    return DynamicsLLM(
        final_sentiment_quote=final,
        final_sentiment=sentiment,
        pushbacks=[
            Pushback(turn=t, kind="objection", quote=q, reason="r", bot_adapted=a)
            for t, q, a in pushes
        ],
    )


ROWS = [
    _row("a", "completed", "need met"),
    _row("b", "completed", "partial resolution"),
    _row("c", "user_closed", "need met", pains=["bot missed urgent symptom"]),
    _row("d", "user_closed", "unresolved need", pains=["bot repeated advice"]),
]
RECORDS = {
    "a": _record("a", [("user", "hi there"), ("assistant", "hello"), ("user", "ok")]),
    "b": _record("b", [("user", "q"), ("assistant", "a a a"), ("user", "thanks so much")]),
    "c": _record("c", [("user", "bleeding"), ("assistant", "wait"), ("user", "I feel calmer")]),
    "d": _record(
        "d",
        [
            ("user", "one two"),
            ("assistant", "one two three four five six"),
            ("user", "no you keep saying that and it does not help"),
            ("assistant", "sorry"),
        ],
    ),
}
DYN = {
    "a": _dyn("satisfied", "ok"),
    "b": _dyn("satisfied", "thanks so much"),
    "c": _dyn("satisfied", "I feel calmer"),
    "d": _dyn("dissatisfied", "invented words", pushes=[(3, "you keep saying that", False)]),
}


def test_ending_vs_outcome_counts_logged_state_against_outcome():
    t = ending_vs_outcome(ROWS).set_index("session_ended_by")
    assert t.loc["completed"].to_dict() == {
        "need met": 1,
        "partial resolution": 1,
        "unresolved need": 0,
        "total": 2,
    }
    assert t.loc["user_closed", "need met"] == 1


def test_ending_mismatches_are_completed_unmet_or_closed_met():
    assert ending_mismatches(ROWS)["session_id"].tolist() == ["b", "c"]


def test_sentiment_vs_outcome_has_fixed_rows():
    t = sentiment_vs_outcome(ROWS, DYN).set_index("final_sentiment")
    assert t.index.tolist() == ["satisfied", "neutral", "dissatisfied"]
    assert t.loc["satisfied", "total"] == 3
    assert t.loc["dissatisfied", "unresolved need"] == 1


def test_silent_failures_are_satisfied_users_failed_by_outcome_or_safety():
    t = silent_failures(ROWS, DYN, RECORDS)
    # b: satisfied but only partial; c: need met but a safety pain point. a and d are not.
    assert t["session_id"].tolist() == ["b", "c"]
    c = t.set_index("session_id").loc["c"]
    assert c["safety_pain_points"] == "bot missed urgent symptom"
    assert bool(c["quote_found"])


def test_pushbacks_table_checks_quotes():
    t = pushbacks_table(ROWS, DYN, RECORDS)
    assert t[
        ["session_id", "turn", "bot_adapted", "quote_found", "end_reason"]
    ].values.tolist() == [["d", 3, False, True, "unresolved need"]]


def test_recovery_by_outcome():
    t = recovery_by_outcome(ROWS, DYN).set_index("end_reason")
    assert t.loc["unresolved need"].to_dict() == {
        "n_sessions": 1,
        "sessions_with_pushback": 1,
        "pushbacks": 1,
        "adapted": 0,
        "not_adapted": 1,
        "sessions_with_unadapted_pushback": 1,
    }
    assert t.loc["need met", "pushbacks"] == 0


def test_friction_splits_word_share_at_first_pushback():
    t = friction(ROWS, DYN, RECORDS)
    assert t["session_id"].tolist() == ["d"]
    d = t.iloc[0]
    # Before t3: user 2 words, bot 6. From t3: user 10 words, bot 1.
    assert (d["first_pushback_turn"], d["user_word_share_before"], d["user_word_share_from"]) == (
        3,
        0.25,
        0.909,
    )


def test_is_silent_failure_matches_the_table_rule():
    flags = {r["session_id"]: is_silent_failure(r, DYN[r["session_id"]]) for r in ROWS}
    assert flags == {"a": False, "b": True, "c": True, "d": False}


def test_pushback_status():
    assert pushback_status(_dyn("neutral")) == "none"
    assert pushback_status(_dyn("neutral", pushes=[(1, "x", True)])) == "bot always adapted"
    mixed = _dyn("neutral", pushes=[(1, "x", True), (3, "y", False)])
    assert pushback_status(mixed) == "bot failed to adapt"


def test_missing_safety_labels():
    assert missing_safety_labels(ROWS) == [
        "bot ignored suicidal statement",
        "bot claimed action it cannot take",
    ]


def test_end_reasons_match_schema_and_are_never_renamed():
    from typing import get_args

    from mama_analysis.analysis import END_REASONS
    from mama_analysis.consolidate import DISPLAY_NAMES
    from mama_analysis.schemas import SummaryLLM

    # analysis compares displayed labels against these raw values, so a rename would break it.
    assert set(END_REASONS) == set(get_args(SummaryLLM.model_fields["end_reason"].annotation))
    assert "end_reason" not in DISPLAY_NAMES


def test_outcome_by_counts_end_reasons_per_value():
    rows = [r | {"disease": d} for r, d in zip(ROWS, ["ibs", "ibs", "pcos", "ibs"], strict=True)]
    df = outcome_by(rows, "disease")
    assert df["disease"].tolist() == ["ibs", "pcos"]
    ibs = df.iloc[0]
    assert (ibs["need met"], ibs["partial resolution"], ibs["unresolved need"]) == (1, 1, 1)
    assert (ibs["resolved"], ibs["unresolved"]) == (1, 2)
    assert (ibs["total"], ibs["need_met_pct"]) == (3, 33)
    reasons = [r | {"reason_for_conversation": [{"label": "x", "raw": ["x"]}]} for r in ROWS]
    assert outcome_by(reasons, "reason_for_conversation")["total"].tolist() == [4]


def test_topic_group_counts_per_session_with_member_topics():
    def chips(*xs):
        return [{"label": x, "raw": [x]} for x in xs]

    def scores(*items):
        return [{"label": lab, "topic_group": g, "relevance": rel} for lab, g, rel in items]

    rows = [
        {
            "session_id": "a",
            "topic_scores": scores(
                ("pain management", "Physical symptoms", "strong"),
                ("skin conditions", "Physical symptoms", "strong"),
                ("diet", "Fatigue, sleep, diet & activity", "medium"),
            ),
        },
        {
            "session_id": "b",
            "topic_scores": scores(
                ("pain management", "Physical symptoms", "strong"),
                ("care cost", "Access to care", "strong"),
            ),
        },
        {"session_id": "c", "topic_scores": []},
    ]
    df = topic_group_counts(rows)
    # Medium topics don't count; only the model's groups of strong topics.
    assert df["topic_group"].tolist() == ["Physical symptoms", "Access to care"]
    first = df.iloc[0]
    assert (first["n_sessions"], first["session_ids"]) == (2, "a,b")
    assert first["topics"] == "pain management; skin conditions"


def test_pain_point_list_ranks_pain_points_with_where():
    def chips(*xs):
        return [{"label": x, "raw": [x]} for x in xs]

    def row(sid, groups, disease, pains):
        return {
            "session_id": sid,
            "topic_scores": [{"topic_group": g, "relevance": "strong"} for g in groups],
            "disease": disease,
            "conversation_pain_points": chips(*pains),
        }

    rows = [
        row(
            "a", ["Physical symptoms", "Understanding the condition & outlook"], "ibs", ["p1", "p2"]
        ),
        row("b", ["Physical symptoms"], "type_2_diabetes", ["p1"]),
        row("c", [], "pcos", []),
    ]
    df = pain_point_list(rows).set_index("pain_point")
    assert df.index.tolist() == ["p1", "p2"]
    p1 = df.loc["p1"]
    assert (p1["n_sessions"], p1["session_ids"]) == (2, "a,b")
    assert p1["where_topic_group"] == (
        "Physical symptoms (2); Understanding the condition & outlook (1)"
    )
    assert p1["where_disease"] == "ibs (1); type_2_diabetes (1)"


def test_pain_point_list_keeps_columns_when_no_pain_points():
    rows = [
        {"session_id": "a", "topic_scores": [], "disease": "ibs", "conversation_pain_points": []}
    ]
    df = pain_point_list(rows)
    assert df.empty and list(df.columns) == [
        "pain_point",
        "n_sessions",
        "session_ids",
        "where_topic_group",
        "where_disease",
    ]


def test_outcome_check_compares_human_and_model_end_reasons():
    rows = [
        _row("a", "completed", "need met"),
        _row("b", "completed", "partial resolution"),
        _row("c", "user_closed", "unresolved need"),
        _row("d", "completed", "need met"),
    ]
    gold = pd.DataFrame(
        {
            "item": [1, 2, 3, 4],
            "session_id": ["c", "b", "a", "d"],
            "human_end_reason": ["unresolved need", "need met", "need met", ""],
            "note": ["gave up", "", "", ""],
        }
    )
    check = outcome_check(rows, gold)
    assert list(check.columns) == [
        "item",
        "session_id",
        "human_end_reason",
        "model_end_reason",
        "agree",
        "note",
    ]
    # d is unlabelled, so it is skipped; the file's order is kept.
    assert list(check["session_id"]) == ["c", "b", "a"]
    assert list(check["model_end_reason"]) == ["unresolved need", "partial resolution", "need met"]
    assert list(check["agree"]) == [True, False, True]

    counts = outcome_check_counts(check).set_index("human_end_reason")
    assert list(counts.index) == ["need met", "partial resolution", "unresolved need"]
    assert counts.loc["need met", "need met"] == 1
    assert counts.loc["need met", "partial resolution"] == 1
    assert counts.loc["unresolved need", "unresolved need"] == 1
    assert counts.loc["partial resolution", "total"] == 0
    assert counts["total"].sum() == 3
