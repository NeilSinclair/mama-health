import pytest
from pydantic import ValidationError

from mama_analysis.schemas import DynamicsLLM, LabelMapping, SummaryLLM


def test_summary_requires_all_fields():
    with pytest.raises(ValidationError):
        SummaryLLM.model_validate({"summary": "x"})


def test_summary_rejects_wrong_types():
    with pytest.raises(ValidationError):
        SummaryLLM.model_validate(
            {
                "main_topics": "not a list",
                "summary": "x",
                "reason_for_conversation": "informational",
                "conversation_pain_points": [],
                "issue_resolved": True,
                "end_reason": "x",
            }
        )


def test_topic_relevance_must_be_strong_medium_or_low():
    base = {
        "summary": "x",
        "reason_for_conversation": "informational",
        "conversation_pain_points": [],
        "issue_resolved": True,
        "end_reason": "need met",
    }
    ok = [{"topic": "t", "topic_group": "Access to care", "reason": "r", "relevance": "medium"}]
    assert (
        SummaryLLM.model_validate(base | {"main_topics": ok}).main_topics[0].relevance == "medium"
    )
    with pytest.raises(ValidationError):
        bad = [{"topic": "t", "topic_group": "Access to care", "reason": "r", "relevance": "high"}]
        SummaryLLM.model_validate(base | {"main_topics": bad})


def test_topic_group_must_be_one_of_the_ten():
    from mama_analysis.schemas import TOPIC_GROUPS

    base = {
        "summary": "x",
        "reason_for_conversation": "informational",
        "conversation_pain_points": [],
        "issue_resolved": True,
        "end_reason": "need met",
    }
    assert len(TOPIC_GROUPS) == 10
    for group in ("Emotional wellbeing", None, "emotional wellbeing"):
        topic = {"topic": "t", "reason": "r", "relevance": "strong"}
        if group is not None:
            topic["topic_group"] = group
        if group == "Emotional wellbeing":
            SummaryLLM.model_validate(base | {"main_topics": [topic]})
        else:
            with pytest.raises(ValidationError):
                SummaryLLM.model_validate(base | {"main_topics": [topic]})


def test_end_reason_is_one_of_three_values():
    base = {
        "main_topics": [],
        "summary": "x",
        "reason_for_conversation": "informational",
        "conversation_pain_points": [],
        "issue_resolved": False,
    }
    for value in ("need met", "partial resolution", "unresolved need"):
        assert SummaryLLM.model_validate(base | {"end_reason": value}).end_reason == value
    with pytest.raises(ValidationError):
        SummaryLLM.model_validate(base | {"end_reason": "gave up"})


def test_summary_schema_has_no_open_dicts():
    # Strict structured-output modes reject free-form objects; the LLM schemas must avoid them.
    for model in (SummaryLLM, LabelMapping, DynamicsLLM):
        text = str(model.model_json_schema())
        assert "additionalProperties': True" not in text


def test_dynamics_rejects_unknown_sentiment_and_kind():
    ok = {"final_sentiment_quote": "q", "final_sentiment": "neutral", "pushbacks": []}
    assert DynamicsLLM.model_validate(ok).pushbacks == []
    with pytest.raises(ValidationError):
        DynamicsLLM.model_validate(ok | {"final_sentiment": "happy"})
    push = {"turn": 3, "kind": "complaint", "quote": "q", "reason": "r", "bot_adapted": False}
    with pytest.raises(ValidationError):
        DynamicsLLM.model_validate(ok | {"pushbacks": [push]})


def test_reason_is_one_of_four_categories():
    base = {
        "main_topics": [],
        "summary": "x",
        "conversation_pain_points": [],
        "issue_resolved": True,
        "end_reason": "need met",
    }
    for value in ("informational", "decisional", "emotional", "access"):
        s = SummaryLLM.model_validate(base | {"reason_for_conversation": value})
        assert s.reason_for_conversation == value
    with pytest.raises(ValidationError):
        SummaryLLM.model_validate(base | {"reason_for_conversation": "checking a symptom"})
