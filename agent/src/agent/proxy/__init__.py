"""In-process proxy over api.argentinadatos.com.

The upstream API only offers full-list endpoints: no lookup by id, no title
search, no province filter, no field projection.  That pushed a lot of
accidental complexity into the agent (synthetic tool params, prompt rules to
stop the model guessing, row caps it had to reason about).

This module is the richer API the agent actually wants, implemented against
a cached copy of the upstream lists:

    /v1/diputados/actas?fields=id,titulo        cheap scan to pick an acta
    /v1/diputados/actas?title=<nombre>          search before any row cap
    search_actas(query)                         named law (vector index + LLM pick)
    /v1/diputados/actas/id/5995                 one acta, full votes
    /v1/diputados/actas/id/5995/votos?vote=afirmativo
    /v1/senado/senadores?province=Misiones      current senators for a province
    /v1/diputados/diputados/HCDN0011            one profile

Everything is resolved in-process (no local HTTP hop): ``resolve()`` is
called directly by the fetch tool.  The route surface lives in routes.py and
is the same declaration the catalog reads to describe it to the model.
"""

from __future__ import annotations

import asyncio
import datetime
import re
from typing import Any

from . import collections as coll
from . import filters, names, upstream
from . import (
    bcra,
    cammesa,
    finanzas_productos,
    historico,
    news,
    openmeteo,
    rem,
    series,
    tmdb,
    wiki,
)
from . import vector_index as vx
from .cache import cache
from .match import match_directory
from .routes import (
    ACTAS_FAMILIES,
    CALENDAR_PATHS,
    DATE_SERIES_PATHS,
    DETAIL_ROW_CAP,
    DIPUTADOS_ACTAS,
    EXTERNAL_ROUTES,
    PROJECTED_CAP,
    ROSTER_FAMILIES,
    SAFETY_CAP,
    SENADO_ACTAS,
    SYNTHETIC_ROUTES,
    TTL_ACTAS,
    TTL_ROSTER,
    ActasFamily,
    RosterFamily,
    actas_family_for,
    client_param_names,
    roster_family_for,
    ttl_for,
)
from .upstream import UpstreamError

__all__ = ["NoMatch", "ProxyError", "UpstreamError", "cache", "resolve", "search_actas"]


#: Placeholder names carry accents (``{año}``), so not ``\w+``.
_PLACEHOLDER = re.compile(r"\{([^}]+)\}")


class ProxyError(RuntimeError):
    """A request the proxy understood but cannot satisfy.

    The message is written to be read by the LLM, so it states what was and
    wasn't found rather than just failing.
    """


class NoMatch(ProxyError):
    """The request was served, but zero rows matched the criteria.

    Raised instead of returning ``[]`` because a bare empty list reads as
    "something went wrong" to a model, which then tells the user it has no
    access to the data.  The message says what was searched and how many rows
    were scanned, so the honest answer ("no encontré registros") is the
    easiest one to give.
    """


_NO_MATCH_GUIDANCE = (
    "The endpoint works and returned data normally — nothing matched these "
    "criteria. Tell the user no records matched, and suggest the most likely "
    "fix (the other chamber, a different spelling, a wider date range, "
    "active=false for past legislators). Do NOT tell the user you lack "
    "access to this data or ask them for a link."
)


def _describe(criteria: dict[str, Any]) -> str:
    return ", ".join(f"{k}={v!r}" for k, v in criteria.items())


