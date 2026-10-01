import json

from fakes import fake_dynamics, fake_summary, topics

from mama_analysis.explorer import (
    PAYLOAD_MARKER,
    attach_dynamics,
    cooccurrence_table,
    explorer_payload,
    label_counts,
    label_graph,
    label_rows,
    render_explorer,
    summaries_table,
)
from mama_analysis.summarise import merge_deterministic, render_conversation

MAPPINGS = {
    "main_topics": {"insomnia": "insomnia", "trouble sleeping": "insomnia", "diet": "diet"},
    "conversation_pain_points": {"bot repeated advice": "bot repeated advice"},
    "reason_for_conversation": {"informational": "informational"},
    "end_reason": {"need met": "need met"},
}


def _rows(records):
    sums = [
        merge_deterministic(records[1], fake_summary(main_topics=topics("trouble sleeping"))),
        merge_deterministic(
            records[0], fake_summary(main_topics=topics("insomnia", "trouble sleeping"))
        ),
    ]
    return label_rows(sums, MAPPINGS)


def test_label_rows_groups_raw_labels_under_canonical(records):
    rows = _rows(records)
    assert [r["session_id"] for r in rows] == ["s1", "s2"]
    assert rows[0]["main_topics"] == [
        {"label": "insomnia", "raw": ["insomnia", "trouble sleeping"]}
    ]
    assert rows[0]["reason_for_conversation"] == [
        {"label": "informational", "raw": ["informational"]}
    ]


def test_label_counts_links_labels_to_sessions(records):
    counts = label_counts(_rows(records))
    topic = counts[counts.field == "main_topics"].iloc[0]
    assert (topic.label, topic.n_sessions, topic.session_ids) == ("insomnia", 2, "s1,s2")


def test_only_strong_topics_become_chips_but_all_scores_are_mapped(records):
    scored = (
        topics("insomnia")
        + topics("trouble sleeping", relevance="medium")
        + topics("diet", relevance="low")
    )
    rows = label_rows([merge_deterministic(records[0], fake_summary(main_topics=scored))], MAPPINGS)
    assert rows[0]["main_topics"] == [{"label": "insomnia", "raw": ["insomnia"]}]
    assert [(t["label"], t["topic"], t["relevance"]) for t in rows[0]["topic_scores"]] == [
        ("insomnia", "insomnia", "strong"),
        ("insomnia", "trouble sleeping", "medium"),
        ("diet", "diet", "low"),
    ]
    t = summaries_table(rows).set_index("session_id")
    assert t.loc["s1", "main_topics"] == "insomnia"
    assert t.loc["s1", "topic_scores"].split(" | ")[1] == (
        "insomnia (trouble sleeping) [medium; Physical symptoms]: user raised trouble sleeping"
    )


def test_summaries_table_keeps_raw_and_canonical(records):
    t = summaries_table(_rows(records)).set_index("session_id")
    assert t.loc["s1", "main_topics"] == "insomnia"
    assert t.loc["s1", "main_topics_raw"] == "insomnia; trouble sleeping"
    assert t.loc["s2", "session_ended_by"] == "user_closed"


def test_payload_marks_missing_version_unavailable(records):
    payload = explorer_payload(
        records,
        {
            "a": {"label": "A", "model_id": "m-a", "rows": _rows(records)},
            "b": {"label": "B", "model_id": "m-b", "rows": None},
        },
    )
    assert [(v["key"], v["available"]) for v in payload["versions"]] == [("a", True), ("b", False)]
    assert payload["conversations"]["s1"][0] == {
        "turn": 1,
        "role": "user",
        "text": "My gut hurts today",
    }


def test_render_explorer_embeds_payload_deterministically(records):
    records[0]["conversation"][0]["text"] = "</script><b>x</b> <!--<script>"
    payload = explorer_payload(records, {"a": {"label": "A", "model_id": "m", "rows": None}})
    html = render_explorer(payload)
    assert html == render_explorer(payload)
    assert PAYLOAD_MARKER not in html
    assert "</script><b>" not in html  # cannot break out of the script tag
    start = html.index("const DATA = ") + len("const DATA = ")
    embedded = html[start : html.index(";\n", start)]
    assert "<" not in embedded  # no "</script>" or "<!--" can reach the HTML parser
    assert json.loads(embedded) == payload


def _graph_rows():
    def chips(*labels):
        return [{"label": x, "raw": [x]} for x in labels]

    base = {"reason_for_conversation": chips("r")}
    return [
        base
        | {
            "session_id": "s1",
            "main_topics": chips("sleep", "diet"),
            "conversation_pain_points": chips("repeated advice"),
            "end_reason": chips("gave up"),
        },
        base
        | {
            "session_id": "s2",
            "main_topics": chips("sleep"),
            "conversation_pain_points": [],
            "end_reason": chips("need met"),
        },
        base
        | {
            "session_id": "s3",
            "main_topics": chips("sleep"),
            "conversation_pain_points": chips("repeated advice"),
            "end_reason": chips("gave up"),
        },
    ]


