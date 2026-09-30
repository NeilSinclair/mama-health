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

Each conversation is summarised by an LLM (topics, summary, reason, conversation pain points, resolved, end reason), and the free-text labels are then consolidated into a smaller vocabulary. This runs twice, with Claude Haiku 4.5 (`haiku`) and OpenAI GPT Luna (`gpt_luna`). Open `outputs/explorer.html` in a browser to explore the results. The Conversations tab lists every summary with filters, and the Relationships tab graphs which topics, conversation pain points and end reasons occur together. The counts behind the graph are in `outputs/summaries/<version>/label_cooccurrence.csv`.

Labels are cached in `data/labels/`, and the pipeline uses the cache by default, so no API key is needed. To regenerate them with your own keys, copy `.env.example` to `.env`, set `ANTHROPIC_API_KEY` and/or `OPENAI_API_KEY`, then run:

```bash
uv run mama-pipeline --relabel haiku     # or gpt_luna, or all: re-summarise and re-consolidate
uv run mama-pipeline --remap haiku       # re-consolidate only, from the cached summaries
```

Models are pinned in `src/mama_analysis/config.py`, and prompts are versioned in `src/mama_analysis/prompts/`. Each cache entry records its model ID, prompt SHA-256, timestamp and token usage.
