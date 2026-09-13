"""REM curated aliases + vs-real join."""

from __future__ import annotations

from typing import Any

import pytest

from agent.catalog import catalog
from agent.proxy import ProxyError, resolve
from agent.proxy import rem
from agent.proxy.cache import cache
from agent.proxy.upstream import UpstreamError


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


SAMPLE_INDEX = [
    "/finanzas/rem/2024/03",
    "/finanzas/rem/2024/02",
    "/finanzas/rem/2024/01",
]

IPC = "Precios minoristas (IPC nivel general-Nacional; INDEC)"


def _rem_row(
    *,
    informe: str,
    periodo: str,
    periodo_desde: str,
    mediana: float,
    muestra: str = "todos",
) -> dict[str, Any]:
    return {
        "informe": informe,
        "fecha": f"{informe}-01",
        "muestra": muestra,
        "indicador": IPC,
        "periodo": periodo,
        "periodoTipo": "mensual",
        "periodoDesde": periodo_desde,
        "periodoHasta": periodo_desde[:8] + "28",
        "unidad": "var. % mensual",
        "mediana": mediana,
        "promedio": mediana,
    }


INFORMES: dict[str, list[dict[str, Any]]] = {
    "2024-01": [
        _rem_row(
            informe="2024-01",
            periodo="Jan-24",
            periodo_desde="2024-01-01",
            mediana=20.0,
        ),
        _rem_row(
            informe="2024-01",
            periodo="Feb-24",
            periodo_desde="2024-02-01",
            mediana=15.0,
        ),
    ],
    "2024-02": [
        _rem_row(
            informe="2024-02",
            periodo="Feb-24",
            periodo_desde="2024-02-01",
            mediana=14.0,
        ),
        _rem_row(
            informe="2024-02",
            periodo="Mar-24",
            periodo_desde="2024-03-01",
            mediana=12.0,
        ),
    ],
    "2024-03": [
        _rem_row(
            informe="2024-03",
            periodo="Mar-24",
            periodo_desde="2024-03-01",
            mediana=11.0,
        ),
    ],
}

INFLACION = [
    {"fecha": "2024-01-31", "valor": 20.6},
    {"fecha": "2024-02-29", "valor": 13.2},
    {"fecha": "2024-03-31", "valor": 11.0},
]


def test_catalog_lists_rem_routes() -> None:
    paths = set(catalog.paths())
    assert "/v1/rem" in paths
    assert "/v1/rem/ultimo" in paths
    assert "/v1/rem/informe" in paths
    assert "/v1/rem/{alias}" in paths
    assert "/v1/rem/vs-real/{alias}" in paths


def test_catalog_match_prefers_vs_real_over_alias() -> None:
    matched = catalog.match("/v1/rem/vs-real/ipc")
    assert matched is not None
    op, params = matched
    assert op.path == "/v1/rem/vs-real/{alias}"
    assert params["alias"] == "ipc"


def test_filter_rows_by_alias() -> None:
    spec = rem.get_alias("ipc")
    assert spec is not None
    rows = rem.filter_rows(
        [
            _rem_row(
                informe="2024-01",
                periodo="Jan-24",
                periodo_desde="2024-01-01",
                mediana=1.0,
            ),
            {
                **_rem_row(
                    informe="2024-01",
                    periodo="Jan-24",
                    periodo_desde="2024-01-01",
                    mediana=2.0,
                ),
                "indicador": "Tipo de cambio nominal",
            },
            _rem_row(
                informe="2024-01",
                periodo="Jan-24",
                periodo_desde="2024-01-01",
                mediana=3.0,
                muestra="top_10",
            ),
        ],
        alias=spec,
        muestra="todos",
    )
    assert len(rows) == 1
    assert rows[0]["mediana"] == 1.0


async def _fake_upstream(path: str, **_k: Any) -> Any:
    """Index + sparse informes; unknown months → empty (as if 404 skipped)."""
    if path == "/v1/finanzas/rem":
        return SAMPLE_INDEX
    if path.startswith("/v1/finanzas/rem/"):
        parts = path.rstrip("/").split("/")
        return INFORMES.get(f"{parts[-2]}-{parts[-1]}", [])
    if path == "/v1/finanzas/indices/inflacion":
        return INFLACION
    raise AssertionError(path)


@pytest.mark.asyncio
async def test_list_informes_expands_beyond_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Upstream index only lists ~12 recent paths; we walk back from newest.
    short_index = [
        "/finanzas/rem/ultimo",
        "/finanzas/rem/2026/08",
        "/finanzas/rem/2026/07",
    ]

    async def fake_get(path: str, **_k: Any) -> Any:
        if path == "/v1/finanzas/rem":
            return short_index
        raise AssertionError(path)

    monkeypatch.setattr("agent.proxy.rem.upstream.get", fake_get)
    rows = await rem.list_informes()
    assert len(rows) == rem.MAX_INFORMES
    assert rows[0] == (2026, "08")
    assert (2024, "06") in rows

    covered = await rem.list_informes(cover_desde="2024-01")
    assert (2024, "01") in covered
    assert (2023, "12") in covered  # one month before for 1m joins


