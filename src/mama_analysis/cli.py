"""Pipeline entry point: `uv run mama-pipeline`."""

from __future__ import annotations

import argparse
from pathlib import Path

from mama_analysis import eda
from mama_analysis.data import DEFAULT_DATA_PATH, load_sessions, sessions_frame, turns_frame

META_COLUMNS = ["gender", "age_group", "country", "disease", "session_ended_by"]


def run_eda(data_path: Path, out_dir: Path) -> dict[str, Path]:
    """Compute EDA tables and write them as CSVs.

    Args:
        data_path: Path to the conversations JSON file.
        out_dir: Output root; tables are written to ``out_dir / "eda"``.

    Returns:
        Mapping from table name to the CSV path written.
    """
    records = load_sessions(data_path)
    sessions = sessions_frame(records)
    turns = turns_frame(records)
    turns = turns.assign(
        words=turns["text"].map(eda.word_count),
        non_ascii_share=turns["text"].map(eda.non_ascii_share),
    )

    features = eda.session_features(sessions, turns)
    volume_cols = ["n_turns", "user_words", "assistant_words", "assistant_to_user_words"]

    target = out_dir / "eda"
    target.mkdir(parents=True, exist_ok=True)
    tables = {
        "session_features": features,
        "timing_summary": eda.timing_summary(features),
        "ending_crosstab": eda.ending_crosstab(features),
        "medians_by_end_state": eda.medians_by(features, "session_ended_by", volume_cols),
        "non_ascii_turns": eda.non_ascii_turns(turns),
        "metadata_counts": eda.categorical_counts(sessions, META_COLUMNS),
        "integrity_issues": eda.integrity_issues(sessions, turns),
        "assistant_repeats": eda.cross_session_repeats(turns, "assistant"),
        "user_repeats": eda.cross_session_repeats(turns, "user"),
        "assistant_openings": eda.opening_phrases(turns, "assistant"),
        "turns": turns,
    }
    written = {}
    for name, df in tables.items():
        path = target / f"{name}.csv"
        df.to_csv(path, index=False)
        written[name] = path
    return written


def main(argv: list[str] | None = None) -> None:
    """Run the pipeline from the command line.

    Args:
        argv: Command-line arguments; defaults to ``sys.argv[1:]``.
    """
    parser = argparse.ArgumentParser(description="mama health conversation analysis pipeline")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--out", type=Path, default=Path("outputs"))
    args = parser.parse_args(argv)

    written = run_eda(args.data, args.out)
    for name, path in written.items():
        print(f"wrote {name}: {path}")


if __name__ == "__main__":
    main()
