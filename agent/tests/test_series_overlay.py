"""derived/series_overlay joins multiple measure datasets on a shared X."""

from __future__ import annotations

from agent.graph import (
    _derived_datasets_for_compose,
    _series_overlay_from_datasets,
)
from agent.series_util import _measure_axes


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


def test_series_overlay_joins_two_dated_measures() -> None:
    datasets = {
        "blue": _ds(
            "/v1/cotizaciones/dolares/blue",
            [
                {"fecha": "2026-02-19", "venta": 1400},
                {"fecha": "2026-02-20", "venta": 1410},
                {"fecha": "2026-02-21", "venta": 1420},
            ],
            casa="blue",
        ),
        "riesgo": _ds(
            "/v1/finanzas/indices/riesgo-pais",
            [
                {"fecha": "2026-02-19", "valor": 1200},
                {"fecha": "2026-02-20", "valor": 1250},
                {"fecha": "2026-02-21", "valor": 1230},
            ],
        ),
    }
    overlay = _series_overlay_from_datasets(datasets)
    assert overlay is not None
    assert overlay["path"] == "derived/series_overlay"
    assert overlay["params"]["x"] == "fecha"
    assert overlay["params"]["x_role"] == "temporal"
    assert "fecha" in overlay["keys"]
    assert len(overlay["keys"]) == 3  # x + 2 series
    assert overlay["N"] == 3
    row = next(r for r in overlay["rows"] if r["fecha"] == "2026-02-20")
    assert 1410 in row.values()
    assert 1250 in row.values()


def test_series_overlay_joins_categorical_x() -> None:
    datasets = {
        "a": _ds(
            "/v1/stats/negativos-por-provincia",
            [
                {"provincia": "CABA", "cantidad": 10},
                {"provincia": "Buenos Aires", "cantidad": 20},
                {"provincia": "Córdoba", "cantidad": 5},
            ],
            label="negativos",
        ),
        "b": _ds(
            "/v1/stats/afirmativos-por-provincia",
            [
                {"provincia": "CABA", "cantidad": 30},
                {"provincia": "Buenos Aires", "cantidad": 40},
                {"provincia": "Córdoba", "cantidad": 15},
            ],
            label="afirmativos",
        ),
    }
    overlay = _series_overlay_from_datasets(datasets)
    assert overlay is not None
    assert overlay["params"]["x"] == "provincia"
    assert overlay["params"]["x_role"] == "categorical"
    assert overlay["N"] == 3
    row = next(r for r in overlay["rows"] if r["provincia"] == "CABA")
    assert 10 in row.values()
    assert 30 in row.values()


def test_series_overlay_skips_without_shared_overlap() -> None:
    datasets = {
        "a": _ds(
            "/v1/a",
            [
                {"mes": "2026-01", "tasa": 1.0},
                {"mes": "2026-02", "tasa": 2.0},
            ],
        ),
        "b": _ds(
            "/v1/b",
            [
                {"mes": "2025-01", "tasa": 3.0},
                {"mes": "2025-02", "tasa": 4.0},
            ],
        ),
    }
    assert _series_overlay_from_datasets(datasets) is None


def test_measure_axes_prefers_temporal_over_categorical() -> None:
    ds = _ds(
        "/v1/fx/blue",
        [
            {"fecha": "2026-02-19", "casa": "blue", "venta": 1400},
            {"fecha": "2026-02-20", "casa": "blue", "venta": 1410},
        ],
        casa="blue",
    )
    axes = _measure_axes(ds)
    assert axes is not None
    assert axes["x_candidates"][0] == "fecha"
    assert axes["y_key"] == "venta"


def test_series_overlay_ffills_sparse_monthly_onto_daily() -> None:
    """Monthly inflación must survive a join onto daily blue (not vanish)."""
    blue_rows = [
        {"fecha": f"2026-02-{day:02d}", "venta": 1400 + day}
        for day in range(3, 28)
    ]
    datasets = {
        "blue": _ds(
            "/v1/cotizaciones/dolares/blue",
            blue_rows,
            casa="blue",
        ),
        "inflacion": _ds(
            "/v1/finanzas/indices/inflacionInteranual",
            [
                {"fecha": "2026-01-31", "valor": 40.0},
                {"fecha": "2026-02-28", "valor": 33.5},
            ],
        ),
    }
    overlay = _series_overlay_from_datasets(datasets)
    assert overlay is not None
    infl_key = next(k for k in overlay["keys"] if k != "fecha" and "infl" in k)
    blue_key = next(k for k in overlay["keys"] if k != "fecha" and k != infl_key)
    filled_infl = [
        r for r in overlay["rows"] if r.get(infl_key) is not None
    ]
    filled_blue = [r for r in overlay["rows"] if r.get(blue_key) is not None]
    # Sparse monthly must be carried onto most daily points.
    assert len(filled_infl) >= len(filled_blue) * 0.8
    mid = next(r for r in overlay["rows"] if r.get(blue_key) is not None)
    assert mid.get(infl_key) in (40.0, 33.5)


def test_series_overlay_skipped_for_single_series() -> None:
    datasets = {
        "blue": _ds(
            "/v1/cotizaciones/dolares/blue",
            [
                {"fecha": "2026-02-19", "venta": 1400},
                {"fecha": "2026-02-20", "venta": 1410},
            ],
            casa="blue",
        ),
    }
    assert _series_overlay_from_datasets(datasets) is None


def test_derived_datasets_includes_series_overlay() -> None:
    datasets = {
        "blue": _ds(
            "/v1/cotizaciones/dolares/blue",
            [
                {"fecha": "2026-02-19", "venta": 1},
                {"fecha": "2026-02-20", "venta": 2},
            ],
            casa="blue",
        ),
        "oficial": _ds(
            "/v1/cotizaciones/dolares/oficial",
            [
                {"fecha": "2026-02-19", "venta": 10},
                {"fecha": "2026-02-20", "venta": 11},
            ],
            casa="oficial",
        ),
    }
    derived = _derived_datasets_for_compose("", datasets)
    assert any(
        str(ds.get("path")) == "derived/series_overlay" for ds in derived.values()
    )
