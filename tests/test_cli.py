from pathlib import Path

import pandas as pd
import pytest
from fakes import FakeLabeller, fake_respond

from mama_analysis import cli
from mama_analysis.cli import main, run_eda, run_summaries

REPO_ROOT = Path(__file__).resolve().parents[1]
# Runs on fake labels skip the repo's memo draft and gold labels: both name real rows and sessions.
NO_MEMO = ("--memo", "no_such_memo.md", "--gold", "no_such_gold.csv")


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
            *NO_MEMO,
        ]
    )
    assert "relabelling gpt_luna" in capsys.readouterr().out
    assert sorted(p.name for p in (labels / "summaries" / "gpt_luna").iterdir()) == [
        "s1.json",
        "s2.json",
    ]
    summaries = pd.read_csv(out / "summaries" / "gpt_luna" / "summaries.csv")
    assert summaries["session_id"].tolist() == ["s1", "s2"]
    # The model's short reason value is shown by its display name, and kept as the raw label.
    assert summaries["reason_for_conversation"].tolist() == ["understand my condition"] * 2
    assert summaries["reason_for_conversation_raw"].tolist() == ["informational"] * 2
    assert (out / "summaries" / "gpt_luna" / "label_counts.csv").exists()
    # --relabel also labels dynamics, so every analysis table is written.
    assert sorted(p.name for p in (labels / "dynamics" / "gpt_luna").iterdir()) == [
        "s1.json",
        "s2.json",
    ]
    assert sorted(p.stem for p in (out / "analysis" / "gpt_luna").iterdir()) == [
        "ending_mismatches",
        "ending_vs_outcome",
        "friction",
        "outcome_by_disease",
        "outcome_by_reason",
        "pain_points",
        "pushbacks",
        "recovery_by_outcome",
        "sentiment_vs_outcome",
        "silent_failures",
        "topic_groups",
    ]


def test_run_summaries_warns_on_stale_cache(data_file, tmp_path, capsys, fake_api, monkeypatch):
    labels = tmp_path / "labels"
    cli.relabel("gpt_luna", data_file, labels)
    capsys.readouterr()
    monkeypatch.setitem(
        cli.MODELS, "gpt_luna", cli.MODELS["gpt_luna"].__class__("openai", "new", "G")
    )
    run_summaries(data_file, labels, tmp_path / "out")
    assert "gpt_luna: 4 cached labels predate" in capsys.readouterr().out


def test_committed_outputs_match_fresh_run(tmp_path):
    """Guard against committed outputs drifting from what the pipeline produces."""
    data = REPO_ROOT / "data" / "conversations.json"
    written = {f"eda/{k}": v for k, v in run_eda(data, tmp_path).items()}
    written |= run_summaries(
        data,
        REPO_ROOT / "data" / "labels",
        tmp_path,
        REPO_ROOT / "docs/memo.md",
        REPO_ROOT / cli.DEFAULT_GOLD_PATH,
    )
    for name, path in written.items():
        committed_file = REPO_ROOT / "outputs" / path.relative_to(tmp_path)
        assert committed_file.exists(), f"{committed_file} not committed; rerun the pipeline"
        assert path.read_bytes() == committed_file.read_bytes(), f"{name} is stale"


def test_remap_rebuilds_mappings_from_cached_summaries(data_file, tmp_path, capsys, fake_api):
    labels = tmp_path / "labels"
    cli.relabel("gpt_luna", data_file, labels)
    before = (labels / "summaries" / "gpt_luna" / "s1.json").read_text()
    (labels / "mappings" / "gpt_luna" / "conversation_pain_points.json").unlink()
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
            *NO_MEMO,
        ]
    )
    assert "re-consolidating gpt_luna" in capsys.readouterr().out
    assert (labels / "mappings" / "gpt_luna" / "conversation_pain_points.json").exists()
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
        {
            "topic": "a label no mapping has seen",
            "topic_group": "Physical symptoms",
            "reason": "r",
            "relevance": "strong",
        }
    ]
    path.write_text(json.dumps(entry))
    with pytest.raises(ValueError, match="run: uv run mama-pipeline --remap gpt_luna"):
        run_summaries(data_file, labels, tmp_path / "out")


def test_memo_page_written_only_when_draft_exists(data_file, tmp_path, fake_api):
    labels, out = tmp_path / "labels", tmp_path / "out"
    cli.relabel("gpt_luna", data_file, labels)
    assert "memo" not in run_summaries(data_file, labels, out, tmp_path / "missing.md")
    draft = tmp_path / "memo.md"
    table = pd.read_csv(out / "analysis" / "gpt_luna" / "outcome_by_reason.csv")
    reason, total = table.iloc[0][["reason_for_conversation", "total"]]
    draft.write_text(
        "# Draft\n\n<!-- memo:outcome_by_reason -->\n\n<!-- memo:breakdown -->\n\n"
        f"Prose total: {{{{ outcome_by_reason | {reason} | total }}}} conversations.\n"
    )
    written = run_summaries(data_file, labels, out, draft)
    page = written["memo"].read_text()
    assert "outputs/analysis/gpt_luna/outcome_by_reason.csv" in page
    assert 'id="bgrid"' in page
    assert f"Prose total: {total} conversations." in page


