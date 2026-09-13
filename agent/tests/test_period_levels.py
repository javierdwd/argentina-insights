"""Period+series joins: evolution overlay and level aggregates."""

from __future__ import annotations

from agent.graph import (
    _coerce_period_bars_widgets,
    _fallback_tree_for_hits,
    _period_levels_from_datasets,
    _period_overlay_from_datasets,
)


def _ds(path: str, rows: list[dict], **params: object) -> dict:
    keys = list(rows[0].keys()) if rows else []
    return {
        "id": path,
        "path": path,
        "params": params,
        "rows": rows,
        "keys": keys,
        "N": len(rows),
        "date_range": None,
    }


def _presidents() -> dict:
    return _ds(
        "/v1/presidentes",
        [
            {
                "nombre": "Cristina",
                "inicio": "2011-12-10",
                "fin": "2015-12-10",
                "periodoPresidencial": "2011-2015",
            },
            {
                "nombre": "Macri",
                "inicio": "2015-12-10",
                "fin": "2019-12-10",
                "periodoPresidencial": "2015-2019",
            },
            {
                "nombre": "Alberto",
                "inicio": "2019-12-10",
                "fin": "2023-12-10",
                "periodoPresidencial": "2019-2023",
            },
            {
                "nombre": "Milei",
                "inicio": "2023-12-10",
                "fin": None,
                "periodoPresidencial": "2023-2027",
            },
        ],
    )


def _blue() -> dict:
    # Sparse daily-ish points spanning the four windows.
    rows = []
    for day, venta in (
        ("2012-06-01", 5.0),
        ("2014-01-15", 10.0),
        ("2016-03-01", 15.0),
        ("2018-08-20", 40.0),
        ("2020-02-10", 80.0),
        ("2022-11-01", 300.0),
        ("2024-05-01", 1200.0),
        ("2025-01-10", 1400.0),
    ):
        rows.append({"fecha": day, "venta": venta, "compra": venta - 1})
    return _ds("/v1/cotizaciones/dolares/blue", rows, casa="blue")


def test_period_levels_max_per_mandate() -> None:
    datasets = {"p": _presidents(), "b": _blue()}
    levels = _period_levels_from_datasets(datasets)
    assert levels is not None
    assert levels["path"] == "derived/period_levels"
    assert levels["keys"][:3] == ["label", "value", "sublabel"]
    assert "entity" in levels["keys"]
    by_label = {r["label"]: r["value"] for r in levels["rows"]}
    assert by_label["Cristina"] == 10.0
    assert by_label["Macri"] == 40.0
    assert by_label["Alberto"] == 300.0
    assert by_label["Milei"] == 1400.0
    assert all("→" in r["sublabel"] for r in levels["rows"])
    assert all(r.get("entity") == "persona" for r in levels["rows"])
    assert levels["params"].get("entity") == "persona"


def test_period_overlay_still_builds() -> None:
    datasets = {"p": _presidents(), "b": _blue()}
    overlay = _period_overlay_from_datasets(datasets)
    assert overlay is not None
    assert "fecha" in overlay["keys"]
    assert overlay["N"] >= 2


def test_period_overlay_slugs_fernandez_without_dropping_accent() -> None:
    people = _ds(
        "/v1/presidentes",
        [
            {
                "nombre": "Mauricio Macri",
                "inicio": "2015-12-10",
                "fin": "2019-12-10",
            },
            {
                "nombre": "Alberto Fernández",
                "inicio": "2019-12-10",
                "fin": "2023-12-10",
            },
            {
                "nombre": "Javier Milei",
                "inicio": "2023-12-10",
                "fin": None,
            },
        ],
    )
    overlay = _period_overlay_from_datasets({"p": people, "b": _blue()})
    assert overlay is not None
    assert "alberto_fernandez" in overlay["keys"]
    assert "alberto_fern_ndez" not in overlay["keys"]
    filled = [r for r in overlay["rows"] if r.get("alberto_fernandez") is not None]
    assert filled


