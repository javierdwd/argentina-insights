"""Pydantic schemas for the UI tree produced by the compose_ui node.

The LLM is constrained to ``ComposeOutput`` via ``with_structured_output``.
``UINode`` is a generic container; widget-specific props are validated by the
frontend Zod schemas (Chart.schema.ts, Metric.schema.ts, etc.).

These schemas are intentionally kept lean so that adding a new widget only
requires a new entry in the catalog and a new frontend schema — not a new
Pydantic class here.
"""

from __future__ import annotations

import hashlib
import json
import re

from pydantic import BaseModel, ConfigDict, Field, model_validator


class UINode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    """A single node in the UI tree.

    ``title`` is rendered by DynamicRenderer above the component — not inside
    it.  This makes it universal across widget types (Chart, Card, List, etc.)
    without each widget implementing its own heading.
    """

    id: str = Field(
        description=(
            "Short, stable, snake_case identifier, e.g. 'fx_aug_blue'. "
            "Preserve on mutation so the frontend can key on it."
        )
    )
    type: str = Field(
        description=(
            "Widget type key. Prefer a catalog type (Metric, Text, Chart, "
            "Stack, Box, …). Host tags (div, p, span, h2, h3, ul, ol, li, "
            "dl, dt, dd, strong, em, and SVG svg/g/path/line/image/…) are allowed "
            "ONLY as children of Box."
        )
    )
    title: str | None = Field(
        default=None,
        description=(
            "Heading rendered above the widget by the renderer — not by the "
            "component itself.  Required for all leaf widgets.  "
            "Examples: 'Dólar Blue durante agosto', 'Comparación créditos UVA'."
        ),
    )
    props: dict = Field(
        default_factory=dict,
        description=(
            "Widget-specific props.  See the catalog for allowed fields per type. "
            "ALL host attributes such as text, className, x, y, fill and viewBox "
            "must be nested inside this props object, never beside id/type. "
            "For Chart: include dataRef, kind, xKey, series.  "
            "Any data-bound widget may use where={field: value} to select rows. "
            "Never include raw data rows — use dataRef."
        ),
    )
    children: list["UINode"] = Field(
        default_factory=list,
        description="Child nodes for container widgets (Stack, Grid, etc.).",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_model_shorthand(cls, value: object) -> object:
        """Recover common model shorthand before strict schema validation."""
        if not isinstance(value, dict):
            return value

        node = dict(value)
        structural = {"id", "type", "title", "props", "children"}
        props = node.get("props")
        props = dict(props) if isinstance(props, dict) else {}
        for key in list(node):
            if key not in structural:
                props.setdefault(key, node.pop(key))
        node["props"] = props

        if not isinstance(node.get("id"), str) or not node["id"].strip():
            kind = re.sub(r"[^a-z0-9]+", "_", str(node.get("type") or "node").casefold())
            payload = json.dumps(
                {
                    "type": node.get("type"),
                    "title": node.get("title"),
                    "props": props,
                    "children": node.get("children") or [],
                },
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]
            node["id"] = f"auto_{kind.strip('_') or 'node'}_{digest}"
        return node


class ComposeOutput(BaseModel):
    """Structured output from the compose_ui LLM node."""

    model_config = ConfigDict(extra="forbid")

    brief: str = Field(
        description=(
            "Plain Spanish chat reply only. If the canvas changed, briefly "
            "confirm what is on screen; otherwise answer directly. Do not "
            "include actions, buttons, markdown, JSON, protocol tags, /v1/ "
            "paths, tool names, or derived dataset names here."
        )
    )
    actions: list[str] = Field(
        default_factory=list,
        max_length=3,
        description=(
            "Zero to three executable Spanish follow-up requests. Each item "
            "must be grounded in a concrete hook from this turn and must not "
            "contain markup or protocol tags. Keep facts and explanations in "
            "brief, never in this list."
        ),
    )
    tree: UINode | None = Field(
        default=None,
        description=(
            "ONE root UINode (often a Stack with children), never a bare list. "
            "Emit only genuinely new widgets for this turn; they are merged into "
            "the current canvas. Never repeat information already visible. Use "
            "`patch` with the existing node id when updating an existing widget. "
            "Leave null when the canvas should remain unchanged."
        ),
    )
    patch: dict[str, dict] | None = Field(
        default=None,
        description=(
            "Cheaper alternative to `tree` for tweaking widgets that ALREADY "
            "exist on the canvas, without restating the rest of the tree: "
            "{node_id: {title?, props?}}. `props` is shallow-merged into that "
            "node's existing props — include only the fields that changed, "
            "plus any nested array/object you're modifying in full (e.g. "
            "changing one series' color still needs that node's whole `series` "
            "array, but none of the other nodes). Use this for color/kind/label "
            "tweaks on 1-2 existing widgets. Ignored when `tree` is set; never "
            "set both."
        ),
    )

    @model_validator(mode="after")
    def _exclusive_mutation(self) -> "ComposeOutput":
        if self.tree is not None and self.patch:
            raise ValueError("tree and patch are mutually exclusive")
        if self.patch == {}:
            raise ValueError("patch cannot be empty")
        return self
