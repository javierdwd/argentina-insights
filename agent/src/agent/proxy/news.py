"""Google News RSS search, normalized for the News widget."""

from __future__ import annotations

import datetime as dt
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import Any

from . import upstream

BASE_URL = "https://news.google.com"
TTL = 15 * 60
MAX_QUERY_LENGTH = 240
MAX_RESULTS = 100

_DATE_OPERATOR = re.compile(r"\b(?:after|before):\d{4}-\d{2}-\d{2}\b", re.IGNORECASE)


def _iso_date(value: Any, name: str) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO date (YYYY-MM-DD).") from exc


def _search_query(q: str, desde: str | None, hasta: str | None) -> str:
    # Date bounds are separate tool parameters. Removing date operators from
    # q prevents contradictory ranges when a model repeats them there.
    terms = " ".join(_DATE_OPERATOR.sub("", q).split()).strip()
    if not terms:
        raise ValueError("q must contain at least one search term.")
    if len(terms) > MAX_QUERY_LENGTH:
        raise ValueError(f"q must be at most {MAX_QUERY_LENGTH} characters.")

    parts = [terms]
    if desde:
        parts.append(f"after:{desde}")
    if hasta:
        # Google treats before: as exclusive. Advancing one day makes the
        # proxy's hasta parameter inclusive, matching the rest of the API.
        exclusive = dt.date.fromisoformat(hasta) + dt.timedelta(days=1)
        parts.append(f"before:{exclusive.isoformat()}")
    return " ".join(parts)


def _child_text(item: ET.Element, name: str) -> str:
    child = item.find(name)
    return (child.text or "").strip() if child is not None else ""


def _clean_title(title: str, source: str) -> str:
    suffix = f" - {source}"
    return title[: -len(suffix)].strip() if source and title.endswith(suffix) else title


def parse_rss(payload: str) -> list[dict[str, str]]:
    """Parse Google News RSS into stable Spanish field names."""
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise upstream.UpstreamError("Google News returned invalid RSS.") from exc

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in root.findall("./channel/item"):
        source = _child_text(item, "source")
        title = _clean_title(_child_text(item, "title"), source)
        url = _child_text(item, "link")
        raw_date = _child_text(item, "pubDate")
        if not title or not url:
            continue

        published = raw_date
        if raw_date:
            try:
                published = parsedate_to_datetime(raw_date).date().isoformat()
            except (TypeError, ValueError, OverflowError):
                pass

        key = (title.casefold(), url)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "title": title,
                "source": source or "Unknown source",
                "publishedAt": published,
                "url": url,
            }
        )
        if len(rows) >= MAX_RESULTS:
            break
    return rows


async def search(
    q: str,
    *,
    desde: Any = None,
    hasta: Any = None,
    refresh: bool = False,
) -> list[dict[str, str]]:
    """Search the Argentine Spanish edition of Google News."""
    start = _iso_date(desde, "desde")
    end = _iso_date(hasta, "hasta")
    if start and end and start > end:
        raise ValueError("desde must be earlier than or equal to hasta.")

    query = _search_query(str(q or ""), start, end)
    payload = await upstream.get(
        "/rss/search",
        query={
            "q": query,
            "hl": "es-419",
            "gl": "AR",
            "ceid": "AR:es-419",
        },
        ttl=TTL,
        refresh=refresh,
        base_url=BASE_URL,
    )
    if not isinstance(payload, str):
        raise upstream.UpstreamError("Google News returned an unexpected response.")
    return parse_rss(payload)
