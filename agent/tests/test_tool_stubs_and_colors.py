"""Regression: indexed ToolMessage stubs must still count as fetch hits."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.graph import _stub_row_count, _turn_had_hits


def test_stub_row_count_parses_indexed_header() -> None:
    stub = (
        "Indexed id=abc path=/v1/presidentes rows=12 dates=2007..2026 "
        "keys=[nombre,inicio] — full rows in datasets index; use sample there."
    )
    assert _stub_row_count(stub) == 12
    assert _stub_row_count('[{"nombre":"X"}]') is None


def test_turn_had_hits_uses_datasets_when_messages_are_stubs() -> None:
    messages = [
        HumanMessage(content="blue por mandato"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "name": "fetch_argentinadatos",
                    "args": {"path": "/v1/presidentes", "params": {}},
                }
            ],
        ),
        ToolMessage(
            content="Indexed id=ds1 path=/v1/presidentes rows=12 dates=— keys=[nombre]",
            tool_call_id="call_1",
            id="tm1",
        ),
    ]
    datasets = {
        "ds1": {
            "id": "ds1",
            "path": "/v1/presidentes",
            "params": {},
            "rows": [{"nombre": "A"}],
            "keys": ["nombre"],
            "N": 12,
            "date_range": None,
        }
    }
    assert _turn_had_hits(messages, datasets) is True
    assert _turn_had_hits(messages, {}) is True  # stub rows=12


def test_turn_had_hits_false_for_empty_stub() -> None:
    messages = [
        HumanMessage(content="x"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "name": "fetch_argentinadatos",
                    "args": {"path": "/v1/presidentes", "params": {}},
                }
            ],
        ),
        ToolMessage(
            content="Indexed id=ds1 path=/v1/presidentes rows=0 dates=— keys=[]",
            tool_call_id="call_1",
            id="tm1",
        ),
    ]
    assert _turn_had_hits(messages, {"ds1": {"id": "ds1", "N": 0}}) is False
