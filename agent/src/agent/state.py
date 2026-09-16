"""LangGraph state definition for the Argentina Insights agent.

MessagesState provides the built-in `messages` field with an append reducer.
Custom fields are added here as the graph grows.
"""

from __future__ import annotations

from typing import Annotated

from langgraph.graph import MessagesState


def _merge_datasets(a: dict, b: dict) -> dict:
    """Merge two dataset dicts; newer entries overwrite older ones."""
    return {**a, **b}


class AgentState(MessagesState):
    """Graph state.

    Attributes:
        messages:       Conversation history (inherited from MessagesState).
        query_type:     Domain label assigned by classify node.
                        One of: "ui" | "data"
                        Legacy values finance/politics/unknown are treated as data.
        ui_tree:        Bound canvas tree for the client (dict | None).
                        Replace reducer: last write wins.  Written by
                        bind_data after resolving dataRefs; compose_ui only
                        updates ``ui_tree_unbound`` so the client never sees
                        an unbound mid-stream tree.
        datasets:       Dataset store keyed by dataset id.  Merge reducer:
                        accumulates across tool calls within a turn.
                        Each record includes id, path, params, rows, keys, N,
                        date_range, status (hit|empty|error), and error.
        has_tool_calls: Routing signal set by respond_node.  True when the LLM
                        just emitted tool calls; False when it produced its final
                        (silent) response.
        skip_compose:   Routing signal set by respond_node.  True when it answered
                        directly with no data fetched this turn (clarifying
                        question / chitchat) — that message IS the final answer;
                        the graph ends instead of routing to compose_ui.
        respond_note:   Factual note from respond after a successful fetch turn.
                        Not shown in chat; compose reads it for aggregates the
                        dataset index cannot show (compose only sees samples).
    """

    query_type: str
    ui_tree: dict | None
    ui_tree_unbound: dict | None  # pre-bind version (keeps dataRef); used by compose_ui
    datasets: Annotated[dict, _merge_datasets]
    has_tool_calls: bool
    skip_compose: bool
    respond_note: str
