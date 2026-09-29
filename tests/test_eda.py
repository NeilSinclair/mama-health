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
