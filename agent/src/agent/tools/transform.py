"""Deterministic dataset reshape tool for the respond agent.

The LLM sees shapes in the datasets index (keys / sample) and calls this tool
to flatten one level of nesting — e.g. actas with ``votos[]`` → one row per
acta with that legislator's scalar ``voto``. No HTTP; reads ``state.datasets``.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from ..proxy import filters

OpName = Literal["unnest_match", "project"]


def _child_matches(child: dict, where: dict[str, Any]) -> bool:
    """AND-match: every where key must match the child field (fold/tokens)."""
    if not where:
        return True
    for key, needle in where.items():
        if needle is None or needle == "":
            continue
        raw = child.get(key)
        if raw is None:
            return False
        # Reuse proxy text matching on a one-field "row".
        if not filters.filter_by_text([{"_": raw}], str(needle), ("_",)):
            return False
    return True


def unnest_match(
    rows: list[dict],
    *,
    nested: str,
    where: dict[str, Any] | None,
    keep: list[str] | None,
    lift: list[str] | None,
    drop_unmatched: bool = True,
) -> list[dict]:
    """One flat row per parent: keep parent fields + lift matched child fields."""
    where = where or {}
    keep = keep or []
    lift = lift or []
    out: list[dict] = []

    for parent in rows:
        if not isinstance(parent, dict):
            continue
        children = parent.get(nested)
        if not isinstance(children, list):
            if not drop_unmatched:
                row = {k: parent.get(k) for k in keep if k in parent}
                for key in lift:
                    row[key] = None
                out.append(row)
            continue

        match: dict | None = None
        for child in children:
            if isinstance(child, dict) and _child_matches(child, where):
                match = child
                break

        if match is None and drop_unmatched:
            continue

        row: dict[str, Any] = {}
        for key in keep:
            if key in parent:
                row[key] = parent.get(key)
        for key in lift:
            if match is not None:
                row[key] = match.get(key)
            else:
                row[key] = None
        out.append(row)

    return out


def project_rows(rows: list[dict], fields: list[str]) -> list[dict]:
    """Keep only the listed top-level keys on each row."""
    if not fields:
        return [dict(r) for r in rows if isinstance(r, dict)]
    return [
        {k: row[k] for k in fields if k in row}
        for row in rows
        if isinstance(row, dict)
    ]


def run_transform(
    datasets: dict,
    *,
    source: str,
    op: str,
    nested: str | None = None,
    where: dict[str, Any] | None = None,
    keep: list[str] | None = None,
    lift: list[str] | None = None,
    drop_unmatched: bool = True,
    fields: list[str] | None = None,
) -> list[dict]:
    """Apply a whitelisted reshape against an indexed dataset."""
    ds = datasets.get(source)
    if not ds:
        known = ", ".join(sorted(datasets)) or "(none)"
        raise ValueError(
            f"Dataset {source!r} not in the index. Known ids: {known}. "
            "Fetch first, then transform."
        )
    rows = [r for r in (ds.get("rows") or []) if isinstance(r, dict)]

    if op == "project":
        return project_rows(rows, fields or [])

    if op == "unnest_match":
        if not nested:
            raise ValueError("unnest_match requires nested=<array key> (e.g. 'votos').")
        return unnest_match(
            rows,
            nested=nested,
            where=where,
            keep=keep,
            lift=lift,
            drop_unmatched=drop_unmatched,
        )

    raise ValueError(f"Unknown op {op!r}. Use unnest_match or project.")


@tool
def transform_dataset(
    source: str,
    op: OpName,
    nested: str | None = None,
    where: dict[str, Any] | None = None,
    keep: list[str] | None = None,
    lift: list[str] | None = None,
    drop_unmatched: bool = True,
    fields: list[str] | None = None,
    state: Annotated[dict, InjectedState] = None,  # type: ignore[assignment]
) -> str:
    """Reshape an already-fetched dataset (no HTTP). One nesting level.

    Use when the datasets index shows a nested array (e.g. key ``votos`` with
    sample ``votos=[{nombre,voto}…]×N``) and the user wants ONE member's value
    on each parent row — e.g. "todos los votos de Losada", "cómo votó ella en
    cada ley". Do NOT send the raw nested array to compose (List will dump JSON).

    Ops:
      - unnest_match: for each parent, find the first child in ``nested`` that
        matches ``where`` (AND, accent-insensitive), keep parent fields + lift
        child fields into a flat row.
      - project: keep only top-level ``fields`` on each row.

    Example (legislator vote history after fetch …/actas?includeVotes=true):
        source=<ds_id from index>
        op=unnest_match
        nested=votos
        where={"nombre": "Losada, Carolina"}
        keep=["actaId", "titulo", "fecha", "resultado"]
        lift=["voto", "nombre"]
        drop_unmatched=true

    Full roll call for ONE acta → fetch …/votos instead; no transform needed.
    Vote history across many actas → always fetch actas with includeVotes=true
    AND desde/hasta from that person's term (or last 12 months); then this tool.

    Args:
        source: Dataset id from the "Already fetched" index (ds_…).
        op: unnest_match | project.
        nested: Array key on each parent row (unnest_match), e.g. "votos".
        where: Child field → needle to match (unnest_match), e.g. nombre.
        keep: Parent keys to copy onto each output row.
        lift: Child keys to copy onto each output row.
        drop_unmatched: If true (default), skip parents with no matching child.
        fields: Keys to keep for op=project.

    Returns:
        JSON list of flat rows, or a No records / Error message.
    """
    datasets = (state or {}).get("datasets") or {}
    try:
        rows = run_transform(
            datasets,
            source=source,
            op=op,
            nested=nested,
            where=where,
            keep=keep,
            lift=lift,
            drop_unmatched=drop_unmatched,
            fields=fields,
        )
    except ValueError as exc:
        return f"Error: {exc}"

    if not rows:
        return (
            f"No records: transform {op!r} on {source!r} produced 0 rows "
            f"(nested={nested!r}, where={where!r}). That can mean nobody "
            "matched — say so; do not invent votes."
        )
    return json.dumps(rows, ensure_ascii=False)
