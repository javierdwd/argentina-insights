"""Generic canvas merge and validation invariants."""

from agent.ui.pipeline import bind_tree, merge_canvas, validate_patch, validate_tree


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
    out = merge_canvas(previous, incoming)
    assert [c["id"] for c in out["children"]] == ["blue", "actas"]
    assert out["type"] == "Stack"


def test_stack_updates_same_id_in_place() -> None:
    previous = _chart("blue", "ds_old")
    incoming = _chart("blue", "ds_new")
    out = merge_canvas(previous, incoming)
    assert out["id"] == "blue"
    assert out["props"]["dataRef"] == "ds_new"


def test_stack_deduplicates_same_widget_and_dataset() -> None:
    previous = _chart("old_model_id", "ds_blue")
    incoming = _chart("new_model_id", "ds_blue")
    out = merge_canvas(previous, incoming)
    assert out["id"] == "new_model_id"
    assert out["props"]["dataRef"] == "ds_blue"


def test_stack_allows_same_widget_for_different_datasets() -> None:
    previous = _chart("blue", "ds_blue")
    incoming = _chart("riesgo", "ds_riesgo")
    out = merge_canvas(previous, incoming)
    assert [c["props"]["dataRef"] for c in out["children"]] == [
        "ds_blue",
        "ds_riesgo",
    ]


def test_validation_rejects_widget_with_missing_dataset() -> None:
    tree = {
        "id": "root",
        "type": "Stack",
        "children": [
            {
                "id": "context",
                "type": "Text",
                "props": {"content": "Contexto"},
            },
            {
                "id": "empty_weather",
                "type": "WeatherUnit",
                "props": {"dataRef": "ds_missing"},
            },
            {
                "id": "news",
                "type": "News",
                "props": {"dataRef": "ds_news"},
            },
        ],
    }
    result = validate_tree(
        tree,
        {"ds_news": {"id": "ds_news", "N": 3, "rows": [{}, {}, {}]}},
    )
    assert not result.valid
    assert any("ds_missing" in error for error in result.errors)


def test_validation_rejects_dataset_from_earlier_turn() -> None:
    tree = {
        "id": "root",
        "type": "Stack",
        "children": [
            _chart("old_weather", "ds_weather"),
            {
                "id": "news",
                "type": "News",
                "props": {"dataRef": "ds_news"},
            },
        ],
    }
    datasets = {
        "ds_weather": {"id": "ds_weather", "N": 1, "rows": [{}]},
        "ds_news": {"id": "ds_news", "N": 3, "rows": [{}, {}, {}]},
    }
    result = validate_tree(
        tree,
        datasets,
        allowed_refs={"ds_news"},
    )
    assert not result.valid
    assert any("not from this turn" in error for error in result.errors)


def test_stack_keeps_grid_as_one_section() -> None:
    previous = _chart("blue", "ds_blue")
    incoming = {
        "id": "pair",
        "type": "Grid",
        "props": {"columns": 2},
        "children": [_chart("a", "ds_a"), _chart("b", "ds_b")],
    }
    out = merge_canvas(previous, incoming)
    assert [c["type"] for c in out["children"]] == ["Chart", "Grid"]


def test_validation_rejects_duplicate_widget_and_dataset() -> None:
    tree = {
        "id": "root",
        "type": "Stack",
        "props": {},
        "children": [_chart("first", "ds_blue"), _chart("second", "ds_blue")],
    }
    datasets = {
        "ds_blue": {
            "id": "ds_blue",
            "status": "hit",
            "N": 1,
            "rows": [{"fecha": "2026-01-01", "valor": 1}],
        }
    }
    result = validate_tree(tree, datasets, allowed_refs={"ds_blue"})
    assert not result.valid
    assert any("duplicate widget/dataRef" in error for error in result.errors)


def test_validation_rejects_widget_already_visible() -> None:
    existing = _chart("old_id", "ds_blue")
    candidate = _chart("new_id", "ds_blue")
    datasets = {
        "ds_blue": {
            "id": "ds_blue",
            "status": "hit",
            "N": 1,
            "rows": [{"fecha": "2026-01-01", "valor": 1}],
        }
    }
    result = validate_tree(
        candidate,
        datasets,
        allowed_refs={"ds_blue"},
        existing_tree=existing,
    )
    assert not result.valid
    assert any("already visible" in error for error in result.errors)


def test_validation_rejects_duplicate_ids_and_authored_rows() -> None:
    tree = {
        "id": "root",
        "type": "Stack",
        "props": {},
        "children": [
            {
                "id": "same",
                "type": "Text",
                "title": "Uno",
                "props": {"content": "A"},
            },
            {
                "id": "same",
                "type": "List",
                "title": "Dos",
                "props": {"dataRef": "ds", "data": [{"value": 1}]},
            },
        ],
    }
    datasets = {"ds": {"status": "hit", "N": 1, "rows": [{"value": 1}]}}
    result = validate_tree(tree, datasets, allowed_refs={"ds"})
    assert not result.valid
    assert any("duplicate node id" in error for error in result.errors)
    assert any("raw rows are forbidden" in error for error in result.errors)


def test_patch_rejects_unknown_target() -> None:
    errors = validate_patch(
        _chart("blue", "ds_blue"),
        {"missing": {"title": "Nuevo"}},
    )
    assert errors == ("patch target 'missing' does not exist",)


def test_generic_binding_applies_mapping_sort_and_limit() -> None:
    tree = {
        "id": "people",
        "type": "PersonCard",
        "title": "Personas",
        "props": {
            "dataRef": "ds_people",
            "fields": {"name": "nombre"},
            "sort": {"key": "nombre", "dir": "asc"},
            "limit": 1,
        },
    }
    datasets = {
        "ds_people": {
            "rows": [
                {"nombre": "Zeta", "foto": "z.jpg"},
                {"nombre": "Alfa", "foto": "a.jpg"},
            ]
        }
    }
    bound = bind_tree(tree, datasets)
    assert bound["props"]["people"] == [{"name": "Alfa", "photoUrl": "a.jpg"}]
    assert "dataRef" not in bound["props"]
