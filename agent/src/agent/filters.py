"""Post-fetch client-side filters for ArgentinaDatos endpoints.

Some endpoints return the full historical series with no server-side date range
parameter.  This module provides:

  - A generic ``filter_by_date`` helper (filters + downsamples a dated array).
  - ``POST_FILTERS``: path-template → filter function, imported by fetch.py.
  - ``SYNTHETIC_PARAMS``: paths that get extra ``desde``/``hasta`` params injected
    into the catalog so the LLM knows it can pass date bounds.

Flow inside fetch_argentinadatos (not a LangChain tool):
    HTTP GET (full series)
        → POST_FILTERS[path](data, desde, hasta)
        → compact JSON returned to LLM
"""

from __future__ import annotations

from typing import Any

# Maximum number of data points to return to the LLM from a filtered series.
_MAX_POINTS = 400

# ── Generic helper ─────────────────────────────────────────────────────────────


def filter_by_date(
    data: list[dict[str, Any]],
    desde: str | None,
    hasta: str | None,
    max_points: int = _MAX_POINTS,
) -> list[dict[str, Any]]:
    """Filter a dated array by an optional ISO date range, then downsample.

    Args:
        data:       List of dicts each containing a ``fecha`` field (ISO date).
        desde:      Lower bound inclusive (``YYYY-MM-DD``).  ``None`` → no lower bound.
        hasta:      Upper bound inclusive (``YYYY-MM-DD``).  ``None`` → no upper bound.
        max_points: Hard cap on returned rows; evenly spaced decimation when exceeded.

    Returns:
        Filtered (and possibly downsampled) list.
    """
    if not isinstance(data, list):
        return data  # unexpected shape — pass through

    filtered: list[dict[str, Any]] = []
    for row in data:
        fecha = row.get("fecha", "")
        if desde and fecha < desde:
            continue
        if hasta and fecha > hasta:
            continue
        filtered.append(row)

    # Downsample: keep evenly-spaced indices when over cap
    if len(filtered) > max_points:
        step = len(filtered) / max_points
        filtered = [filtered[int(i * step)] for i in range(max_points)]

    return filtered


# ── Per-path processors ────────────────────────────────────────────────────────


def _filter_cotizaciones(
    data: Any,
    client_params: dict[str, str],
) -> Any:
    return filter_by_date(
        data,
        desde=client_params.get("desde"),
        hasta=client_params.get("hasta"),
    )


def _filter_indices(
    data: Any,
    client_params: dict[str, str],
) -> Any:
    return filter_by_date(
        data,
        desde=client_params.get("desde"),
        hasta=client_params.get("hasta"),
    )


# ── Registry ──────────────────────────────────────────────────────────────────

#: path template → callable(payload, client_params) → filtered payload
POST_FILTERS: dict[str, Any] = {
    "/v1/cotizaciones/dolares": _filter_cotizaciones,
    "/v1/cotizaciones/dolares/{casa}": _filter_cotizaciones,
    "/v1/finanzas/indices/inflacion": _filter_indices,
    "/v1/finanzas/indices/inflacionInteranual": _filter_indices,
    "/v1/finanzas/indices/uva": _filter_indices,
    "/v1/finanzas/indices/riesgo-pais": _filter_indices,
    "/v1/politica/indices/confianza-gobierno": _filter_indices,
    "/v1/finanzas/tasas/depositos30Dias": _filter_indices,
    "/v1/finanzas/rendimientos/{entidad}": _filter_indices,
}

#: paths that receive synthetic ``desde`` / ``hasta`` catalog params
FILTERABLE_PATHS: frozenset[str] = frozenset(POST_FILTERS)
