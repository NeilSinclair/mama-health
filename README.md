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

Qualitative labels are cached in `data/labels/`, and the pipeline uses the cache by default, so no API key is needed. To regenerate them with your own key, copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`. _(Relabel command to be added.)_
