import pandas as pd

from mama_analysis.cli import main, run_eda


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
