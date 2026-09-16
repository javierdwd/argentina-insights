"""Composer validation and single-repair behavior."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from agent.graph import compose_ui_node
from agent.ui.schemas import ComposeOutput


class _StructuredModel:
    def __init__(self, outputs: list[ComposeOutput]) -> None:
        self.outputs = iter(outputs)
        self.calls: list[list] = []

    def invoke(self, messages: list, config: dict) -> ComposeOutput:
        self.calls.append(messages)
        return next(self.outputs)


class _Model:
    def __init__(self, structured: _StructuredModel) -> None:
        self.structured = structured

    def with_structured_output(self, *_: object, **__: object) -> _StructuredModel:
        return self.structured


def _dataset() -> dict:
    return {
        "ds_blue": {
            "id": "ds_blue",
            "path": "/v1/cotizaciones/dolares/blue",
            "params": {},
            "rows": [{"fecha": "2026-09-15", "venta": 1500}],
            "keys": ["fecha", "venta"],
            "N": 1,
            "date_range": "2026-09-15",
            "status": "hit",
            "error": None,
        }
    }


def test_compose_schema_rejects_malformed_or_ambiguous_mutations() -> None:
    with pytest.raises(ValidationError):
        ComposeOutput.model_validate(
            {
                "brief": "mal",
                "tree": [{"id": "x", "type": "Text", "props": {}}],
            }
        )
    with pytest.raises(ValidationError):
        ComposeOutput(
            brief="mal",
            tree={"id": "x", "type": "Text", "title": "X", "props": {}},
            patch={"x": {"title": "Y"}},
        )


def test_invalid_tree_is_repaired_once(monkeypatch) -> None:
    model = _StructuredModel(
        [
            ComposeOutput(
                brief="Primer intento",
                tree={
                    "id": "blue",
                    "type": "Chart",
                    "props": {"dataRef": "ds_blue"},
                },
            ),
            ComposeOutput(
                brief="Blue actualizado",
                tree={
                    "id": "blue",
                    "type": "Chart",
                    "title": "Dólar blue",
                    "props": {"dataRef": "ds_blue"},
                },
            ),
        ]
    )
    monkeypatch.setattr("agent.graph.get_model", lambda _: _Model(model))
    update = compose_ui_node(
        {
            "query_type": "ui",
            "messages": [HumanMessage(content="mostrá el blue")],
            "datasets": _dataset(),
            "ui_tree": None,
            "ui_tree_unbound": None,
            "respond_note": "",
        }
    )
    assert len(model.calls) == 2
    assert update["ui_tree"]["title"] == "Dólar blue"
    assert "validation error" in model.calls[1][-1].content


def test_semantic_duplicate_is_repaired_as_patch(monkeypatch) -> None:
    existing = {
        "id": "blue",
        "type": "Chart",
        "title": "Dólar blue",
        "props": {"dataRef": "ds_blue"},
    }
    model = _StructuredModel(
        [
            ComposeOutput(
                brief="Duplicado",
                tree={
                    "id": "otro_blue",
                    "type": "Chart",
                    "title": "Blue de hoy",
                    "props": {"dataRef": "ds_blue"},
                },
            ),
            ComposeOutput(
                brief="Actualicé el título",
                tree=None,
                patch={"blue": {"title": "Blue de hoy"}},
            ),
        ]
    )
    monkeypatch.setattr("agent.graph.get_model", lambda _: _Model(model))
    update = compose_ui_node(
        {
            "query_type": "ui",
            "messages": [HumanMessage(content="actualizá el blue")],
            "datasets": _dataset(),
            "ui_tree": existing,
            "ui_tree_unbound": existing,
            "respond_note": "",
        }
    )
    assert len(model.calls) == 2
    assert update["ui_tree"]["id"] == "blue"
    assert update["ui_tree"]["title"] == "Blue de hoy"


def test_mixed_duplicate_and_new_widget_is_pruned_without_repair(monkeypatch) -> None:
    datasets = {
        "ds_geo": {
            "id": "ds_geo",
            "path": "/v1/diputados/votos",
            "params": {},
            "rows": [{"provincia": "Córdoba", "negativo": 2}],
            "keys": ["provincia", "negativo"],
            "N": 1,
            "status": "hit",
        },
        "ds_blocs": {
            "id": "ds_blocs",
            "path": "derived/votos_por_bloque",
            "params": {},
            "rows": [{"bloque": "A", "afirmativo": 3, "negativo": 2}],
            "keys": ["bloque", "afirmativo", "negativo"],
            "N": 1,
            "status": "hit",
        },
    }
    existing = {
        "id": "desglose_provincial",
        "type": "ProvinceMap",
        "title": "Votación por provincia",
        "props": {
            "dataRef": "ds_geo",
            "nameKey": "provincia",
            "valueKey": "negativo",
        },
    }
    model = _StructuredModel(
        [
            ComposeOutput(
                brief="Incorporé el cruce por bloque.",
                tree={
                    "id": "cruce",
                    "type": "Stack",
                    "children": [
                        {
                            "id": "mapa_repetido",
                            "type": "ProvinceMap",
                            "title": "Votación por provincia",
                            "props": {
                                "dataRef": "ds_geo",
                                "nameKey": "provincia",
                                "valueKey": "negativo",
                            },
                        },
                        {
                            "id": "bloques",
                            "type": "Chart",
                            "title": "Votos por bloque",
                            "props": {
                                "dataRef": "ds_blocs",
                                "kind": "bar",
                                "xKey": "bloque",
                                "series": [
                                    {"key": "afirmativo", "label": "Afirmativo"},
                                    {"key": "negativo", "label": "Negativo"},
                                ],
                            },
                        },
                    ],
                },
            )
        ]
    )
    monkeypatch.setattr("agent.graph.get_model", lambda _: _Model(model))

    update = compose_ui_node(
        {
            "query_type": "ui",
            "messages": [
                HumanMessage(
                    content="Cruzá la votación por provincia con cada bloque"
                )
            ],
            "datasets": datasets,
            "ui_tree": existing,
            "ui_tree_unbound": existing,
            "respond_note": "",
        }
    )

    assert len(model.calls) == 1
    children = update["ui_tree"]["children"]
    assert [child["id"] for child in children] == [
        "desglose_provincial",
        "bloques",
    ]


def test_failed_repair_keeps_previous_canvas(monkeypatch) -> None:
    existing = {
        "id": "blue",
        "type": "Chart",
        "title": "Dólar blue",
        "props": {"dataRef": "ds_blue"},
    }
    invalid = ComposeOutput(
        brief="Mostré datos",
        tree={
            "id": "ghost",
            "type": "Chart",
            "title": "Inventado",
            "props": {"dataRef": "ds_missing"},
        },
    )
    model = _StructuredModel([invalid, invalid])
    monkeypatch.setattr("agent.graph.get_model", lambda _: _Model(model))
    update = compose_ui_node(
        {
            "query_type": "ui",
            "messages": [HumanMessage(content="cambiá el gráfico")],
            "datasets": _dataset(),
            "ui_tree": existing,
            "ui_tree_unbound": existing,
            "respond_note": "",
        }
    )
    assert len(model.calls) == 2
    assert "ui_tree" not in update
    assert "forma segura" in update["messages"][0].content
