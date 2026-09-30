from pathlib import Path

import pandas as pd
import pytest
from fakes import FakeLabeller, fake_respond

from mama_analysis import cli
from mama_analysis.cli import main, run_eda, run_summaries

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def no_api(monkeypatch):
    def refuse(version):
        raise AssertionError("default pipeline run must not construct an API client")

    monkeypatch.setattr(cli, "make_labeller", refuse)


@pytest.fixture
def fake_api(monkeypatch):
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.setattr(
        cli, "make_labeller", lambda version: FakeLabeller(fake_respond, version=version)
    )


def test_run_eda_writes_tables(data_file, tmp_path):
    written = run_eda(data_file, tmp_path / "out")
    assert set(written) >= {"session_features", "integrity_issues", "turns"}
    for path in written.values():
        assert path.exists()
    feats = pd.read_csv(written["session_features"])
    assert len(feats) == 2


def test_main_runs_without_labels_or_api(data_file, tmp_path, capsys, no_api):
    main(["--data", str(data_file), "--out", str(tmp_path / "out"), "--labels", str(tmp_path)])
    out = capsys.readouterr().out
    assert "wrote session_features" in out
    assert "no complete cached labels for gpt_luna" in out
    assert (tmp_path / "out" / "explorer.html").exists()
    assert not (tmp_path / "out" / "summaries").exists()


def test_relabel_then_build_from_cache(data_file, tmp_path, capsys, fake_api):
    labels, out = tmp_path / "labels", tmp_path / "out"
    main(
        [
            "--data",
            str(data_file),
            "--out",
            str(out),
            "--labels",
            str(labels),
            "--relabel",
            "gpt_luna",
        ]
    )
    assert "relabelling gpt_luna" in capsys.readouterr().out
    assert sorted(p.name for p in (labels / "summaries" / "gpt_luna").iterdir()) == [
        "s1.json",
        "s2.json",
    ]
    summaries = pd.read_csv(out / "summaries" / "gpt_luna" / "summaries.csv")
    assert summaries["session_id"].tolist() == ["s1", "s2"]
    assert (out / "summaries" / "gpt_luna" / "label_counts.csv").exists()


def test_run_summaries_warns_on_stale_cache(data_file, tmp_path, capsys, fake_api, monkeypatch):
    labels = tmp_path / "labels"
    cli.relabel("gpt_luna", data_file, labels)
    capsys.readouterr()
    monkeypatch.setitem(
        cli.MODELS, "gpt_luna", cli.MODELS["gpt_luna"].__class__("openai", "new", "G")
    )
    run_summaries(data_file, labels, tmp_path / "out")
    assert "gpt_luna: 5 cached labels predate" in capsys.readouterr().out


def test_committed_outputs_match_fresh_run(tmp_path):
    """Guard against committed outputs drifting from what the pipeline produces."""
    data = REPO_ROOT / "data" / "conversations.json"
    written = {f"eda/{k}": v for k, v in run_eda(data, tmp_path).items()}
    written |= run_summaries(data, REPO_ROOT / "data" / "labels", tmp_path)
    for name, path in written.items():
        committed_file = REPO_ROOT / "outputs" / path.relative_to(tmp_path)
        assert committed_file.exists(), f"{committed_file} not committed; rerun the pipeline"
        assert path.read_bytes() == committed_file.read_bytes(), f"{name} is stale"


def test_remap_rebuilds_mappings_from_cached_summaries(data_file, tmp_path, capsys, fake_api):
    labels = tmp_path / "labels"
    cli.relabel("gpt_luna", data_file, labels)
    before = (labels / "summaries" / "gpt_luna" / "s1.json").read_text()
    (labels / "mappings" / "gpt_luna" / "reason_for_conversation.json").unlink()
    main(
        [
            "--data",
            str(data_file),
            "--out",
            str(tmp_path / "out"),
            "--labels",
            str(labels),
            "--remap",
            "gpt_luna",
        ]
    )
    assert "re-consolidating gpt_luna" in capsys.readouterr().out
    assert (labels / "mappings" / "gpt_luna" / "reason_for_conversation.json").exists()
    assert (labels / "summaries" / "gpt_luna" / "s1.json").read_text() == before


def test_remap_without_summaries_exits(tmp_path, fake_api):
    with pytest.raises(SystemExit, match="run --relabel gpt_luna first"):
        cli.remap("gpt_luna", tmp_path)


def test_relabel_closes_client_even_on_failure(data_file, tmp_path, monkeypatch):
    made = []

    def broken(version):
        def respond(schema, user):
            raise RuntimeError("api down")

        lab = FakeLabeller(respond, version=version)
        made.append(lab)
        return lab

    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.setattr(cli, "make_labeller", broken)
    with pytest.raises(RuntimeError, match="api down"):
        cli.relabel("gpt_luna", data_file, tmp_path)
    assert made[0].closed


def test_mapping_that_misses_new_summary_labels_fails_clearly(data_file, tmp_path, fake_api):
    """A relabel that dies during consolidation leaves new summaries beside old mappings."""
    import json

    labels = tmp_path / "labels"
    cli.relabel("gpt_luna", data_file, labels)
    path = labels / "summaries" / "gpt_luna" / "s1.json"
    entry = json.loads(path.read_text())
    entry["output"]["main_topics"] = [
        {"topic": "a label no mapping has seen", "reason": "r", "relevance": "strong"}
    ]
    path.write_text(json.dumps(entry))
    with pytest.raises(ValueError, match="run: uv run mama-pipeline --remap gpt_luna"):
        run_summaries(data_file, labels, tmp_path / "out")


def test_old_schema_cache_fails_with_relabel_hint(data_file, tmp_path, fake_api):
    import json

    labels = tmp_path / "labels"
    cli.relabel("gpt_luna", data_file, labels)
    path = labels / "summaries" / "gpt_luna" / "s1.json"
    entry = json.loads(path.read_text())
    entry["output"]["pain_points"] = entry["output"].pop("conversation_pain_points")
    path.write_text(json.dumps(entry))
    with pytest.raises(ValueError, match="run: uv run mama-pipeline --relabel gpt_luna"):
        run_summaries(data_file, labels, tmp_path / "out")
