# mama health — conversation analysis

Take-home analysis of 50 chatbot–patient conversations. The memo is in [MEMO.md](MEMO.md) (in progress). The brief is in [docs/project_description.md](docs/project_description.md).

## Run it

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/NeilSinclair/mama-health.git && cd mama-health
uv sync
uv run mama-pipeline
```

Outputs are written to `outputs/`. Tests: `uv run pytest`. If the memo draft `docs/memo.md` exists, the run also renders it, with its tables and interactive panels, to `memo.html` in the repo root. A `{{ table | row | column }}` placeholder in the draft is filled with that cell of the pipeline table (D-049). If the hand labels in `data/gold/outcome_check.csv` exist, the run compares them with the model's end reasons and writes `outcome_check.csv` and `outcome_check_counts.csv` under `outputs/analysis/` (D-050).

## LLM labels

Each conversation is summarised by an LLM (topics, summary, reason, conversation pain points, resolved, end reason), and the free-text labels are then consolidated into a smaller vocabulary. The model scores each topic's relevance (strong, medium or low) with a one-line reason, and files each topic in one of ten fixed topic groups (e.g. "Physical symptoms", "Access to care"). Reasons for conversation are one of four fixed need types, shown as "understand my condition", "decide on treatment", "emotional support" and "get access to care", and end reasons one of three (need met, partial resolution, unresolved need), so neither needs consolidation. All topics are consolidated into one shared vocabulary, but only strong topics are shown as chips, counted and graphed; every score and reason is kept in the cache, in the `topic_scores` column of `summaries.csv` and under "Topic scores" in the explorer. The model is Claude Sonnet 5.5 (`claude-sonnet-5-5`, version key `sonnet`); this is the version the memo uses. Labels from OpenAI GPT Luna (`gpt-6-luna`, version key `gpt_luna`), the model used before the switch (D-055), are kept for comparison and shown as a second version in the explorer. Open `outputs/explorer.html` in a browser to explore the results. The Conversations tab lists every summary with filters, the Relationships tab graphs which reasons for conversation, topics, conversation pain points and end reasons occur together, and the Breakdown tab shows linked counts: click any label (e.g. a topic) and every other field recounts for just those conversations. The counts behind the graph are in `outputs/summaries/<version>/label_cooccurrence.csv`.

Labels are cached in `data/labels/`, and the pipeline uses the cache by default, so no API key is needed. Every number in the memo comes from this cache. Regenerated labels will differ slightly from run to run (in three repeat runs the outcome was the same in 47 of 50 conversations), so figures for small groups will move. To regenerate them with your own keys, copy `.env.example` to `.env`, set `ANTHROPIC_API_KEY` (and `OPENAI_API_KEY` for the `gpt_luna` version), then run:

```bash
uv run mama-pipeline --relabel sonnet   # re-summarise, re-consolidate and re-label dynamics
uv run mama-pipeline --remap sonnet     # re-consolidate only, from the cached summaries
uv run mama-pipeline --dynamics sonnet  # re-label conversation dynamics only (pushback, final sentiment)
```

A separate dynamics pass labels each conversation's pushback turns (and whether the bot's next reply adapted) and the user's final sentiment. From these and the summaries, `outputs/analysis/<version>/` holds: the logged end state vs the outcome, silent failures (the user sounded satisfied but the need was not met or a safety failure occurred), every pushback, recovery by outcome, and the user's share of words before and after the first pushback. The explorer shows the same labels: final sentiment, silent failure and pushback status as filters, row badges and Breakdown panels, and each expanded conversation marks the pushback turns (kind, whether the bot's next reply adapted, and why).

Models are pinned in `src/mama_analysis/config.py`, and prompts are versioned in `src/mama_analysis/prompts/`. Each cache entry records its model ID, prompt SHA-256, timestamp and token usage.
