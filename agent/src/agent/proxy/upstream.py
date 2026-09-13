"""HTTP access to upstream APIs, always through the TTL cache.

Originally ArgentinaDatos-only; now any host. Cache keys are prefixed with
the base URL so the same path on two hosts never collide.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

import httpx

from .cache import cache

BASE_URL = "https://api.argentinadatos.com"
TIMEOUT = 20.0
USER_AGENT = "argentina-insights/1.0 (public-data agent; contact: local-dev)"

_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    """Reuse one client so TLS/connection setup is not paid on every miss."""
    global _client
    if _client is not None and _client.is_closed:
        _client = None
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
    return _client


# ArgentinaDatos path ``fecha`` values use YYYY/MM/DD, not ISO YYYY-MM-DD.
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class UpstreamError(RuntimeError):
    """Upstream returned an error status or was unreachable."""


def path_value(name: str, value: Any) -> str:
    """Format a path-parameter value for the upstream URL.

    The OpenAPI spec marks ``fecha`` as ``format: date`` (ISO), but the live
    API only accepts slashes (``2023/12/31``).  ISO values 404; rewrite them.
    Non-date tokens such as ``ultimo`` / ``penultimo`` are left unchanged.
    """
    text = str(value)
    if name == "fecha" and _ISO_DATE.match(text):
        return text.replace("-", "/")
    return text


_SECRET_QUERY_KEYS = frozenset({"api_key", "access_token", "token"})


def _cache_key(base_url: str, url_path: str, query: dict[str, Any] | None) -> str:
    host = urlsplit(base_url).netloc or base_url
    key = f"{host}{url_path}"
    if query:
        # Never put Authorization / secrets in the key — only public query.
        public = {
            k: v for k, v in query.items() if k.casefold() not in _SECRET_QUERY_KEYS
        }
        if public:
            key += "?" + "&".join(f"{k}={v}" for k, v in sorted(public.items()))
    return key


async def _get(
    base_url: str,
    url_path: str,
    query: dict[str, Any] | None,
    headers: dict[str, str] | None,
) -> Any:
    url = base_url.rstrip("/") + url_path
    try:
        response = await _http().get(
            url,
            params=query or None,
            headers=headers or None,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise UpstreamError(
            f"HTTP {exc.response.status_code} from {urlsplit(base_url).netloc}: "
            f"{exc.response.text[:500]}"
        ) from exc
    except httpx.RequestError as exc:
        raise UpstreamError(
            f"Request error connecting to {urlsplit(base_url).netloc}: {exc}"
        ) from exc

    try:
        return response.json()
    except ValueError:
        return response.text


async def get(
    url_path: str,
    *,
    query: dict[str, Any] | None = None,
    ttl: float,
    refresh: bool = False,
    base_url: str = BASE_URL,
    headers: dict[str, str] | None = None,
) -> Any:
    """GET *url_path* on *base_url* through the cache.

    The cache key includes host + path + query so different upstreams never
    share an entry. Optional *headers* (e.g. Bearer) are sent on the request
    but never part of the cache key.
    """
    key = _cache_key(base_url, url_path, query)
    return await cache.get_or_fetch(
        key,
        ttl=ttl,
        fetch=lambda: _get(base_url, url_path, query, headers),
        refresh=refresh,
    )
