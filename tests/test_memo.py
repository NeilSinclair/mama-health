import json
import re

import pandas as pd
import pytest

from mama_analysis.analysis import outcome_by, pain_point_list
from mama_analysis.memo import (
    fill_values,
    memo_breakdown,
    outcome_table_html,
    pain_points_html,
    pretty,
    render_memo,
)


def _chips(*labels):
    return [{"label": x, "raw": [x]} for x in labels]


def _strong(group):
    return {"label": group.lower(), "topic_group": group, "relevance": "strong"}


def _row(sid, reason, topics, end, disease):
    return {
        "session_id": sid,
        "reason_for_conversation": _chips(reason),
        "main_topics": _chips(*topics),
        "topic_scores": [
            {"label": t, "topic_group": "Physical symptoms", "relevance": "strong"} for t in topics
        ],
        "conversation_pain_points": [],
        "end_reason": _chips(end),
        "disease": disease,
        "summary": f"Summary of {sid}. More.",
    }


ROWS = [
    _row("s1", "decide", ["common", "rare"], "need met", "type_2_diabetes"),
    _row("s2", "decide", ["common"], "need met", "ibs"),
    _row("s3", "understand", ["other"], "unresolved need", "ibs"),
]


def test_pretty():
    assert pretty("type_2_diabetes") == "type 2 diabetes"


def test_memo_breakdown_flattens_labels_per_conversation():
    records = [
        {"session_id": sid, "conversation": [{"turn": 1, "role": "user", "text": f"hi {sid}"}]}
        for sid in ("s3", "s1", "s2", "s9")
    ]
    b = memo_breakdown(ROWS, records)
    # Transcripts for the rows only, sorted by session ID.
    assert list(b["conversations"]) == ["s1", "s2", "s3"]
    assert b["conversations"]["s1"] == [{"turn": 1, "role": "user", "text": "hi s1"}]
    assert b["fields"] == [
        "reason_for_conversation",
        "topic_group",
        "conversation_pain_points",
        "end_reason",
        "disease",
    ]
    first = b["rows"][0]
    assert first["session_id"] == "s1"
    assert first["reason_for_conversation"] == ["decide"]
    assert first["disease"] == ["type 2 diabetes"]
    assert first["topic_group"] == ["Physical symptoms"]
    assert set(first) == {"session_id", "summary", *b["fields"]}


def test_outcome_table_html_shows_resolved_unresolved_and_pct():
    page = outcome_table_html(outcome_by(ROWS, "disease"), "disease", "outputs/x.csv")
    assert '<table class="sortable">' in page
    assert "<th>Disease</th>" in page and "outputs/x.csv" in page
    heads = re.findall(r'<th class="num"[^>]*>([^<]+)</th>', page)
    assert heads == ["Resolved", "Unresolved", "Total", "Resolved %"]
    # Behind a disclosure widget, closed by default, in ascending order of resolved %.
    assert page.startswith(
        '<details class="tablefold"><summary>Table: resolved and unresolved by disease</summary>'
    )
    assert "<details open" not in page and page.endswith("</figure></details>")
    assert '<th class="num" aria-sort="ascending">Resolved %</th>' in page
    assert re.findall(r'<th scope="row">([^<]+)</th>', page) == ["ibs", "type 2 diabetes", "All"]
    assert re.search(
        r'<th scope="row">ibs</th>'
        + r'<td class="num">1</td>' * 2
        + r'<td class="num">2</td><td class="num">50%</td>',
        page,
    )
    assert re.search(r'<tr class="all"><th scope="row">All</th>.*?67%</td></tr>', page)
    assert "type 2 diabetes" in page


def test_outcome_table_html_sorts_by_resolved_pct_then_larger_group():
    # "few" sorts before "more" by name, so a tie broken by name would fail below.
    ends = {"more": ["need met"] * 2 + ["unresolved need"] * 2, "all": ["need met"] * 3}
    ends["few"] = ["need met", "unresolved need"]
    rows = [
        _row(f"{d}{i}", "decide", ["t"], end, d)
        for d, es in ends.items()
        for i, end in enumerate(es)
    ]
    df = outcome_by(rows, "disease")
    assert df["disease"].tolist() == ["more", "all", "few"]  # by total, as in the CSV
    page = outcome_table_html(df, "disease", "s")
    # 50% (4 conversations), 50% (2 conversations), 100%, then All.
    assert re.findall(r'<th scope="row">([^<]+)</th>', page) == ["more", "few", "all", "All"]


def test_outcome_table_html_by_topic_group_uses_the_overall_counts():
    rows = [r | {"topic_scores": r["topic_scores"] + [_strong("Access to care")]} for r in ROWS]
    df = outcome_by(rows, "topic_group")
    assert df["total"].sum() == 2 * len(ROWS)
    page = outcome_table_html(df, "topic_group", "outputs/t.csv", overall=(2, 1, 3))
    assert "<th>Topic group (strong topics)</th>" in page
    assert re.search(
        r'<tr class="all"><th scope="row">All</th><td class="num">2</td><td class="num">1</td>'
        r'<td class="num">3</td><td class="num">67%</td></tr>',
        page,
    )
    assert "can count in more than one row" in page
    assert "can count in more than one row" not in outcome_table_html(df, "topic_group", "s")


