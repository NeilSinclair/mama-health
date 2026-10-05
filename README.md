# mama health — conversation analysis

Take-home analysis of 50 synthetic chatbot–patient conversations for mama health. The brief is in [docs/project_description.md](docs/project_description.md).

- **The memo** is [memo.html](memo.html): open it in a browser. Its text is written in [docs/memo.md](docs/memo.md), and the pipeline fills in the tables and interactive panels.
- **The explorer** is [outputs/explorer.html](outputs/explorer.html): every conversation with its labels, filters and linked counts.
- **The tables** behind both are CSV files under [outputs/](outputs/).

All three are committed, so you can read them without running anything.

## Run it from a fresh clone

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) (it installs the right Python, 3.12, for you). No API key is needed.

```bash
git clone https://github.com/NeilSinclair/mama-health.git && cd mama-health
uv sync
uv run mama-pipeline
```

What the three commands do:

1. `git clone ...` downloads the repo, including the conversations in `data/conversations.json` and the saved LLM labels in `data/labels/`.
2. `uv sync` creates a virtual environment in `.venv/` and installs the dependencies from `uv.lock`.
3. `uv run mama-pipeline` rebuilds every table in `outputs/`, the explorer page and `memo.html` from the saved labels. It takes a few seconds, makes no API calls, and should leave `git status` clean, because the committed outputs are what the pipeline produces.

Then open the memo:

```bash
open memo.html              # macOS; on Linux use xdg-open, on Windows start
```

To run the tests and the lint checks (the same ones CI runs on every pull request):

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

## What is where

```
memo.html                  the memo, rendered by the pipeline
docs/memo.md               the memo text; edit this, then rerun the pipeline
data/conversations.json    the 50 conversations (never modified)
data/labels/               saved LLM labels the pipeline reads
data/gold/                 10 hand-labelled outcomes used to check the model
data/labels_stability/     repeat-run experiments cited in the memo appendix
outputs/                   generated tables and the explorer page
src/mama_analysis/         the pipeline
scripts/                   one-off experiments (label stability)
tests/                     offline tests
```

A `{{ table | row | column }}` placeholder in `docs/memo.md` is filled with that cell of the pipeline table, so numbers in the memo text cannot drift from the tables. If you change `docs/memo.md`, rerun `uv run mama-pipeline` and commit `memo.html` with it; a test fails otherwise.

## How the labelling works

Each conversation is summarised by an LLM (topics, summary, reason, conversation pain points, resolved, end reason), and the free-text labels are then consolidated into a smaller vocabulary. The model scores each topic's relevance (strong, medium or low) with a one-line reason, and files each topic in one of ten fixed topic groups (e.g. "Physical symptoms", "Access to care"). Reasons for conversation are one of four fixed need types, shown as "understand my condition", "decide on treatment", "emotional support" and "get access to care", and end reasons one of three (need met, partial resolution, unresolved need), so neither needs consolidation. All topics are consolidated into one shared vocabulary, but only strong topics are shown as chips, counted and graphed; every score and reason is kept in the cache, in the `topic_scores` column of `summaries.csv` and under "Topic scores" in the explorer. The model is Claude Sonnet 5.5 (`claude-sonnet-5-5`, version key `sonnet`); this is the version the memo uses. Labels from OpenAI GPT Luna (`gpt-6-luna`, version key `gpt_luna`), the model used before the switch, are kept for comparison and shown as a second version in the explorer. Open `outputs/explorer.html` in a browser to explore the results. The Conversations tab lists every summary with filters, the Relationships tab graphs which reasons for conversation, topics, conversation pain points and end reasons occur together, and the Breakdown tab shows linked counts: click any label (e.g. a topic) and every other field recounts for just those conversations. The counts behind the graph are in `outputs/summaries/<version>/label_cooccurrence.csv`.

## Regenerating the labels (optional, needs an API key)

Labels are cached in `data/labels/`, and the pipeline uses the cache by default, so no API key is needed. Every number in the memo comes from this cache. Regenerated labels will differ slightly from run to run (in three repeat runs the outcome was the same in 47 of 50 conversations), so figures for small groups will move. To regenerate them with your own key, copy `.env.example` to `.env`, set `ANTHROPIC_API_KEY` (and `OPENAI_API_KEY` only if you want the `gpt_luna` version too), then run one of the three `mama-pipeline` commands:

```bash
cp .env.example .env                    # once; then edit .env and paste your key

uv run mama-pipeline --relabel sonnet   # re-summarise, re-consolidate and re-label dynamics
uv run mama-pipeline --remap sonnet     # re-consolidate only, from the cached summaries
uv run mama-pipeline --dynamics sonnet  # re-label conversation dynamics only (pushback, final sentiment)
```

A full `--relabel sonnet` costs about $1.50 and takes a few minutes. It overwrites the saved labels, so the tables and the numbers filled into the memo will change slightly; `git checkout -- data/labels outputs memo.html` restores the committed ones.

The repeat-run tables cited in the memo appendix are rebuilt offline, without a key, by `uv run python scripts/sonnet_label_stability.py analyse`.

A separate dynamics pass labels each conversation's pushback turns (and whether the bot's next reply adapted) and the user's final sentiment. From these and the summaries, `outputs/analysis/<version>/` holds: the logged end state vs the outcome, silent failures (the user sounded satisfied but the need was not met or a safety failure occurred), every pushback, recovery by outcome, and the user's share of words before and after the first pushback. The explorer shows the same labels: final sentiment, silent failure and pushback status as filters, row badges and Breakdown panels, and each expanded conversation marks the pushback turns (kind, whether the bot's next reply adapted, and why).

Models are pinned in `src/mama_analysis/config.py`, and prompts are versioned in `src/mama_analysis/prompts/`. Each cache entry records its model ID, prompt SHA-256, timestamp and token usage.
