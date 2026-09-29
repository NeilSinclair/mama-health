import json

import pytest

from mama_analysis.data import load_sessions, sessions_frame, turns_frame


def test_load_sessions_reads_list(data_file):
    records = load_sessions(data_file)
    assert [r["session_id"] for r in records] == ["s1", "s2"]


def test_load_sessions_rejects_non_list(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"session_id": "s1"}))
    with pytest.raises(ValueError, match="expected a list"):
        load_sessions(path)


def test_load_sessions_rejects_missing_keys(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps([{"session_id": "s1"}]))
    with pytest.raises(ValueError, match="missing keys"):
        load_sessions(path)


def test_sessions_frame_flattens_meta_and_parses_times(records):
    df = sessions_frame(records)
    assert list(df["session_id"]) == ["s1", "s2"]
    assert {"gender", "disease", "session_ended_by"} <= set(df.columns)
    assert str(df["started_at"].dt.tz) == "UTC"


def test_turns_frame_one_row_per_turn(records):
    df = turns_frame(records)
    assert len(df) == 5
    assert df[df.session_id == "s2"]["position"].tolist() == [0, 1, 2]
    assert df.iloc[0]["role"] == "user"
