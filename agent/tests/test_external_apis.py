"""External upstreams: BCRA, Series, Open-Meteo, wiki, histórico."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from agent.catalog import catalog
from agent.graph import _period_levels_from_datasets
from agent.proxy import NoMatch, ProxyError, resolve
from agent.proxy import bcra, historico, openmeteo, series, wiki
from agent.proxy.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def test_catalog_lists_external_routes() -> None:
    paths = set(catalog.paths())
    assert "/v1/bcra/variables" in paths
    assert "/v1/bcra/{alias}" in paths
    assert "/v1/cammesa" in paths
    assert "/v1/cammesa/demanda" in paths
    assert "/v1/cammesa/{alias}" in paths
    assert "/v1/series" in paths
    assert "/v1/series/search" in paths
    assert "/v1/series/{alias}" in paths
    assert "/v1/series/id/{serieId}" in paths
    assert "/v1/clima/historico" in paths
    assert "/v1/clima/pronostico" in paths
    assert "/v1/clima/actual" in paths
    assert "/v1/historico/dias" in paths
    assert "/v1/historico/dia" in paths
    assert "/v1/wiki/summary" in paths
    assert "/v1/cine/discover" in paths
    assert "/v1/cine/search" in paths
    assert "/v1/cine/pelicula/{id}" in paths
    assert "/v1/cine/persona/search" in paths
    assert "/v1/cine/persona/{id}" in paths
    assert "/v1/cine/persona/{id}/filmografia" in paths


def test_catalog_match_prefers_series_id_over_alias() -> None:
    matched = catalog.match("/v1/series/id/64.2_POBLACION_NUA_0_0_34_74")
    assert matched is not None
    op, params = matched
    assert op.path == "/v1/series/id/{serieId}"
    assert params["serieId"] == "64.2_POBLACION_NUA_0_0_34_74"


def test_bcra_normalize_series() -> None:
    raw = {
        "results": [
            {
                "idVariable": 1,
                "detalle": [
                    {"fecha": "2024-01-02", "valor": 100.0},
                    {"fecha": "2024-01-01", "valor": 90.0},
                ],
            }
        ]
    }
    var = bcra.get_variable("reservas")
    assert var is not None
    rows = bcra._normalize_series(raw, var)
    assert [r["fecha"] for r in rows] == ["2024-01-01", "2024-01-02"]
    assert rows[0]["valor"] == 90.0
    assert rows[0]["kind"] == "stock"
    assert rows[0]["alias"] == "reservas"


@pytest.mark.asyncio
async def test_resolve_bcra_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(*_a: Any, **_k: Any) -> dict:
        return {
            "results": [
                {
                    "detalle": [
                        {"fecha": "2023-12-10", "valor": 21000.0},
                        {"fecha": "2024-06-01", "valor": 28000.0},
                    ]
                }
            ]
        }

    monkeypatch.setattr("agent.proxy.bcra.upstream.get", fake_get)
    rows = await resolve("/v1/bcra/{alias}", {"alias": "reservas"})
    assert isinstance(rows, list)
    assert rows[0]["fecha"] == "2023-12-10"
    assert rows[-1]["valor"] == 28000.0


@pytest.mark.asyncio
async def test_resolve_bcra_variables() -> None:
    rows = await resolve("/v1/bcra/variables", {})
    aliases = {r["alias"] for r in rows}
    assert "reservas" in aliases
    assert "depositos_privados" in aliases


def test_series_normalize_list_rows() -> None:
    raw = {"data": [["2024-01-01", 100.5], ["2024-02-01", 101.0]]}
    rows = series._normalize_series(raw, "143.3_NO_PR_2004_A_31")
    assert len(rows) == 2
    assert rows[0] == {
        "fecha": "2024-01-01",
        "valor": 100.5,
        "serieId": "143.3_NO_PR_2004_A_31",
    }


@pytest.mark.asyncio
async def test_resolve_series_search(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(*_a: Any, **_k: Any) -> dict:
        return {
            "data": [
                {
                    "field": {
                        "id": "143.3_NO_PR_2004_A_31",
                        "description": "EMAE desestacionalizado",
                        "units": "índice",
                        "frequency": "R/P1M",
                    },
                    "dataset": {
                        "title": "EMAE",
                        "source": "INDEC",
                    },
                }
            ]
        }

    monkeypatch.setattr("agent.proxy.series.upstream.get", fake_get)
    hits = await resolve("/v1/series/search", {"q": "EMAE"})
    assert hits[0]["serieId"] == "143.3_NO_PR_2004_A_31"
    assert "EMAE" in hits[0]["titulo"]


@pytest.mark.asyncio
async def test_resolve_series_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(*_a: Any, **_k: Any) -> dict:
        return {"data": [["2024-01-01", 0.28], ["2024-07-01", 0.31]]}

    monkeypatch.setattr("agent.proxy.series.upstream.get", fake_get)
    rows = await resolve("/v1/series/{alias}", {"alias": "pobreza"})
    assert rows[0]["alias"] == "pobreza"
    assert rows[0]["kind"] == "stock"
    assert rows[0]["valor"] == 0.28


@pytest.mark.asyncio
async def test_openmeteo_historico(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(*_a: Any, **_k: Any) -> dict:
        return {
            "daily": {
                "time": ["2024-06-12"],
                "temperature_2m_min": [8.0],
                "temperature_2m_max": [16.0],
                "precipitation_sum": [0.0],
                "weather_code": [2],
            }
        }

    monkeypatch.setattr("agent.proxy.openmeteo.upstream.get", fake_get)
    rows = await resolve(
        "/v1/clima/historico",
        {"provincia": "CABA", "desde": "2024-06-12", "hasta": "2024-06-12"},
    )
    assert len(rows) == 1
    assert rows[0]["provincia"] == "CABA"
    assert rows[0]["tmin"] == 8.0
    assert rows[0]["tmax"] == 16.0
    assert rows[0]["valor"] == 12.0
    assert rows[0]["weather_code"] == 2


@pytest.mark.asyncio
async def test_openmeteo_actual_all_provinces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(*_a: Any, **_k: Any) -> list:
        # 24 jurisdictions
        out = []
        for _ in range(24):
            out.append(
                {
                    "current": {
                        "time": "2026-09-13T12:00",
                        "temperature_2m": 18.5,
                        "precipitation": 0.0,
                    }
                }
            )
        return out

    monkeypatch.setattr("agent.proxy.openmeteo.upstream.get", fake_get)
    rows = await resolve("/v1/clima/actual", {})
    assert len(rows) == 24
    assert "temperatura" in rows[0]
    assert "provincia" in rows[0]


@pytest.mark.asyncio
async def test_wiki_enrich_merges_bio(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def fake_get(path: str, **kwargs: Any) -> Any:
        calls.append(path)
        base = kwargs.get("base_url", "")
        if "wbsearchentities" in str(kwargs.get("query", {})) or (
            path == "/w/api.php"
            and (kwargs.get("query") or {}).get("action") == "wbsearchentities"
        ):
            return {
                "search": [
                    {
                        "id": "Q123",
                        "description": "senador argentino",
                    }
                ]
            }
        query = kwargs.get("query") or {}
        if query.get("action") == "wbgetentities" and query.get("ids") == "Q123":
            return {
                "entities": {
                    "Q123": {
                        "claims": {
                            "P18": [
                                {
                                    "mainsnak": {
                                        "datavalue": {"value": "Foo.jpg"}
                                    }
                                }
                            ]
                        },
                        "sitelinks": {"eswiki": {"title": "Juan_Pérez"}},
                    }
                }
            }
        if query.get("action") == "wbgetentities":
            return {"entities": {}}
        if "summary" in path:
            return {
                "extract": "Político argentino. Senador por Misiones.",
                "thumbnail": {"source": "https://example.com/thumb.jpg"},
            }
        return {}

    monkeypatch.setattr("agent.proxy.wiki.upstream.get", fake_get)
    row = await wiki.enrich_person(
        {"nombre": "Pérez, Juan", "provincia": "Misiones"}
    )
    assert "bio" in row
    assert "Político" in row["bio"]
    assert row.get("foto") or row.get("imagen")


@pytest.mark.asyncio
async def test_wiki_skipped_on_multi_roster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Roster list with 2+ people must not call Wikipedia."""
    enrich = AsyncMock(side_effect=lambda row, **_: row)
    monkeypatch.setattr("agent.proxy.wiki.enrich_person", enrich)

    async def fake_upstream_get(*_a: Any, **_k: Any) -> list:
        return [
            {"id": "1", "nombre": "A, Uno", "provincia": "Misiones"},
            {"id": "2", "nombre": "B, Dos", "provincia": "Misiones"},
        ]

    monkeypatch.setattr("agent.proxy.upstream.get", fake_upstream_get)
    # Bypass active-term filtering by stubbing the roster filter path.
    with patch(
        "agent.proxy._apply_roster_filters",
        new=AsyncMock(
            return_value=[
                {"id": "1", "nombre": "A, Uno", "provincia": "Misiones"},
                {"id": "2", "nombre": "B, Dos", "provincia": "Misiones"},
            ]
        ),
    ):
        rows = await resolve(
            "/v1/senado/senadores",
            {"province": "Misiones", "active": "false"},
        )
    assert len(rows) == 2
    enrich.assert_not_called()


