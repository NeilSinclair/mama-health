from mama_analysis.analysis import (
    ending_mismatches,
    ending_vs_outcome,
    friction,
    is_silent_failure,
    missing_safety_labels,
    pushback_status,
    pushbacks_table,
    recovery_by_outcome,
    sentiment_vs_outcome,
    silent_failures,
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
