"""The single data tool exposed to the LLM.

Thin adapter: it validates the path against the catalog, hands everything to
the in-process proxy (``agent.proxy``), and serializes the result.  All the
real work — caching, id lookup, title/province search, vote filtering, field
projection, row caps — lives in the proxy, so the model only has to pick a
path and params.

See ``proxy/routes.py`` for the surface and ``proxy/filters.py`` for the
filtering semantics.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from .. import proxy
from ..catalog import catalog


@tool
async def fetch_argentinadatos(
    path: str,
    params: dict[str, Any] | None = None,
) -> str:
    """Fetch Argentine public/financial data from the catalog.

    Pick a path from the catalog in the system prompt and pass its params.
    Filtering is done server-side, so ask for exactly what you need.
    Covers ArgentinaDatos plus BCRA stocks, Series de Tiempo (INDEC),
    Open-Meteo climate, curated historical days (Wikipedia), wiki
    summaries, Google News headlines, and TMDB Argentine cinema — all under
    the same path surface.

    Named laws go through search_actas, not this tool. Use this for series,
    rosters, "últimas leyes", and a roll call once you already have an acta id:
        {"path": "/v1/diputados/actas", "params": {"fields": "id,titulo,fecha"}}
        {"path": "/v1/diputados/actas/id/{actaId}/votos",
         "params": {"actaId": "<id from search_actas or a scan>"}}

    Rosters (historical unless filtered — active=true is the default):
        {"path": "/v1/senado/senadores", "params": {"province": "Misiones"}}
        {"path": "/v1/diputados/diputados", "params": {"names": "Yasky, Hugo|Yedlin, Pablo"}}

    Series (pass a date range to keep full resolution):
        {"path": "/v1/cotizaciones/dolares/{casa}",
         "params": {"casa": "blue", "desde": "2026-08-01", "hasta": "2026-08-31"}}
        {"path": "/v1/bcra/{alias}", "params": {"alias": "reservas", "desde": "2019-12-10"}}
        {"path": "/v1/series/{alias}", "params": {"alias": "emae", "desde": "2020-01-01"}}
        {"path": "/v1/historico/dia",
         "params": {"fecha": "2023-12-10"}}
        {"path": "/v1/presidentes", "params": {"name": "Javier Milei"}}
        {"path": "/v1/clima/historico",
         "params": {"provincia": "CABA", "desde": "2023-12-10", "hasta": "2023-12-10"}}
        {"path": "/v1/wiki/summary", "params": {"q": "Presidencia de Javier Milei"}}
        {"path": "/v1/noticias",
         "params": {"q": "Milei inflación", "desde": "2024-01-01"}}

    An empty list or a "No records" error means nothing matched the criteria —
    the dataset itself is available, so say that nothing matched instead of
    claiming the data is out of reach.

    Args:
        path:   Endpoint path template exactly as listed in the catalog.
        params: Flat dict of values — path params (e.g. casa='blue',
                actaId from a previous scan) plus any query params the
                catalog lists for that path.

    Returns:
        JSON text on success, or a message explaining what went wrong.
    """
    params = params or {}

    # Accept both the template ("/actas/id/{actaId}" + {"actaId": "5995"}) and
    # the already-filled path ("/actas/id/5995"), which is what models tend to
    # send.  Values recovered from the path are merged in, explicit params win.
    matched = catalog.match(path)
    if matched is None:
        all_paths = "\n".join(f"  {p}" for p in sorted(catalog.paths()))
        return (
            f"Error: '{path}' is not in the catalog.\n"
            f"Valid paths:\n{all_paths}"
        )
    op, from_path = matched

    try:
        data = await proxy.resolve(op.path, {**from_path, **params})
    except proxy.ProxyError as exc:
        return str(exc)
    except proxy.UpstreamError as exc:
        return f"Error fetching upstream data: {exc}"

    if isinstance(data, str):
        return data
    return json.dumps(data, ensure_ascii=False)
