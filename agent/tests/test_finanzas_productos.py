"""Curated plazos / hipotecarios UVA / FCI proxy."""

from __future__ import annotations

from typing import Any

import pytest

from agent.catalog import catalog
from agent.proxy import ProxyError, resolve
from agent.proxy import finanzas_productos as fp
from agent.proxy.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def test_slugify_fondo() -> None:
    assert fp.slugify_fondo("Delta Pesos - Clase A") == "delta-pesos-clase-a"
    assert fp.slugify_fondo("Mercado Fondo — Clase A") == "mercado-fondo-clase-a"


def test_as_pct_fraction_and_percent() -> None:
    assert fp._as_pct(0.1875) == 18.75
    assert fp._as_pct(18.75) == 18.75
    assert fp._as_pct(None) is None


def test_flatten_plazos_ranks_by_best_tna() -> None:
    raw = [
        {
            "entidad": "Banco Bajo",
            "tnaClientes": 0.10,
            "tasas": [{"plazoMinDias": 30, "tna": 0.11}],
        },
        {
            "entidad": "Banco Alto",
            "tnaClientes": 0.20,
            "tasas": [
                {"plazoMinDias": 60, "tna": 0.22},
                {"plazoMinDias": 90, "tna": 0.25},
            ],
        },
    ]
    rows = fp.flatten_plazos(raw)
    assert rows[0]["entidad"] == "Banco Alto"
    assert rows[0]["tna"] == 25.0
    assert rows[0]["plazoDias"] == 90
    assert rows[1]["tna"] == 11.0


def test_flatten_hipotecarios_sorts_ascending() -> None:
    raw = [
        {
            "entidad": "Caro",
            "nombreComercial": "Caro",
            "tna": 0.09,
            "metadata": {"plazo_max_anios": 20, "financiamiento": "70%"},
        },
        {
            "entidad": "Barato",
            "nombreComercial": "Barato",
            "tna": 0.06,
            "metadata": {"plazo_max_anios": 30, "financiamiento": "75%"},
        },
    ]
    rows = fp.flatten_hipotecarios(raw)
    assert [r["entidad"] for r in rows] == ["Barato", "Caro"]
    assert rows[0]["tna"] == 6.0
    assert rows[0]["plazoMaxAnios"] == 30


@pytest.mark.asyncio
async def test_plazos_ranking_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(path: str, **_kw: Any) -> Any:
        assert path == "/v1/finanzas/tasas/plazoFijo"
        return [
            {
                "entidad": "Nación",
                "tnaClientes": 0.18,
                "tasas": [{"plazoMinDias": 30, "tna": 0.19}],
            }
        ]

    monkeypatch.setattr(fp.upstream, "get", fake_get)
    rows = await resolve("/v1/plazos/ranking", {"limit": 5})
    assert isinstance(rows, list)
    assert rows[0]["entidad"] == "Nación"
    assert rows[0]["tna"] == 19.0


@pytest.mark.asyncio
async def test_hipotecarios_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(path: str, **_kw: Any) -> Any:
        assert path == "/v1/finanzas/creditos/hipotecariosUva"
        return [
            {
                "entidad": "BNA",
                "nombreComercial": "BNA",
                "tna": 0.067,
                "metadata": {"plazo_max_anios": 30},
            }
        ]

    monkeypatch.setattr(fp.upstream, "get", fake_get)
    rows = await resolve("/v1/hipotecarios-uva", {})
    assert rows[0]["tna"] == 6.7


@pytest.mark.asyncio
async def test_fci_search_and_historico(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(path: str, **_kw: Any) -> Any:
        if path == "/v1/finanzas/fci/fondos":
            return {
                "fondos": [
                    {"nombre": "Delta Pesos - Clase A", "tipoRenta": "Renta Mixta"},
                    {"nombre": "Otro Fondo", "tipoRenta": "Renta Fija"},
                ]
            }
        if path.endswith("/historico"):
            return {
                "historico": [
                    {
                        "fecha": "2024-01-02",
                        "valorCuotaparte": 100.0,
                        "nombre": "Delta Pesos - Clase A",
                    },
                    {
                        "fecha": "2024-06-01",
                        "valorCuotaparte": 150.0,
                        "nombre": "Delta Pesos - Clase A",
                    },
                ]
            }
        if "fondos/" in path:
            return {
                "nombre": "Delta Pesos - Clase A",
                "fondoId": "394",
                "tipoRenta": "Renta Mixta",
            }
        raise AssertionError(path)

    monkeypatch.setattr(fp.upstream, "get", fake_get)
    hits = await resolve("/v1/fci/search", {"q": "Delta Pesos"})
    assert hits[0]["slug"] == "delta-pesos-clase-a"

    hist = await resolve(
        "/v1/fci/{slug}/historico",
        {"slug": "delta_pesos_a", "desde": "2024-01-01", "hasta": "2024-12-31"},
    )
    assert len(hist) == 2
    assert hist[0]["valor"] == 100.0


@pytest.mark.asyncio
async def test_fci_search_requires_q() -> None:
    with pytest.raises(ProxyError, match="requires q"):
        await resolve("/v1/fci/search", {})


def test_curated_paths_in_catalog() -> None:
    text = catalog.as_prompt_text("data")
    assert "/v1/plazos/ranking" in text
    assert "/v1/hipotecarios-uva" in text
    assert "/v1/fci/search" in text
    assert "/v1/feriados/{año}" in text
    assert "/v1/eventos/presidenciales" in text
