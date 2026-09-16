"""Small, domain-agnostic UI tree pipeline.

The composer chooses widgets. This module only enforces structural invariants,
merges the canvas, and binds rows to widget props.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .catalog import (
    data_prop_for,
    field_aliases_for,
    requires_data_ref,
    widget_types,
)
from .schemas import UINode

LAYOUT_TYPES = frozenset({"Stack", "Grid", "Box"})
HOST_TYPES = frozenset(
    {
        "div", "p", "span", "h2", "h3", "ul", "ol", "li", "dl", "dt",
        "dd", "strong", "em", "svg", "g", "path", "line", "polyline",
        "polygon", "circle", "rect", "text", "defs", "marker", "title",
    }
)
MAX_TREE_DEPTH = 12
MAX_TREE_NODES = 100


@dataclass(frozen=True)
class ValidationResult:
    tree: dict | None
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return self.tree is not None and not self.errors


def validate_tree(
    tree: dict | None,
    datasets: dict,
    *,
    allowed_refs: set[str] | None = None,
    existing_tree: dict | None = None,
) -> ValidationResult:
    """Validate only universal tree/data invariants."""
    if not isinstance(tree, dict):
        return ValidationResult(None, ("tree must be one object",))
    try:
        normalized = UINode.model_validate(tree).model_dump(exclude_none=True)
    except Exception as exc:  # noqa: BLE001 - return structured validation feedback
        return ValidationResult(None, (f"tree schema is invalid: {exc}",))

    errors: list[str] = []
    identities: set[tuple[str, str]] = set()
    existing_identities: set[tuple[str, str]] = set()
    node_ids: set[str] = set()
    node_count = 0
    known_types = set(widget_types()) | HOST_TYPES

    def collect_existing(node: object) -> None:
        if not isinstance(node, dict):
            return
        identity = _identity(node)
        if identity is not None:
            existing_identities.add(identity)
        for child in node.get("children") or []:
            collect_existing(child)

    collect_existing(existing_tree)

    def visit(
        node: object,
        location: str,
        *,
        host_allowed: bool = False,
        depth: int = 0,
    ) -> None:
        nonlocal node_count
        if not isinstance(node, dict):
            errors.append(f"{location}: node must be an object")
            return
        node_count += 1
        if node_count > MAX_TREE_NODES:
            errors.append(f"{location}: tree exceeds {MAX_TREE_NODES} nodes")
            return
        if depth > MAX_TREE_DEPTH:
            errors.append(f"{location}: tree exceeds depth {MAX_TREE_DEPTH}")
            return
        node_id = node.get("id")
        if node_id in node_ids:
            errors.append(f"{location}: duplicate node id {node_id!r}")
        elif isinstance(node_id, str):
            node_ids.add(node_id)
        kind = node.get("type")
        if kind not in known_types:
            errors.append(f"{location}: unknown widget type {kind!r}")
            return
        if kind in HOST_TYPES and not host_allowed:
            errors.append(f"{location}: host tag {kind!r} is only valid inside Box")
        props = node.get("props")
        if not isinstance(props, dict):
            errors.append(f"{location}: props must be an object")
            props = {}
        children = node.get("children") or []
        if not isinstance(children, list):
            errors.append(f"{location}: children must be an array")
            children = []
        if kind not in LAYOUT_TYPES and kind not in HOST_TYPES and children:
            errors.append(f"{location}: leaf widget {kind} cannot have children")
        if kind in {"Stack", "Grid"} and not children:
            errors.append(f"{location}: container {kind} requires children")
        if kind not in LAYOUT_TYPES and kind not in HOST_TYPES and not node.get("title"):
            errors.append(f"{location}: leaf widget {kind} requires a title")
        if "data" in props or "people" in props:
            errors.append(f"{location}: raw rows are forbidden; use dataRef")

        data_ref = props.get("dataRef")
        if kind in HOST_TYPES | {"Box"} and data_ref:
            errors.append(f"{location}: {kind} cannot bind dataRef")
        if requires_data_ref(str(kind)) and not data_ref:
            errors.append(f"{location}: {kind} requires dataRef")
        if isinstance(data_ref, str) and data_ref:
            dataset = datasets.get(data_ref)
            if not dataset:
                errors.append(f"{location}: dataRef {data_ref!r} does not exist")
            elif dataset.get("status", "hit") != "hit" or not dataset.get("rows"):
                errors.append(f"{location}: dataRef {data_ref!r} has no rows")
            elif allowed_refs is not None and data_ref not in allowed_refs:
                errors.append(f"{location}: dataRef {data_ref!r} is not from this turn")
            identity = (str(kind), data_ref)
            if identity in identities:
                errors.append(f"{location}: duplicate widget/dataRef {identity!r}")
            if identity in existing_identities:
                errors.append(
                    f"{location}: widget/dataRef {identity!r} is already visible; "
                    "use patch or omit it"
                )
            identities.add(identity)

        for index, child in enumerate(children):
            visit(
                child,
                f"{location}.children[{index}]",
                host_allowed=kind == "Box" or (host_allowed and kind in HOST_TYPES),
                depth=depth + 1,
            )

    visit(normalized, "tree")
    return ValidationResult(normalized, tuple(errors))


def validate_patch(tree: dict | None, patch: dict[str, dict] | None) -> tuple[str, ...]:
    """Validate patch targets and payload shape before applying a mutation."""
    if not isinstance(tree, dict):
        return ("patch requires an existing canvas",)
    if not patch:
        return ("patch must contain at least one node update",)
    known_ids: set[str] = set()

    def collect(node: object) -> None:
        if not isinstance(node, dict):
            return
        node_id = node.get("id")
        if isinstance(node_id, str):
            known_ids.add(node_id)
        for child in node.get("children") or []:
            collect(child)

    collect(tree)
    errors: list[str] = []
    for node_id, changes in patch.items():
        if node_id not in known_ids:
            errors.append(f"patch target {node_id!r} does not exist")
        if not isinstance(changes, dict) or not changes:
            errors.append(f"patch target {node_id!r} has no changes")
            continue
        unexpected = set(changes) - {"title", "props"}
        if unexpected:
            errors.append(
                f"patch target {node_id!r} has unsupported keys {sorted(unexpected)!r}"
            )
        if "props" in changes and not isinstance(changes["props"], dict):
            errors.append(f"patch target {node_id!r} props must be an object")
    return tuple(errors)


def _children(node: dict) -> list[dict]:
    if node.get("type") == "Stack":
        children = [item for item in node.get("children") or [] if isinstance(item, dict)]
        if children:
            return children
    return [node]


def _identity(node: dict) -> tuple[str, str] | None:
    data_ref = (node.get("props") or {}).get("dataRef")
    if not isinstance(data_ref, str) or not data_ref:
        return None
    return str(node.get("type") or ""), data_ref


def merge_canvas(previous: dict | None, incoming: dict) -> dict:
    """Append new widgets, replacing equal id or equal type+dataRef."""
    if not previous:
        return incoming
    items = list(_children(previous))
    for node in _children(incoming):
        match = next(
            (
                index
                for index, current in enumerate(items)
                if (
                    node.get("id")
                    and current.get("id") == node.get("id")
                    or _identity(node) is not None
                    and _identity(current) == _identity(node)
                )
            ),
            None,
        )
        if match is None:
            items.append(node)
        else:
            items[match] = node
    if len(items) == 1:
        return items[0]
    return {
        "id": "canvas_stack",
        "type": "Stack",
        "props": {"gap": "lg"},
        "children": items,
    }


def _scalar(value: object) -> object | None:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list) and all(
        isinstance(item, (str, int, float)) for item in value
    ):
        return value
    return None


def _mapped_rows(rows: list[dict], mapping: dict, aliases: dict) -> list[dict]:
    if not mapping and not aliases:
        return rows
    output: list[dict] = []
    targets = set(mapping) | set(aliases)
    for row in rows:
        item: dict[str, Any] = {}
        for target in targets:
            source = mapping.get(target)
            candidates = aliases.get(target, ())
            if source is not None:
                candidates = (source, *candidates)
            for candidate in candidates:
                keys = candidate if isinstance(candidate, (list, tuple)) else (candidate,)
                if all(key in row for key in keys):
                    values = [_scalar(row.get(key)) for key in keys]
                    if all(value not in (None, "") for value in values):
                        item[target] = " ".join(map(str, values)) if len(values) > 1 else values[0]
                        break
            else:
                if isinstance(source, str) and source not in row and target not in aliases:
                    item[target] = source
        output.append(item)
    return output


def bind_tree(tree: dict, datasets: dict) -> dict:
    """Resolve dataRef recursively with generic sort/limit/field mapping."""
    node = dict(tree)
    props = dict(node.get("props") or {})
    data_ref = props.pop("dataRef", None)
    if isinstance(data_ref, str):
        rows = list((datasets.get(data_ref) or {}).get("rows") or [])
        sort = props.pop("sort", None)
        if isinstance(sort, dict) and sort.get("key"):
            key = str(sort["key"])
            rows.sort(
                key=lambda row: (
                    row.get(key) is None,
                    str(row.get(key) or "").casefold(),
                ),
                reverse=sort.get("dir") == "desc",
            )
        limit = props.pop("limit", None)
        if isinstance(limit, int) and limit >= 0:
            rows = rows[:limit]
        mapping = props.pop("fields", None)
        rows = _mapped_rows(
            [row for row in rows if isinstance(row, dict)],
            mapping if isinstance(mapping, dict) else {},
            field_aliases_for(str(node.get("type") or "")),
        )
        props[data_prop_for(str(node.get("type") or ""))] = rows
    node["props"] = props
    node["children"] = [
        bind_tree(child, datasets)
        for child in node.get("children") or []
        if isinstance(child, dict)
    ]
    return node
