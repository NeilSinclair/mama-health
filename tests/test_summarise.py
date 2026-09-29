import asyncio

from fakes import FakeLabeller, fake_summary

from mama_analysis.cache import read_entries
from mama_analysis.labellers import Prompt
from mama_analysis.summarise import (
    merge_deterministic,
    render_conversation,
    summarise_all,
    summary_dir,
)

PROMPT = Prompt("summary_v1", "SYSTEM", "sha")


def test_render_conversation(records):
    text = render_conversation(records[0])
    assert text.splitlines() == [
        "session_id: s1",
        "[t1] user: My gut hurts today",
        "[t2] assistant: I'm sorry to hear that.",
    ]
    # Metadata is copied deterministically elsewhere, never shown to the model.
    assert "ibs" not in text and "UK" not in text


def test_summary_dir(tmp_path):
    assert summary_dir(tmp_path, "haiku") == tmp_path / "summaries" / "haiku"


def test_summarise_all_warms_then_writes_every_session(records, tmp_path):
    records = records + [dict(records[0], session_id=f"x{i}") for i in range(4)]
    lab = FakeLabeller(lambda schema, user: fake_summary(summary=user.splitlines()[0]))
    entries = asyncio.run(summarise_all(records, lab, PROMPT, tmp_path, concurrency=2))

    assert set(entries) == {r["session_id"] for r in records}
    assert entries["s2"].output["summary"] == "session_id: s2"
    # Warm-up call finishes before any other call starts; later calls respect the bound.
    assert lab.events[0][0] == "start" and lab.events[1][0] == "end"
    assert lab.max_active == 2
    assert read_entries(tmp_path) == entries
    assert entries["s1"].prompt_sha256 == "sha"


def test_merge_deterministic_ignores_llm_for_metadata(records):
    s = merge_deterministic(records[1], fake_summary())
    assert (s.session_id, s.disease, s.country, s.age_group, s.gender) == (
        "s2",
        "ibs",
        "UK",
        "35-44",
        "female",
    )
    assert s.session_ended_by == "user_closed"
    assert s.main_topics == ["gut pain"]
