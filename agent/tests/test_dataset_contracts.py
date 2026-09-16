"""Dataset identity, provenance, and outcome contracts."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.graph import index_datasets_node
from agent.series_util import _dataset_id
from agent.ui.datasets import current_turn_ids, hit_ids


def _messages(content: str) -> list:
    return [
        HumanMessage(content="consulta"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "name": "fetch_argentinadatos",
                    "args": {"path": "/v1/test", "params": {"q": "x"}},
                }
            ],
        ),
        ToolMessage(content=content, tool_call_id="call_1"),
    ]


@pytest.mark.parametrize(
    ("content", "status", "count"),
    [
        (json.dumps([{"value": 1}]), "hit", 1),
        (json.dumps([]), "empty", 0),
        ("No records: nothing matched", "empty", 0),
        ("Error: upstream failed", "error", 0),
    ],
)
def test_index_preserves_structured_outcome(
    content: str,
    status: str,
    count: int,
) -> None:
    messages = _messages(content)
    update = index_datasets_node({"messages": messages, "datasets": {}})
    dataset_id = _dataset_id("/v1/test", {"q": "x"})
    dataset = update["datasets"][dataset_id]
    assert dataset["status"] == status
    assert dataset["N"] == count
    assert (dataset["error"] is not None) is (status == "error")
    assert current_turn_ids(messages) == {dataset_id}
    expected_hits = {dataset_id} if status == "hit" else set()
    assert hit_ids(update["datasets"], {dataset_id}) == expected_hits
