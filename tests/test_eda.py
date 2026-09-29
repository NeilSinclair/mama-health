import pandas as pd
import pytest

from mama_analysis import eda
from mama_analysis.data import sessions_frame, turns_frame


@pytest.fixture
def frames(records):
    return sessions_frame(records), turns_frame(records)


def test_word_count():
    assert eda.word_count("I'm fine, thanks!") == 4
    assert eda.word_count("") == 0


def test_non_ascii_share():
    assert eda.non_ascii_share("hello") == 0.0
    assert eda.non_ascii_share("héllo") == pytest.approx(0.2)
    assert eda.non_ascii_share("123 !!") == 0.0


def test_session_features(frames):
    sessions, turns = frames
    f = eda.session_features(sessions, turns).set_index("session_id")
    assert f.loc["s1", "n_turns"] == 2
    assert f.loc["s2", "n_assistant"] == 2
    assert f.loc["s1", "user_words"] == 4
    assert f.loc["s1", "duration_min"] == pytest.approx(10.0)
    assert f.loc["s2", "duration_min"] < 0


def test_integrity_issues_flags_known_problems(frames):
    sessions, turns = frames
    issues = eda.integrity_issues(sessions, turns)
    found = set(zip(issues["session_id"], issues["check"], strict=True))
    assert ("s2", "role_not_alternating") in found
    assert ("s2", "ends_before_start") in found
    assert not any(sid == "s1" for sid, _ in found)


def test_integrity_issues_turn_numbering_and_empty_text(records):
    records[0]["conversation"][1]["turn"] = 5
    records[0]["conversation"][1]["text"] = "  "
    issues = eda.integrity_issues(sessions_frame(records), turns_frame(records))
    checks = set(issues[issues.session_id == "s1"]["check"])
    assert {"turn_numbering", "empty_text"} <= checks


def test_cross_session_repeats(frames):
    _, turns = frames
    rep = eda.cross_session_repeats(turns, "assistant")
    assert rep["text"].tolist() == ["I'm sorry to hear that."]
    assert rep.iloc[0]["sessions"] == "s1,s2"


def test_opening_phrases(frames):
    _, turns = frames
    op = eda.opening_phrases(turns, "assistant", n_words=2)
    assert op.iloc[0].to_dict() == {"opening": "i m", "count": 2}


def test_categorical_counts(frames):
    sessions, _ = frames
    c = eda.categorical_counts(sessions, ["session_ended_by"])
    assert set(c["value"]) == {"completed", "user_closed"}
    assert isinstance(c, pd.DataFrame)


def test_session_features_word_ratio_and_timing(frames):
    sessions, turns = frames
    f = eda.session_features(sessions, turns).set_index("session_id")
    # s1: "I'm sorry to hear that." -> I, m, sorry, to, hear, that = 6 words; user has 4
    assert f.loc["s1", "assistant_words"] == 6
    assert f.loc["s1", "assistant_to_user_words"] == pytest.approx(6 / 4)
    assert f.loc["s1", "seconds_per_turn"] == pytest.approx(300.0)
    assert bool(f.loc["s1", "starts_on_hour"])


def test_session_features_zero_user_words_gives_nan_ratio(records):
    records[0]["conversation"][0]["text"] = "..."
    f = eda.session_features(sessions_frame(records), turns_frame(records))
    assert pd.isna(f.set_index("session_id").loc["s1", "assistant_to_user_words"])


def _checks(records):
    issues = eda.integrity_issues(sessions_frame(records), turns_frame(records))
    return set(zip(issues["session_id"], issues["check"], strict=True))


def test_integrity_duplicate_session_id(records):
    records[1]["session_id"] = "s1"
    assert ("s1", "duplicate_session_id") in _checks(records)


def test_integrity_no_turns(records):
    records[0]["conversation"] = []
    assert ("s1", "no_turns") in _checks(records)


def test_integrity_unknown_role_and_first_turn(records):
    records[0]["conversation"][0]["role"] = "system"
    found = _checks(records)
    assert ("s1", "unknown_role") in found
    assert ("s1", "first_turn_not_user") in found


def test_integrity_null_text_is_empty(records):
    records[0]["conversation"][1]["text"] = None
    assert ("s1", "empty_text") in _checks(records)


def test_integrity_repeated_text_in_session(records):
    records[0]["conversation"][1]["text"] = records[0]["conversation"][0]["text"]
    assert ("s1", "repeated_text_in_session") in _checks(records)


def test_integrity_missing_timestamp(records):
    records[0]["session_meta"]["ended_at"] = None
    assert ("s1", "missing_timestamp") in _checks(records)


def test_timing_summary_detects_constant_pace(frames):
    sessions, turns = frames
    s = eda.timing_summary(eda.session_features(sessions, turns)).set_index("metric")["value"]
    assert s["n_sessions"] == 2
    assert s["n_starts_on_hour"] == 2
    # s1: 600 s / 2 turns = 300; s2: -60 s / 3 turns = -20 -> two distinct paces
    assert s["n_distinct_seconds_per_turn"] == 2


def test_ending_crosstab(frames):
    sessions, turns = frames
    ct = eda.ending_crosstab(eda.session_features(sessions, turns))
    assert ct.to_dict("records") == [
        {"last_role": "assistant", "session_ended_by": "completed", "n_sessions": 1},
        {"last_role": "assistant", "session_ended_by": "user_closed", "n_sessions": 1},
    ]


def test_medians_by(frames):
    sessions, turns = frames
    m = eda.medians_by(eda.session_features(sessions, turns), "session_ended_by", ["n_turns"])
    assert m.set_index("session_ended_by").loc["user_closed", "n_turns"] == 3
    assert m["n_sessions"].tolist() == [1, 1]


def test_non_ascii_turns(frames):
    _, turns = frames
    turns.loc[2, "text"] = "você"
    turns = turns.assign(non_ascii_share=turns["text"].map(eda.non_ascii_share))
    hits = eda.non_ascii_turns(turns)
    assert hits["text"].tolist() == ["você"]
