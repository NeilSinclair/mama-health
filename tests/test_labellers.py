import asyncio
from types import SimpleNamespace

import pytest
from fakes import fake_summary

from mama_analysis.config import MODELS, ModelSpec
from mama_analysis.labellers import OpenAILabeller, load_prompt, make_labeller
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


def _openai_client(parsed):
    usage = SimpleNamespace(
        input_tokens=100, output_tokens=20, input_tokens_details=SimpleNamespace(cached_tokens=64)
    )
    resp = SimpleNamespace(output_parsed=parsed, usage=usage, status="completed")
    return SimpleNamespace(responses=_Recorder(resp), close=_async_flag)


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


def test_make_labeller_uses_configured_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    for version, spec in MODELS.items():
        lab = make_labeller(version)
        assert isinstance(lab, OpenAILabeller)
        assert (lab.version, lab.spec) == (version, spec)


def test_adapter_closes_its_client():
    CLOSED.clear()
    spec = ModelSpec("openai", "gpt-x", "G")
    asyncio.run(OpenAILabeller("v", spec, client=_openai_client(None)).aclose())
    assert CLOSED == [True]
