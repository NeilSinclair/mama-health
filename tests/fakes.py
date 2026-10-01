"""Offline fakes for LLM labelling tests."""

import asyncio

from mama_analysis.config import ModelSpec
from mama_analysis.schemas import (
    DynamicsLLM,
    LabelMapping,
    LabelPair,
    Pushback,
    SummaryLLM,
    Usage,
)


class FakeLabeller:
    """Offline stand-in for a provider adapter; records call order and concurrency."""

    def __init__(self, respond, version="fake", model_id="fake-model", delay=0.01):
        self.version = version
        self.spec = ModelSpec("openai", model_id, "Fake")
        self.respond = respond
        self.delay = delay
        self.events = []
        self.active = 0
        self.max_active = 0

    async def complete(self, system, user, schema):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.events.append(("start", user))
        await asyncio.sleep(self.delay)
        self.events.append(("end", user))
        self.active -= 1
        return self.respond(schema, user), Usage(input_tokens=10, output_tokens=5)

    async def aclose(self):
        self.closed = True


def topics(*names, relevance="strong", group="Physical symptoms"):
    """Scored topics as the model returns them, all with the same relevance and group."""
    return [
        {"topic": n, "topic_group": group, "reason": f"user raised {n}", "relevance": relevance}
        for n in names
    ]


def fake_summary(**overrides):
    base = {
        "main_topics": topics("gut pain"),
        "summary": "User asked about gut pain.",
        "reason_for_conversation": "informational",
        "conversation_pain_points": ["bot repeated advice"],
        "issue_resolved": True,
        "end_reason": "need met",
    }
    return SummaryLLM(**(base | overrides))


def identity_mapping(schema, user):
    """Respond to a consolidation call by mapping every listed label to itself, lower-cased."""
    labels = user.split("\n")[2:]
    return LabelMapping(mappings=[LabelPair(raw=x, canonical=x.lower()) for x in labels])


def fake_dynamics(user):
    """Dynamics that quote the transcript's first user turn, so quote checks pass."""
    first = next(line for line in user.split("\n") if line.startswith("[t1] user: "))
    text = first.removeprefix("[t1] user: ")
    push = Pushback(turn=1, kind="objection", quote=text, reason="r", bot_adapted=False)
    return DynamicsLLM(final_sentiment_quote=text, final_sentiment="satisfied", pushbacks=[push])


def fake_respond(schema, user):
    if schema is SummaryLLM:
        return fake_summary()
    if schema is DynamicsLLM:
        return fake_dynamics(user)
    return identity_mapping(schema, user)
