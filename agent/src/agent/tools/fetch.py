"""ArgentinaDatos fetch tool — the single HTTP tool exposed to the LLM.

The model picks an endpoint path from the catalog injected in the system
prompt, supplies param values, and this tool resolves them against the live API.

Path parameters (e.g. {casa}) are interpolated into the URL.
Any remaining params are forwarded as query-string parameters.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
from langchain_core.tools import tool

from ..catalog import catalog

_BASE_URL = "https://api.argentinadatos.com"


@tool
async def fetch_argentinadatos(
    path: str,
    params: dict[str, Any] | None = None,
) -> str:
    """Fetch data from the ArgentinaDatos API.

    Use the catalog provided in the system prompt to choose the right endpoint.

    Args:
        path:   Endpoint path template exactly as listed in the catalog
                (e.g. '/v1/cotizaciones/dolares/{casa}').
        params: Parameter values as a flat dict.  Path parameters (e.g. casa='blue')
                are interpolated into the URL; anything else becomes a query param.

    Returns:
        Raw JSON response text on success, or a structured error string.
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

    # ── Interpolate path params ────────────────────────────────────────────────
    url_path = path
    path_param_names = {p.name for p in op.params if p.location == "path"}
    query_params: dict[str, Any] = {}

    for key, value in params.items():
        if key in path_param_names:
            url_path = url_path.replace(f"{{{key}}}", str(value))
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
        return response.text
    except httpx.HTTPStatusError as exc:
        return f"HTTP {exc.response.status_code}: {exc.response.text[:500]}"
    except httpx.RequestError as exc:
        return f"Request error connecting to ArgentinaDatos: {exc}"
