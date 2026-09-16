"""Google News RSS proxy normalization and route behavior."""

from __future__ import annotations

from typing import Any

import pytest

from agent.catalog import catalog
from agent.proxy import ProxyError, resolve
from agent.proxy import news


RSS = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Milei anunció nuevas medidas - Ejemplo Diario</title>
      <link>https://news.google.com/rss/articles/example</link>
      <guid>example</guid>
      <pubDate>Sat, 06 Jan 2024 08:00:00 GMT</pubDate>
      <source url="https://example.com">Ejemplo Diario</source>
    </item>
  </channel>
</rss>
"""


def test_parse_rss_normalizes_news_rows() -> None:
    assert news.parse_rss(RSS) == [
        {
            "title": "Milei anunció nuevas medidas",
            "source": "Ejemplo Diario",
            "publishedAt": "2024-01-06",
            "url": "https://news.google.com/rss/articles/example",
        }
    ]


@pytest.mark.asyncio
async def test_news_search_uses_spanish_argentina_and_date_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_get(path: str, **kwargs: Any) -> str:
        captured["path"] = path
        captured.update(kwargs)
        return RSS

    monkeypatch.setattr("agent.proxy.news.upstream.get", fake_get)
    rows = await news.search(
        "Milei inflación",
        desde="2024-01-01",
        hasta="2024-01-31",
    )

    assert len(rows) == 1
    assert captured["path"] == "/rss/search"
    assert captured["query"]["hl"] == "es-419"
    assert captured["query"]["gl"] == "AR"
    assert captured["query"]["ceid"] == "AR:es-419"
    assert "after:2024-01-01" in captured["query"]["q"]
    assert "before:2024-02-01" in captured["query"]["q"]


def test_news_route_is_cross_cutting() -> None:
    assert catalog.get("/v1/noticias") is not None
    assert "/v1/noticias" in {
        operation.path for operation in catalog.for_domain("finance")
    }
    assert "/v1/noticias" in {
        operation.path for operation in catalog.for_domain("politics")
    }


@pytest.mark.asyncio
async def test_news_route_requires_query() -> None:
    with pytest.raises(ProxyError, match="requires q"):
        await resolve("/v1/noticias", {})
