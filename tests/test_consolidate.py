import asyncio

import pytest
from fakes import FakeLabeller, fake_respond, fake_summary

from mama_analysis.consolidate import (
    FIELDS,
    apply_mapping,
    consolidate_all,
    mapping_dir,
    raw_labels,
    render_labels,
    validate_mapping,
)
from mama_analysis.labellers import Prompt
from mama_analysis.schemas import LabelMapping, LabelPair

PROMPT = Prompt("consolidate_v1", "SYSTEM", "sha")


def _mapping(**pairs):
    return LabelMapping(mappings=[LabelPair(raw=r, canonical=c) for r, c in pairs.items()])


def test_raw_labels_handles_list_and_scalar_fields():
    sums = [fake_summary(main_topics=["b", "a"]), fake_summary(main_topics=["a"])]
    assert raw_labels(sums, "main_topics") == ["a", "b"]
    assert raw_labels(sums, "end_reason") == ["need met"]


def test_render_labels():
    assert render_labels("end_reason", ["x", "y"]) == "field: end_reason\nlabels:\nx\ny"


def test_validate_mapping_ok_and_sorted():
    assert validate_mapping(["b", "a"], _mapping(b="B", a="A")) == {"a": "A", "b": "B"}


def test_validate_mapping_rejects_unmapped():
    with pytest.raises(ValueError, match="unmapped"):
        validate_mapping(["a", "b"], _mapping(a="A"))


def test_validate_mapping_rejects_empty_and_conflicts():
    with pytest.raises(ValueError, match="empty"):
        validate_mapping(["a"], _mapping(a="  "))
    conflict = LabelMapping(
        mappings=[LabelPair(raw="a", canonical="X"), LabelPair(raw="a", canonical="Y")]
    )
    with pytest.raises(ValueError, match="conflicting"):
        validate_mapping(["a"], conflict)


def test_validate_mapping_drops_extras_with_warning():
    with pytest.warns(UserWarning, match="dropped 1"):
        assert validate_mapping(["a"], _mapping(a="A", zzz="Z")) == {"a": "A"}


def test_apply_mapping_keeps_unique_labels_and_dedupes():
    m = {"insomnia": "insomnia", "trouble sleeping": "insomnia", "rare thing": "rare thing"}
    assert apply_mapping(["trouble sleeping", "rare thing", "insomnia"], m) == [
        "insomnia",
        "rare thing",
    ]
    assert apply_mapping("trouble sleeping", m) == "insomnia"


def test_consolidate_all_caches_one_mapping_per_field(tmp_path):
    lab = FakeLabeller(fake_respond)
    sums = [fake_summary(main_topics=["Sleep", "gut pain"]), fake_summary()]
    entries = asyncio.run(consolidate_all(sums, lab, PROMPT, tmp_path))
    assert set(entries) == set(FIELDS)
    assert entries["main_topics"].output == {"mapping": {"Sleep": "sleep", "gut pain": "gut pain"}}
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(f"{f}.json" for f in FIELDS)


def test_consolidate_all_retries_then_fails(tmp_path):
    lab = FakeLabeller(lambda schema, user: LabelMapping(mappings=[]))
    with pytest.raises(ValueError, match="unmapped"):
        asyncio.run(consolidate_all([fake_summary()], lab, PROMPT, tmp_path))
    starts = [e for e in lab.events if e[0] == "start"]
    # The warm-up field fails after 3 attempts, before other fields are sent.
    assert len(starts) == 3


def test_consolidate_all_recovers_on_retry(tmp_path):
    calls = {"n": 0}

    def flaky(schema, user):
        calls["n"] += 1
        return LabelMapping(mappings=[]) if calls["n"] == 1 else fake_respond(schema, user)

    entries = asyncio.run(consolidate_all([fake_summary()], FakeLabeller(flaky), PROMPT, tmp_path))
    assert set(entries) == set(FIELDS)


def test_mapping_dir(tmp_path):
    assert mapping_dir(tmp_path, "haiku") == tmp_path / "mappings" / "haiku"


def test_consolidate_all_records_usage_of_failed_attempts(tmp_path):
    calls = {"n": 0}

    def flaky(schema, user):
        calls["n"] += 1
        return LabelMapping(mappings=[]) if calls["n"] == 1 else fake_respond(schema, user)

    entries = asyncio.run(consolidate_all([fake_summary()], FakeLabeller(flaky), PROMPT, tmp_path))
    # FakeLabeller reports 10 input tokens per call; the warm-up field took two attempts.
    assert entries[FIELDS[0]].usage.input_tokens == 20
    assert entries[FIELDS[1]].usage.input_tokens == 10
