"""Composer validation and single-repair behavior."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from agent.graph import compose_ui_node
from agent.ui.pipeline import validate_tree
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


def test_long_format_chart_requires_series_by_and_value_key() -> None:
    dataset = {
        "ds_stats": {
            "status": "hit",
            "rows": [
                {
                    "season": "2024",
                    "team": "River Plate",
                    "pointsPerGame": 2.1,
                },
                {
                    "season": "2024",
                    "team": "Boca Juniors",
                    "pointsPerGame": 1.7,
                },
            ],
        }
    }
    invalid = {
        "id": "comparison",
        "type": "Chart",
        "title": "Comparación",
        "props": {
            "dataRef": "ds_stats",
            "kind": "line",
            "xKey": "season",
            "series": [
                {"key": "River Plate", "label": "River Plate"},
                {"key": "Boca Juniors", "label": "Boca Juniors"},
            ],
        },
    }
    result = validate_tree(invalid, dataset)
    assert any("seriesBy" in error for error in result.errors)

    valid = {
        **invalid,
        "props": {
            **invalid["props"],
            "seriesBy": "team",
            "valueKey": "pointsPerGame",
        },
    }
    assert validate_tree(valid, dataset).errors == ()

    split = {
        "id": "home_away",
        "type": "Stack",
        "props": {"gap": "md"},
        "children": [
            {
                "id": team.lower().replace(" ", "_"),
                "type": "Chart",
                "title": f"{team}: local y visitante",
                "props": {
                    "dataRef": "ds_stats",
                    "where": {"team": team},
                    "kind": "line",
                    "xKey": "season",
                    "series": [
                        {"key": "pointsPerGame", "label": "Puntos por partido"},
                    ],
                },
            }
            for team in ("River Plate", "Boca Juniors")
        ],
    }
    assert validate_tree(split, dataset).errors == ()


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
    with pytest.raises(ValidationError):
        ComposeOutput(
            brief="Demasiadas acciones",
            actions=["Una", "Dos", "Tres", "Cuatro"],
        )


def test_compose_schema_normalizes_flattened_host_node_shorthand() -> None:
    output = ComposeOutput.model_validate(
        {
            "brief": "Mapa listo",
            "tree": {
                "id": "relationship_map",
                "type": "Box",
                "children": [
                    {
                        "type": "svg",
                        "viewBox": "0 0 400 240",
                        "className": "w-full h-auto",
                        "children": [
                            {
                                "type": "circle",
                                "cx": "120",
                                "cy": "100",
                                "r": "32",
                                "fill": "#2563eb",
                            },
                            {
                                "type": "text",
                                "x": "120",
                                "y": "150",
                                "text": "Persona",
                                "textAnchor": "middle",
                            },
                            {
                                "type": "image",
                                "x": "96",
                                "y": "76",
                                "width": "48",
                                "height": "48",
                                "href": "https://example.com/persona.jpg",
                            },
                        ],
                    }
                ],
            },
        }
    )

    tree = output.tree.model_dump(exclude_none=True)
    svg = tree["children"][0]
    assert svg["id"].startswith("auto_svg_")
    assert svg["props"]["viewBox"] == "0 0 400 240"
    assert svg["props"]["className"] == "w-full h-auto"
    assert svg["children"][0]["props"]["cx"] == "120"
    assert svg["children"][1]["props"]["text"] == "Persona"
    assert svg["children"][2]["type"] == "image"
    assert validate_tree(tree, {}).errors == ()


def test_box_accepts_nested_semantic_html_table() -> None:
    tree = {
        "id": "authored_comparison",
        "type": "Box",
        "props": {"className": "overflow-x-auto"},
        "children": [
            {
                "id": "comparison_table",
                "type": "table",
                "props": {"className": "min-w-full border-collapse"},
                "children": [
                    {
                        "id": "comparison_head",
                        "type": "thead",
                        "props": {},
                        "children": [
                            {
                                "id": "comparison_head_row",
                                "type": "tr",
                                "props": {},
                                "children": [
                                    {
                                        "id": "comparison_heading",
                                        "type": "th",
                                        "props": {"text": "Alternativa"},
                                        "children": [],
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "id": "comparison_body",
                        "type": "tbody",
                        "props": {},
                        "children": [],
                    },
                ],
            }
        ],
    }

    assert validate_tree(tree, {}).errors == ()


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


def test_compose_serializes_typed_actions_without_language_heuristics(
    monkeypatch,
) -> None:
    model = _StructuredModel(
        [
            ComposeOutput(
                brief="Organicé los resultados en el canvas.",
                actions=["Contrastá este período con la semana anterior"],
                tree={
                    "id": "blue",
                    "type": "Chart",
                    "title": "Dólar blue",
                    "props": {"dataRef": "ds_blue"},
                },
                patch=None,
            ),
        ]
    )
    monkeypatch.setattr("agent.graph.get_model", lambda _: _Model(model))
    update = compose_ui_node(
        {
            "query_type": "ui",
            "messages": [HumanMessage(content="armá una tabla")],
            "datasets": _dataset(),
            "ui_tree": None,
            "ui_tree_unbound": None,
            "respond_note": "",
        }
    )
    assert len(model.calls) == 1
    assert update["ui_tree"]["id"] == "blue"
    assert (
        "[[actions]]\nContrastá este período con la semana anterior\n[[/actions]]"
        in update["messages"][0].content
    )


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


def test_repair_prompt_resolves_vote_grain_and_required_province_map(
    monkeypatch,
) -> None:
    datasets = {
        "ds_cross": {
            "id": "ds_cross",
            "path": "derived/votos_por_bloque_provincia",
            "params": {},
            "rows": [
                {
                    "bloque": "A",
                    "provincia": "Córdoba",
                    "afirmativo": 1,
                    "negativo": 0,
                },
                {
                    "bloque": "A",
                    "provincia": "Santa Fe",
                    "afirmativo": 1,
                    "negativo": 0,
                },
            ],
            "keys": ["bloque", "provincia", "afirmativo", "negativo"],
            "N": 2,
            "status": "hit",
        },
        "ds_votes": {
            "id": "ds_votes",
            "path": "derived/votos_nominales",
            "params": {},
            "rows": [
                {
                    "nombre": "Uno",
                    "bloque": "A",
                    "provincia": "Córdoba",
                    "voto": "AFIRMATIVO",
                },
                {
                    "nombre": "Dos",
                    "bloque": "A",
                    "provincia": "Santa Fe",
                    "voto": "NEGATIVO",
                },
            ],
            "keys": ["nombre", "bloque", "provincia", "voto"],
            "N": 2,
            "status": "hit",
        },
    }
    model = _StructuredModel(
        [
            ComposeOutput(
                brief="Reconstruí la votación.",
                tree={
                    "id": "votacion",
                    "type": "Chart",
                    "title": "Votos por bloque",
                    "props": {
                        "dataRef": "ds_cross",
                        "kind": "bar",
                        "xKey": "bloque",
                        "series": [
                            {"key": "afirmativo", "label": "Afirmativo"},
                            {"key": "negativo", "label": "Negativo"},
                        ],
                    },
                },
            ),
            ComposeOutput(
                brief="Reconstruí la votación por bloque y provincia.",
                tree={
                    "id": "votacion",
                    "type": "Stack",
                    "children": [
                        {
                            "id": "votos_bloque",
                            "type": "Chart",
                            "title": "Votos por bloque",
                            "props": {
                                "dataRef": "ds_votes",
                                "kind": "bar",
                                "xKey": "bloque",
                                "series": [
                                    {"key": "AFIRMATIVO", "label": "Afirmativo"},
                                    {"key": "NEGATIVO", "label": "Negativo"},
                                ],
                            },
                        },
                        {
                            "id": "votos_provincia",
                            "type": "ProvinceMap",
                            "title": "Votos negativos por provincia",
                            "props": {
                                "dataRef": "ds_votes",
                                "nameKey": "provincia",
                                "valueKey": "NEGATIVO",
                            },
                        },
                    ],
                },
            ),
        ]
    )
    monkeypatch.setattr("agent.graph.get_model", lambda _: _Model(model))

    update = compose_ui_node(
        {
            "query_type": "data",
            "messages": [
                HumanMessage(content="Mostrá cómo votó cada bloque y provincia")
            ],
            "datasets": datasets,
            "ui_tree": None,
            "ui_tree_unbound": None,
            "respond_note": "Hay dos votos nominales.",
        }
    )

    assert len(model.calls) == 2
    repair_prompt = model.calls[1][-1].content
    assert "compatible data shape or selection" in repair_prompt
    assert "required widget types" in repair_prompt
    assert [child["type"] for child in update["ui_tree"]["children"]] == [
        "Chart",
        "ProvinceMap",
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
