"""Actas list + desde/hasta must pull year-scoped history (mandate windows)."""

from __future__ import annotations

import pytest

from agent.proxy import NoMatch, resolve
from agent.proxy import upstream


@pytest.fixture(autouse=True)
async def _reset_upstream_client():
    """Avoid httpx client bound to a closed event loop across async tests."""
    yield
    client = upstream._client
    upstream._client = None
    if client is not None and not client.is_closed:
        await client.aclose()


@pytest.mark.asyncio
async def test_senado_actas_macri_window_uses_year_lists() -> None:
    rows = await resolve(
        "/v1/senado/actas",
        {
            "desde": "2015-12-10",
            "hasta": "2019-12-10",
            "fields": "actaId,titulo,fecha,resultado",
        },
    )
    assert isinstance(rows, list)
    assert len(rows) >= 20
    dates = [str(r.get("fecha", ""))[:10] for r in rows]
    assert min(dates) >= "2015-12-10"
    assert max(dates) <= "2019-12-10"
    assert any(d.startswith("2016") for d in dates)


@pytest.mark.asyncio
async def test_diputados_actas_macri_window_may_be_empty() -> None:
    """Diputados year paths 404 historically — honest NoMatch, not a hang."""
    with pytest.raises(NoMatch) as exc:
        await resolve(
            "/v1/diputados/actas",
            {
                "desde": "2015-12-10",
                "hasta": "2019-12-10",
                "fields": "id,titulo,fecha,resultado",
            },
        )
    assert "senado/actas" in str(exc.value).casefold()


@pytest.mark.asyncio
async def test_senado_acta_detail_finds_year_only_id() -> None:
    """Macri-era ids live in year lists — detail/votos must still resolve."""
    detail = await resolve(
        "/v1/senado/actas/id/{actaId}",
        {"actaId": 44, "fields": "actaId,titulo,fecha,resultado"},
    )
    assert isinstance(detail, dict)
    assert str(detail.get("actaId")) == "44"
    assert str(detail.get("fecha", "")).startswith("2016")

    votos = await resolve(
        "/v1/senado/actas/id/{actaId}/votos",
        {"actaId": 44, "fields": "nombre,voto"},
    )
    # Year payloads sometimes ship empty votos[] upstream; the contract is
    # that the id resolves (no "does not exist"), not that votes are filled.
    assert isinstance(votos, list)
