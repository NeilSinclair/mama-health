# Decision log

Append-only. Each entry records the decision, its rationale, the alternatives considered, and what would change it. To reverse a decision, add a new entry marked "Supersedes D-xxx"; don't edit the old one.

---

### D-001 — Cache LLM labels in the repo; allow reviewers to regenerate with their own key
- **Date:** 2026-09-29
- **Decision:** Qualitative labels produced by an LLM are cached in `data/labels/` and committed. The pipeline reads the cache by default, with no API calls. Reviewers can put their own `ANTHROPIC_API_KEY` in `.env` and rerun labelling.
- **Rationale:** The brief requires reviewers to reproduce every number. Live LLM calls need a key, cost money, and aren't deterministic. Caching makes the default path reproducible, and the relabel path keeps it honest.
- **Alternatives:** (a) Deterministic methods only (keywords, heuristics): reproducible but weak on judgement-heavy measures like safety and emotional register. (b) Live LLM calls only: not reproducible without a key.
- **Would change if:** The reviewers said they won't run anything requiring a key *and* distrust cached labels. In that case we'd add a heuristic baseline alongside the LLM labels.

### D-002 — Use uv for environment and dependency management
- **Date:** 2026-09-29
- **Decision:** `uv` with `pyproject.toml` and a committed `uv.lock`. Python pinned via `.python-version`.
- **Rationale:** User preference. It also gives a one-command, locked, reproducible setup (`uv sync`), which serves the brief's "≤ 3 commands" constraint.
- **Alternatives:** pip + venv + requirements.txt; conda.

### D-003 — Maintain a decision log (this file)
- **Date:** 2026-09-29
- **Decision:** Every scope, methodology, definition, metric and tooling decision is logged here.
- **Rationale:** The brief grades *what we chose* to measure and *what we refused to claim*. A running log makes those choices explicit and feeds the memo and NOTES.md directly.

### D-004 — Mandatory code review by an agent before every push and PR merge
- **Date:** 2026-09-29
- **Decision:** A code-review agent (to be created by the user in `.claude/agents/`) must review the diff before every `git push` and every PR merge. The rule is recorded in CLAUDE.md.
- **Rationale:** Correctness of the pipeline underpins every claim in the memo, and the brief discounts any claim we can't reproduce.

### D-005 — Tests required for all code
- **Date:** 2026-09-29
- **Decision:** Every module in `src/` has pytest tests. Tests run offline and never call the LLM API.
- **Rationale:** Reproducibility and trust in the numbers. Offline tests keep CI and reviewer runs free and deterministic.

### D-006 — Package layout: `src/mama_analysis`, plain Python modules, single CLI entry point
- **Date:** 2026-09-29
- **Decision:** The pipeline is an installable package (`src/mama_analysis`) exposed as `uv run mama-pipeline`. Numbers in the memo come from package code, not notebooks.
- **Rationale:** Notebooks are hard to test and to run headless. A single entry point keeps the reviewer path to `git clone` → `uv sync` → `uv run mama-pipeline`.
- **Alternatives:** Notebook-driven analysis; Makefile orchestration.
- **Would change if:** The user prefers notebooks for narrative exploration. That's fine for EDA, as long as memo numbers still come from the package.

### D-007 — Log AI usage and hours in NOTES.md as we go
- **Date:** 2026-09-29
- **Decision:** `NOTES.md` holds a running AI-usage/override log, an hours log and an anomalies list.
- **Rationale:** The brief explicitly asks for these and says it treats hours as data. A retrospective reconstruction would be less accurate.

### D-008 — Sequence: EDA before the design document
- **Date:** 2026-09-29
- **Decision:** Start with exploratory data analysis. The user will then write a design document informed by it, before the main pipeline is built.
- **Rationale:** What "working" means, and which measures matter, should be grounded in what the data actually contains.

### D-009 — Don't use timestamps as a behavioural signal
- **Date:** 2026-09-29
- **Decision:** Session duration, time of day and turn timing are excluded from any engagement or "working" metric.
- **Rationale:** EDA shows every session starts exactly on the hour and `duration = 0.7 min × n_turns` for all 50 sessions. The timestamps are generated, so they carry no information beyond turn count. They're UTC with no user timezone, so local time of day isn't recoverable either. See docs/eda.html.
- **Would change if:** We got real timestamps, or learned they encode something real (e.g. reply latency).

### D-010 — Treat `session_ended_by` as a weak signal, not the outcome
- **Date:** 2026-09-29
- **Decision:** `session_ended_by` won't be used alone as the success/outcome variable. Conversation endings are judged from the text.
- **Rationale:** Only 2 of the 4 documented values occur. 13 sessions end on a user turn. Some `completed` sessions end with a disengaged-sounding user (s046) and some `user_closed` ones end after a clear bot failure (s030). The label is *how*, not *why*, as the brief itself warns.

### D-011 — Commit generated outputs
- **Date:** 2026-09-29
- **Decision:** `outputs/` is committed alongside code.
- **Rationale:** The memo cites files in `outputs/`, so a reader can follow citations without running anything. The pipeline regenerates them identically, which checks reproducibility.
- **Alternatives:** gitignore `outputs/` and have reviewers generate them.

### D-012 — Discussion documents are written as HTML
- **Date:** 2026-09-29
- **Decision:** Documents for the user and Claude to discuss (EDA write-ups, findings, design notes, comparisons) go in `docs/` as self-contained `.html` files. Submission files (`MEMO.md`, `README.md`, `NOTES.md`, `decisions.md`, `CLAUDE.md`) stay Markdown. `docs/eda.md` was converted to `docs/eda.html`.
- **Rationale:** User preference: HTML reads better for discussion (cards, tables, callouts). The brief specifies Markdown or PDF for the memo, so submission files keep that format.
- **Would change if:** A discussion doc gets promoted into the submission. It would then be rewritten as Markdown.

### D-013 — Google-style docstrings, enforced by ruff
- **Date:** 2026-09-29
- **Decision:** Every public module, class and function in `src/` has a Google-style docstring (`Args:` / `Returns:` / `Raises:`). Ruff's `D` rules run with `convention = "google"`; `tests/` is exempt.
- **Rationale:** User preference. Consistent docstrings make the pipeline easier for reviewers to follow, and lint enforcement stops drift.
- **Note:** Ruff flags missing docstrings and malformed sections but not missing `Args:` sections, so completeness still relies on review.
