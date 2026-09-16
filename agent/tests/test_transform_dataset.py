"""Tests for transform_dataset unnest_match / project."""

from __future__ import annotations

import json

import pytest

from agent.tools.transform import (
    explode_rows,
    group_count,
    group_duration,
    project_rows,
    run_transform,
    unnest_match,
)


def _actas():
    return [
        {
            "actaId": 1,
            "titulo": "Ley A",
            "fecha": "2026-08-27",
            "resultado": "AFIRMATIVA",
            "votos": [
                {"nombre": "Abad, Maximiliano", "voto": "afirmativo"},
                {"nombre": "Losada, Carolina", "voto": "negativo"},
            ],
        },
        {
            "actaId": 2,
            "titulo": "Ley B",
            "fecha": "2026-08-07",
            "resultado": "AFIRMATIVA",
            "votos": [
                {"nombre": "Losada, Carolina", "voto": "afirmativo"},
                {"nombre": "Kirchner, Alicia", "voto": "negativo"},
            ],
        },
        {
            "actaId": 3,
            "titulo": "Ley C",
            "fecha": "2026-07-01",
            "resultado": "NEGATIVA",
            "votos": [
                {"nombre": "Abad, Maximiliano", "voto": "afirmativo"},
            ],
        },
    ]


def test_unnest_match_lifts_scalar_voto():
    rows = unnest_match(
        _actas(),
        nested="votos",
        where={"nombre": "Losada, Carolina"},
        keep=["actaId", "titulo", "fecha", "resultado"],
        lift=["voto", "nombre"],
        drop_unmatched=True,
    )
    assert len(rows) == 2
    assert all("votos" not in r for r in rows)
    assert rows[0]["voto"] == "negativo"
    assert rows[0]["nombre"] == "Losada, Carolina"
    assert rows[0]["titulo"] == "Ley A"
    assert rows[1]["voto"] == "afirmativo"
    assert rows[1]["actaId"] == 2


def test_unnest_match_accent_insensitive():
    rows = unnest_match(
        _actas(),
        nested="votos",
        where={"nombre": "losada carolina"},
        keep=["actaId", "titulo"],
        lift=["voto"],
        drop_unmatched=True,
    )
    assert len(rows) == 2


def test_unnest_match_drop_unmatched_empty():
    rows = unnest_match(
        _actas(),
        nested="votos",
        where={"nombre": "Nadie, Inventado"},
        keep=["actaId"],
        lift=["voto"],
        drop_unmatched=True,
    )
    assert rows == []


def test_unnest_match_keep_unmatched_null_voto():
    rows = unnest_match(
        _actas(),
        nested="votos",
        where={"nombre": "Nadie, Inventado"},
        keep=["actaId", "titulo"],
        lift=["voto"],
        drop_unmatched=False,
    )
    assert len(rows) == 3
    assert all(r.get("voto") is None for r in rows)


def test_project_rows():
    out = project_rows(_actas(), ["actaId", "titulo"])
    assert out == [
        {"actaId": 1, "titulo": "Ley A"},
        {"actaId": 2, "titulo": "Ley B"},
        {"actaId": 3, "titulo": "Ley C"},
    ]


def test_explode_rows_flattens_every_nested_object():
    rows = explode_rows(
        _actas()[:1],
        nested="votos",
        keep=["actaId", "titulo"],
        lift=["nombre", "voto"],
    )
    assert rows == [
        {
            "actaId": 1,
            "titulo": "Ley A",
            "nombre": "Abad, Maximiliano",
            "voto": "afirmativo",
        },
        {
            "actaId": 1,
            "titulo": "Ley A",
            "nombre": "Losada, Carolina",
            "voto": "negativo",
        },
    ]


def test_group_count_builds_wide_chart_rows():
    votes = [
        {"bloque": "UCR", "voto": "afirmativo"},
        {"bloque": "UCR", "voto": "negativo"},
        {"bloque": "UCR", "voto": "afirmativo"},
        {"bloque": "LLA", "voto": "negativo"},
    ]
    rows = group_count(
        votes,
        group_by=["bloque"],
        category="voto",
        categories=["afirmativo", "negativo", "ausente"],
    )
    assert rows == [
        {"bloque": "UCR", "afirmativo": 2, "negativo": 1, "ausente": 0},
        {"bloque": "LLA", "negativo": 1, "afirmativo": 0, "ausente": 0},
    ]


def test_group_duration_builds_chart_ready_totals():
    terms = [
        {
            "nombre": "President A",
            "partido": "Partido Uno",
            "inicio": "2020-01-01",
            "fin": "2020-01-11",
        },
        {
            "nombre": "President B",
            "partido": "Partido Uno",
            "inicio": "2021-01-01",
            "fin": "2021-01-06",
        },
        {
            "nombre": "President C",
            "partido": "Partido Dos",
            "inicio": "2022-01-01",
            "fin": None,
        },
    ]
    rows = group_duration(
        terms,
        group_by=["partido"],
        start_field="inicio",
        end_field="fin",
        as_of="2022-01-04",
        output_field="dias_acumulados",
    )
    assert rows == [
        {"partido": "Partido Uno", "dias_acumulados": 15, "periods": 2},
        {"partido": "Partido Dos", "dias_acumulados": 3, "periods": 1},
    ]


def test_run_transform_from_datasets_index():
    datasets = {
        "ds_test": {
            "id": "ds_test",
            "path": "/v1/senado/actas",
            "rows": _actas(),
            "keys": ["actaId", "titulo", "fecha", "resultado", "votos"],
            "N": 3,
        }
    }
    rows = run_transform(
        datasets,
        source="ds_test",
        op="unnest_match",
        nested="votos",
        where={"nombre": "Losada"},
        keep=["actaId", "titulo", "fecha"],
        lift=["voto"],
    )
    assert len(rows) == 2
    assert {r["voto"] for r in rows} == {"afirmativo", "negativo"}


def test_run_transform_missing_source():
    with pytest.raises(ValueError, match="not in the index"):
        run_transform({}, source="ds_missing", op="project", fields=["titulo"])


def test_tool_json_roundtrip():
    """Tool return must be JSON list index_datasets can parse."""
    datasets = {
        "ds_test": {
            "id": "ds_test",
            "path": "/v1/senado/actas",
            "rows": _actas(),
            "keys": ["actaId", "titulo", "votos"],
            "N": 3,
        }
    }
    rows = run_transform(
        datasets,
        source="ds_test",
        op="unnest_match",
        nested="votos",
        where={"nombre": "Losada, Carolina"},
        keep=["actaId", "titulo", "fecha", "resultado"],
        lift=["voto", "nombre"],
    )
    payload = json.loads(json.dumps(rows, ensure_ascii=False))
    assert isinstance(payload, list)
    assert payload[0]["voto"] in {"afirmativo", "negativo"}
