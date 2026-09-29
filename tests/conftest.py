import json

import pytest


def _session(
    sid,
    convo,
    ended_by="completed",
    start="2026-05-21T01:00:00+00:00",
    end="2026-05-21T01:10:00+00:00",
):
    return {
        "session_id": sid,
        "user_meta": {"gender": "female", "age_group": "35-44", "country": "UK", "disease": "ibs"},
        "session_meta": {"started_at": start, "ended_at": end, "session_ended_by": ended_by},
        "conversation": [
            {"turn": i + 1, "role": role, "text": text} for i, (role, text) in enumerate(convo)
        ],
    }


@pytest.fixture
def records():
    return [
        _session(
            "s1",
            [("user", "My gut hurts today"), ("assistant", "I'm sorry to hear that.")],
        ),
        _session(
            "s2",
            [
                ("user", "Hola, me duele"),
                ("assistant", "I'm sorry to hear that."),
                ("assistant", "Can you tell me more?"),
            ],
            ended_by="user_closed",
            start="2026-05-21T02:00:00+00:00",
            end="2026-05-21T01:59:00+00:00",
        ),
    ]


@pytest.fixture
def data_file(tmp_path, records):
    path = tmp_path / "conversations.json"
    path.write_text(json.dumps(records))
    return path
