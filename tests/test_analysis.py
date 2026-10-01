from mama_analysis.analysis import (
    ending_mismatches,
    ending_vs_outcome,
    friction,
    is_silent_failure,
    missing_safety_labels,
    outcome_by,
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

    rows = [
        {"session_id": "a", "main_topics": chips("pain management", "skin conditions")},
        {"session_id": "b", "main_topics": chips("pain management", "new thing")},
        {"session_id": "c", "main_topics": []},
    ]
    df = topic_group_counts(rows)
    assert df["topic_group"].tolist() == ["Physical symptoms", "(ungrouped)"]
    first = df.iloc[0]
    assert (first["n_sessions"], first["session_ids"]) == (2, "a,b")
    assert first["topics"] == "pain management; skin conditions"


def test_pain_point_list_ranks_pain_points_with_where():
    def chips(*xs):
        return [{"label": x, "raw": [x]} for x in xs]

    def row(sid, topics, disease, pains):
        return {
            "session_id": sid,
            "main_topics": chips(*topics),
            "disease": disease,
            "conversation_pain_points": chips(*pains),
        }

    rows = [
        row("a", ["pain management", "cancer risk"], "ibs", ["p1", "p2"]),
        row("b", ["skin conditions"], "type_2_diabetes", ["p1"]),
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
        {"session_id": "a", "main_topics": [], "disease": "ibs", "conversation_pain_points": []}
    ]
    df = pain_point_list(rows)
    assert df.empty and list(df.columns) == [
        "pain_point",
        "n_sessions",
        "session_ids",
        "where_topic_group",
        "where_disease",
    ]