def test_fill_values_replaces_placeholders_with_table_cells():
    tables = {"outcome_by_disease": outcome_by(ROWS, "disease")}
    row = tables["outcome_by_disease"].iloc[0]
    name = row["disease"]
    table = "outcome_by_disease"
    text = f"{{{{ {table} | {name} | resolved }}}} of {{{{{table}|{name}|total}}}}."
    assert fill_values(text, tables) == f"{row['resolved']} of {row['total']}."
    assert fill_values("No placeholders.", tables) == "No placeholders."


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("{{ outcome_by_disease | total }}", "is not"),
        ("{{ nope | x | total }}", "unknown table"),
        ("{{ outcome_by_disease | nope | total }}", "no row"),
    ],
)
def test_fill_values_rejects_bad_placeholders(value, message):
    with pytest.raises(ValueError, match=message):
        fill_values(value, {"outcome_by_disease": outcome_by(ROWS, "disease")})


@pytest.mark.parametrize("text", ["{{ outcome_by_disease | ibs", "a }} b", "{{ a | b\n| c }}"])
def test_fill_values_rejects_unclosed_placeholders(text):
    with pytest.raises(ValueError, match="not closed"):
        fill_values(text, {"outcome_by_disease": outcome_by(ROWS, "disease")})


def test_fill_values_escapes_cell_text():
    tables = {"t": pd.DataFrame({"key": ["a"], "label": ["<b>bot</b> & co"]})}
    assert fill_values("{{ t | a | label }}", tables) == "&lt;b&gt;bot&lt;/b&gt; &amp; co"


def test_fill_values_rejects_unknown_column():
    tables = {"outcome_by_disease": outcome_by(ROWS, "disease")}
    name = tables["outcome_by_disease"].iloc[0]["disease"]
    with pytest.raises(ValueError, match="no column"):
        fill_values(f"{{{{ outcome_by_disease | {name} | nope }}}}", tables)


def test_render_memo_replaces_markers_and_embeds_breakdown():
    text = "# My memo\n\nIntro *text*.\n\n<!-- memo:t -->\n\n<!-- memo:breakdown -->\n"
    data = {"rows": [{"summary": "</script>"}], "fields": []}
    page = render_memo(text, {"t": "<table id='t'></table>"}, data)
    assert "<title>My memo</title>" in page
    assert '<h1 id="my-memo">My memo</h1>' in page and "<em>text</em>" in page
    assert "<nav" not in page  # no sections, so no contents list
    assert "<table id='t'></table>" in page and 'id="bgrid"' in page
    deepdive = page[page.index('<details class="deepdive">') :]
    assert deepdive.index('id="bgrid"') < deepdive.index("</section></details>")
    assert "memo:" not in page
    payload = page.split("const DATA = ", 1)[1].split(";\n", 1)[0]
    assert "</script>" not in payload
    assert json.loads(payload) == data


def test_render_memo_contents_list_links_second_and_third_level_headings():
    text = "# Memo\n\n## First part\n\n### A detail\n\n#### Too deep\n\n## Second part\n"
    page = render_memo(text, {}, {"rows": [], "fields": []})
    nav = page[page.index('<nav class="contents"') : page.index("</nav>")]
    assert re.findall(r'<a href="#([^"]+)">([^<]+)</a>', nav) == [
        ("first-part", "First part"),
        ("a-detail", "A detail"),
        ("second-part", "Second part"),
    ]
    assert page.index("</nav>") < page.index("<main>")
    assert '<h2 id="first-part">First part</h2>' in page
    assert '<h4 id="too-deep">Too deep</h4>' in page


def test_render_memo_rejects_unknown_marker():
    with pytest.raises(ValueError, match="unknown memo marker"):
        render_memo("<!-- memo:nope -->", {}, {"rows": [], "fields": []})


def test_render_memo_renders_markdown_inside_collapsible_sections():
    text = (
        '## Part\n\n<details markdown="1">\n<summary>Deep dive</summary>\n\n'
        "Some **bold** text.\n\n- a point\n\n</details>\n"
    )
    page = render_memo(text, {}, {"rows": [], "fields": []})
    details = page[page.index("<details") : page.index("</details>")]
    assert "<summary>Deep dive</summary>" in details
    assert "<strong>bold</strong>" in details and "<li>a point</li>" in details


def test_pain_points_html_one_table_with_where_column_per_field():
    rows = [r | {"conversation_pain_points": _chips("bot repeated advice")} for r in ROWS]
    page = pain_points_html(pain_point_list(rows), "outputs/p.csv")
    assert re.findall(r'<option value="(\w+)">', page) == ["topic_group", "disease"]
    assert 'data-rows="topic_group"' in page and page.count("<table") == 1
    assert '<th data-field="disease">Where it happens (disease)</th>' in page
    assert '<span class="wchip">type 2 diabetes <b>1</b></span>' in page
    assert '<th scope="row">bot repeated advice</th><td class="num">3</td>' in page
    assert "any pain point" not in page and 'class="all"' not in page
    assert page.startswith(
        '<details class="tablefold"><summary>Table: conversation pain points</summary>'
    )
    assert "s1, s2, s3" in page and "outputs/p.csv" in page


def test_pain_points_html_rejects_malformed_where():
    df = pain_point_list([]).iloc[:0]
    bad = pd.DataFrame(
        [
            {
                "pain_point": "x",
                "n_sessions": 1,
                "session_ids": "a",
                "where_topic_group": "no count",
                "where_disease": "",
            }
        ]
    )
    with pytest.raises(ValueError, match="unexpected 'where' item"):
        pain_points_html(pd.concat([df, bad]), "s")