def _split_params(
    path: str,
    params: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Split the flat param dict into path / synthetic / upstream-query parts."""
    path_names = set(_PLACEHOLDER.findall(path))
    synthetic_names = client_param_names(path)

    path_params: dict[str, Any] = {}
    client_params: dict[str, Any] = {}
    query_params: dict[str, Any] = {}

    for key, value in params.items():
        if key in path_names:
            path_params[key] = value
        elif key in synthetic_names:
            client_params[key] = value
        else:
            query_params[key] = value

    return path_params, client_params, query_params


def _field_list(client_params: dict[str, Any]) -> list[str]:
    raw = client_params.get("fields")
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(f).strip() for f in raw if str(f).strip()]
    return [f.strip() for f in str(raw).split(",") if f.strip()]


async def _load_actas_year_list(
    family: ActasFamily,
    year: int,
    *,
    refresh: bool,
) -> list[dict]:
    year_path = family.year_path.replace("{año}", str(year))
    try:
        data = await upstream.get(
            year_path,
            ttl=ttl_for(family.list_path),
            refresh=refresh,
        )
    except UpstreamError:
        return []
    if not isinstance(data, list):
        return []
    return [r for r in data if isinstance(r, dict)]


async def _find_acta_by_id(
    family: ActasFamily,
    wanted: str,
    *,
    refresh: bool,
) -> tuple[dict | None, int]:
    """Locate one acta in the chamber list, then year-scoped lists if needed.

    Older sessions often exist only under ``/actas/{año}`` and are absent from
    the chamber dump — list-by-date already merges years, but detail/votos
    used to scan the dump alone and falsely claim the id does not exist.
    """
    rows = await upstream.get(
        family.list_path,
        ttl=ttl_for(family.list_path),
        refresh=refresh,
    )
    if not isinstance(rows, list):
        rows = []
    dict_rows = [r for r in rows if isinstance(r, dict)]
    scanned = len(dict_rows)
    match = next(
        (r for r in dict_rows if str(r.get(family.id_field)) == wanted),
        None,
    )
    if match is not None:
        return match, scanned

    year_hi = datetime.date.today().year
    year_lo = 2000
    year_lists = await asyncio.gather(
        *[
            _load_actas_year_list(family, year, refresh=refresh)
            for year in range(year_hi, year_lo - 1, -1)
        ]
    )
    for data in year_lists:
        scanned += len(data)
        match = next(
            (r for r in data if str(r.get(family.id_field)) == wanted),
            None,
        )
        if match is not None:
            return match, scanned
    return None, scanned


async def _resolve_synthetic(
    path: str,
    path_params: dict[str, Any],
    client_params: dict[str, Any],
) -> Any:
    """Resolve an id-based route by scanning the cached upstream list."""
    route = SYNTHETIC_ROUTES[path]
    id_value = path_params.get(route.id_param)
    if id_value is None:
        raise ProxyError(
            f"Missing required path parameter '{route.id_param}' for {path}."
        )

    wanted = str(id_value)
    refresh = filters.is_true(client_params.get("refresh", False))
    family = actas_family_for(path)

    if family is not None:
        match, scanned = await _find_acta_by_id(family, wanted, refresh=refresh)
        if match is None:
            raise ProxyError(
                f"No records: {family.list_path} (+ year lists) has no row with "
                f"{family.id_field}={wanted} (searched {scanned} rows). "
                "Tell the user nothing matched and offer the closest alternative "
                "(e.g. the other chamber, or a title search) — the data itself "
                "IS available, this id simply does not exist."
            )
    else:
        rows = await upstream.get(
            route.upstream,
            ttl=route.ttl,
            refresh=refresh,
        )
        if not isinstance(rows, list):
            raise ProxyError(f"Upstream {route.upstream} did not return a list.")

        match = next(
            (
                r
                for r in rows
                if isinstance(r, dict) and str(r.get(route.id_field)) == wanted
            ),
            None,
        )
        if match is None:
            raise ProxyError(
                f"No records: {route.upstream} has no row with "
                f"{route.id_field}={wanted} (searched all {len(rows)} rows). "
                "Tell the user nothing matched and offer the closest alternative "
                "(e.g. the other chamber, or a title search) — the data itself "
                "IS available, this id simply does not exist."
            )

    fields = _field_list(client_params)
    vote = client_params.get("vote")

    if family is not None:
        match = filters.normalize_votes(match, family)
        match = await _with_roster_profile(
            match,
            family,
            refresh=refresh,
        )

    # ``/votos`` sub-route: return the vote list itself, so it can be bound
    # to a List/PersonCard widget as a dataset of rows.
    if route.subfield:
        votes = match.get(route.subfield) or []
        if not isinstance(votes, list):
            votes = []
        total = len(votes)
        if vote and family is not None:
            votes = filters.filter_votes(match, family, str(vote))[route.subfield]
            if not votes:
                raise NoMatch(
                    f"No records: acta {wanted} has 0 votes of type "
                    f"{str(vote)!r} (out of {total} votes cast). That IS the "
                    "answer — nobody voted that way. State it as a fact (e.g. "
                    "'no hubo votos en contra'), do not treat it as missing "
                    "data."
                )
        if fields:
            votes = _project_checked(votes, fields, path)
        # Stamp the parent acta's fecha/titulo onto every vote row so a
        # follow-up ("el dólar el día de la votación") can read the date
        # from this dataset — `fields=nombre,voto` would otherwise drop it.
        votes = _stamp_acta_meta(votes, match)
        return filters.cap(votes, PROJECTED_CAP)

    if vote and family is not None:
        match = filters.filter_votes(match, family, str(vote))
    if fields:
        roster = roster_family_for(path)
        if roster is not None:
            fields = _with_identity_fields(fields, _ROSTER_PROFILE_FIELDS)
        match = _project_checked([match], fields, path)[0]

    # Single legislator / profile → optional Wikipedia bio + photo fallback.
    if roster_family_for(path) is not None and isinstance(match, dict):
        match = await wiki.enrich_person(match, refresh=refresh)
    return match


_ACTA_META_KEYS = ("fecha", "titulo", "resultado")

# Always keep these on roster projections so PersonCard can show contact +
# party even when the model copies a slim fields= example.
_ROSTER_PROFILE_FIELDS = (
    "id",
    "nombre",
    "apellido",
    "foto",
    "imagen",
    "bloque",
    "partido",
    "provincia",
    "email",
    "telefono",
    "redes",
    "bio",
)


def _fold_person_name(value: object) -> str:
    """Accent-fold + collapse punctuation so vote names match roster names."""
    text = " ".join(str(value or "").replace(",", " ").split())
    return filters.normalize(text)


def _roster_display_name(row: dict, family: RosterFamily) -> str:
    nombre = str(row.get("nombre") or "").strip()
    apellido = str(row.get("apellido") or "").strip()
    if family.chamber == "diputados" and apellido and nombre and "," not in nombre:
        return f"{apellido}, {nombre}"
    return nombre or apellido


def _roster_name_index(rows: list, family: RosterFamily) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = _fold_person_name(_roster_display_name(row, family))
        if key:
            index[key] = row
    return index


def _stamp_scalars_from_roster(vote: dict, roster: dict) -> dict:
    """Fill missing profile fields on a vote row from the roster match.

    Skips nested objects (periodos, meta). Keeps string lists (``redes``).
    Does not overwrite values the vote row already has (e.g. Diputados
    ``imagen``).
    """
    out = dict(vote)
    for key, value in roster.items():
        if value in (None, ""):
            continue
        if isinstance(value, dict):
            continue
        if isinstance(value, list):
            if not value or not all(isinstance(x, (str, int, float)) for x in value):
                continue
        if out.get(key) not in (None, "", []):
            continue
        out[key] = value
    return out


async def _with_roster_profile(
    acta: dict,
    family: ActasFamily,
    *,
    refresh: bool = False,
) -> dict:
    """Attach bloque/partido/foto (etc.) from the chamber roster onto votos[].

    So ``…/votos`` rows already carry what PersonCard needs — respond does not
    have to fetch the roster separately, and compose sees one enriched dataset.
    """
    votes = acta.get(family.votes_field)
    if not isinstance(votes, list) or not votes:
        return acta

    roster_family = next(
        (r for r in ROSTER_FAMILIES if r.chamber == family.chamber),
        None,
    )
    if roster_family is None:
        return acta

    try:
        rows = await upstream.get(
            roster_family.list_path,
            ttl=TTL_ROSTER,
            refresh=refresh,
        )
    except Exception:
        return acta
    if not isinstance(rows, list):
        return acta

    # Historical first, then active overwrites — current legislators win on
    # name collisions (the roster goes back decades).
    today = datetime.date.today().isoformat()
    by_name = _roster_name_index(rows, roster_family)
    by_name.update(
        _roster_name_index(
            filters.filter_active(rows, roster_family, today),
            roster_family,
        )
    )
    if not by_name:
        return acta

    enriched = []
    for vote in votes:
        if not isinstance(vote, dict):
            enriched.append(vote)
            continue
        voter = vote.get("nombre") or ""
        roster = by_name.get(_fold_person_name(voter))
        enriched.append(_stamp_scalars_from_roster(vote, roster) if roster else vote)

    return {**acta, family.votes_field: enriched}


def _stamp_acta_meta(votes: list, acta: dict) -> list:
    """Copy fecha/titulo from the parent acta onto each vote row."""
    meta = {k: acta[k] for k in _ACTA_META_KEYS if acta.get(k)}
    if not meta:
        return votes
    stamped = []
    for vote in votes:
        if isinstance(vote, dict):
            stamped.append({**meta, **vote})
        else:
            stamped.append(vote)
    return stamped


def _with_identity_fields(fields: list[str], extra: tuple[str, ...]) -> list[str]:
    """Keep identity/date columns even when the model asked for a slim projection.

    Follow-ups like "el dólar el día de esa votación" read `fecha` off the
    dataset index. A `fields=id,titulo` scan would otherwise throw the date
    away and leave the next turn with nothing to resolve against.
    """
    if not fields:
        return fields
    kept = [f for f in extra if f not in fields]
    return [*kept, *fields] if kept else fields


def _project_checked(rows: list[dict], fields: list[str], path: str) -> list[dict]:
    """Project *rows* onto *fields*, failing loudly if none of them exist.

    Silently returning empty objects would leave the model convinced the data
    is missing, when it actually just used the wrong key for this chamber
    (``id`` vs ``actaId``).
    """
    if rows:
        available = set(rows[0])
        if not (available & set(fields)):
            raise ProxyError(
                f"None of the requested fields {fields} exist on {path}. "
                f"Available fields: {sorted(available)}. Retry with these names."
            )
    return filters.project(rows, fields)


def _search_actas(
    rows: list[dict],
    family: ActasFamily,
    client_params: dict[str, Any],
) -> list[dict]:
    """Narrow an actas list by title search and date range.

    Runs on raw rows, before the vote transforms, so the expensive
    per-legislator work only touches the rows that survive.
    """
    title = client_params.get("title")
    if title:
        rows = filters.filter_by_text(rows, str(title), family.text_fields)

    desde = client_params.get("desde")
    hasta = client_params.get("hasta")
    if desde or hasta:
        rows = filters.filter_by_date(rows, desde, hasta)

    return rows


def _transform_actas_votes(
    rows: list[dict],
    family: ActasFamily,
    client_params: dict[str, Any],
) -> list[dict]:
    """Normalize each row's ``votos[]``, then keep, filter or summarize it."""
    vote = client_params.get("vote")
    keep_votes = _keeps_votes(client_params)

    transformed = []
    for row in rows:
        row = filters.normalize_votes(row, family)
        if vote:
            row = filters.filter_votes(row, family, str(vote))
        elif not keep_votes:
            row = filters.summarize_votes(row, family)
        transformed.append(row)
    return transformed


def _require_matches(
    rows: list[dict],
    path: str,
    scanned: int,
    client_params: dict[str, Any],
    filter_names: tuple[str, ...],
    suggestion: str = "",
) -> None:
    """Raise NoMatch when filters were supplied and nothing survived them.

    Only fires if the caller actually filtered: an endpoint that is genuinely
    empty upstream is a different problem and should stay an empty list.
    """
    if rows:
        return
    criteria = {k: client_params[k] for k in filter_names if client_params.get(k)}
    if not criteria:
        return
    message = (
        f"No records: 0 of {scanned} rows in {path} match "
        f"{_describe(criteria)}. {_NO_MATCH_GUIDANCE}"
    )
    raise NoMatch(f"{message} {suggestion}".rstrip())


def _keeps_votes(client_params: dict[str, Any]) -> bool:
    """Whether this request keeps the heavy per-legislator array."""
    return bool(client_params.get("vote")) or filters.is_true(
        client_params.get("includeVotes", False)
    )


def _name_needles(client_params: dict[str, Any]) -> list[str]:
    needles: list[str] = []
    name = client_params.get("name")
    if name:
        needles.append(str(name))
    raw_names = client_params.get("names")
    if raw_names:
        entries = (
            raw_names if isinstance(raw_names, (list, tuple)) else str(raw_names).split("|")
        )
        needles.extend(str(n) for n in entries)
    return needles


async def _apply_roster_filters(
    rows: list[dict],
    family: Any,
    client_params: dict[str, Any],
) -> list[dict]:
    """Filter a legislator roster by term, province and name.

    ``active`` defaults to true: these endpoints return the historical roster
    (Senado back to the 1940s, 1377 rows), so "los senadores por Misiones"
    would otherwise answer with 33 people, most of them from last century.
    Pass ``active=false`` for the historical list.

    Name matching uses the offline vector index (fingerprint from the full
    unfiltered list) then intersects with the province/active subset.
    """
    collection = coll.ROSTER_COLLECTION[family.chamber]
    expected_fp = coll.fingerprint_for(collection, rows)

    if filters.is_true(client_params.get("active", True)):
        today = datetime.date.today().isoformat()
        rows = filters.filter_active(rows, family, today)

    province = client_params.get("province")
    if province:
        rows = filters.filter_by_text(rows, str(province), ("provincia",))

    needles = _name_needles(client_params)
    if needles:
        try:
            rows = await names.match_roster(
                rows,
                needles,
                family,
                expected_fingerprint=expected_fp,
            )
        except vx.VectorIndexError as exc:
            raise ProxyError(str(exc)) from exc

    return rows


async def _apply_presidentes_filters(
    rows: list[dict],
    client_params: dict[str, Any],
) -> list[dict]:
    needles = _name_needles(client_params)
    if not needles:
        return rows
    expected_fp = coll.fingerprint_for(coll.PRESIDENTES, rows)
    try:
        return await names.match_presidentes(
            rows,
            needles,
            expected_fingerprint=expected_fp,
        )
    except vx.VectorIndexError as exc:
        raise ProxyError(str(exc)) from exc


async def _augment_actas_with_year_lists(
    rows: list[dict],
    family: ActasFamily,
    client_params: dict[str, Any],
    *,
    refresh: bool,
) -> list[dict]:
    """Merge ``/actas/{año}`` into the chamber list when a date window is set.

    Upstream ``/actas`` lists are incomplete for older years (gaps / recent-only
    for Diputados). Year-scoped paths hold the historical sessions. Without
    this merge, ``desde``/``hasta`` on the list path falsely returns NoMatch
    for whole mandates (e.g. Macri 2015–2019) even though year endpoints work.
    """
    desde = client_params.get("desde")
    hasta = client_params.get("hasta")
    if not desde and not hasta:
        return rows

    lo_raw = str(desde or "2000-01-01")[:4]
    hi_raw = str(hasta or datetime.date.today().isoformat())[:4]
    try:
        year_lo, year_hi = int(lo_raw), int(hi_raw)
    except ValueError:
        return rows
    if year_hi < year_lo or year_hi - year_lo > 40:
        return rows

    merged: dict[str, dict] = {}
    orphan: list[dict] = []
    for row in rows:
        key = str(row.get(family.id_field) or "").strip()
        if key:
            merged[key] = row
        else:
            orphan.append(row)

    for year in range(year_lo, year_hi + 1):
        for row in await _load_actas_year_list(family, year, refresh=refresh):
            key = str(row.get(family.id_field) or "").strip()
            if key:
                merged[key] = row
            else:
                orphan.append(row)

    return orphan + list(merged.values())


async def resolve(path: str, params: dict[str, Any] | None = None) -> Any:
    """Serve a proxy request.

    Args:
        path:   A proxy path template (synthetic route or upstream path).
        params: Flat param dict — path params are interpolated, synthetic
                params are applied here, anything else is forwarded upstream.

    Returns:
        A list of rows for list routes, a single object for ``/{id}`` detail
        routes, or the raw upstream payload for non-list endpoints.

    Raises:
        ProxyError:    The request is valid but nothing matched.
        UpstreamError: An upstream errored or was unreachable.
    """
    params = params or {}
    path_params, client_params, query_params = _split_params(path, params)
    refresh = filters.is_true(client_params.get("refresh", False))

    if path in EXTERNAL_ROUTES:
        return await _resolve_external(path, path_params, client_params)

    if path in SYNTHETIC_ROUTES:
        return await _resolve_synthetic(path, path_params, client_params)

    # ── Passthrough: interpolate path params, fetch (cached), then filter ────
    url_path = path
    for key, value in path_params.items():
        url_path = url_path.replace(f"{{{key}}}", upstream.path_value(key, value))

    unresolved = _PLACEHOLDER.findall(url_path)
    if unresolved:
        raise ProxyError(
            f"Missing required path parameter(s): {', '.join(unresolved)}. "
            "Provide them in the params dict."
        )

    data = await upstream.get(
        url_path,
        query=query_params,
        ttl=ttl_for(path),
        refresh=refresh,
    )
    data = _unwrap_row_collection(path, data)
    if not isinstance(data, list):
        return data  # scalar endpoints (presidencia, índices de viajes, …)

    rows = [r for r in data if isinstance(r, dict)]
    scanned = len(rows)
    fields = _field_list(client_params)

    actas = actas_family_for(path)
    roster = roster_family_for(path)

    if actas is not None:
        # Historical windows need year-scoped upstream lists — the chamber
        # ``/actas`` dump alone often has gaps (or only recent Diputados rows).
        if path == actas.list_path and (
            client_params.get("desde") or client_params.get("hasta")
        ):
            rows = await _augment_actas_with_year_lists(
                rows, actas, client_params, refresh=refresh
            )
            scanned = len(rows)
        rows = _search_actas(rows, actas, client_params)
        other = SENADO_ACTAS if actas is DIPUTADOS_ACTAS else DIPUTADOS_ACTAS
        suggestion = (
            f"This is the {actas.chamber} record. If the user may have the "
            f"chamber wrong, the same search on {other.list_path} is the "
            "single best next call."
        )
        if (
            actas is DIPUTADOS_ACTAS
            and (client_params.get("desde") or client_params.get("hasta"))
        ):
            suggestion = (
                "Diputados year-scoped actas are often missing upstream for "
                "older windows (2016–2019 404). Retry the same desde/hasta on "
                f"{SENADO_ACTAS.list_path} — do not tell the user the API lacks "
                "access or that the date filter is wrong."
            )
        _require_matches(
            rows,
            path,
            scanned,
            client_params,
            ("title", "desde", "hasta"),
            suggestion=suggestion,
        )
    elif roster is not None:
        rows = await _apply_roster_filters(rows, roster, client_params)
        _require_matches(
            rows, path, scanned, client_params, ("province", "name", "names", "active")
        )
        if fields:
            fields = _with_identity_fields(fields, _ROSTER_PROFILE_FIELDS)
    elif path == "/v1/presidentes":
        rows = await _apply_presidentes_filters(rows, client_params)
        _require_matches(
            rows, path, scanned, client_params, ("name", "names")
        )
        if fields:
            fields = _with_identity_fields(fields, _ROSTER_PROFILE_FIELDS)
    elif path in DATE_SERIES_PATHS and (
        client_params.get("desde") or client_params.get("hasta")
    ):
        # Charts want resolution: keep up to MAX_SERIES_POINTS for the range
        # instead of the much tighter generic cap.
        rows = filters.filter_by_date(
            rows, client_params.get("desde"), client_params.get("hasta")
        )
        _require_matches(rows, path, scanned, client_params, ("desde", "hasta"))
        return _project_checked(rows, fields, path) if fields else rows
    elif path in CALENDAR_PATHS and (
        client_params.get("desde") or client_params.get("hasta")
    ):
        # Apply before SAFETY_CAP so older eventos/feriados survive.
        rows = filters.filter_by_date(
            rows, client_params.get("desde"), client_params.get("hasta")
        )
        _require_matches(rows, path, scanned, client_params, ("desde", "hasta"))
        if fields:
            return _project_checked(rows, fields, path)
        return rows

    # Cap BEFORE the per-row transforms below: an actas list carries ~257
    # vote entries per row, so normalizing all 1300 rows to then drop all but
    # the last 60 costs ~300 ms of pure waste.
    votes_in_output = (
        actas is not None
        and _keeps_votes(client_params)
        and (not fields or actas.votes_field in fields)
    )
    if votes_in_output:
        row_cap = DETAIL_ROW_CAP
    elif fields:
        row_cap = PROJECTED_CAP
    else:
        row_cap = SAFETY_CAP
    rows = filters.cap(rows, row_cap)

    if actas is not None:
        rows = _transform_actas_votes(rows, actas, client_params)
        fields = _with_identity_fields(fields, (actas.id_field, "fecha"))

    if fields:
        rows = _project_checked(rows, fields, path)

    # After projection so a slim fields= example cannot strip bio/foto.
    # Exactly one person → Wikipedia bio/photo. Never enrich full rosters.
    if (roster is not None or path == "/v1/presidentes") and len(rows) == 1:
        rows = [await wiki.enrich_person(rows[0], refresh=refresh)]
    return rows


async def _resolve_external(
    path: str,
    path_params: dict[str, Any],
    client_params: dict[str, Any],
) -> Any:
    """Dispatch BCRA / Series / Open-Meteo proxy routes."""
    refresh = filters.is_true(client_params.get("refresh", False))
    desde = client_params.get("desde")
    hasta = client_params.get("hasta")
    provincia = client_params.get("provincia") or client_params.get("province")

    try:
        if path == "/v1/bcra/variables":
            return bcra.list_variables()
        if path == "/v1/bcra/{alias}":
            alias = str(path_params.get("alias") or "")
            rows = await bcra.fetch_series(
                alias, desde=desde, hasta=hasta, refresh=refresh
            )
            if not rows:
                raise NoMatch(
                    f"No records: BCRA alias {alias!r} returned 0 points for "
                    f"desde={desde!r} hasta={hasta!r}. {_NO_MATCH_GUIDANCE}"
                )
            return rows

        if path == "/v1/cammesa":
            return cammesa.list_aliases()
        if path == "/v1/cammesa/demanda":
            rows = await cammesa.fetch_wide(
                desde=desde, hasta=hasta, refresh=refresh
            )
            if not rows:
                raise NoMatch(
                    f"No records: CAMMESA demanda empty for "
                    f"desde={desde!r} hasta={hasta!r}. {_NO_MATCH_GUIDANCE}"
                )
            return rows
        if path == "/v1/cammesa/{alias}":
            alias = str(path_params.get("alias") or "")
            rows = await cammesa.fetch_by_alias(
                alias, desde=desde, hasta=hasta, refresh=refresh
            )
            if not rows:
                raise NoMatch(
                    f"No records: CAMMESA alias {alias!r} empty. "
                    f"{_NO_MATCH_GUIDANCE}"
                )
            return rows

        if path == "/v1/series":
            return series.list_aliases()
        if path == "/v1/series/search":
            q = client_params.get("q")
            if not q:
                raise ProxyError("/v1/series/search requires q=…")
            hits = await series.search(str(q), refresh=refresh)
            if not hits:
                raise NoMatch(
                    f"No records: series search {q!r} matched nothing. "
                    f"{_NO_MATCH_GUIDANCE}"
                )
            return hits
        if path == "/v1/series/{alias}":
            alias = str(path_params.get("alias") or "")
            rows = await series.fetch_by_alias(
                alias, desde=desde, hasta=hasta, refresh=refresh
            )
            if not rows:
                raise NoMatch(
                    f"No records: series alias {alias!r} returned 0 points. "
                    f"{_NO_MATCH_GUIDANCE}"
                )
            return rows
        if path == "/v1/series/id/{serieId}":
            serie_id = str(path_params.get("serieId") or "")
            rows = await series.fetch_by_id(
                serie_id, desde=desde, hasta=hasta, refresh=refresh
            )
            if not rows:
                raise NoMatch(
                    f"No records: serieId {serie_id!r} returned 0 points. "
                    f"{_NO_MATCH_GUIDANCE}"
                )
            return rows

        if path == "/v1/clima/historico":
            if not desde or not hasta:
                raise ProxyError(
                    "/v1/clima/historico requires desde and hasta (ISO dates)."
                )
            rows = await openmeteo.historico(
                provincia=str(provincia) if provincia else None,
                desde=str(desde),
                hasta=str(hasta),
                refresh=refresh,
            )
            if not rows:
                raise NoMatch(
                    f"No records: climate historico empty for "
                    f"provincia={provincia!r} {desde}…{hasta}. {_NO_MATCH_GUIDANCE}"
                )
            return rows
        if path == "/v1/clima/pronostico":
            dias = client_params.get("dias") or 7
            try:
                dias_i = int(dias)
            except (TypeError, ValueError):
                dias_i = 7
            rows = await openmeteo.pronostico(
                provincia=str(provincia) if provincia else None,
                dias=dias_i,
                refresh=refresh,
            )
            if not rows:
                raise NoMatch(
                    f"No records: climate forecast empty. {_NO_MATCH_GUIDANCE}"
                )
            return rows
        if path == "/v1/clima/actual":
            rows = await openmeteo.actual(
                provincia=str(provincia) if provincia else None,
                refresh=refresh,
            )
            if not rows:
                raise NoMatch(
                    f"No records: climate actual empty. {_NO_MATCH_GUIDANCE}"
                )
            return rows

        if path == "/v1/historico/dias":
            rows = historico.list_days(desde=str(desde) if desde else None, hasta=str(hasta) if hasta else None)
            if not rows:
                raise NoMatch(
                    f"No records: no curated historical days in "
                    f"desde={desde!r} hasta={hasta!r}. {_NO_MATCH_GUIDANCE}"
                )
            return rows
        if path == "/v1/historico/dia":
            fecha = client_params.get("fecha")
            if not fecha:
                raise ProxyError("/v1/historico/dia requires fecha=YYYY-MM-DD.")
            row = await historico.fetch_day(str(fecha), refresh=refresh)
            if not row:
                raise NoMatch(
                    f"No records: fecha {fecha!r} is not in the curated "
                    f"historical index (2016–2024). Try /v1/historico/dias or "
                    f"/v1/wiki/summary?q=…. {_NO_MATCH_GUIDANCE}"
                )
            return row
        if path == "/v1/wiki/summary":
            q = client_params.get("q")
            if not q:
                raise ProxyError("/v1/wiki/summary requires q=… (article title).")
            row = await wiki.fetch_summary(str(q), refresh=refresh)
            if not row.get("extract") and not row.get("bio"):
                raise NoMatch(
                    f"No records: Wikipedia summary empty for {q!r}. "
                    f"{_NO_MATCH_GUIDANCE}"
                )
            return row
        if path == "/v1/noticias":
            q = str(client_params.get("q") or "").strip()
            if not q:
                raise ProxyError("/v1/noticias requires q=… (search terms).")
            try:
                rows = await news.search(
                    q,
                    desde=desde,
                    hasta=hasta,
                    refresh=refresh,
                )
            except ValueError as exc:
                raise ProxyError(str(exc)) from exc
            if not rows:
                raise NoMatch(
                    f"No records: Google News matched no articles for q={q!r}, "
                    f"desde={desde!r}, hasta={hasta!r}. {_NO_MATCH_GUIDANCE}"
                )
            return rows

        if path == "/v1/cine/discover":
            rows = await tmdb.discover(
                anio=client_params.get("anio") or client_params.get("año"),
                genero=(
                    str(client_params["genero"])
                    if client_params.get("genero") is not None
                    else None
                ),
                sort=(
                    str(client_params["sort"])
                    if client_params.get("sort") is not None
                    else None
                ),
                page=(
                    int(client_params["page"])
                    if client_params.get("page") is not None
                    else None
                ),
                refresh=refresh,
            )
            if not rows:
                raise NoMatch(
                    f"No records: cine discover empty for "
                    f"anio={client_params.get('anio')!r} "
                    f"genero={client_params.get('genero')!r}. "
                    f"{_NO_MATCH_GUIDANCE}"
                )
            return rows
        if path == "/v1/cine/search":
            q = client_params.get("q")
            if not q:
                raise ProxyError("/v1/cine/search requires q=… (film title).")
            rows = await tmdb.search_movies(
                str(q),
                anio=client_params.get("anio") or client_params.get("año"),
                refresh=refresh,
            )
            if not rows:
                raise NoMatch(
                    f"No records: no Argentine films matched q={q!r}. "
                    f"{_NO_MATCH_GUIDANCE}"
                )
            return rows
        if path == "/v1/cine/pelicula/{id}":
            movie_id = path_params.get("id")
            if movie_id is None or str(movie_id).strip() == "":
                raise ProxyError("/v1/cine/pelicula/{{id}} requires id.")
            row = await tmdb.movie_detail(str(movie_id), refresh=refresh)
            if not row:
                raise NoMatch(
                    f"No records: film id {movie_id!r} not found. "
                    f"{_NO_MATCH_GUIDANCE}"
                )
            return row
        if path == "/v1/cine/persona/search":
            q = client_params.get("q")
            if not q:
                raise ProxyError(
                    "/v1/cine/persona/search requires q=… (person name)."
                )
            rows = await tmdb.search_people(str(q), refresh=refresh)
            if not rows:
                raise NoMatch(
                    f"No records: no people matched q={q!r}. "
                    f"{_NO_MATCH_GUIDANCE}"
                )
            return rows
        if path == "/v1/cine/persona/{id}":
            person_id = path_params.get("id")
            if person_id is None or str(person_id).strip() == "":
                raise ProxyError("/v1/cine/persona/{{id}} requires id.")
            row = await tmdb.person_detail(str(person_id), refresh=refresh)
            if not row:
                raise NoMatch(
                    f"No records: person id {person_id!r} not found. "
                    f"{_NO_MATCH_GUIDANCE}"
                )
            return row
        if path == "/v1/cine/persona/{id}/filmografia":
            person_id = path_params.get("id")
            if person_id is None or str(person_id).strip() == "":
                raise ProxyError(
                    "/v1/cine/persona/{{id}}/filmografia requires id."
                )
            rows = await tmdb.person_filmography(
                str(person_id), refresh=refresh
            )
            if not rows:
                raise NoMatch(
                    f"No records: no Argentine films for person id "
                    f"{person_id!r}. {_NO_MATCH_GUIDANCE}"
                )
            return rows

        if path == "/v1/rem":
            return rem.list_aliases()
        if path == "/v1/rem/ultimo":
            rows = await rem.fetch_ultimo(refresh=refresh)
            rows = _filter_rem_rows(rows, client_params)
            if not rows:
                raise NoMatch(
                    f"No records: REM ultimo empty for "
                    f"alias={client_params.get('alias')!r}. {_NO_MATCH_GUIDANCE}"
                )
            return rows
        if path == "/v1/rem/informe":
            anio = client_params.get("año") or client_params.get("anio")
            mes = client_params.get("mes")
            if anio is None or mes is None:
                raise ProxyError(
                    "/v1/rem/informe requires año=YYYY and mes=MM."
                )
            rows = await rem.fetch_informe(int(anio), mes, refresh=refresh)
            rows = _filter_rem_rows(rows, client_params)
            if not rows:
                raise NoMatch(
                    f"No records: REM informe {anio}-{mes} empty for "
                    f"alias={client_params.get('alias')!r}. {_NO_MATCH_GUIDANCE}"
                )
            return rows
        if path == "/v1/rem/{alias}":
            alias = str(path_params.get("alias") or "")
            rows = await rem.series_for_alias(
                alias, desde=desde, hasta=hasta, refresh=refresh
            )
            if not rows:
                raise NoMatch(
                    f"No records: REM series {alias!r} empty. {_NO_MATCH_GUIDANCE}"
                )
            return rows
        if path == "/v1/rem/vs-real/{alias}":
            alias = str(path_params.get("alias") or "")
            horizon = str(client_params.get("horizon") or "1m")
            rows = await rem.vs_real(
                alias,
                horizon=horizon,
                desde=desde,
                hasta=hasta,
                refresh=refresh,
            )
            if not rows:
                raise NoMatch(
                    f"No records: REM vs-real {alias!r} "
                    f"horizon={horizon!r} matched nothing. {_NO_MATCH_GUIDANCE}"
                )
            return rows

        if path == "/v1/plazos":
            return finanzas_productos.list_plazos_aliases()
        if path == "/v1/plazos/ranking":
            limit_raw = client_params.get("limit")
            try:
                limit = int(limit_raw) if limit_raw is not None else 25
            except (TypeError, ValueError):
                limit = 25
            limit = max(1, min(limit, 40))
            rows = await finanzas_productos.fetch_plazos_ranking(
                limit=limit, refresh=refresh
            )
            if not rows:
                raise NoMatch(
                    f"No records: plazos ranking empty. {_NO_MATCH_GUIDANCE}"
                )
            return rows
        if path == "/v1/hipotecarios-uva":
            rows = await finanzas_productos.fetch_hipotecarios(refresh=refresh)
            if not rows:
                raise NoMatch(
                    f"No records: hipotecarios UVA empty. {_NO_MATCH_GUIDANCE}"
                )
            return rows
        if path == "/v1/fci":
            return finanzas_productos.list_fci_aliases()
        if path == "/v1/fci/search":
            q = str(client_params.get("q") or "").strip()
            if not q:
                raise ProxyError("/v1/fci/search requires q=… (fund name).")
            rows = await finanzas_productos.search_fci(q, refresh=refresh)
            if not rows:
                raise NoMatch(
                    f"No records: FCI search q={q!r} matched 0 funds. "
                    f"{_NO_MATCH_GUIDANCE}"
                )
            return rows
        if path == "/v1/fci/{slug}":
            slug = str(path_params.get("slug") or "")
            return await finanzas_productos.fetch_fci_detail(
                slug, refresh=refresh
            )
        if path == "/v1/fci/{slug}/historico":
            slug = str(path_params.get("slug") or "")
            rows = await finanzas_productos.fetch_fci_historico(
                slug, desde=desde, hasta=hasta, refresh=refresh
            )
            if not rows:
                raise NoMatch(
                    f"No records: FCI historico {slug!r} empty for "
                    f"desde={desde!r} hasta={hasta!r}. {_NO_MATCH_GUIDANCE}"
                )
            return rows
    except UpstreamError:
        raise

    raise ProxyError(f"External route {path!r} has no handler.")


_FEE_LIST_KEYS: dict[str, str] = {
    "/v1/finanzas/brokers/comisiones": "comisiones",
    "/v1/finanzas/cobros/comisiones": "comisiones",
    "/v1/finanzas/remesas": "remesas",
}

#: Template path → nested list keys to flatten into comparable rows.
#: Multiple keys are concatenated (e.g. nacionales + internacionales).
#: Parent scalar fields (diputadoId, …) are stamped onto each child.
_ROW_COLLECTION_KEYS: dict[str, tuple[str, ...]] = {
    **{path: (key,) for path, key in _FEE_LIST_KEYS.items()},
    "/v1/finanzas/fci/fondos": ("fondos",),
    "/v1/diputados/misiones": ("misiones",),
    "/v1/diputados/diputados/{id}/misiones": ("misiones",),
    "/v1/diputados/diputados/{id}/viajes": ("nacionales", "internacionales"),
    "/v1/senado/senadores/{id}/viajes": ("nacionales", "internacionales"),
}


def _unwrap_row_collection(path: str, data: Any) -> Any:
    """Flatten wrapped collections into a list of row dicts.

    Upstream often returns ``{diputadoId, nacionales:[…]}`` or
    ``{fechaActualizacion, comisiones:[…]}``. List/ComparisonTable bind to
    arrays — a one-row wrapper dumps the nested JSON into a cell.
    """
    keys = _ROW_COLLECTION_KEYS.get(path)
    if not keys or not isinstance(data, dict):
        return data

    stamped: list[dict] = []
    parent = {
        k: v
        for k, v in data.items()
        if k not in keys and not isinstance(v, (list, dict))
    }
    for key in keys:
        rows = data.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            item = {**parent, **row}
            stamped.append(item)
    return stamped if stamped or any(isinstance(data.get(k), list) for k in keys) else data


def _filter_rem_rows(
    rows: list[dict],
    client_params: dict[str, Any],
) -> list[dict]:
    alias_name = client_params.get("alias")
    spec = rem.get_alias(str(alias_name)) if alias_name else None
    return rem.filter_rows(
        rows,
        alias=spec,
        indicador=None if spec else (str(client_params["indicador"]) if client_params.get("indicador") else None),
        muestra=str(client_params.get("muestra") or "todos"),
        periodo_tipo=(
            str(client_params["periodoTipo"])
            if client_params.get("periodoTipo")
            else None
        ),
    )


def _actas_families(chamber: str | None) -> tuple[ActasFamily, ...]:
    if not chamber:
        return ACTAS_FAMILIES
    key = filters.normalize(chamber)
    if key.startswith("sen"):
        return (SENADO_ACTAS,)
    if key.startswith("dip"):
        return (DIPUTADOS_ACTAS,)
    return ACTAS_FAMILIES


def _compact_acta(row: dict, family: ActasFamily) -> dict:
    return {
        "id": row.get(family.id_field),
        "titulo": row.get("titulo"),
        "fecha": row.get("fecha"),
        "resultado": row.get("resultado"),
        "camara": family.chamber,
    }


def _roll_call(row: dict, family: ActasFamily) -> list[dict]:
    """Flatten one acta into stamped vote rows for the Acta widget."""
    normalized = filters.normalize_votes(row, family)
    votes = normalized.get(family.votes_field) or []
    if not isinstance(votes, list) or not votes:
        return [_compact_acta(row, family)]
    stamped = _stamp_acta_meta(votes, normalized)
    acta_id = row.get(family.id_field)
    out = []
    for vote in stamped:
        if not isinstance(vote, dict):
            continue
        out.append({
            **vote,
            "id": acta_id,
            "camara": family.chamber,
        })
    return out or [_compact_acta(row, family)]


async def search_actas(query: str, chamber: str | None = None) -> list[dict]:
    """Find actas by name via the offline vector index + a small LLM pick.

    No exact/substring pre-filter — chat queries rarely match titles
    verbatim. Flow: load precomputed embeddings → top-k → model picks ids
    among those candidates only. Hits return a **compact** id/título/fecha/
    resultado/camara row (not the full roll call) so the canvas stays light;
    the agent fetches ``…/votos`` only if the user asks who voted how.
    Zero hits → ``NoMatch``. Indexes from ``scripts/generate_embeddings.py``.
    """
    needle = str(query or "").strip()
    if not needle:
        raise ProxyError("search_actas needs a query (the law name the user typed).")

    families = _actas_families(chamber)
    by_id: dict[str, tuple[ActasFamily, dict]] = {}
    collections_fp: list[tuple[str, str]] = []
    scanned = 0

    for family in families:
        rows = await upstream.get(family.list_path, ttl=TTL_ACTAS)
        if not isinstance(rows, list):
            continue
        rows = [r for r in rows if isinstance(r, dict)]
        scanned += len(rows)
        collection = coll.ACTAS_COLLECTION[family.chamber]
        collections_fp.append((collection, coll.fingerprint_for(collection, rows)))
        for row in rows:
            raw = row.get(family.id_field)
            if raw is None or raw == "":
                continue
            by_id[coll.composite_id(family.chamber, raw)] = (family, row)

    if not collections_fp:
        raise ProxyError("search_actas could not load any actas lists from upstream.")

    try:
        hits = await vx.query_many(collections_fp, needle, k=vx.DEFAULT_TOP_K)
    except vx.VectorIndexError as exc:
        raise ProxyError(str(exc)) from exc

    if not hits:
        scopes = " and ".join(f.chamber for f in families)
        raise NoMatch(
            f"No records: 0 of {scanned} actas in {scopes} matched {needle!r}. "
            f"{_NO_MATCH_GUIDANCE}"
        )

    lines = [f"{hit.id}\t{hit.label}" for hit in hits]
    stubs = {hit.id: {"id": hit.id} for hit in hits}
    picked = await match_directory(
        kind="actas-candidates",
        lines=lines,
        queries=[needle],
        by_id=stubs,
        role="default",
    )

    resolved: list[tuple[ActasFamily, dict]] = []
    seen: set[str] = set()
    for stub in picked:
        cid = str(stub.get("id") or "")
        if cid in seen or cid not in by_id:
            continue
        seen.add(cid)
        resolved.append(by_id[cid])

    if not resolved:
        scopes = " and ".join(f.chamber for f in families)
        raise NoMatch(
            f"No records: 0 of {scanned} actas in {scopes} matched {needle!r}. "
            f"{_NO_MATCH_GUIDANCE} Do NOT answer by describing whatever is "
            "already on the canvas from a previous topic."
        )

    compact = [_compact_acta(row, family) for family, row in resolved]
    return filters.cap(compact, filters.EXACT_LIST_CAP)
