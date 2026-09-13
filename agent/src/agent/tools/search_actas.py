"""Find a named law in the congressional voting record.

The model only passes the user's words. Title match is resolved in the proxy
(vector index + pick). Returns a compact acta summary (id, título, fecha,
resultado, cámara) — not the full roll call. Fetch ``…/actas/id/{id}/votos``
when the user asks how each legislator voted.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from .. import proxy


@tool
async def search_actas(
    query: str,
    chamber: str | None = None,
) -> str:
    """Find a named Argentine law or bill in Diputados and Senado actas.

    Call this whenever the user names a law, bill, or acta — including
    follow-ups like "y la ley X?". Pass only the law name, not the whole
    sentence. Omit chamber unless they named one; do not ask
    nacional/provincial first. Returns a compact summary; use
    fetch_argentinadatos on …/actas/id/{actaId}/votos only if they ask
    for the per-legislator roll call.

    Args:
        query: The law name (not the surrounding question).
        chamber: Optional "diputados" or "senado". Omit to search both.
    """
    try:
        data = await proxy.search_actas(query, chamber)
    except proxy.ProxyError as exc:
        return str(exc)
    except proxy.UpstreamError as exc:
        return f"Error fetching upstream data: {exc}"

    if isinstance(data, str):
        return data
    return json.dumps(data, ensure_ascii=False)
