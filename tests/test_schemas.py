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


def test_summary_schema_has_no_open_dicts():
    # Strict structured-output modes reject free-form objects; the LLM schemas must avoid them.
    for model in (SummaryLLM, LabelMapping):
        text = str(model.model_json_schema())
        assert "additionalProperties': True" not in text
