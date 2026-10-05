# CLAUDE.md

Guidance for Claude sessions working in this repo. Read this, [decisions.md](docs/decisions.md) and [NOTES.md](docs/NOTES.md) at the start of every session.


## What this project is

A take-home challenge for a **Senior Data Scientist** role at mama health (full brief: [docs/project_description.md](docs/project_description.md)). mama health runs a chatbot companion for people with chronic disease. We analyse 50 synthetic bot–patient conversations and advise product leadership (CAIO / VP Product).

The audience for the final output is product leadership, not data scientists. The brief rewards judgement over volume: what we *chose* to measure, what we *noticed* that wasn't asked, what we *refused to claim*, and one actionable recommendation.

## Deliverables and hard constraints

| Deliverable | Constraint |
|---|---|
| `MEMO.md` (primary) | ≤ 3 pages. Addressed to CAIO / VP Product. Must cover the 3 anchors below, plus anything else worth their attention. |
| Pipeline (`src/`) | Runnable end-to-end from a fresh clone in **≤ 3 shell commands**, written exactly in `README.md`. |
| `README.md` | Exact run commands; how to supply an API key to regenerate LLM labels. |
| `docs/NOTES.md` | AI usage (where used, where overridden, and enough detail to reproduce the workflow), actual hours worked, and anomalies noticed in the brief or data. |
| `data/conversations.json` | Keep at this path. **Never modify it.** |

Memo anchors:
1. **Is the bot working?** Define "working", defend the definition, report against it, and say what we *can't* claim.
2. **What should product build next?** Exactly **one** specific recommendation, with its evidence and what evidence would change our mind.
3. **Five most interesting conversations**, by a stated definition of "interesting". One paragraph each.

**Traceability rule:** every substantive claim in `MEMO.md` must point to a specific pipeline output (a file in `outputs/`, a table, a chart) that the pipeline reproduces. If a number isn't produced by code, it doesn't go in the memo.

## Data

`data/conversations.json` is a list of 50 records:

```
session_id, user_meta{gender, age_group, country, disease},
session_meta{started_at, ended_at, session_ended_by},
conversation[{turn, role: user|assistant, text}]
```

- `session_ended_by` records *how* a session ended, not *why*. The brief lists `completed | user_closed | timeout | user_asked_for_human`, but the data only contains `completed` and `user_closed` (see decisions.md / EDA).
- The data is synthetic and "not clean" on purpose. Treat oddities as findings and write them down; don't silently clean them away.
- n = 50. Be disciplined about what that sample can support. Prefer counts and concrete examples over percentages and significance tests on tiny subgroups.

## Repo layout

```
CLAUDE.md            this file
memo.html            the memo rendered as a page by the pipeline
MEMO.md              the memo (primary deliverable)
README.md            how to run
docs/                brief, decisions.md (append-only decision log), NOTES.md (AI-usage log,
                     hours log, anomalies), plus discussion docs as .html
data/conversations.json   raw data (read-only)
data/labels/         cached LLM labels (committed; see LLM labelling)
src/mama_analysis/   pipeline package
tests/               pytest tests, mirroring src/
outputs/             generated tables/charts the memo cites
```

## Commands

```bash
uv sync                      # install deps (incl. dev group)
uv run pytest                # run tests
uv run ruff check . && uv run ruff format --check .   # lint / format check
uv run mama-pipeline         # run the pipeline end-to-end (uses cached labels)
```

Use `uv` for everything: `uv add <pkg>` / `uv add --dev <pkg>`. Don't use pip, and don't edit dependency lists by hand. Commit `uv.lock`.

## LLM labelling

- Qualitative measures (e.g. safety handling, emotional register) may be labelled by an LLM against an explicit, versioned rubric kept in the repo.
- **Labels are cached in `data/labels/` and committed.** By default the pipeline reads the cache and makes **no API calls**, so reviewers can reproduce every number without a key.
- A reviewer can regenerate labels with their own key: copy `.env.example` to `.env`, set `ANTHROPIC_API_KEY`, and run the pipeline with the relabel flag (exact commands in `README.md`). Never commit `.env` or any key.
- Cache entries must record the model ID, prompt/rubric version (or hash) and a timestamp, so stale labels can be detected.
- The labelling model is Claude Sonnet 5.5 (`claude-sonnet-5-5`), which replaced OpenAI GPT Luna after a stability and gold-set comparison (D-054, D-055). GPT Luna's labels are kept as a second version for comparison. Pin the exact model IDs in `src/mama_analysis/config.py`.
- **Tests must never call the API.** Mock the client or use fixture labels.
- Spot-check LLM labels by hand. Where we disagree with the model, record it in `docs/NOTES.md` (this counts as "where we overrode AI").

## Workflow rules (mandatory)

1. **Code review before every push and every PR merge.** Run the **`code-reviewer`** agent (`.claude/agents/code-reviewer.md`) on the diff before `git push` and before merging any PR. Fix or explicitly respond to its findings first. If the agent is missing or can't run, stop and tell the user rather than skipping the review.
2. **Tests for all code.** Every module in `src/` gets tests in `tests/`. New or changed behaviour ships with tests in the same change. `uv run pytest` must pass before any commit. Keep tests fast and offline; use small hand-built fixtures rather than the full dataset where possible.
3. **Log decisions in [decisions.md](docs/decisions.md).** Any choice about scope, methodology, definitions (e.g. what "working" means), metrics, tooling, or what we refuse to claim gets a dated entry: decision, rationale, alternatives considered, and what would change it. Append; don't rewrite history. If a decision is reversed, add a new entry that supersedes the old one.
4. **Keep `docs/NOTES.md` current.** Log AI usage and overrides as they happen, not retrospectively. Log hours per session.
5. **Git.** Don't commit to `main` directly; work on a branch and open a PR. Only commit or push when the user asks.
6. **Discussion documents are HTML.** Anything written for the user and Claude to discuss (EDA write-ups, findings, design notes, option comparisons) goes in `docs/` as a self-contained `.html` file: inline CSS, readable in light and dark mode, no external dependencies beyond fonts. Submission files stay Markdown: `MEMO.md`, `README.md`, `NOTES.md`, `decisions.md`, `CLAUDE.md`.
7. Put shared, reusable data access and helpers in `src/mama_analysis/`. Exploratory one-offs are fine in `scripts/` or notebooks, but any number that reaches the memo must come from tested pipeline code.

## Style

- Python ≥ 3.12, type hints, small pure functions, ruff for lint and format.
- **Google-style docstrings** on every public module, class and function in `src/` (`Args:`, `Returns:`, `Raises:` sections where applicable). Enforced by ruff's pydocstyle rules (`D`, `convention = "google"`). Tests are exempt.
- Outputs are deterministic: fixed seeds, sorted keys, stable file names.
- Write memo prose for executives: short, concrete, with evidence cited inline (e.g. `[outputs/safety_table.csv]`, `session s017 turn 9`).


## Behavioral Guidelines

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