@pytest.mark.asyncio
async def test_presidentes_fields_keeps_wiki_bio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Slim fields= must not strip Wikipedia bio added after projection."""
    enrich = AsyncMock(
        side_effect=lambda row, **_: {**row, "bio": "Extracto wiki."}
    )
    monkeypatch.setattr("agent.proxy.wiki.enrich_person", enrich)

    async def fake_upstream_get(*_a: Any, **_k: Any) -> list:
        return [{"nombre": "Javier Milei", "partido": "LLA", "imagen": "http://x"}]

    monkeypatch.setattr("agent.proxy.upstream.get", fake_upstream_get)
    with patch(
        "agent.proxy._apply_presidentes_filters",
        new=AsyncMock(
            return_value=[
                {"nombre": "Javier Milei", "partido": "LLA", "imagen": "http://x"}
            ]
        ),
    ):
        rows = await resolve(
            "/v1/presidentes",
            {"name": "Milei", "fields": "nombre,inicio,fin,partido,imagen"},
        )
    assert len(rows) == 1
    enrich.assert_awaited_once()
    assert rows[0]["bio"] == "Extracto wiki."


@pytest.mark.asyncio
async def test_bind_enriches_single_person_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 1-person card bound from a larger dataset still gets Wikipedia."""
    from agent.graph import _bind_node, _enrich_bound_person_cards

    async def fake_card(person: dict, **_: Any) -> dict:
        return {
            **person,
            "bio": "Senador argentino.",
            "links": ["https://es.wikipedia.org/wiki/X"],
        }

    monkeypatch.setattr("agent.graph.wiki.enrich_person_card", fake_card)

    datasets = {
        "ds": {
            "id": "ds",
            "keys": ["nombre", "bloque"],
            "N": 2,
            "rows": [
                {"nombre": "A Uno", "bloque": "UCR"},
                {"nombre": "B Dos", "bloque": "LLA"},
            ],
        }
    }
    tree = {
        "id": "card",
        "type": "PersonCard",
        "props": {"dataRef": "ds", "limit": 1},
    }
    bound = _bind_node(tree, datasets)
    out = await _enrich_bound_person_cards(bound)
    person = out["props"]["people"][0]
    assert person["bio"] == "Senador argentino."
    assert "wikipedia.org" in person["links"][0]


