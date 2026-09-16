"""Small, domain-agnostic UI tree pipeline.

The composer chooses widgets. This module only enforces structural invariants,
merges the canvas, and binds rows to widget props.
"""

from __future__ import annotations

import json
import unicodedata
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
        "div", "section", "header", "p", "span", "h2", "h3", "ul", "ol", "li",
        "dl", "dt", "dd", "strong", "em", "table", "thead", "tbody", "tr", "th",
        "td", "svg", "g", "path", "line", "polyline", "polygon", "circle", "rect",
        "text", "image", "defs", "marker", "title",
    }
)
MAX_TREE_DEPTH = 12
MAX_TREE_NODES = 100


def _filter_value(value: object) -> object:
    if isinstance(value, str):
        normalized = unicodedata.normalize("NFKD", value)
        return " ".join(
            "".join(char for char in normalized if not unicodedata.combining(char))
            .casefold()
            .split()
        )
    return value


def _matches_where(row: dict, where: dict) -> bool:
    """AND across fields, OR across list values; strings ignore case/accents."""
    for key, expected in where.items():
        options = expected if isinstance(expected, list) else [expected]
        actual = _filter_value(row.get(key))
        if not any(actual == _filter_value(option) for option in options):
            return False
    return True


def _valid_where_value(value: object) -> bool:
    if isinstance(value, (dict, tuple, set)):
        return False
    if isinstance(value, list):
        return bool(value) and all(
            not isinstance(item, (dict, list, tuple, set)) for item in value
        )
    return True


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
    identities: set[tuple[str, str, str, str]] = set()
    existing_identities: set[tuple[str, str, str, str]] = set()
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
        where = props.get("where")
        if where is not None and (
            not isinstance(where, dict)
            or not where
            or any(not isinstance(key, str) or not key for key in where)
            or any(not _valid_where_value(value) for value in where.values())
        ):
            errors.append(
                f"{location}: where must be a non-empty object of scalar or scalar-list values"
            )
            where = None
        if where is not None and not data_ref:
            errors.append(f"{location}: where requires dataRef")
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
            rows = [
                row
                for row in (dataset or {}).get("rows") or []
                if isinstance(row, dict)
            ]
            chart_rows = rows
            if isinstance(where, dict):
                missing = [
                    key for key in where if not any(key in row for row in rows)
                ]
                if missing:
                    errors.append(
                        f"{location}: where keys do not exist in {data_ref!r}: "
                        + ", ".join(repr(key) for key in missing)
                    )
                else:
                    chart_rows = [
                        row for row in rows if _matches_where(row, where)
                    ]
                    if not chart_rows:
                        errors.append(
                            f"{location}: where matches no rows in {data_ref!r}"
                        )
            if (
                kind == "Chart"
                and props.get("kind") in {"line", "bar", "area"}
                and chart_rows
            ):
                x_key = props.get("xKey")
                series_by = props.get("seriesBy")
                value_key = props.get("valueKey")
                series = props.get("series")
                row_keys = {key for row in chart_rows for key in row}
                series_keys = [
                    item.get("key")
                    for item in series or []
                    if isinstance(item, dict) and isinstance(item.get("key"), str)
                ]
                if series_by:
                    for field in (x_key, series_by, value_key):
                        if not isinstance(field, str) or field not in row_keys:
                            errors.append(
                                f"{location}: long-format Chart field "
                                f"{field!r} does not exist in {data_ref!r}"
                            )
                    category_values = {
                        str(row.get(str(series_by)))
                        for row in chart_rows
                        if row.get(str(series_by)) is not None
                    }
                    unknown = [
                        key for key in series_keys if key not in category_values
                    ]
                    if unknown:
                        errors.append(
                            f"{location}: series keys are not values of "
                            f"{series_by!r}: {unknown!r}"
                        )
                else:
                    missing_series = [
                        key for key in series_keys if key not in row_keys
                    ]
                    vote_values = {
                        str(row.get("voto"))
                        for row in chart_rows
                        if row.get("voto") is not None
                    }
                    invalid = [
                        key for key in missing_series if key not in vote_values
                    ]
                    vote_chart = bool(missing_series) and not invalid
                    if invalid:
                        errors.append(
                            f"{location}: series keys do not exist as columns: "
                            f"{invalid!r}. For long-format rows use "
                            "seriesBy=<category field> and valueKey=<metric field>."
                        )
                    if isinstance(x_key, str) and not vote_chart:
                        x_values = [
                            str(row.get(x_key))
                            for row in chart_rows
                            if row.get(x_key) is not None
                        ]
                        if len(x_values) != len(set(x_values)):
                            selected_teams = (
                                where.get("team")
                                if isinstance(where, dict)
                                else None
                            )
                            team_hint = (
                                " Create one Chart per team using a scalar "
                                'where={"team":"<exact team>"} and keep the '
                                "home/away metric columns as series."
                                if isinstance(selected_teams, list)
                                and len(selected_teams) > 1
                                else ""
                            )
                            errors.append(
                                f"{location}: duplicate {x_key!r} values require "
                                "seriesBy+valueKey or a scalar filter."
                                + team_hint
                            )
            identity = _identity(node)
            assert identity is not None
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