@pytest.mark.asyncio
async def test_vs_real_horizon_1m(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agent.proxy.rem.upstream.get", _fake_upstream)
    rows = await rem.vs_real("ipc", horizon="1m")
    # Feb target ← Jan informe (15 vs 13.2); Mar ← Feb (12 vs 11)
    assert [r["fecha"] for r in rows] == ["2024-02-01", "2024-03-01"]
    feb = rows[0]
    assert feb["esperado"] == 15.0
    assert feb["real"] == 13.2
    assert feb["error"] == pytest.approx(1.8)
    assert feb["informe"] == "2024-01"


@pytest.mark.asyncio
async def test_vs_real_horizon_nowcast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agent.proxy.rem.upstream.get", _fake_upstream)
    rows = await rem.vs_real("ipc", horizon="nowcast")
    assert [r["fecha"] for r in rows] == [
        "2024-01-01",
        "2024-02-01",
        "2024-03-01",
    ]
    assert rows[0]["esperado"] == 20.0
    assert rows[0]["real"] == 20.6


@pytest.mark.asyncio
async def test_series_for_alias_nowcasts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agent.proxy.rem.upstream.get", _fake_upstream)
    rows = await rem.series_for_alias("ipc")
    assert [r["fecha"] for r in rows] == [
        "2024-01-01",
        "2024-02-01",
        "2024-03-01",
    ]
    assert rows[1]["mediana"] == 14.0
    assert rows[1]["valor"] == 14.0


@pytest.mark.asyncio
async def test_resolve_rem_aliases() -> None:
    rows = await resolve("/v1/rem", {})
    aliases = {r["alias"] for r in rows}
    assert aliases == {"ipc", "ipc_nucleo", "tc", "desempleo"}


@pytest.mark.asyncio
async def test_resolve_rem_informe_requires_params() -> None:
    with pytest.raises(ProxyError, match="año"):
        await resolve("/v1/rem/informe", {})


@pytest.mark.asyncio
async def test_resolve_vs_real(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agent.proxy.rem.upstream.get", _fake_upstream)
    rows = await resolve(
        "/v1/rem/vs-real/{alias}",
        {"alias": "ipc", "horizon": "1m"},
    )
    assert isinstance(rows, list)
    assert rows[0]["esperado"] == 15.0


@pytest.mark.asyncio
async def test_unwrap_fee_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(*_a: Any, **_k: Any) -> dict:
        return {
            "fechaActualizacion": "2026-09-01T00:00:00Z",
            "comisiones": [
                {"entidad": "iol", "producto": "cedears", "tasa": 0.005},
                {"entidad": "balanz", "producto": "cedears", "tasa": 0.006},
            ],
        }

    monkeypatch.setattr("agent.proxy.upstream.get", fake_get)
    rows = await resolve("/v1/finanzas/brokers/comisiones", {})
    assert isinstance(rows, list)
    assert len(rows) == 2
    assert rows[0]["entidad"] == "iol"
    assert rows[0]["fechaActualizacion"] == "2026-09-01T00:00:00Z"


@pytest.mark.asyncio
async def test_unwrap_diputado_viajes(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(*_a: Any, **_k: Any) -> dict:
        return {
            "diputadoId": "HCDN2831",
            "nacionales": [
                {
                    "ambito": "nacional",
                    "anio": 2024,
                    "mesNombre": "Julio",
                    "nombre": "Cafiero Santiago Andres",
                    "origen": "Aeroparque",
                    "destino": "Corrientes",
                },
                {
                    "ambito": "nacional",
                    "anio": 2024,
                    "mesNombre": "Julio",
                    "nombre": "Cafiero Santiago Andres",
                    "origen": "Resistencia",
                    "destino": "Aeroparque",
                },
            ],
            "internacionales": [],
        }

    monkeypatch.setattr("agent.proxy.upstream.get", fake_get)
    rows = await resolve(
        "/v1/diputados/diputados/{id}/viajes",
        {"id": "HCDN2831"},
    )
    assert isinstance(rows, list)
    assert len(rows) == 2
    assert rows[0]["diputadoId"] == "HCDN2831"
    assert rows[0]["origen"] == "Aeroparque"
    assert "nacionales" not in rows[0]


@pytest.mark.asyncio
async def test_vs_real_unknown_alias() -> None:
    with pytest.raises(UpstreamError, match="Unknown REM alias"):
        await resolve("/v1/rem/vs-real/{alias}", {"alias": "nope"})
