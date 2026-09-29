from pathlib import Path

import pandas as pd

from mama_analysis.cli import main, run_eda

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_run_eda_writes_tables(data_file, tmp_path):
    written = run_eda(data_file, tmp_path / "out")
    assert set(written) >= {"session_features", "integrity_issues", "turns"}
    for path in written.values():
        assert path.exists()
    feats = pd.read_csv(written["session_features"])
    assert len(feats) == 2


def test_main_runs(data_file, tmp_path, capsys):
    main(["--data", str(data_file), "--out", str(tmp_path / "out")])
    assert "wrote session_features" in capsys.readouterr().out


def test_committed_outputs_match_fresh_run(tmp_path):
    """Guard against committed outputs drifting from what the pipeline produces."""
    committed = REPO_ROOT / "outputs" / "eda"
    written = run_eda(REPO_ROOT / "data" / "conversations.json", tmp_path)
    for name, path in written.items():
        committed_file = committed / path.name
        assert committed_file.exists(), f"{committed_file} not committed; rerun the pipeline"
        assert path.read_bytes() == committed_file.read_bytes(), f"{name} is stale"
