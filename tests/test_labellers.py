import asyncio
from types import SimpleNamespace

import pytest
from fakes import fake_summary

from mama_analysis.config import MODELS, ModelSpec
from mama_analysis.labellers import (
    AnthropicLabeller,
    OpenAILabeller,
    load_prompt,
    make_labeller,
)
from mama_analysis.schemas import SummaryLLM


class _Recorder:
    """Mimics the async ``create``/``parse`` method of an SDK resource."""

    def __init__(self, response):
        self.response = response
        self.kwargs = None

    async def parse(self, **kwargs):
        self.kwargs = kwargs
        return self.response


CLOSED = []


async def _async_flag():
    CLOSED.append(True)


def _anthropic_client(parsed):
    usage = SimpleNamespace(
        input_tokens=100,
        output_tokens=20,
        cache_read_input_tokens=80,
        cache_creation_input_tokens=0,
    )
    msg = SimpleNamespace(parsed_output=parsed, usage=usage, stop_reason="end_turn")
    return SimpleNamespace(messages=_Recorder(msg), close=_async_flag)


def _openai_client(parsed):
    usage = SimpleNamespace(
        input_tokens=100, output_tokens=20, input_tokens_details=SimpleNamespace(cached_tokens=64)
    )
    resp = SimpleNamespace(output_parsed=parsed, usage=usage, status="completed")
    return SimpleNamespace(responses=_Recorder(resp), close=_async_flag)


SPEC = ModelSpec("anthropic", "model-x", "X")


def test_anthropic_marks_system_prompt_for_caching_and_uses_schema():
    client = _anthropic_client(fake_summary())
    lab = AnthropicLabeller("v", SPEC, client=client)
    out, usage = asyncio.run(lab.complete("SYSTEM", "USER", SummaryLLM))
    kw = client.messages.kwargs
    assert kw["system"] == [
        {"type": "text", "text": "SYSTEM", "cache_control": {"type": "ephemeral"}}
    ]
    assert kw["messages"] == [{"role": "user", "content": "USER"}]
    assert kw["output_format"] is SummaryLLM
    assert kw["model"] == "model-x"
    assert out == fake_summary()
    assert (usage.cache_read_tokens, usage.cache_write_tokens) == (80, 0)


def test_anthropic_raises_without_parsed_output():
    lab = AnthropicLabeller("v", SPEC, client=_anthropic_client(None))
    with pytest.raises(ValueError, match="no parsed output"):
        asyncio.run(lab.complete("S", "U", SummaryLLM))


def test_openai_uses_text_format_and_stable_cache_key():
    client = _openai_client(fake_summary())
    lab = OpenAILabeller("v", ModelSpec("openai", "gpt-x", "G"), client=client)
    _, usage = asyncio.run(lab.complete("SYSTEM", "USER", SummaryLLM))
    kw = client.responses.kwargs
    assert kw["instructions"] == "SYSTEM"
    assert kw["input"] == "USER"
    assert kw["text_format"] is SummaryLLM
    first_key = kw["prompt_cache_key"]
    asyncio.run(lab.complete("SYSTEM", "OTHER USER", SummaryLLM))
    assert client.responses.kwargs["prompt_cache_key"] == first_key
    assert usage.cache_read_tokens == 64


def test_openai_raises_without_parsed_output():
    lab = OpenAILabeller("v", ModelSpec("openai", "gpt-x", "G"), client=_openai_client(None))
    with pytest.raises(ValueError, match="no parsed output"):
        asyncio.run(lab.complete("S", "U", SummaryLLM))


def test_load_prompt_hash_is_stable():
    a, b = load_prompt("summary_v1"), load_prompt("summary_v1")
    assert a.sha256 == b.sha256 and len(a.sha256) == 64
    assert a.text.strip()
    assert load_prompt("consolidate_v1").sha256 != a.sha256


def test_make_labeller_picks_provider(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    kinds = {v: type(make_labeller(v)) for v in MODELS}
    for version, spec in MODELS.items():
        expected = AnthropicLabeller if spec.provider == "anthropic" else OpenAILabeller
        assert kinds[version] is expected


def test_adapters_close_their_clients():
    CLOSED.clear()
    for cls in (AnthropicLabeller, OpenAILabeller):
        client = _anthropic_client(None) if cls is AnthropicLabeller else _openai_client(None)
        asyncio.run(cls("v", SPEC, client=client).aclose())
    assert CLOSED == [True, True]
