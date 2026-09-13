"""CAMMESA monthly demand proxy."""

from __future__ import annotations

from typing import Any

import pytest

from agent.catalog import catalog
from agent.proxy import NoMatch, resolve
from agent.proxy import cammesa
from agent.proxy.cache import cache
from agent.proxy.upstream import UpstreamError

SAMPLE_CSV = """indice_tiempo,demanda_total,demanda_residencial,comercio_e_industria,grandes_usuarios,temperatura_promedio,potencia_maxima
2024-01-01,11000.5,5000.1,4000.2,2000.2,24.5,22000
2024-02-01,11800.0,5600.0,4100.0,2100.0,26.0,24500
2024-03-01,10500.0,4800.0,3900.0,1800.0,22.0,21000
2025-01-01,11200.0,5100.0,4000.0,2100.0,25.0,23000
"""


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def test_catalog_lists_cammesa_routes() -> None:
    paths = set(catalog.paths())
    assert "/v1/cammesa" in paths
    assert "/v1/cammesa/demanda" in paths
    assert "/v1/cammesa/{alias}" in paths


def test_catalog_match_prefers_demanda_over_alias() -> None:
    matched = catalog.match("/v1/cammesa/demanda")
    assert matched is not None
    op, params = matched
    assert op.path == "/v1/cammesa/demanda"
    assert params == {}


def test_catalog_match_alias() -> None:
    matched = catalog.match("/v1/cammesa/residencial")
    assert matched is not None
    op, params = matched
    assert op.path == "/v1/cammesa/{alias}"
    assert params["alias"] == "residencial"


@pytest.mark.asyncio
async def test_fetch_wide(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(*_a: Any, **_k: Any) -> str:
        return SAMPLE_CSV

    monkeypatch.setattr("agent.proxy.cammesa.upstream.get", fake_get)
    rows = await cammesa.fetch_wide(desde="2024-01", hasta="2024-12")
    assert len(rows) == 3
    assert rows[1]["fecha"] == "2024-02-01"
    assert rows[1]["demanda_total"] == 11800.0
    assert rows[1]["temperatura"] == 26.0
    assert rows[1]["valor"] == 11800.0


@pytest.mark.asyncio
async def test_fetch_by_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(*_a: Any, **_k: Any) -> str:
        return SAMPLE_CSV

    monkeypatch.setattr("agent.proxy.cammesa.upstream.get", fake_get)
    rows = await cammesa.fetch_by_alias("temperatura", desde="2024-02")
    assert [r["fecha"] for r in rows] == [
        "2024-02-01",
        "2024-03-01",
        "2025-01-01",
    ]
    assert rows[0]["valor"] == 26.0
    assert rows[0]["unidad"] == "°C"


@pytest.mark.asyncio
async def test_resolve_cammesa_demanda(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(*_a: Any, **_k: Any) -> str:
        return SAMPLE_CSV

    monkeypatch.setattr("agent.proxy.cammesa.upstream.get", fake_get)
    rows = await resolve("/v1/cammesa/demanda", {"desde": "2024-01", "hasta": "2024-02"})
    assert isinstance(rows, list)
    assert len(rows) == 2
    assert "potencia_maxima" in rows[0]


@pytest.mark.asyncio
async def test_resolve_cammesa_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(*_a: Any, **_k: Any) -> str:
        return SAMPLE_CSV

    monkeypatch.setattr("agent.proxy.cammesa.upstream.get", fake_get)
    rows = await resolve("/v1/cammesa/{alias}", {"alias": "demanda"})
    assert rows[-1]["alias"] == "demanda"
    assert rows[-1]["unidad"] == "GWh"


@pytest.mark.asyncio
async def test_resolve_aliases_list() -> None:
    rows = await resolve("/v1/cammesa", {})
    aliases = {r["alias"] for r in rows}
    assert "demanda" in aliases
    assert "temperatura" in aliases


@pytest.mark.asyncio
async def test_unknown_alias() -> None:
    with pytest.raises(UpstreamError, match="Unknown CAMMESA alias"):
        await resolve("/v1/cammesa/{alias}", {"alias": "nope"})


@pytest.mark.asyncio
async def test_empty_window_nomatch(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(*_a: Any, **_k: Any) -> str:
        return SAMPLE_CSV

    monkeypatch.setattr("agent.proxy.cammesa.upstream.get", fake_get)
    with pytest.raises(NoMatch):
        await resolve(
            "/v1/cammesa/demanda",
            {"desde": "2010-01", "hasta": "2010-06"},
        )
