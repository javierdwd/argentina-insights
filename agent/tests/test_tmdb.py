"""TMDB Argentine cinema proxy."""

from __future__ import annotations

from typing import Any

import pytest

from agent.catalog import catalog
from agent.proxy import NoMatch, ProxyError, resolve
from agent.proxy import tmdb
from agent.proxy.cache import cache
from agent.proxy.upstream import UpstreamError


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _tmdb_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "TMDB_READ_TOKEN",
        "test-bearer-token",
    )
    monkeypatch.delenv("TMDB_API_KEY", raising=False)


def test_catalog_lists_cine_routes() -> None:
    paths = set(catalog.paths())
    assert "/v1/cine/discover" in paths
    assert "/v1/cine/search" in paths
    assert "/v1/cine/pelicula/{id}" in paths
    assert "/v1/cine/persona/search" in paths
    assert "/v1/cine/persona/{id}" in paths
    assert "/v1/cine/persona/{id}/filmografia" in paths


def test_catalog_match_pelicula_id() -> None:
    matched = catalog.match("/v1/cine/pelicula/12345")
    assert matched is not None
    op, params = matched
    assert op.path == "/v1/cine/pelicula/{id}"
    assert params["id"] == "12345"


def test_normalize_movie_image_url() -> None:
    row = tmdb._normalize_movie(
        {
            "id": 1,
            "title": "Relatos salvajes",
            "release_date": "2014-08-21",
            "overview": "…",
            "poster_path": "/abc.jpg",
            "vote_average": 7.9,
            "vote_count": 100,
            "popularity": 12.0,
            "origin_country": ["AR"],
        }
    )
    assert row["titulo"] == "Relatos salvajes"
    assert row["foto"] == "https://image.tmdb.org/t/p/w500/abc.jpg"
    assert row["valor"] == 7.9
    assert row["origen"] == "AR"


def test_is_ar_origin_production_countries() -> None:
    assert tmdb._is_ar_origin(
        {"production_countries": [{"iso_3166_1": "AR", "name": "Argentina"}]}
    )
    assert not tmdb._is_ar_origin(
        {"production_countries": [{"iso_3166_1": "US", "name": "United States"}]}
    )


def test_genre_id_aliases() -> None:
    assert tmdb._genre_id("drama") == 18
    assert tmdb._genre_id("Comedia") == 35
    assert tmdb._genre_id("35") == 35
    assert tmdb._genre_id("nope") is None


def test_missing_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TMDB_READ_TOKEN", raising=False)
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    with pytest.raises(UpstreamError, match="TMDB credentials missing"):
        tmdb._credentials()


