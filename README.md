# mama health — conversation analysis

Take-home analysis of 50 chatbot–patient conversations. The memo is in [MEMO.md](MEMO.md) (in progress). The brief is in [docs/project_description.md](docs/project_description.md).

## Run it

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/NeilSinclair/mama-health.git && cd mama-health
uv sync
uv run mama-pipeline
```

Outputs are written to `outputs/`. Tests: `uv run pytest`.

## LLM labels

Each conversation is summarised by an LLM (topics, summary, reason, conversation pain points, resolved, end reason), and the free-text labels are then consolidated into a smaller vocabulary. The model scores each topic's relevance (strong, medium or low) with a one-line reason. End reasons are one of three fixed values (need met, partial resolution, unresolved need), so they need no consolidation. All topics are consolidated into one shared vocabulary, but only strong topics are shown as chips, counted and graphed; every score and reason is kept in the cache, in the `topic_scores` column of `summaries.csv` and under "Topic scores" in the explorer. The model is OpenAI GPT Luna (`gpt-6-luna`, version key `gpt_luna`). Open `outputs/explorer.html` in a browser to explore the results. The Conversations tab lists every summary with filters, the Relationships tab graphs which reasons for conversation, topics, conversation pain points and end reasons occur together, and the Breakdown tab shows linked counts: click any label (e.g. a topic) and every other field recounts for just those conversations. The counts behind the graph are in `outputs/summaries/<version>/label_cooccurrence.csv`.

Labels are cached in `data/labels/`, and the pipeline uses the cache by default, so no API key is needed. To regenerate them with your own keys, copy `.env.example` to `.env`, set `OPENAI_API_KEY`, then run:

```bash
uv run mama-pipeline --relabel gpt_luna   # re-summarise and re-consolidate
uv run mama-pipeline --remap gpt_luna     # re-consolidate only, from the cached summaries
uv run mama-pipeline --dynamics gpt_luna  # re-label conversation dynamics only (pushback, final sentiment)
```

A separate dynamics pass labels each conversation's pushback turns (and whether the bot's next reply adapted) and the user's final sentiment. From these and the summaries, `outputs/analysis/<version>/` holds: the logged end state vs the outcome, silent failures (the user sounded satisfied but the need was not met or a safety failure occurred), every pushback, recovery by outcome, and the user's share of words before and after the first pushback. The explorer shows the same labels: final sentiment, silent failure and pushback status as filters, row badges and Breakdown panels, and each expanded conversation marks the pushback turns (kind, whether the bot's next reply adapted, and why).

Models are pinned in `src/mama_analysis/config.py`, and prompts are versioned in `src/mama_analysis/prompts/`. Each cache entry records its model ID, prompt SHA-256, timestamp and token usage.