@pytest.mark.asyncio
async def test_bind_skips_wiki_on_roster_person_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent.graph import _bind_node, _enrich_bound_person_cards

    enrich = AsyncMock(side_effect=lambda person, **_: person)
    monkeypatch.setattr("agent.graph.wiki.enrich_person_card", enrich)
    datasets = {
        "ds": {
            "id": "ds",
            "keys": ["nombre"],
            "N": 2,
            "rows": [{"nombre": "A Uno"}, {"nombre": "B Dos"}],
        }
    }
    tree = {"id": "card", "type": "PersonCard", "props": {"dataRef": "ds"}}
    bound = _bind_node(tree, datasets)
    await _enrich_bound_person_cards(bound)
    enrich.assert_not_called()


@pytest.mark.asyncio
async def test_enrich_person_card_maps_wiki_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_enrich(row: dict, **_: Any) -> dict:
        return {
            **row,
            "bio": "Político argentino.",
            "foto": "https://example.com/p.jpg",
            "url": "https://es.wikipedia.org/wiki/Juan_Perez",
            "redes": ["https://es.wikipedia.org/wiki/Juan_Perez"],
        }

    monkeypatch.setattr("agent.proxy.wiki.enrich_person", fake_enrich)
    out = await wiki.enrich_person_card({"name": "Juan Pérez", "party": "UCR"})
    assert out["bio"] == "Político argentino."
    assert out["photoUrl"] == "https://example.com/p.jpg"
    assert "wikipedia.org" in out["links"][0]
    assert out["party"] == "UCR"


def test_period_levels_last_for_stock() -> None:
    presidents = {
        "id": "p",
        "path": "/v1/presidentes",
        "params": {},
        "rows": [
            {"nombre": "A", "inicio": "2019-12-10", "fin": "2023-12-10"},
            {"nombre": "B", "inicio": "2023-12-10", "fin": None},
        ],
        "keys": ["nombre", "inicio", "fin"],
        "N": 2,
        "date_range": None,
    }
    reservas = {
        "id": "r",
        "path": "/v1/bcra/reservas",
        "params": {"kind": "stock"},
        "rows": [
            {"fecha": "2020-06-01", "valor": 40000.0, "kind": "stock"},
            {"fecha": "2022-06-01", "valor": 35000.0, "kind": "stock"},
            {"fecha": "2023-12-01", "valor": 21000.0, "kind": "stock"},
            {"fecha": "2024-06-01", "valor": 28000.0, "kind": "stock"},
            {"fecha": "2025-01-01", "valor": 30000.0, "kind": "stock"},
        ],
        "keys": ["fecha", "valor", "kind"],
        "N": 5,
        "date_range": None,
    }
    levels = _period_levels_from_datasets({"p": presidents, "r": reservas})
    assert levels is not None
    assert levels["params"]["op"] == "last"
    by_label = {r["label"]: r for r in levels["rows"]}
    assert by_label["A"]["value"] == 21000.0
    assert by_label["B"]["value"] == 30000.0
    assert "delta" in by_label["A"]