def test_label_graph_counts_sessions_per_node_and_cross_field_edge():
    g = label_graph(_graph_rows())
    nodes = {n["id"]: n for n in g["nodes"]}
    assert nodes["main_topics:sleep"]["n_sessions"] == 3
    assert nodes["end_reason:gave up"]["session_ids"] == ["s1", "s3"]
    assert nodes["reason_for_conversation:r"]["n_sessions"] == 3
    edges = {(e["source"], e["target"]): e for e in g["edges"]}
    assert (
        edges[("conversation_pain_points:repeated advice", "end_reason:gave up")]["n_sessions"] == 2
    )
    assert edges[("end_reason:gave up", "main_topics:sleep")]["session_ids"] == ["s1", "s3"]
    assert edges[("main_topics:sleep", "reason_for_conversation:r")]["n_sessions"] == 3
    # Labels from the same field are never joined.
    assert ("main_topics:diet", "main_topics:sleep") not in edges
    assert [e["source"] < e["target"] for e in g["edges"]] == [True] * len(g["edges"])


def test_cooccurrence_table_sorted_by_count():
    t = cooccurrence_table(label_graph(_graph_rows()))
    assert t.iloc[0]["n_sessions"] == 3
    assert list(t.columns) == [
        "field_a",
        "label_a",
        "field_b",
        "label_b",
        "n_sessions",
        "session_ids",
    ]
    top = t[(t.label_a == "repeated advice") & (t.label_b == "gave up")].iloc[0]
    assert top["session_ids"] == "s1,s3"


def test_payload_includes_graph_only_for_available_versions(records):
    payload = explorer_payload(
        records,
        {
            "a": {"label": "A", "model_id": "m", "rows": _graph_rows()},
            "b": {"label": "B", "model_id": "m", "rows": None},
        },
    )
    graphs = {v["key"]: v["graph"] for v in payload["versions"]}
    assert graphs["b"] is None
    assert len(graphs["a"]["nodes"]) == 6


def test_template_field_names_match_python():
    from importlib.resources import files

    from mama_analysis.consolidate import FIELDS
    from mama_analysis.explorer import GRAPH_FIELDS

    template = (files("mama_analysis") / "templates" / "explorer.html").read_text()
    for field in (*FIELDS, *GRAPH_FIELDS):
        assert f'"{field}"' in template, f"template doesn't reference {field}"
    start = template.index("const GRAPH_FIELDS = [")
    graph_block = template[start : template.index("];", start)]
    for field in GRAPH_FIELDS:
        assert f'["{field}", ' in graph_block, f"graph doesn't show {field}"


def test_breakdown_fields_exist_in_rows(records):
    import re
    from importlib.resources import files

    template = (files("mama_analysis") / "templates" / "explorer.html").read_text()
    start = template.index("const BREAK_FIELDS = [")
    keys = re.findall(r'\["(\w+)", "', template[start : template.index("];", start)])
    by_id = {r["session_id"]: r for r in records}
    dyn = {sid: fake_dynamics(render_conversation(rec)) for sid, rec in by_id.items()}
    row = attach_dynamics(_rows(records), dyn, by_id)[0]
    # Topic groups are derived in the page from the topics and the payload's group table.
    assert "topic_group" in keys and "main_topics" in row and "topic_scores" in row
    keys = [k for k in keys if k != "topic_group"]
    assert keys and all(k in row for k in keys), keys
    assert 'data-tab="breakdown"' in template


def test_attach_dynamics_adds_status_fields_and_quote_checks(records):
    by_id = {r["session_id"]: r for r in records}
    dyn = {sid: fake_dynamics(render_conversation(rec)) for sid, rec in by_id.items()}
    dyn["s2"].pushbacks[0].quote = "words nobody said"
    rows = attach_dynamics(_rows(records), dyn, by_id)
    s1, s2 = rows
    # fake_summary: need met, no safety pain point, so a satisfied user is not a silent failure.
    assert (s1["final_sentiment"], s1["silent_failure"], s1["pushback"]) == (
        "satisfied",
        "no",
        "bot failed to adapt",
    )
    assert s1["dynamics"]["pushbacks"][0]["quote_found"] is True
    assert s2["dynamics"]["pushbacks"][0]["quote_found"] is False
    assert s1["dynamics"]["final_quote_found"] is True
    json.dumps(rows)  # embeddable in the page


def test_attach_dynamics_without_labels_returns_rows_unchanged(records):
    rows = _rows(records)
    assert attach_dynamics(rows, None, {}) is rows
