"""Render the memo draft (Markdown) as an HTML page with pipeline tables and linked counts.

The draft places generated blocks with HTML-comment markers, e.g. ``<!-- memo:breakdown -->``,
which stay invisible when the Markdown is read on its own. Numbers in the prose can be
placeholders, e.g. ``{{ outcome_by_reason | emotional support | need_met_pct }}``, filled from
the pipeline tables.
"""

from __future__ import annotations

import html
import json
import re
from importlib.resources import files
from pathlib import Path
from typing import Any

import markdown
import pandas as pd

from mama_analysis.consolidate import topic_groups
from mama_analysis.explorer import PAYLOAD_MARKER

DEFAULT_MEMO_PATH = Path("docs/memo.md")

BODY_MARKER = "<!--__BODY__-->"
TITLE_MARKER = "__TITLE__"
MARKER_RE = re.compile(r"<!--\s*memo:([a-z_]+)\s*-->")
VALUE_RE = re.compile(r"\{\{(.*?)\}\}")

# Linked-count panels, in order (as in the explorer's Breakdown tab).
BREAKDOWN_FIELDS = (
    "reason_for_conversation",
    "topic_group",
    "conversation_pain_points",
    "end_reason",
    "disease",
)

FIELD_TITLES = {"reason_for_conversation": "Reason for conversation", "disease": "Disease"}


def pretty(value: str) -> str:
    """Display form of a dataset value: ``"type_2_diabetes"`` → ``"type 2 diabetes"``.

    Args:
        value: Raw value.

    Returns:
        The value with underscores shown as spaces.
    """
    return value.replace("_", " ")


def fill_values(text: str, tables: dict[str, pd.DataFrame]) -> str:
    """Replace ``{{ table | row | column }}`` placeholders with cells of the pipeline tables.

    Args:
        text: Memo Markdown.
        tables: Pipeline tables by name. A table's first column names its rows.

    Returns:
        The Markdown with every placeholder replaced by its cell's value.

    Raises:
        ValueError: If a placeholder is not in ``table | row | column`` form, or names an
            unknown table, row or column.
    """

    def cell(m: re.Match[str]) -> str:
        parts = [part.strip() for part in m.group(1).split("|")]
        if len(parts) != 3:
            raise ValueError(f"memo value {m.group(0)!r} is not {{{{ table | row | column }}}}")
        table, row, column = parts
        if table not in tables:
            raise ValueError(f"memo value {m.group(0)!r}: unknown table; known: {sorted(tables)}")
        df = tables[table]
        rows = df[df.iloc[:, 0] == row]
        if rows.empty:
            raise ValueError(f"memo value {m.group(0)!r}: no row; rows: {list(df.iloc[:, 0])}")
        if column not in df.columns:
            raise ValueError(f"memo value {m.group(0)!r}: no column; columns: {list(df.columns)}")
        return str(rows.iloc[0][column])

    return VALUE_RE.sub(cell, text)


