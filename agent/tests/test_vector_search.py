"""Tests for offline vector index + search_actas / name RAG (no OpenAI calls)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from agent.proxy import NoMatch, ProxyError, search_actas
from agent.proxy import collections as coll
from agent.proxy import names
from agent.proxy import vector_index as vx
from agent.proxy.routes import DIPUTADOS_ACTAS, DIPUTADOS_ROSTER, SENADO_ACTAS


@pytest.fixture(autouse=True)
def _clean_index_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("VECTOR_INDEX_DIR", str(tmp_path))
    monkeypatch.setenv("EMBEDDING_MODEL", "test-embed")
    vx.clear_memory_cache()
    yield
    vx.clear_memory_cache()


def _write_index(
    collection: str,
    docs: list[tuple[str, str, str]],
    vectors: np.ndarray,
) -> str:
    ids = [d[0] for d in docs]
    labels = [d[2] for d in docs]
    fp = vx.fingerprint([(i, t) for i, t, _ in docs])
    vx.write_collection(
        collection=collection,
        fingerprint=fp,
        model="test-embed",
        ids=ids,
        labels=labels,
        matrix=vectors,
    )
    return fp


ACTA_ROWS = [
    {
        "id": 100,
        "titulo": "Ley Joaquín de protección animal",
        "fecha": "2024-01-15",
        "resultado": "afirmativo",
        "votos": [{"diputado": "A", "tipoVoto": "afirmativo"}],
    },
    {
        "id": 101,
        "titulo": "Modificación del código penal",
        "fecha": "2023-06-01",
        "resultado": "negativo",
        "votos": [],
    },
    {
        "id": 102,
        "titulo": "Presupuesto 2024",
        "fecha": "2023-12-01",
        "resultado": "afirmativo",
        "votos": [],
    },
]


def _actas_docs_and_vectors():
    docs = coll.actas_docs(DIPUTADOS_ACTAS, ACTA_ROWS)
    # Orthogonal-ish vectors: Joaquín ≈ [1,0,0], others elsewhere
    vectors = np.array(
        [
            [1.0, 0.0, 0.0],  # Joaquín
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )
    return docs, vectors


@pytest.mark.asyncio
async def test_query_typo_recovers_joaquin_in_topk():
    docs, vectors = _actas_docs_and_vectors()
    fp = _write_index(coll.ACTAS_DIPUTADOS, docs, vectors)

    embed_calls = {"n": 0}

    def embed_fn(_text: str) -> np.ndarray:
        embed_calls["n"] += 1
        # Query close to Joaquín vector
        return np.array([0.95, 0.05, 0.0], dtype=np.float32)

    hits = await vx.query(
        coll.ACTAS_DIPUTADOS,
        "joequin",
        expected_fingerprint=fp,
        k=2,
        embed_fn=embed_fn,
    )
    assert embed_calls["n"] == 1
    assert hits[0].id == "diputados:100"
    assert "Joaquín" in hits[0].label


@pytest.mark.asyncio
async def test_missing_index_mentions_script():
    with pytest.raises(vx.VectorIndexError, match="generate_embeddings"):
        await vx.load(coll.ACTAS_DIPUTADOS, "deadbeefdeadbeef")


@pytest.mark.asyncio
async def test_load_does_not_call_document_embedder():
    docs, vectors = _actas_docs_and_vectors()
    fp = _write_index(coll.ACTAS_DIPUTADOS, docs, vectors)

    with patch("agent.proxy.vector_index.embed_query", new_callable=AsyncMock) as mocked:
        await vx.load(coll.ACTAS_DIPUTADOS, fp)
        mocked.assert_not_called()


@pytest.mark.asyncio
async def test_search_actas_picks_joaquin(monkeypatch):
    docs, vectors = _actas_docs_and_vectors()
    fp = _write_index(coll.ACTAS_DIPUTADOS, docs, vectors)
    # Empty senado index so dual-chamber search still works when only diputados asked
    senado_docs = coll.actas_docs(SENADO_ACTAS, [])
    # Need at least empty handling — search with chamber=diputados

    async def fake_get(path: str, **kwargs: Any) -> list[dict]:
        assert path == DIPUTADOS_ACTAS.list_path
        return ACTA_ROWS

    async def fake_match(**kwargs: Any) -> list[dict]:
        return [{"id": "diputados:100"}]

    def embed_fn(_text: str) -> np.ndarray:
        return np.array([1.0, 0.0, 0.0], dtype=np.float32)

    monkeypatch.setattr("agent.proxy.upstream.get", fake_get)
    monkeypatch.setattr("agent.proxy.match_directory", fake_match)

    with patch(
        "agent.proxy.vector_index.embed_query",
        new=AsyncMock(side_effect=lambda t: embed_fn(t)),
    ):
        result = await search_actas("Ley Joaquín", chamber="diputados")

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["id"] == 100
    assert "Joaquín" in str(result[0].get("titulo") or "")
    # Compact summary only — not the flattened roll call.
    assert "voto" not in result[0]
    assert "nombre" not in result[0]


@pytest.mark.asyncio
async def test_search_actas_agustin_nomatch(monkeypatch):
    docs, vectors = _actas_docs_and_vectors()
    _write_index(coll.ACTAS_DIPUTADOS, docs, vectors)

    async def fake_get(path: str, **kwargs: Any) -> list[dict]:
        return ACTA_ROWS

    async def fake_match(**kwargs: Any) -> list[dict]:
        # Model refuses weak candidates
        return []

    def embed_fn(_text: str) -> np.ndarray:
        # Query near "presupuesto" — still in top-k but pick returns empty
        return np.array([0.1, 0.1, 0.9], dtype=np.float32)

    monkeypatch.setattr("agent.proxy.upstream.get", fake_get)
    monkeypatch.setattr("agent.proxy.match_directory", fake_match)

    with patch(
        "agent.proxy.vector_index.embed_query",
        new=AsyncMock(side_effect=lambda t: embed_fn(t)),
    ):
        with pytest.raises(NoMatch, match="Agustín|0 of"):
            await search_actas("Ley Agustín", chamber="diputados")


@pytest.mark.asyncio
async def test_search_actas_missing_index_is_proxy_error(monkeypatch):
    async def fake_get(path: str, **kwargs: Any) -> list[dict]:
        return ACTA_ROWS

    monkeypatch.setattr("agent.proxy.upstream.get", fake_get)

    with pytest.raises(ProxyError, match="generate_embeddings"):
        await search_actas("Ley Joaquín", chamber="diputados")


@pytest.mark.asyncio
async def test_roster_typo_match(monkeypatch):
    rows = [
        {"id": "HCDN1", "nombre": "Juan", "apellido": "Pérez"},
        {"id": "HCDN2", "nombre": "María", "apellido": "García"},
        {"id": "HCDN3", "nombre": "Luis", "apellido": "Gómez"},
    ]
    docs = coll.roster_docs(DIPUTADOS_ROSTER, rows)
    vectors = np.eye(3, dtype=np.float32)
    fp = _write_index(coll.ROSTER_DIPUTADOS, docs, vectors)

    async def fake_match(**kwargs: Any) -> list[dict]:
        return [{"id": "diputados:HCDN1"}]

    monkeypatch.setattr("agent.proxy.names.match_directory", fake_match)

    with patch(
        "agent.proxy.vector_index.embed_query",
        new=AsyncMock(return_value=np.array([1.0, 0.0, 0.0], dtype=np.float32)),
    ):
        matched = await names.match_roster(
            rows,
            ["juan peres"],
            DIPUTADOS_ROSTER,
            expected_fingerprint=fp,
        )

    assert len(matched) == 1
    assert matched[0]["id"] == "HCDN1"


@pytest.mark.asyncio
async def test_fingerprint_mismatch():
    docs, vectors = _actas_docs_and_vectors()
    _write_index(coll.ACTAS_DIPUTADOS, docs, vectors)
    with pytest.raises(vx.VectorIndexError, match="missing|mismatch|generate_embeddings"):
        await vx.load(coll.ACTAS_DIPUTADOS, "0000000000000000")