def test_outcome_check_written_only_when_gold_labels_exist(data_file, tmp_path, fake_api):
    labels, out = tmp_path / "labels", tmp_path / "out"
    cli.relabel("gpt_luna", data_file, labels)
    written = run_summaries(data_file, labels, out, gold_path=tmp_path / "missing.csv")
    assert "analysis/gpt_luna/outcome_check" not in written
    gold = tmp_path / "gold.csv"
    gold.write_text('item,session_id,human_end_reason,note\n1,s1,need met,""\n2,s2,,""\n')
    written = run_summaries(data_file, labels, out, gold_path=gold)
    check = pd.read_csv(written["analysis/gpt_luna/outcome_check"])
    assert list(check["session_id"]) == ["s1"]
    assert check["agree"].iloc[0] == (check["model_end_reason"].iloc[0] == "need met")
    counts = pd.read_csv(written["analysis/gpt_luna/outcome_check_counts"])
    assert counts["total"].sum() == 1


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


def test_missing_dynamics_skips_only_those_tables(data_file, tmp_path, capsys, fake_api):
    import shutil

    labels, out = tmp_path / "labels", tmp_path / "out"
    cli.relabel("gpt_luna", data_file, labels)
    shutil.rmtree(labels / "dynamics")
    capsys.readouterr()
    run_summaries(data_file, labels, out)
    assert "no complete cached dynamics for gpt_luna" in capsys.readouterr().out
    assert sorted(p.stem for p in (out / "analysis" / "gpt_luna").iterdir()) == [
        "ending_mismatches",
        "ending_vs_outcome",
        "outcome_by_disease",
        "outcome_by_reason",
        "pain_points",
        "topic_groups",
    ]


def test_dynamics_flag_relabels_only_dynamics(data_file, tmp_path, capsys, fake_api):
    labels = tmp_path / "labels"
    cli.relabel("gpt_luna", data_file, labels)
    summary = (labels / "summaries" / "gpt_luna" / "s1.json").read_text()
    (labels / "dynamics" / "gpt_luna" / "s1.json").unlink()
    args = ["--data", str(data_file), "--out", str(tmp_path / "out"), "--labels", str(labels)]
    main([*args, "--dynamics", "gpt_luna", *NO_MEMO])
    assert "labelling gpt_luna conversation dynamics" in capsys.readouterr().out
    assert (labels / "dynamics" / "gpt_luna" / "s1.json").exists()
    assert (labels / "summaries" / "gpt_luna" / "s1.json").read_text() == summary


def test_old_schema_dynamics_fail_with_hint(data_file, tmp_path, fake_api):
    import json

    labels = tmp_path / "labels"
    cli.relabel("gpt_luna", data_file, labels)
    path = labels / "dynamics" / "gpt_luna" / "s1.json"
    entry = json.loads(path.read_text())
    entry["output"]["final_sentiment"] = "happy"
    path.write_text(json.dumps(entry))
    with pytest.raises(ValueError, match="run: uv run mama-pipeline --dynamics gpt_luna"):
        run_summaries(data_file, labels, tmp_path / "out")


def test_invented_dynamics_quotes_are_reported(data_file, tmp_path, capsys, fake_api):
    import json

    labels = tmp_path / "labels"
    cli.relabel("gpt_luna", data_file, labels)
    path = labels / "dynamics" / "gpt_luna" / "s1.json"
    entry = json.loads(path.read_text())
    entry["output"]["pushbacks"][0]["quote"] = "words nobody said"
    path.write_text(json.dumps(entry))
    capsys.readouterr()
    run_summaries(data_file, labels, tmp_path / "out")
    assert "gpt_luna: 1 dynamics quotes not found" in capsys.readouterr().out


def test_stale_dynamics_warn(data_file, tmp_path, capsys, fake_api, monkeypatch):
    labels = tmp_path / "labels"
    cli.relabel("gpt_luna", data_file, labels)
    capsys.readouterr()
    monkeypatch.setitem(
        cli.MODELS, "gpt_luna", cli.MODELS["gpt_luna"].__class__("openai", "new", "G")
    )
    run_summaries(data_file, labels, tmp_path / "out")
    assert "gpt_luna: 2 cached dynamics labels predate" in capsys.readouterr().out


def test_dynamics_closes_client_even_on_failure(data_file, tmp_path, monkeypatch):
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
        cli.dynamics("gpt_luna", data_file, tmp_path)
    assert made[0].closed