def memo_breakdown(rows: list[dict[str, Any]], records: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-conversation labels and transcripts for the memo's linked-count panels.

    Args:
        rows: Output of ``explorer.label_rows``.
        records: Raw session records, for the transcripts shown when a matching
            conversation is opened.

    Returns:
        ``{"fields", "rows", "conversations"}``; each row has ``session_id``, ``summary``
        and, per field in ``BREAKDOWN_FIELDS``, a list of labels (topic groups of the strong
        topics, via the model's ``topic_group``; disease in display form).
        ``conversations`` maps each row's session ID to its ``{turn, role, text}`` turns.
    """
    ids = {r["session_id"] for r in rows}
    return {
        "fields": list(BREAKDOWN_FIELDS),
        "conversations": {
            rec["session_id"]: [
                {"turn": t["turn"], "role": t["role"], "text": t["text"]}
                for t in rec["conversation"]
            ]
            for rec in sorted(records, key=lambda rec: rec["session_id"])
            if rec["session_id"] in ids
        },
        "rows": [
            {
                "session_id": r["session_id"],
                "summary": r["summary"],
                **{
                    f: [c["label"] for c in r[f]]
                    for f in ("reason_for_conversation", "conversation_pain_points", "end_reason")
                },
                "topic_group": topic_groups(r["topic_scores"]),
                "disease": [pretty(r["disease"])],
            }
            for r in rows
        ],
    }


def outcome_table_html(df: pd.DataFrame, field: str, source: str) -> str:
    """Render an ``analysis.outcome_by`` table as HTML: resolved vs unresolved, with an "All" row.

    Args:
        df: Output of ``analysis.outcome_by``.
        field: The field the table is split by.
        source: Output path of the CSV, cited under the table.

    Returns:
        A ``<figure>`` holding the table and its source line.
    """
    cols = ["resolved", "unresolved", "total"]
    head = "".join(f'<th class="num">{c.capitalize()}</th>' for c in cols)
    head += '<th class="num">Need met %</th>'

    def tr(cells: list[str], cls: str = "") -> str:
        first, *rest = cells
        tds = "".join(f'<td class="num">{c}</td>' for c in rest)
        return f'<tr{cls}><th scope="row">{first}</th>{tds}</tr>'

    body = [
        tr([html.escape(pretty(r[field])), *(str(r[c]) for c in cols), f"{r['need_met_pct']}%"])
        for _, r in df.iterrows()
    ]
    totals = [int(df[c].sum()) for c in cols]
    all_pct = f"{round(100 * totals[0] / totals[-1])}%"
    body.append(tr(["All", *map(str, totals), all_pct], ' class="all"'))
    return (
        '<figure class="table-fig"><div class="table-wrap"><table class="sortable">'
        f"<thead><tr><th>{html.escape(FIELD_TITLES.get(field, field))}</th>{head}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></div>"
        f"<figcaption>Resolved = need met; unresolved = partial resolution or unresolved need. "
        f"Source: <code>{html.escape(source)}</code></figcaption></figure>"
    )


WHERE_FIELDS = {"topic_group": "Topic group", "disease": "Disease"}
WHERE_RE = re.compile(r"^(.*) \((\d+)\)$")


def _where_chips(where: str) -> str:
    """Render ``"value (n); ..."`` as chips: the value, then its count in bold."""
    chips = []
    for item in where.split("; ") if where else []:
        m = WHERE_RE.match(item)
        if m is None:
            raise ValueError(f"unexpected 'where' item {item!r}")
        value, n = m.groups()
        chips.append(f'<span class="wchip">{html.escape(pretty(value))} <b>{n}</b></span>')
    return " ".join(chips)


def pain_points_html(df: pd.DataFrame, source: str) -> str:
    """Render the ranked pain-point list, with a dropdown for the "where" column.

    Args:
        df: Output of ``analysis.pain_point_list``.
        source: Output path of its CSV, cited under the table.

    Returns:
        A ``<figure>`` with the dropdown and one sortable table. It holds a "where" column
        per field in ``WHERE_FIELDS``, and CSS shows the one the dropdown picks (topic
        group by default).

    Raises:
        ValueError: If a "where" value is not in ``"value (n); ..."`` form.
    """
    options = "".join(f'<option value="{f}">{t}</option>' for f, t in WHERE_FIELDS.items())
    where_heads = "".join(
        f'<th data-field="{f}">Where it happens ({t.lower()})</th>' for f, t in WHERE_FIELDS.items()
    )
    head = f'<th>Pain point</th><th class="num">Conversations</th>{where_heads}<th>Which</th>'
    body = []
    for _, r in df.iterrows():
        wheres = "".join(
            f'<td data-field="{f}">{_where_chips(r[f"where_{f}"])}</td>' for f in WHERE_FIELDS
        )
        ids = html.escape(r["session_ids"].replace(",", ", "))
        body.append(
            f'<tr><th scope="row">{html.escape(r["pain_point"])}</th>'
            f'<td class="num">{r["n_sessions"]}</td>{wheres}<td class="ids">{ids}</td></tr>'
        )
    return (
        '<figure class="table-fig pain-fig" data-rows="topic_group">'
        f'<label class="rowpick">Where by <select id="pain-rows">{options}</select></label>'
        '<div class="table-wrap"><table class="sortable pain-table">'
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
        "<figcaption>Counts are conversations; pain points are what the bot did wrong, "
        "most common first. A conversation can count in more than one topic group. "
        f"Source: <code>{html.escape(source)}</code></figcaption></figure>"
    )


# Folded by default: the reader opens it to explore (a <details> block, like the list inside it).
BREAKDOWN_BLOCK = (
    '<details class="deepdive"><summary>Deep dive: explore the conversations</summary>'
    '<section class="breakdown"><div class="bcontrols" id="bcontrols"></div>'
    '<p class="bhint">Counts are conversations. Click a bar to keep only the conversations '
    "with that label; every panel recounts. Click more bars to narrow further (all must "
    "match); click a selected bar again to remove it.</p>"
    '<div class="bgrid" id="bgrid"></div>'
    '<details class="bdetails"><summary id="bhead"></summary><ul class="blist" id="blist"></ul>'
    "</details></section></details>"
)


def render_memo(text: str, blocks: dict[str, str], breakdown: dict[str, Any]) -> str:
    """Convert the memo Markdown to a self-contained HTML page.

    Args:
        text: Memo Markdown.
        blocks: HTML for each table marker name.
        breakdown: Output of ``memo_breakdown``, embedded for the ``breakdown`` marker.

    Returns:
        The HTML page.

    Raises:
        ValueError: If the Markdown uses a marker name with no block.
    """
    blocks = blocks | {"breakdown": BREAKDOWN_BLOCK}
    unknown = sorted(set(MARKER_RE.findall(text)) - blocks.keys())
    if unknown:
        raise ValueError(f"unknown memo marker(s) {unknown}; known: {sorted(blocks)}")
    # md_in_html renders Markdown inside <details markdown="1"> blocks (collapsible sections).
    body = markdown.markdown(text, extensions=["tables", "sane_lists", "md_in_html"])
    body = MARKER_RE.sub(lambda m: blocks[m.group(1)], body)
    title = next((ln[2:].strip() for ln in text.splitlines() if ln.startswith("# ")), "Memo")
    template = (files("mama_analysis") / "templates" / "memo.html").read_text(encoding="utf-8")
    # Escaping every "<" keeps label text from closing the script.
    data = json.dumps(breakdown, sort_keys=True, ensure_ascii=False).replace("<", "\\u003c")
    return (
        template.replace(TITLE_MARKER, html.escape(title))
        .replace(BODY_MARKER, body)
        .replace(PAYLOAD_MARKER, data)
    )
