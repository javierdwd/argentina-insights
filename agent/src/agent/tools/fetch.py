"""ArgentinaDatos fetch tool — the single HTTP tool exposed to the LLM.

The model picks an endpoint path from the catalog injected in the system
prompt, supplies param values, and this tool resolves them against the live API.

Path parameters (e.g. {casa}) are interpolated into the URL.
Query parameters are forwarded as-is.
Client-side parameters (location="client", e.g. ``desde``/``hasta``) are
stripped from the HTTP request and applied as post-fetch filters — the API
never sees them.  This allows the LLM to request date-bounded slices of
endpoints that return the full historical series.

If a filterable endpoint is called without date bounds the response is
capped at the most recent _SAFETY_CAP rows to protect the LLM context window.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from langchain_core.tools import tool

from ..catalog import catalog
from ..filters import POST_FILTERS

_BASE_URL = "https://api.argentinadatos.com"

# Rows returned when a filterable series is fetched with no date bounds.
_SAFETY_CAP = 60

# ArgentinaDatos path ``fecha`` values use YYYY/MM/DD, not ISO YYYY-MM-DD.
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _path_value(name: str, value: Any) -> str:
    """Format a path-parameter value for the ArgentinaDatos URL.

    The OpenAPI spec marks ``fecha`` as ``format: date`` (ISO), but the live
    API only accepts slashes (``2023/12/31``).  ISO values 404; rewrite them.
    Non-date tokens such as ``ultimo`` / ``penultimo`` are left unchanged.
    """
    text = str(value)
    if name == "fecha" and _ISO_DATE.match(text):
        return text.replace("-", "/")
    return text


@tool
async def fetch_argentinadatos(
    path: str,
    params: dict[str, Any] | None = None,
) -> str:
    """Fetch data from the ArgentinaDatos API.

    Use the catalog provided in the system prompt to choose the right endpoint.

    For historical-series endpoints (inflación, dólar, UVA, riesgo país, etc.)
    pass ``desde`` and ``hasta`` (ISO format ``YYYY-MM-DD``) inside ``params``
    to receive only the requested date range.  Without those bounds the response
    is capped at the most recent rows.

    Args:
        path:   Endpoint path template exactly as listed in the catalog
                (e.g. '/v1/cotizaciones/dolares/{casa}').
        params: Parameter values as a flat dict.  Path parameters (e.g. casa='blue')
                are interpolated into the URL; ISO dates on path ``fecha`` are
                rewritten to ``YYYY/MM/DD``; ``desde``/``hasta`` are applied
                client-side; anything else becomes a query param.

    Returns:
        JSON text on success, or a structured error string.
    """
    params = params or {}

    # ── Validate against catalog ───────────────────────────────────────────────
    op = catalog.get(path)
    if op is None:
        all_paths = "\n".join(f"  {p}" for p in sorted(catalog.paths()))
        return (
            f"Error: '{path}' is not in the catalog.\n"
            f"Valid paths:\n{all_paths}"
        )

    # ── Split params by location ───────────────────────────────────────────────
    path_param_names = {p.name for p in op.params if p.location == "path"}
    client_param_names = {p.name for p in op.params if p.location == "client"}

    url_path = path
    query_params: dict[str, Any] = {}
    client_params: dict[str, str] = {}

    for key, value in params.items():
        if key in path_param_names:
            url_path = url_path.replace(f"{{{key}}}", _path_value(key, value))
        elif key in client_param_names:
            client_params[key] = str(value)
        else:
            query_params[key] = value

    # Detect un-substituted path params
    unresolved = re.findall(r"\{(\w+)\}", url_path)
    if unresolved:
        return (
            f"Error: missing required path parameter(s): {', '.join(unresolved)}. "
            "Provide them in the params dict."
        )

    url = _BASE_URL + url_path

    # ── HTTP GET ───────────────────────────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=query_params or None)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return f"HTTP {exc.response.status_code}: {exc.response.text[:500]}"
    except httpx.RequestError as exc:
        return f"Request error connecting to ArgentinaDatos: {exc}"

    # ── Post-filter (client-side date range / safety cap) ─────────────────────
    filter_fn = POST_FILTERS.get(path)
    if filter_fn is not None:
        try:
            data = response.json()
        except Exception:
            return response.text  # not JSON — pass through

        if client_params:
            # LLM supplied date bounds → apply the filter
            filtered = filter_fn(data, client_params)
        else:
            # No bounds → cap at the most recent rows to protect context window
            if isinstance(data, list) and len(data) > _SAFETY_CAP:
                filtered = data[-_SAFETY_CAP:]
            else:
                filtered = data

        return json.dumps(filtered, ensure_ascii=False)

    return response.text
