"""New widgets append under the current canvas; Limpiar is the wipe."""

from agent.graph import _stack_onto_canvas


def _chart(node_id: str, ref: str) -> dict:
    return {
        "id": node_id,
        "type": "Chart",
        "title": node_id,
        "props": {"dataRef": ref},
    }


def test_stack_appends_new_widget_below_existing() -> None:
    previous = {"id": "root", "type": "Stack", "children": [_chart("blue", "ds_blue")]}
    incoming = _chart("actas", "ds_actas")
    out = _stack_onto_canvas(previous, incoming)
    assert [c["id"] for c in out["children"]] == ["blue", "actas"]
    assert out["type"] == "Stack"


def test_stack_updates_same_id_in_place() -> None:
    previous = _chart("blue", "ds_old")
    incoming = _chart("blue", "ds_new")
    out = _stack_onto_canvas(previous, incoming)
    assert out["id"] == "blue"
    assert out["props"]["dataRef"] == "ds_new"


def test_stack_keeps_grid_as_one_section() -> None:
    previous = _chart("blue", "ds_blue")
    incoming = {
        "id": "pair",
        "type": "Grid",
        "props": {"columns": 2},
        "children": [_chart("a", "ds_a"), _chart("b", "ds_b")],
    }
    out = _stack_onto_canvas(previous, incoming)
    assert [c["type"] for c in out["children"]] == ["Chart", "Grid"]
