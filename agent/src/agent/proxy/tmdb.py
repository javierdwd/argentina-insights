"""TMDB — Argentine cinema (origin country AR).

Auth: ``TMDB_READ_TOKEN`` (Bearer, preferred) or ``TMDB_API_KEY`` (query).
Attribution: The Movie Database (TMDB).
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any

from . import upstream
from .upstream import UpstreamError

BASE_URL = "https://api.themoviedb.org"
IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
LANGUAGE = "es-AR"
ORIGIN = "AR"
LIST_CAP = 24
CAST_CAP = 12
TTL_LIST = 6 * 60 * 60
TTL_DETAIL = 24 * 60 * 60

_GENRE_IDS: dict[str, int] = {
    "accion": 28,
    "acción": 28,
    "action": 28,
    "aventura": 12,
    "animacion": 16,
    "animación": 16,
    "comedia": 35,
    "crimen": 80,
    "documental": 99,
    "drama": 18,
    "familia": 10751,
    "fantasia": 14,
    "fantasía": 14,
    "historia": 36,
    "terror": 27,
    "horror": 27,
    "musica": 10402,
    "música": 10402,
    "misterio": 9648,
    "romance": 10749,
    "ciencia ficcion": 878,
    "ciencia ficción": 878,
    "sci-fi": 878,
    "thriller": 53,
    "belica": 10752,
    "bélica": 10752,
    "guerra": 10752,
    "western": 37,
}

_SORT_ALLOWED = frozenset(
    {
        "popularity.desc",
        "popularity.asc",
        "vote_average.desc",
        "vote_average.asc",
        "primary_release_date.desc",
        "primary_release_date.asc",
        "title.asc",
        "title.desc",
        "revenue.desc",
        "revenue.asc",
    }
)

_YEAR_RE = re.compile(r"^\d{4}$")


def _credentials() -> tuple[dict[str, str] | None, dict[str, Any]]:
    """Return (headers, extra_query) for TMDB auth."""
    token = (os.environ.get("TMDB_READ_TOKEN") or "").strip()
    api_key = (os.environ.get("TMDB_API_KEY") or "").strip()
    if token:
        return {"Authorization": f"Bearer {token}"}, {}
    if api_key:
        return None, {"api_key": api_key}
    raise UpstreamError(
        "TMDB credentials missing: set TMDB_READ_TOKEN (preferred) or "
        "TMDB_API_KEY in the environment."
    )


async def _tmdb_get(
    path: str,
    *,
    query: dict[str, Any] | None = None,
    ttl: float,
    refresh: bool = False,
) -> Any:
    headers, auth_query = _credentials()
    merged = {**auth_query, **(query or {})}
    return await upstream.get(
        path,
        query=merged,
        ttl=ttl,
        refresh=refresh,
        base_url=BASE_URL,
        headers=headers,
    )


def _image_url(path: Any) -> str | None:
    if not path or not isinstance(path, str):
        return None
    if path.startswith("http"):
        return path
    return f"{IMAGE_BASE}{path}"


def _is_ar_origin(obj: dict[str, Any]) -> bool:
    countries = obj.get("origin_country")
    if isinstance(countries, list):
        return any(str(c).upper() == ORIGIN for c in countries)
    # production_countries on full movie detail
    prod = obj.get("production_countries")
    if isinstance(prod, list):
        return any(
            str(p.get("iso_3166_1") or "").upper() == ORIGIN
            for p in prod
            if isinstance(p, dict)
        )
    return False


def _genre_id(genero: str | None) -> int | None:
    if not genero:
        return None
    text = str(genero).strip()
    if text.isdigit():
        return int(text)
    key = text.casefold()
    return _GENRE_IDS.get(key)


def _normalize_movie(raw: dict[str, Any]) -> dict[str, Any]:
    foto = _image_url(raw.get("poster_path"))
    titulo = raw.get("title") or raw.get("original_title") or ""
    fecha = str(raw.get("release_date") or "")[:10] or None
    vote = raw.get("vote_average")
    out: dict[str, Any] = {
        "id": raw.get("id"),
        "titulo": titulo,
        "fecha": fecha,
        "overview": (raw.get("overview") or "") or None,
        "foto": foto,
        "valor": float(vote) if vote is not None else None,
        "votos": raw.get("vote_count"),
        "popularidad": raw.get("popularity"),
        "origen": ORIGIN,
    }
    return {k: v for k, v in out.items() if v is not None}


def _normalize_person(raw: dict[str, Any]) -> dict[str, Any]:
    foto = _image_url(raw.get("profile_path"))
    out: dict[str, Any] = {
        "id": raw.get("id"),
        "nombre": raw.get("name"),
        "foto": foto,
        "conocido_por": raw.get("known_for_department"),
    }
    known = raw.get("known_for")
    if isinstance(known, list):
        titles = []
        for item in known[:5]:
            if not isinstance(item, dict):
                continue
            t = item.get("title") or item.get("name")
            if t:
                titles.append(str(t))
        if titles:
            out["conocido_por_obras"] = titles
    return {k: v for k, v in out.items() if v is not None}


def _youtube_trailer(videos: Any) -> str | None:
    if not isinstance(videos, dict):
        return None
    results = videos.get("results")
    if not isinstance(results, list):
        return None
    preferred: dict[str, Any] | None = None
    for item in results:
        if not isinstance(item, dict):
            continue
        if str(item.get("site") or "").lower() != "youtube":
            continue
        if str(item.get("type") or "").lower() != "trailer":
            continue
        if item.get("official") and item.get("key"):
            preferred = item
            break
        if preferred is None and item.get("key"):
            preferred = item
    if preferred and preferred.get("key"):
        return f"https://www.youtube.com/watch?v={preferred['key']}"
    return None


def _cast_rows(credits: Any) -> list[dict[str, Any]]:
    if not isinstance(credits, dict):
        return []
    cast = credits.get("cast")
    if not isinstance(cast, list):
        return []
    rows: list[dict[str, Any]] = []
    for person in cast[:CAST_CAP]:
        if not isinstance(person, dict):
            continue
        row: dict[str, Any] = {
            "id": person.get("id"),
            "name": person.get("name"),
            "nombre": person.get("name"),
            "photoUrl": _image_url(person.get("profile_path")),
            "foto": _image_url(person.get("profile_path")),
            "role": person.get("character") or "Elenco",
            "cargo": person.get("character") or "Elenco",
        }
        rows.append({k: v for k, v in row.items() if v is not None})
    return rows


async def discover(
    *,
    anio: str | int | None = None,
    genero: str | None = None,
    sort: str | None = None,
    page: int | None = None,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    sort_by = str(sort or "popularity.desc").strip()
    if sort_by not in _SORT_ALLOWED:
        sort_by = "popularity.desc"
    query: dict[str, Any] = {
        "language": LANGUAGE,
        "with_origin_country": ORIGIN,
        "sort_by": sort_by,
        "include_adult": "false",
        "page": max(1, int(page or 1)),
    }
    if anio is not None and _YEAR_RE.match(str(anio).strip()):
        query["primary_release_year"] = int(str(anio).strip())
    gid = _genre_id(genero)
    if gid is not None:
        query["with_genres"] = gid

    raw = await _tmdb_get(
        "/3/discover/movie",
        query=query,
        ttl=TTL_LIST,
        refresh=refresh,
    )
    results = (raw or {}).get("results") if isinstance(raw, dict) else None
    if not isinstance(results, list):
        return []
    # discover already filters with_origin_country=AR
    rows = [_normalize_movie(r) for r in results if isinstance(r, dict)]
    return rows[:LIST_CAP]


async def search_movies(
    q: str,
    *,
    anio: str | int | None = None,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {
        "language": LANGUAGE,
        "query": q,
        "include_adult": "false",
        "page": 1,
    }
    if anio is not None and _YEAR_RE.match(str(anio).strip()):
        query["year"] = int(str(anio).strip())

    raw = await _tmdb_get(
        "/3/search/movie",
        query=query,
        ttl=TTL_LIST,
        refresh=refresh,
    )
    results = (raw or {}).get("results") if isinstance(raw, dict) else None
    if not isinstance(results, list):
        return []

    candidates = [r for r in results if isinstance(r, dict) and r.get("id")][:40]
    # Search payloads often omit origin_country — verify via detail (cached).
    details = await asyncio.gather(
        *[_movie_raw(int(r["id"]), refresh=refresh) for r in candidates],
        return_exceptions=True,
    )
    rows: list[dict[str, Any]] = []
    for detail in details:
        if isinstance(detail, Exception) or not isinstance(detail, dict):
            continue
        if not _is_ar_origin(detail):
            continue
        rows.append(_normalize_movie(detail))
        if len(rows) >= LIST_CAP:
            break
    return rows


async def _movie_raw(movie_id: int, *, refresh: bool = False) -> dict[str, Any]:
    raw = await _tmdb_get(
        f"/3/movie/{movie_id}",
        query={
            "language": LANGUAGE,
            "append_to_response": "credits,videos",
        },
        ttl=TTL_DETAIL,
        refresh=refresh,
    )
    return raw if isinstance(raw, dict) else {}


async def movie_detail(
    movie_id: int | str,
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    raw = await _movie_raw(int(movie_id), refresh=refresh)
    if not raw or not raw.get("id"):
        return {}
    if not _is_ar_origin(raw):
        return {}
    out = _normalize_movie(raw)
    runtime = raw.get("runtime")
    if runtime is not None:
        out["runtime"] = runtime
    genres = raw.get("genres")
    if isinstance(genres, list):
        names = [str(g.get("name")) for g in genres if isinstance(g, dict) and g.get("name")]
        if names:
            out["generos"] = names
    elenco = _cast_rows(raw.get("credits"))
    if elenco:
        out["elenco"] = elenco
    trailer = _youtube_trailer(raw.get("videos"))
    if trailer:
        out["trailer_url"] = trailer
    return out


async def search_people(q: str, *, refresh: bool = False) -> list[dict[str, Any]]:
    raw = await _tmdb_get(
        "/3/search/person",
        query={
            "language": LANGUAGE,
            "query": q,
            "include_adult": "false",
            "page": 1,
        },
        ttl=TTL_LIST,
        refresh=refresh,
    )
    results = (raw or {}).get("results") if isinstance(raw, dict) else None
    if not isinstance(results, list):
        return []
    return [
        _normalize_person(r)
        for r in results[:LIST_CAP]
        if isinstance(r, dict)
    ]


async def person_detail(
    person_id: int | str,
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    raw = await _tmdb_get(
        f"/3/person/{int(person_id)}",
        query={"language": LANGUAGE},
        ttl=TTL_DETAIL,
        refresh=refresh,
    )
    if not isinstance(raw, dict) or not raw.get("id"):
        return {}

    out = _normalize_person(raw)
    bio = (raw.get("biography") or "").strip()
    if bio:
        out["bio"] = bio
        out["overview"] = bio
    birthday = raw.get("birthday")
    if birthday:
        out["fecha_nacimiento"] = str(birthday)[:10]
    place = raw.get("place_of_birth")
    if place:
        out["lugar_nacimiento"] = place

    out["filmografia"] = await person_filmography(
        person_id, refresh=refresh
    )
    return out


async def person_filmography(
    person_id: int | str,
    *,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    """Flat Argentine-origin films for a person (discover with_people + AR)."""
    film_raw = await _tmdb_get(
        "/3/discover/movie",
        query={
            "language": LANGUAGE,
            "with_origin_country": ORIGIN,
            "with_people": int(person_id),
            "sort_by": "popularity.desc",
            "include_adult": "false",
            "page": 1,
        },
        ttl=TTL_LIST,
        refresh=refresh,
    )
    results = (film_raw or {}).get("results") if isinstance(film_raw, dict) else None
    filmografia: list[dict[str, Any]] = []
    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict):
                filmografia.append(_normalize_movie(item))
            if len(filmografia) >= LIST_CAP:
                break
    return filmografia
