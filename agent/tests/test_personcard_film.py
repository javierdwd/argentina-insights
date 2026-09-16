"""Person-name guards for Wikipedia enrichment."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agent.proxy import wiki


@pytest.mark.asyncio
async def test_enrich_skips_junk_name(monkeypatch: pytest.MonkeyPatch) -> None:
    enrich = AsyncMock(side_effect=AssertionError("must not call wiki"))
    monkeypatch.setattr(wiki, "enrich_person", enrich)
    out = await wiki.enrich_person_card({"name": "name"})
    assert out == {"name": "name"}
    enrich.assert_not_called()


def test_looks_like_person_name() -> None:
    assert wiki.looks_like_person_name("Ricardo Darín")
    assert not wiki.looks_like_person_name("name")
    assert not wiki.looks_like_person_name("nombre")
    assert not wiki.looks_like_person_name("ab")
