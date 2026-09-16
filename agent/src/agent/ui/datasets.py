"""Generic dataset contracts shared by tool indexing and UI composition."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from langchain_core.messages import AIMessage, HumanMessage

from ..series_util import _dataset_date_range, _dataset_id

DatasetStatus = Literal["hit", "empty", "error"]


class DatasetRecord(TypedDict):
    id: str
    path: str
    params: dict[str, Any]
    rows: list[dict[str, Any]]
    keys: list[str]
    N: int
    date_range: str | None
    status: DatasetStatus
    error: str | None


def dataset_record(
    *,
    dataset_id: str,
    path: str,
    params: dict[str, Any],
    rows: list,
    error: str | None = None,
) -> DatasetRecord:
    """Build one normalized dataset result."""
    object_rows = [row for row in rows if isinstance(row, dict)]
    return {
        "id": dataset_id,
        "path": path,
        "params": params,
        "rows": object_rows,
        "keys": list(object_rows[0]) if object_rows else [],
        "N": len(object_rows),
        "date_range": _dataset_date_range(object_rows),
        "status": "error" if error else ("hit" if object_rows else "empty"),
        "error": error,
    }


def tool_call_source(tool_call: dict) -> tuple[str, dict]:
    """Return the stable path/params identity of a supported tool call."""
    args = tool_call.get("args") or {}
    name = tool_call.get("name") or ""
    if name == "search_actas":
        return "/search/actas", {
            "query": args.get("query"),
            "chamber": args.get("chamber"),
        }
    if name == "transform_dataset":
        return "derived/transform", {
            key: args.get(key)
            for key in (
                "source",
                "op",
                "nested",
                "where",
                "keep",
                "lift",
                "fields",
                "group_by",
                "category",
                "categories",
            )
        } | {"drop_unmatched": args.get("drop_unmatched", True)}
    return args.get("path") or "", args.get("params") or {}


def current_turn_ids(messages: list) -> set[str]:
    """Dataset ids issued since the latest user message."""
    last_human = next(
        (
            index
            for index in range(len(messages) - 1, -1, -1)
            if isinstance(messages[index], HumanMessage)
        ),
        0,
    )
    ids: set[str] = set()
    for message in messages[last_human:]:
        if not isinstance(message, AIMessage):
            continue
        for tool_call in message.tool_calls:
            path, params = tool_call_source(tool_call)
            ids.add(_dataset_id(path, params))
    return ids


def hit_ids(datasets: dict, candidates: set[str]) -> set[str]:
    """Candidate ids whose structured status is a non-empty hit."""
    return {
        dataset_id
        for dataset_id in candidates
        if (datasets.get(dataset_id) or {}).get("status", "hit") == "hit"
        and ((datasets.get(dataset_id) or {}).get("N") or 0) > 0
    }
