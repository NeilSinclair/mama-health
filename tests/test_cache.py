import asyncio

from fakes import FakeLabeller, fake_respond, fake_summary

from mama_analysis.cache import (
    make_entry,
    read_entries,
    stale_keys,
    warm_then_parallel,
    write_entry,
)
from mama_analysis.config import ModelSpec
from mama_analysis.labellers import Prompt
from mama_analysis.schemas import Usage

PROMPT = Prompt("summary_v1", "text", "abc")


def _entry(model_id="fake-model", prompt=PROMPT):
    lab = FakeLabeller(fake_respond, model_id=model_id)
    return make_entry(lab, prompt, Usage(input_tokens=3), fake_summary())


def test_make_entry_records_provenance():
    e = _entry()
    assert (e.version, e.provider, e.model_id) == ("fake", "openai", "fake-model")
    assert (e.prompt_version, e.prompt_sha256) == ("summary_v1", "abc")
    assert e.created_at.endswith("+00:00")
    assert e.usage.input_tokens == 3
    assert e.output["summary"] == "User asked about gut pain."


def test_write_and_read_round_trip(tmp_path):
    e = _entry()
    write_entry(e, tmp_path / "x" / "s1.json")
    text = (tmp_path / "x" / "s1.json").read_text()
    assert text.endswith("\n") and '"created_at"' in text
    assert read_entries(tmp_path / "x") == {"s1": e}


def test_read_entries_missing_dir(tmp_path):
    assert read_entries(tmp_path / "nope") == {}


def test_stale_keys_flags_model_or_prompt_change():
    spec = ModelSpec("openai", "fake-model", "F")
    entries = {
        "ok": _entry(),
        "old_model": _entry(model_id="older"),
        "old_prompt": _entry(prompt=Prompt("summary_v1", "old", "zzz")),
    }
    assert stale_keys(entries, spec, PROMPT) == ["old_model", "old_prompt"]


def test_warm_then_parallel_runs_first_call_alone_then_bounded():
    events = []
    active = {"now": 0, "max": 0}

    async def call(i):
        active["now"] += 1
        active["max"] = max(active["max"], active["now"])
        events.append(("start", i))
        await asyncio.sleep(0.01)
        events.append(("end", i))
        active["now"] -= 1
        return i * 10

    out = asyncio.run(warm_then_parallel(list(range(7)), call, concurrency=3))
    assert out == [0, 10, 20, 30, 40, 50, 60]
    assert events[:2] == [("start", 0), ("end", 0)]
    assert active["max"] == 3


def test_warm_then_parallel_empty():
    async def call(_):
        raise AssertionError("should not be called")

    assert asyncio.run(warm_then_parallel([], call, concurrency=2)) == []
