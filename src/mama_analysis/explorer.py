"""Tables and the HTML explorer built from cached summaries and label mappings."""

from __future__ import annotations

import json
from importlib.resources import files
from itertools import combinations
from typing import Any

import pandas as pd

from mama_analysis.consolidate import FIELDS, apply_mapping, as_list
from mama_analysis.schemas import SessionSummary

PAYLOAD_MARKER = "/*__PAYLOAD__*/null"

# Fields shown as nodes in the explorer's relationship graph.
GRAPH_FIELDS = ("reason_for_conversation", "main_topics", "conversation_pain_points", "end_reason")


def label_rows(
    summaries: list[SessionSummary], mappings: dict[str, dict[str, str]]
) -> list[dict[str, Any]]:
    """Attach canonical labels to each session summary.

    Args:
        summaries: Session summaries, one per session.
        mappings: Raw-to-canonical dict per field in ``FIELDS``.

    Returns:
        One dict per session, sorted by session ID: the summary fields, plus for each
        field in ``FIELDS`` a list of ``{"label": canonical, "raw": [raw, ...]}`` chips.
    """
    rows = []
    for s in sorted(summaries, key=lambda s: s.session_id):
        row = s.model_dump()
        for field in FIELDS:
            chips: dict[str, list[str]] = {}
            for raw in as_list(row[field]):
                chips.setdefault(apply_mapping(raw, mappings[field]), []).append(raw)
            row[field] = [{"label": k, "raw": v} for k, v in chips.items()]
        rows.append(row)
    return rows


def summaries_table(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Flatten labelled rows to one CSV-friendly row per session.

    Args:
        rows: Output of ``label_rows``.

    Returns:
        DataFrame with metadata, summary and ``issue_resolved``, plus for each label
        field a canonical column and a ``<field>_raw`` column, lists joined with ``"; "``.
    """
    out = []
    for r in rows:
        flat = {k: v for k, v in r.items() if k not in FIELDS}
        for field in FIELDS:
            flat[field] = "; ".join(c["label"] for c in r[field])
            flat[f"{field}_raw"] = "; ".join(raw for c in r[field] for raw in c["raw"])
        out.append(flat)
    return pd.DataFrame(out)


def label_counts(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Count sessions per canonical label, for each label field.

    Args:
        rows: Output of ``label_rows``.

    Returns:
        DataFrame with ``field``, ``label``, ``n_sessions`` and comma-joined
        ``session_ids``, sorted by field, then count descending, then label.
    """
    sessions: dict[tuple[str, str], list[str]] = {}
    for r in rows:
        for field in FIELDS:
            for chip in r[field]:
                sessions.setdefault((field, chip["label"]), []).append(r["session_id"])
    df = pd.DataFrame(
        [
            {"field": f, "label": lab, "n_sessions": len(ids), "session_ids": ",".join(ids)}
            for (f, lab), ids in sessions.items()
        ],
        columns=["field", "label", "n_sessions", "session_ids"],
    )
    return df.sort_values(
        ["field", "n_sessions", "label"], ascending=[True, False, True], ignore_index=True
    )


def label_graph(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Build a co-occurrence graph of canonical labels across ``GRAPH_FIELDS``.

    Args:
        rows: Output of ``label_rows``.

    Returns:
        ``{"nodes": [...], "edges": [...]}``. A node is one canonical label in one field,
        with ``id`` (``"<field>:<label>"``), ``field``, ``label``, ``n_sessions`` and
        ``session_ids``. An edge joins two labels from different fields that appear in the
        same session, with ``source``, ``target``, ``n_sessions`` and ``session_ids``.
        Both lists are sorted by ID.
    """
    node_sessions: dict[str, list[str]] = {}
    edge_sessions: dict[tuple[str, str], list[str]] = {}
    for r in rows:
        ids = sorted({f"{f}:{c['label']}" for f in GRAPH_FIELDS for c in r[f]})
        for node in ids:
            node_sessions.setdefault(node, []).append(r["session_id"])
        for a, b in combinations(ids, 2):
            if a.split(":", 1)[0] != b.split(":", 1)[0]:
                edge_sessions.setdefault((a, b), []).append(r["session_id"])
    nodes = [
        {
            "id": node,
            "field": node.split(":", 1)[0],
            "label": node.split(":", 1)[1],
            "n_sessions": len(sids),
            "session_ids": sids,
        }
        for node, sids in sorted(node_sessions.items())
    ]
    edges = [
        {"source": a, "target": b, "n_sessions": len(sids), "session_ids": sids}
        for (a, b), sids in sorted(edge_sessions.items())
    ]
    return {"nodes": nodes, "edges": edges}


def cooccurrence_table(graph: dict[str, list[dict[str, Any]]]) -> pd.DataFrame:
    """Flatten the label graph's edges to a table.

    Args:
        graph: Output of ``label_graph``.

    Returns:
        DataFrame with ``field_a``, ``label_a``, ``field_b``, ``label_b``, ``n_sessions``
        and comma-joined ``session_ids``, sorted by count descending, then labels.
    """
    rows = []
    for e in graph["edges"]:
        field_a, label_a = e["source"].split(":", 1)
        field_b, label_b = e["target"].split(":", 1)
        rows.append(
            {
                "field_a": field_a,
                "label_a": label_a,
                "field_b": field_b,
                "label_b": label_b,
                "n_sessions": e["n_sessions"],
                "session_ids": ",".join(e["session_ids"]),
            }
        )
    df = pd.DataFrame(
        rows, columns=["field_a", "label_a", "field_b", "label_b", "n_sessions", "session_ids"]
    )
    return df.sort_values(
        ["n_sessions", "field_a", "label_a", "field_b", "label_b"],
        ascending=[False, True, True, True, True],
        ignore_index=True,
    )


def explorer_payload(
    records: list[dict[str, Any]], versions: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Assemble the data embedded in the explorer page.

    Args:
        records: Raw session records, for the full transcripts.
        versions: Per version key, ``{"label", "model_id", "rows"}``; ``rows`` is the output
            of ``label_rows``, or ``None`` if the version has no complete cached labels.

    Returns:
        ``{"versions": [...], "conversations": {session_id: [{turn, role, text}]}}``; each
        available version also carries its ``label_graph``.
    """
    return {
        "versions": [
            {
                "key": key,
                **v,
                "available": v["rows"] is not None,
                "graph": label_graph(v["rows"]) if v["rows"] is not None else None,
            }
            for key, v in versions.items()
        ],
        "conversations": {
            r["session_id"]: [
                {"turn": t["turn"], "role": t["role"], "text": t["text"]} for t in r["conversation"]
            ]
            for r in sorted(records, key=lambda r: r["session_id"])
        },
    }


def render_explorer(payload: dict[str, Any]) -> str:
    """Embed the payload in the explorer HTML template.

    Args:
        payload: Output of ``explorer_payload``.

    Returns:
        A self-contained HTML page.
    """
    template = (files("mama_analysis") / "templates" / "explorer.html").read_text(encoding="utf-8")
    # Escaping every "<" keeps any payload text from closing the script or opening a comment.
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False).replace("<", "\\u003c")
    return template.replace(PAYLOAD_MARKER, data)