def _identity(node: dict) -> tuple[str, str, str, str] | None:
    props = node.get("props") or {}
    data_ref = props.get("dataRef")
    if not isinstance(data_ref, str) or not data_ref:
        return None
    where = props.get("where")
    metric_signature = ""
    if node.get("type") == "Chart":
        metric_signature = json.dumps(
            {
                "xKey": props.get("xKey"),
                "seriesBy": props.get("seriesBy"),
                "valueKey": props.get("valueKey"),
                "series": [
                    item.get("key")
                    for item in props.get("series") or []
                    if isinstance(item, dict)
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    return (
        str(node.get("type") or ""),
        data_ref,
        json.dumps(
            where if isinstance(where, dict) else {},
            ensure_ascii=False,
            sort_keys=True,
        ),
        metric_signature,
    )


def omit_existing_data_widgets(
    incoming: dict | None,
    existing: dict | None,
) -> dict | None:
    """Drop repeated data widgets while preserving new siblings.

    A compose result can legitimately contain both an already-visible widget
    and a new companion. Rejecting the whole tree makes the repair model choose
    between ``tree`` and ``patch`` even though neither can express both actions.
    """
    existing_identities: set[tuple[str, str, str, str]] = set()

    def collect(node: object) -> None:
        if not isinstance(node, dict):
            return
        identity = _identity(node)
        if identity is not None:
            existing_identities.add(identity)
        for child in node.get("children") or []:
            collect(child)

    def prune(node: object) -> dict | None:
        if not isinstance(node, dict):
            return None
        identity = _identity(node)
        if identity is not None and identity in existing_identities:
            return None
        cleaned = dict(node)
        cleaned["children"] = [
            child
            for item in node.get("children") or []
            if (child := prune(item)) is not None
        ]
        if cleaned.get("type") in {"Stack", "Grid"} and not cleaned["children"]:
            return None
        return cleaned

    collect(existing)
    return prune(incoming)


def merge_canvas(previous: dict | None, incoming: dict) -> dict:
    """Append widgets, replacing equal id or equal type+dataRef+where."""
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


def _expand_nested_rows(rows: list[dict], mapping: dict, aliases: dict) -> list[dict]:
    """Use a nested object array when parent rows cannot satisfy the identity field."""
    name_candidates = []
    source = mapping.get("name")
    if source is not None:
        name_candidates.append(source)
    name_candidates.extend(aliases.get("name", ()))

    def has_name(row: dict) -> bool:
        for candidate in name_candidates:
            keys = candidate if isinstance(candidate, (list, tuple)) else (candidate,)
            if all(_scalar(row.get(key)) not in (None, "") for key in keys):
                return True
        return False

    if not name_candidates or any(has_name(row) for row in rows):
        return rows

    nested = [
        child
        for row in rows
        for value in row.values()
        if isinstance(value, list)
        for child in value
        if isinstance(child, dict) and has_name(child)
    ]
    return nested or rows


def bind_tree(tree: dict, datasets: dict) -> dict:
    """Resolve dataRef recursively with generic sort/limit/field mapping."""
    node = dict(tree)
    props = dict(node.get("props") or {})
    data_ref = props.pop("dataRef", None)
    if isinstance(data_ref, str):
        rows = list((datasets.get(data_ref) or {}).get("rows") or [])
        mapping = props.pop("fields", None)
        mapping = mapping if isinstance(mapping, dict) else {}
        aliases = field_aliases_for(str(node.get("type") or ""))
        if aliases.get("name"):
            rows = _expand_nested_rows(
                [row for row in rows if isinstance(row, dict)],
                mapping,
                aliases,
            )
        where = props.pop("where", None)
        if isinstance(where, dict) and where:
            rows = [
                row
                for row in rows
                if isinstance(row, dict) and _matches_where(row, where)
            ]
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
        rows = _mapped_rows(
            [row for row in rows if isinstance(row, dict)],
            mapping,
            aliases,
        )
        if aliases.get("name"):
            rows = [row for row in rows if row.get("name") not in (None, "")]
        props[data_prop_for(str(node.get("type") or ""))] = rows
    node["props"] = props
    node["children"] = [
        bind_tree(child, datasets)
        for child in node.get("children") or []
        if isinstance(child, dict)
    ]
    return node
