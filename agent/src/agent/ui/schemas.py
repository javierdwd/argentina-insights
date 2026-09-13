"""Pydantic schemas for the UI tree produced by the compose_ui node.

The LLM is constrained to ``ComposeOutput`` via ``with_structured_output``.
``UINode`` is a generic container; widget-specific props are validated by the
frontend Zod schemas (Chart.schema.ts, Metric.schema.ts, etc.).

These schemas are intentionally kept lean so that adding a new widget only
requires a new entry in the catalog and a new frontend schema — not a new
Pydantic class here.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class UINode(BaseModel):
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
            "dl, dt, dd, strong, em, and SVG svg/g/path/line/…) are allowed "
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
            "For Chart: include dataRef, kind, xKey, series.  "
            "Never include raw data rows — use dataRef."
        ),
    )
    children: list["UINode"] = Field(
        default_factory=list,
        description="Child nodes for container widgets (Stack, Grid, etc.).",
    )


def _coerce_tree(value: Any) -> Any:
    """Tolerate common LLM mistakes for ``tree``.

    Models sometimes emit a bare list of widgets (or worse, List sort
    fragments like ``{id, dir}``) instead of a single root ``UINode``.
    Wrap real widgets in a Stack; drop junk so compose can still return a brief.
    """
    if value is None or isinstance(value, UINode):
        return value
    if isinstance(value, list):
        nodes = [
            item
            for item in value
            if isinstance(item, dict) and isinstance(item.get("type"), str)
        ]
        if not nodes:
            return None
        if len(nodes) == 1:
            return nodes[0]
        return {
            "id": "root",
            "type": "Stack",
            "props": {"direction": "vertical"},
            "children": nodes,
        }
    if isinstance(value, dict):
        if not isinstance(value.get("type"), str):
            return None
        return value
    return None


class ComposeOutput(BaseModel):
    """Structured output from the compose_ui LLM node."""

    brief: str = Field(
        description=(
            "Chat reply in Spanish. "
            "If the canvas changed: (1) one sentence confirming what is on "
            "screen; (2) then 2–3 next analyses as a clickable block:\n"
            "[[actions]]\n"
            "executable Spanish ask\n"
            "second ask\n"
            "[[/actions]]\n"
            "Each action line must be grounded in a concrete hook from this "
            "turn (date, peak, person, bill) — not chart cosmetics. "
            "If the canvas did NOT change: answer here with inline "
            "[boton]executable Spanish ask[/boton] offers in the sentence. "
            "No markdown, no JSON, no [[next]] tags, no /v1/ paths, "
            "no derived/ dataset names. "
            "[[actions]] is allowed and required when offering next moves."
        )
    )
    tree: UINode | None = Field(
        default=None,
        description=(
            "ONE root UINode (often a Stack with children), never a bare list. "
            "Full UI tree replacing the canvas. Use ONLY when building from "
            "scratch or making a STRUCTURAL change (add/remove/reorder widgets). "
            "Leave null when using `patch` instead, or when leaving the canvas "
            "unchanged (chitchat, clarification, error without a visual)."
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

    @field_validator("tree", mode="before")
    @classmethod
    def _normalize_tree(cls, value: Any) -> Any:
        return _coerce_tree(value)