def test_coerce_chart_series_maps_fernandez_key() -> None:
    from agent.graph import _coerce_chart_series_widgets

    datasets = {
        "ds": {
            "id": "ds",
            "path": "derived/period_overlay",
            "keys": ["fecha", "mauricio_macri", "alberto_fern_ndez", "javier_milei"],
            "rows": [],
            "N": 1,
        }
    }
    tree = {
        "id": "chart",
        "type": "Chart",
        "props": {
            "dataRef": "ds",
            "kind": "line",
            "xKey": "fecha",
            "series": [
                {"key": "mauricio_macri", "label": "Mauricio Macri"},
                {"key": "alberto_fernandez", "label": "Alberto Fernández"},
                {"key": "javier_milei", "label": "Javier Milei"},
            ],
        },
    }
    out = _coerce_chart_series_widgets(tree, datasets)
    keys = [s["key"] for s in out["props"]["series"]]
    assert keys == ["mauricio_macri", "alberto_fern_ndez", "javier_milei"]


def test_coerce_period_bars_retargets_invented_keys() -> None:
    datasets = {
        "p": _presidents(),
        "b": _blue(),
    }
    levels = _period_levels_from_datasets(datasets)
    assert levels is not None
    datasets[levels["id"]] = levels

    tree = {
        "id": "bad",
        "type": "PeriodBars",
        "title": "Máximo blue",
        "props": {
            "labelKey": "periodoPresidencial",
            "valueKey": "venta",
            "sublabelKey": "inicio_fin",
            "dataRef": "b",  # raw FX — wrong shape
            "limit": 4,
        },
    }
    out = _coerce_period_bars_widgets(tree, datasets)
    assert out["props"]["dataRef"] == levels["id"]
    assert out["props"]["labelKey"] == "label"
    assert out["props"]["valueKey"] == "value"
    assert out["props"]["sublabelKey"] == "sublabel"


def test_fallback_tree_uses_period_widgets() -> None:
    datasets = {"p": _presidents(), "b": _blue()}
    levels = _period_levels_from_datasets(datasets)
    overlay = _period_overlay_from_datasets(datasets)
    assert levels is not None and overlay is not None
    bag = {levels["id"]: levels, overlay["id"]: overlay}
    tree = _fallback_tree_for_hits(bag, {levels["id"], overlay["id"]})
    assert tree is not None
    kinds = [child["type"] for child in tree["children"]]
    assert kinds == ["PeriodBars", "Chart"]
    bars, chart = tree["children"]
    assert bars["props"]["dataRef"] == levels["id"]
    assert bars["props"]["labelKey"] == "label"
    assert chart["props"]["dataRef"] == overlay["id"]
    assert chart["props"]["xKey"] == "fecha"
    assert chart["props"]["kind"] == "line"
    assert len(chart["props"]["series"]) >= 2


def test_period_levels_copies_person_fields_without_president_logic() -> None:
    """Any nombre+inicio table (not just presidents) gets entity + extras."""
    people = _ds(
        "/v1/gobernadores",
        [
            {
                "nombre": "Juan Pérez",
                "inicio": "2019-12-10",
                "fin": "2023-12-10",
                "partido": "UCR",
                "imagen": "https://example.com/a.jpg",
            },
            {
                "nombre": "Ana Gómez",
                "inicio": "2023-12-10",
                "fin": None,
                "partido": "LLA",
                "imagen": "https://example.com/b.jpg",
            },
        ],
    )
    series = _ds(
        "/v1/series/emae",
        [
            {"fecha": "2020-06-01", "valor": 100.0},
            {"fecha": "2022-06-01", "valor": 110.0},
            {"fecha": "2023-11-01", "valor": 120.0},
            {"fecha": "2024-06-01", "valor": 130.0},
        ],
        kind="stock",
    )
    levels = _period_levels_from_datasets({"p": people, "s": series})
    assert levels is not None
    by_label = {r["label"]: r for r in levels["rows"]}
    assert by_label["Juan Pérez"]["entity"] == "persona"
    assert by_label["Juan Pérez"]["partido"] == "UCR"
    assert by_label["Ana Gómez"]["partido"] == "LLA"
    assert by_label["Juan Pérez"]["imagen"].startswith("https://")