def test_period_levels_still_max_for_fx() -> None:
    presidents = {
        "id": "p",
        "path": "/v1/presidentes",
        "params": {},
        "rows": [
            {"nombre": "A", "inicio": "2019-12-10", "fin": "2023-12-10"},
            {"nombre": "B", "inicio": "2023-12-10", "fin": None},
        ],
        "keys": ["nombre", "inicio", "fin"],
        "N": 2,
        "date_range": None,
    }
    blue = {
        "id": "b",
        "path": "/v1/cotizaciones/dolares/blue",
        "params": {},
        "rows": [
            {"fecha": "2020-06-01", "venta": 100.0},
            {"fecha": "2022-06-01", "venta": 200.0},
            {"fecha": "2023-11-01", "venta": 900.0},
            {"fecha": "2024-06-01", "venta": 1200.0},
            {"fecha": "2025-01-01", "venta": 1400.0},
        ],
        "keys": ["fecha", "venta"],
        "N": 5,
        "date_range": None,
    }
    levels = _period_levels_from_datasets({"p": presidents, "b": blue})
    assert levels is not None
    assert levels["params"]["op"] == "max"
    by_label = {r["label"]: r["value"] for r in levels["rows"]}
    assert by_label["A"] == 900.0
    assert by_label["B"] == 1400.0


@pytest.mark.asyncio
async def test_clima_historico_requires_dates() -> None:
    with pytest.raises(ProxyError, match="desde"):
        await resolve("/v1/clima/historico", {"provincia": "CABA"})


@pytest.mark.asyncio
async def test_unknown_bcra_alias() -> None:
    with pytest.raises(Exception):
        await resolve("/v1/bcra/{alias}", {"alias": "no_existe"})


def test_historico_list_covers_last_decade() -> None:
    rows = historico.list_days(desde="2016-01-01", hasta="2024-12-31")
    assert len(rows) >= 10
    fechas = {r["fecha"] for r in rows}
    assert "2023-12-10" in fechas
    assert "2019-08-11" in fechas
    asuncion = next(r for r in rows if r["fecha"] == "2023-12-10")
    assert asuncion["persona"] == "Javier Milei"
    assert asuncion["provincia"] == "CABA"
    paso = next(r for r in rows if r["fecha"] == "2019-08-11")
    assert "persona" not in paso


@pytest.mark.asyncio
async def test_resolve_historico_dia(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_summary(title: str, *, refresh: bool = False) -> dict:
        return {
            "extract": f"Resumen de {title}.",
            "foto": "https://example.com/thumb.jpg",
            "url": "https://es.wikipedia.org/wiki/Test",
        }

    monkeypatch.setattr("agent.proxy.historico.wiki.fetch_summary", fake_summary)
    row = await resolve("/v1/historico/dia", {"fecha": "2023-12-10"})
    assert isinstance(row, dict)
    assert row["fecha"] == "2023-12-10"
    assert row["titulo"] == "Asunción de Javier Milei"
    assert "Milei" in row["extract"]
    assert "blue" in row["series_sugeridas"]
    assert row["persona"] == "Javier Milei"
    assert row["provincia"] == "CABA"


@pytest.mark.asyncio
async def test_resolve_historico_dias_filter() -> None:
    rows = await resolve(
        "/v1/historico/dias",
        {"desde": "2023-01-01", "hasta": "2023-12-31"},
    )
    assert isinstance(rows, list)
    assert all("2023" in r["fecha"] for r in rows)
    assert len(rows) >= 3


@pytest.mark.asyncio
async def test_resolve_wiki_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_summary(title: str, *, refresh: bool = False) -> dict:
        return {"extract": "Texto wiki.", "url": "https://es.wikipedia.org/wiki/X"}

    monkeypatch.setattr("agent.proxy.wiki.fetch_summary", fake_summary)
    row = await resolve("/v1/wiki/summary", {"q": "Test Article"})
    assert row["extract"] == "Texto wiki."


@pytest.mark.asyncio
async def test_historico_dia_requires_fecha() -> None:
    with pytest.raises(ProxyError, match="fecha"):
        await resolve("/v1/historico/dia", {})


@pytest.mark.asyncio
async def test_historico_dia_unknown_date() -> None:
    with pytest.raises(NoMatch, match="not in the curated"):
        await resolve("/v1/historico/dia", {"fecha": "1999-01-01"})