@pytest.mark.asyncio
async def test_resolve_discover(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(path: str, **kwargs: Any) -> dict:
        assert path == "/3/discover/movie"
        assert kwargs["headers"]["Authorization"] == "Bearer test-bearer-token"
        q = kwargs.get("query") or {}
        assert q["with_origin_country"] == "AR"
        assert "api_key" not in q
        return {
            "results": [
                {
                    "id": 10,
                    "title": "El secreto de sus ojos",
                    "release_date": "2009-08-13",
                    "poster_path": "/x.jpg",
                    "vote_average": 8.0,
                    "vote_count": 50,
                    "popularity": 20,
                    "origin_country": ["AR"],
                }
            ]
        }

    monkeypatch.setattr(tmdb.upstream, "get", fake_get)
    rows = await resolve("/v1/cine/discover", {"anio": 2009})
    assert isinstance(rows, list)
    assert rows[0]["titulo"] == "El secreto de sus ojos"
    assert rows[0]["foto"].endswith("/x.jpg")


@pytest.mark.asyncio
async def test_resolve_search_filters_non_ar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_get(path: str, **kwargs: Any) -> dict:
        calls.append(path)
        if path == "/3/search/movie":
            return {
                "results": [
                    {"id": 1, "title": "US Film"},
                    {"id": 2, "title": "AR Film"},
                ]
            }
        if path == "/3/movie/1":
            return {
                "id": 1,
                "title": "US Film",
                "origin_country": ["US"],
                "production_countries": [{"iso_3166_1": "US"}],
            }
        if path == "/3/movie/2":
            return {
                "id": 2,
                "title": "AR Film",
                "release_date": "2020-01-01",
                "poster_path": "/ar.jpg",
                "vote_average": 7.0,
                "origin_country": ["AR"],
                "production_countries": [{"iso_3166_1": "AR"}],
                "credits": {"cast": []},
                "videos": {"results": []},
            }
        raise AssertionError(path)

    monkeypatch.setattr(tmdb.upstream, "get", fake_get)
    rows = await resolve("/v1/cine/search", {"q": "Film"})
    assert len(rows) == 1
    assert rows[0]["titulo"] == "AR Film"
    assert "/3/movie/1" in calls and "/3/movie/2" in calls


@pytest.mark.asyncio
async def test_resolve_pelicula_rejects_non_ar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(path: str, **_k: Any) -> dict:
        return {
            "id": 99,
            "title": "Not AR",
            "origin_country": ["US"],
            "production_countries": [{"iso_3166_1": "US"}],
        }

    monkeypatch.setattr(tmdb.upstream, "get", fake_get)
    with pytest.raises(NoMatch):
        await resolve("/v1/cine/pelicula/{id}", {"id": 99})


@pytest.mark.asyncio
async def test_resolve_pelicula_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(path: str, **_k: Any) -> dict:
        return {
            "id": 42,
            "title": "Relatos salvajes",
            "overview": "Antología",
            "runtime": 122,
            "vote_average": 7.9,
            "poster_path": "/r.jpg",
            "origin_country": ["AR"],
            "genres": [{"id": 35, "name": "Comedia"}],
            "credits": {
                "cast": [
                    {
                        "id": 7,
                        "name": "Ricardo Darín",
                        "character": "Simón",
                        "profile_path": "/d.jpg",
                    }
                ]
            },
            "videos": {
                "results": [
                    {
                        "site": "YouTube",
                        "type": "Trailer",
                        "official": True,
                        "key": "abc123",
                    }
                ]
            },
        }

    monkeypatch.setattr(tmdb.upstream, "get", fake_get)
    row = await resolve("/v1/cine/pelicula/{id}", {"id": "42"})
    assert row["titulo"] == "Relatos salvajes"
    assert row["runtime"] == 122
    assert row["generos"] == ["Comedia"]
    assert row["elenco"][0]["name"] == "Ricardo Darín"
    assert row["trailer_url"].endswith("abc123")


@pytest.mark.asyncio
async def test_resolve_search_requires_q() -> None:
    with pytest.raises(ProxyError, match="requires q"):
        await resolve("/v1/cine/search", {})


@pytest.mark.asyncio
async def test_resolve_persona_filmografia_ar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(path: str, **kwargs: Any) -> dict:
        if path.startswith("/3/person/"):
            return {
                "id": 5,
                "name": "Lucrecia Martel",
                "biography": "Directora",
                "profile_path": "/m.jpg",
                "known_for_department": "Directing",
            }
        if path == "/3/discover/movie":
            q = kwargs.get("query") or {}
            assert q["with_people"] == 5
            assert q["with_origin_country"] == "AR"
            return {
                "results": [
                    {
                        "id": 3,
                        "title": "La ciénaga",
                        "release_date": "2001-01-01",
                        "poster_path": "/c.jpg",
                        "vote_average": 7.0,
                    }
                ]
            }
        raise AssertionError(path)

    monkeypatch.setattr(tmdb.upstream, "get", fake_get)
    row = await resolve("/v1/cine/persona/{id}", {"id": 5})
    assert row["nombre"] == "Lucrecia Martel"
    assert row["bio"] == "Directora"
    assert row["filmografia"][0]["titulo"] == "La ciénaga"


@pytest.mark.asyncio
async def test_resolve_persona_filmografia_flat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(path: str, **kwargs: Any) -> dict:
        if path == "/3/discover/movie":
            q = kwargs.get("query") or {}
            assert q["with_people"] == 5
            assert q["with_origin_country"] == "AR"
            return {
                "results": [
                    {
                        "id": 3,
                        "title": "La ciénaga",
                        "release_date": "2001-01-01",
                        "poster_path": "/c.jpg",
                        "vote_average": 7.0,
                    }
                ]
            }
        raise AssertionError(path)

    monkeypatch.setattr(tmdb.upstream, "get", fake_get)
    rows = await resolve("/v1/cine/persona/{id}/filmografia", {"id": 5})
    assert isinstance(rows, list)
    assert rows[0]["titulo"] == "La ciénaga"
    assert "filmografia" not in rows[0]


@pytest.mark.asyncio
async def test_missing_token_on_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TMDB_READ_TOKEN", raising=False)
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    with pytest.raises(UpstreamError, match="TMDB credentials missing"):
        await resolve("/v1/cine/discover", {})


def test_cache_key_omits_api_key() -> None:
    from agent.proxy import upstream

    keyed = upstream._cache_key(
        "https://api.themoviedb.org",
        "/3/discover/movie",
        {"api_key": "secret", "language": "es-AR"},
    )
    assert "secret" not in keyed
    assert "language=es-AR" in keyed
