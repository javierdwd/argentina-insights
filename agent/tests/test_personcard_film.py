"""PersonCard binding: film elenco unnest + literal-field guards."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from agent.graph import (
    _bind_node,
    _enrich_bound_person_cards,
    _map_rows,
    _person_card_source_rows,
    _plausible_mapping_literal,
    _resolve_source,
)
from agent.proxy import wiki
from agent.ui.catalog import field_aliases_for


def test_name_field_miss_is_not_literal() -> None:
    """Film rows lack top-level ``name`` — must not print the word 'name'."""
    row = {"titulo": "Nueve reinas", "valor": 7.7}
    assert _resolve_source(row, "name", literals=True, target="name") is None
    assert not _plausible_mapping_literal("name", target="name")
    assert _plausible_mapping_literal("Senador", target="role")


def test_map_rows_falls_back_to_aliases_after_bad_name_mapping() -> None:
    aliases = field_aliases_for("PersonCard")
    rows = _map_rows(
        [{"nombre": "Gastón Pauls", "foto": "/x.jpg", "role": "Juan"}],
        {"name": "name", "photoUrl": "foto", "role": "role"},
        aliases,
    )
    assert rows[0]["name"] == "Gastón Pauls"
    assert rows[0]["photoUrl"] == "/x.jpg"
    assert rows[0]["role"] == "Juan"


def test_person_card_source_rows_unnests_elenco() -> None:
    film = {
        "titulo": "Nueve reinas",
        "runtime": 114,
        "elenco": [
            {"name": "Gastón Pauls", "foto": "/a.jpg", "role": "Juan"},
            {"name": "Ricardo Darín", "foto": "/b.jpg", "role": "Marcos"},
        ],
    }
    people = _person_card_source_rows([film])
    assert len(people) == 2
    assert people[0]["name"] == "Gastón Pauls"


def test_person_card_source_rows_keeps_real_person_profile() -> None:
    person = {
        "nombre": "Lucrecia Martel",
        "foto": "/m.jpg",
        "filmografia": [{"titulo": "La ciénaga"}],
    }
    assert _person_card_source_rows([person])[0]["nombre"] == "Lucrecia Martel"


def test_bind_film_person_card_uses_elenco() -> None:
    datasets = {
        "ds_film": {
            "id": "ds_film",
            "keys": ["titulo", "elenco", "valor"],
            "N": 1,
            "rows": [
                {
                    "titulo": "Nueve reinas",
                    "valor": 7.79,
                    "runtime": 114,
                    "elenco": [
                        {
                            "id": 1,
                            "name": "Gastón Pauls",
                            "nombre": "Gastón Pauls",
                            "foto": "https://image.tmdb.org/t/p/w500/a.jpg",
                            "role": "Juan",
                        },
                        {
                            "id": 2,
                            "name": "Ricardo Darín",
                            "nombre": "Ricardo Darín",
                            "foto": "https://image.tmdb.org/t/p/w500/b.jpg",
                            "role": "Marcos",
                        },
                    ],
                }
            ],
        }
    }
    tree = {
        "id": "cast",
        "type": "PersonCard",
        "title": "Elenco",
        "props": {
            "dataRef": "ds_film",
            "layout": "list",
            "fields": {
                "name": "name",
                "photoUrl": "foto",
                "role": "role",
            },
        },
    }
    bound = _bind_node(tree, datasets)
    people = bound["props"]["people"]
    assert len(people) == 2
    assert people[0]["name"] == "Gastón Pauls"
    assert people[0]["role"] == "Juan"
    assert "image.tmdb.org" in people[0]["photoUrl"]


@pytest.mark.asyncio
async def test_enrich_skips_junk_name(monkeypatch: pytest.MonkeyPatch) -> None:
    enrich = AsyncMock(side_effect=AssertionError("must not call wiki"))
    monkeypatch.setattr(wiki, "enrich_person", enrich)
    out = await wiki.enrich_person_card({"name": "name"})
    assert out == {"name": "name"}
    enrich.assert_not_called()


@pytest.mark.asyncio
async def test_bind_film_limit_1_does_not_wiki_junk_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: literal 'name' + wiki fuzzy-match used to yield Ñame bio."""
    enrich = AsyncMock(side_effect=AssertionError("must not wiki-enrich junk"))
    monkeypatch.setattr("agent.graph.wiki.enrich_person_card", enrich)

    datasets = {
        "ds_film": {
            "id": "ds_film",
            "keys": ["titulo", "valor"],
            "N": 1,
            "rows": [{"titulo": "Nueve reinas", "valor": 7.7}],
        }
    }
    tree = {
        "id": "cast",
        "type": "PersonCard",
        "props": {
            "dataRef": "ds_film",
            "fields": {"name": "name"},
            "limit": 1,
        },
    }
    bound = _bind_node(tree, datasets)
    # No elenco + blocked literal → empty people list (no fake "name" card).
    assert bound["props"]["people"] == []
    out = await _enrich_bound_person_cards(bound)
    enrich.assert_not_called()
    assert out["props"]["people"] == []


def test_looks_like_person_name() -> None:
    assert wiki.looks_like_person_name("Ricardo Darín")
    assert not wiki.looks_like_person_name("name")
    assert not wiki.looks_like_person_name("nombre")
    assert not wiki.looks_like_person_name("ab")
