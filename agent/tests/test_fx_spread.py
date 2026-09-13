"""derived/fx_spread joins two FX house series into spread ARS + %."""

from __future__ import annotations

from agent.graph import _derived_datasets_for_compose, _fx_spread_from_datasets


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


def test_fx_spread_blue_vs_oficial() -> None:
    datasets = {
        "blue": _ds(
            "/v1/cotizaciones/dolares/blue",
            [
                {"fecha": "2026-08-14", "venta": 1400},
                {"fecha": "2026-08-15", "venta": 1415},
                {"fecha": "2026-08-16", "venta": 1420},
            ],
            casa="blue",
        ),
        "oficial": _ds(
            "/v1/cotizaciones/dolares/oficial",
            [
                {"fecha": "2026-08-14", "venta": 1385},
                {"fecha": "2026-08-15", "venta": 1400},
                {"fecha": "2026-08-16", "venta": 1405},
            ],
            casa="oficial",
        ),
    }
    spread = _fx_spread_from_datasets(datasets)
    assert spread is not None
    assert spread["path"] == "derived/fx_spread"
    assert spread["params"]["a"] == "blue"
    assert spread["params"]["b"] == "oficial"
    assert "spread" in spread["keys"]
    assert "spread_pct" in spread["keys"]
    assert spread["N"] == 3
    row = next(r for r in spread["rows"] if r["fecha"] == "2026-08-15")
    assert row["spread"] == 15.0
    assert abs(row["spread_pct"] - (15.0 / 1400.0 * 100.0)) < 1e-6


def test_fx_spread_requires_overlap() -> None:
    datasets = {
        "blue": _ds(
            "/v1/cotizaciones/dolares/blue",
            [
                {"fecha": "2026-08-14", "venta": 1400},
                {"fecha": "2026-08-15", "venta": 1415},
            ],
            casa="blue",
        ),
        "oficial": _ds(
            "/v1/cotizaciones/dolares/oficial",
            [
                {"fecha": "2026-07-01", "venta": 1000},
                {"fecha": "2026-07-02", "venta": 1001},
            ],
            casa="oficial",
        ),
    }
    assert _fx_spread_from_datasets(datasets) is None


def test_derived_includes_fx_spread() -> None:
    datasets = {
        "blue": _ds(
            "/v1/cotizaciones/dolares/blue",
            [
                {"fecha": "2026-08-14", "venta": 10},
                {"fecha": "2026-08-15", "venta": 12},
            ],
            casa="blue",
        ),
        "oficial": _ds(
            "/v1/cotizaciones/dolares/oficial",
            [
                {"fecha": "2026-08-14", "venta": 8},
                {"fecha": "2026-08-15", "venta": 9},
            ],
            casa="oficial",
        ),
    }
    derived = _derived_datasets_for_compose("", datasets)
    assert any(str(ds.get("path")) == "derived/fx_spread" for ds in derived.values())
