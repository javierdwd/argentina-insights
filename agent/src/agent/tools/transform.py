"""Generic deterministic dataset reshapes for the respond agent.

The LLM sees shapes in the dataset index and explicitly projects, flattens, or
groups them before composition. No HTTP; reads ``state.datasets``.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from ..proxy import filters

OpName = Literal["unnest_match", "explode", "group_count", "project"]


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


def explode_rows(
    rows: list[dict],
    *,
    nested: str,
    keep: list[str] | None,
    lift: list[str] | None,
) -> list[dict]:
    """Flatten every object in a nested array into its own row."""
    output: list[dict] = []
    for parent in rows:
        children = parent.get(nested)
        if not isinstance(children, list):
            continue
        for child in children:
            if not isinstance(child, dict):
                continue
            row = {key: parent.get(key) for key in (keep or []) if key in parent}
            keys = lift or list(child)
            row.update({key: child.get(key) for key in keys if key in child})
            output.append(row)
    return output


def group_count(
    rows: list[dict],
    *,
    group_by: list[str],
    category: str,
    categories: list[str] | None,
) -> list[dict]:
    """Count category values per group, producing chart-ready wide rows."""
    grouped: dict[tuple, dict] = {}
    known_categories = list(categories or [])
    for source in rows:
        key = tuple(source.get(field) for field in group_by)
        row = grouped.setdefault(
            key,
            {field: source.get(field) for field in group_by},
        )
        value = source.get(category)
        if value in (None, ""):
            continue
        label = str(value)
        row[label] = int(row.get(label, 0)) + 1
        if label not in known_categories:
            known_categories.append(label)
    for row in grouped.values():
        for label in known_categories:
            row.setdefault(label, 0)
    return list(grouped.values())


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
    group_by: list[str] | None = None,
    category: str | None = None,
    categories: list[str] | None = None,
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

    if op == "explode":
        if not nested:
            raise ValueError("explode requires nested=<array key>.")
        return explode_rows(rows, nested=nested, keep=keep, lift=lift)

    if op == "group_count":
        if not group_by or not category:
            raise ValueError("group_count requires group_by and category.")
        return group_count(
            rows,
            group_by=group_by,
            category=category,
            categories=categories,
        )

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
    group_by: list[str] | None = None,
    category: str | None = None,
    categories: list[str] | None = None,
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
      - explode: flatten every object in ``nested`` into one row. Use for
        nested filmografia/elenco or any array that must become a List/cards.
      - group_count: count ``category`` values per ``group_by`` fields into
        wide chart-ready rows (for example vote counts per bloque).
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
        group_by: Grouping keys for group_count.
        category: Field whose values become count columns for group_count.
        categories: Optional complete category list; missing counts become 0.

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
            group_by=group_by,
            category=category,
            categories=categories,
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
