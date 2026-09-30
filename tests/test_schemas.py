import pytest
from pydantic import ValidationError

from mama_analysis.schemas import LabelMapping, SummaryLLM


def test_summary_requires_all_fields():
    with pytest.raises(ValidationError):
        SummaryLLM.model_validate({"summary": "x"})


def test_summary_rejects_wrong_types():
    with pytest.raises(ValidationError):
        SummaryLLM.model_validate(
            {
                "main_topics": "not a list",
                "summary": "x",
                "reason_for_conversation": "x",
                "conversation_pain_points": [],
                "issue_resolved": True,
                "end_reason": "x",
            }
        )


def test_topic_relevance_must_be_strong_medium_or_low():
    base = {
        "summary": "x",
        "reason_for_conversation": "x",
        "conversation_pain_points": [],
        "issue_resolved": True,
        "end_reason": "need met",
    }
    ok = [{"topic": "t", "reason": "r", "relevance": "medium"}]
    assert (
        SummaryLLM.model_validate(base | {"main_topics": ok}).main_topics[0].relevance == "medium"
    )
    with pytest.raises(ValidationError):
        bad = [{"topic": "t", "reason": "r", "relevance": "high"}]
        SummaryLLM.model_validate(base | {"main_topics": bad})


def test_end_reason_is_one_of_three_values():
    base = {
        "main_topics": [],
        "summary": "x",
        "reason_for_conversation": "x",
        "conversation_pain_points": [],
        "issue_resolved": False,
    }
    for value in ("need met", "partial resolution", "unresolved need"):
        assert SummaryLLM.model_validate(base | {"end_reason": value}).end_reason == value
    with pytest.raises(ValidationError):
        SummaryLLM.model_validate(base | {"end_reason": "gave up"})


def test_summary_schema_has_no_open_dicts():
    # Strict structured-output modes reject free-form objects; the LLM schemas must avoid them.
    for model in (SummaryLLM, LabelMapping):
        text = str(model.model_json_schema())
        assert "additionalProperties': True" not in text
