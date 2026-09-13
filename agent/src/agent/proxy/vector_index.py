"""Offline-built vector index for actas and people name search.

Documents are embedded by ``scripts/generate_embeddings.py`` and written to
disk as ``.npy`` + JSON meta. Runtime only **loads** those files and embeds
the query string — it never batch-embeds the catalog.

Invalidation is fingerprint-based (ids + indexable text + embedding model).
HTTP TTLs and process restarts do not regenerate embeddings; run the script
again when upstream catalogs change or you switch ``EMBEDDING_MODEL``.

Disk layout::

    {VECTOR_INDEX_DIR}/{collection}/{model_slug}/{fingerprint}.npy
    {VECTOR_INDEX_DIR}/{collection}/{model_slug}/{fingerprint}.json
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_MODEL = "text-embedding-3-small"
# Bare eponyms ("joaquin") often rank ~20–40 with text-embedding-3-small;
# keep enough neighbors so the pick model actually sees the right title.
DEFAULT_TOP_K = 40
REGENERATE_HINT = (
    "Run from the agent package: "
    "`python scripts/generate_embeddings.py` "
    "(requires OPENAI_API_KEY). Re-run when upstream lists or EMBEDDING_MODEL change."
)

_MODEL_SLUG = re.compile(r"[^a-zA-Z0-9._-]+")


class VectorIndexError(RuntimeError):
    """Index missing, corrupt, or fingerprint mismatch — tell the operator to regenerate."""


@dataclass(frozen=True)
class Hit:
    id: str
    label: str
    score: float


@dataclass
class CollectionIndex:
    collection: str
    fingerprint: str
    model: str
    ids: list[str]
    labels: list[str]
    matrix: np.ndarray  # (n, dim) float32, L2-normalized


# In-process cache: collection → loaded index
_loaded: dict[str, CollectionIndex] = {}
_locks: dict[str, asyncio.Lock] = {}


def embedding_model() -> str:
    return os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def index_root() -> Path:
    raw = os.getenv("VECTOR_INDEX_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    # agent/.cache/vector_index — this file lives in agent/src/agent/proxy/
    return Path(__file__).resolve().parents[3] / ".cache" / "vector_index"


def model_slug(model: str | None = None) -> str:
    name = model or embedding_model()
    return _MODEL_SLUG.sub("_", name)


def collection_dir(collection: str, model: str | None = None) -> Path:
    return index_root() / collection / model_slug(model)


def artifact_paths(
    collection: str,
    fingerprint: str,
    model: str | None = None,
) -> tuple[Path, Path]:
    base = collection_dir(collection, model) / fingerprint
    return base.with_suffix(".npy"), base.with_suffix(".json")


def fingerprint(entries: Sequence[tuple[str, str]]) -> str:
    """Stable hash of sorted (id, text) pairs."""
    lines = sorted(f"{i}\t{t}" for i, t in entries if i and t)
    digest = hashlib.sha256("\n".join(lines).encode()).hexdigest()
    return digest[:16]


def row_text(row: dict, fields: Sequence[str]) -> str:
    parts = [str(row.get(f) or "").strip() for f in fields]
    return " ".join(p for p in parts if p)


def l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return (matrix / norms).astype(np.float32, copy=False)


def _lock_for(collection: str) -> asyncio.Lock:
    lock = _locks.get(collection)
    if lock is None:
        lock = asyncio.Lock()
        _locks[collection] = lock
    return lock


def clear_memory_cache() -> None:
    """Drop in-process indexes (tests)."""
    _loaded.clear()


def write_collection(
    *,
    collection: str,
    fingerprint: str,
    model: str,
    ids: list[str],
    labels: list[str],
    matrix: np.ndarray,
) -> tuple[Path, Path]:
    """Persist a built index. Used by the offline script only."""
    if len(ids) != len(labels) or len(ids) != matrix.shape[0]:
        raise ValueError("ids, labels, and matrix rows must align")
    npy_path, json_path = artifact_paths(collection, fingerprint, model)
    npy_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = l2_normalize(np.asarray(matrix, dtype=np.float32))
    np.save(npy_path, normalized)
    meta = {
        "collection": collection,
        "fingerprint": fingerprint,
        "model": model,
        "ids": ids,
        "labels": labels,
        "count": len(ids),
        "dim": int(normalized.shape[1]),
    }
    json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return npy_path, json_path


def _read_disk(collection: str, expected_fingerprint: str) -> CollectionIndex:
    model = embedding_model()
    npy_path, json_path = artifact_paths(collection, expected_fingerprint, model)
    if not npy_path.is_file() or not json_path.is_file():
        # Helpful: list what fingerprints exist for this collection/model
        cdir = collection_dir(collection, model)
        existing = sorted(p.stem for p in cdir.glob("*.json")) if cdir.is_dir() else []
        hint = (
            f" Found on disk: {existing}."
            if existing
            else " No index files found for this collection/model."
        )
        raise VectorIndexError(
            f"Vector index missing for {collection!r} "
            f"(model={model}, fingerprint={expected_fingerprint})."
            f"{hint} {REGENERATE_HINT}"
        )

    meta = json.loads(json_path.read_text(encoding="utf-8"))
    disk_fp = str(meta.get("fingerprint") or "")
    disk_model = str(meta.get("model") or "")
    if disk_fp != expected_fingerprint:
        raise VectorIndexError(
            f"Vector index fingerprint mismatch for {collection!r}: "
            f"live={expected_fingerprint} disk={disk_fp}. {REGENERATE_HINT}"
        )
    if disk_model and disk_model != model:
        raise VectorIndexError(
            f"Vector index model mismatch for {collection!r}: "
            f"env={model} disk={disk_model}. {REGENERATE_HINT}"
        )

    ids = [str(x) for x in meta.get("ids") or []]
    labels = [str(x) for x in meta.get("labels") or []]
    matrix = np.load(npy_path)
    if matrix.ndim != 2 or matrix.shape[0] != len(ids):
        raise VectorIndexError(
            f"Corrupt vector index for {collection!r}: "
            f"matrix shape {matrix.shape} vs {len(ids)} ids. {REGENERATE_HINT}"
        )
    if len(labels) != len(ids):
        labels = (labels + [""] * len(ids))[: len(ids)]

    return CollectionIndex(
        collection=collection,
        fingerprint=expected_fingerprint,
        model=model,
        ids=ids,
        labels=labels,
        matrix=l2_normalize(matrix),
    )


async def load(collection: str, expected_fingerprint: str) -> CollectionIndex:
    """Load index from disk into RAM. Never embeds documents."""
    cached = _loaded.get(collection)
    if (
        cached is not None
        and cached.fingerprint == expected_fingerprint
        and cached.model == embedding_model()
    ):
        return cached

    async with _lock_for(collection):
        cached = _loaded.get(collection)
        if (
            cached is not None
            and cached.fingerprint == expected_fingerprint
            and cached.model == embedding_model()
        ):
            return cached
        index = _read_disk(collection, expected_fingerprint)
        _loaded[collection] = index
        return index


async def embed_query(text: str) -> np.ndarray:
    """Embed a single search string (runtime's only embedding call)."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI()
    response = await client.embeddings.create(
        model=embedding_model(),
        input=text,
    )
    vec = np.asarray(response.data[0].embedding, dtype=np.float32)
    return l2_normalize(vec.reshape(1, -1))[0]


def _dedupe_hits(hits: list[Hit], *, k: int) -> list[Hit]:
    hits = sorted(hits, key=lambda h: h.score, reverse=True)
    seen: set[str] = set()
    out: list[Hit] = []
    for hit in hits:
        if hit.id in seen:
            continue
        seen.add(hit.id)
        out.append(hit)
        if len(out) >= k:
            break
    return out


async def query(
    collection: str,
    needle: str,
    *,
    expected_fingerprint: str,
    k: int = DEFAULT_TOP_K,
    embed_fn: Callable[[str], Any] | None = None,
) -> list[Hit]:
    """Return top-*k* embedding neighbors for *needle*."""
    index = await load(collection, expected_fingerprint)
    text = str(needle or "").strip()
    if not text or index.matrix.shape[0] == 0:
        return []

    if embed_fn is None:
        q = await embed_query(text)
    else:
        result = embed_fn(text)
        if asyncio.iscoroutine(result):
            result = await result
        q = np.asarray(result, dtype=np.float32).reshape(-1)
        n = np.linalg.norm(q)
        q = q / max(n, 1e-12)

    scores = index.matrix @ q
    k_eff = min(max(k, 1), scores.shape[0])
    idx = np.argpartition(-scores, k_eff - 1)[:k_eff]
    idx = idx[np.argsort(-scores[idx])]
    return _dedupe_hits(
        [
            Hit(id=index.ids[i], label=index.labels[i], score=float(scores[i]))
            for i in idx
        ],
        k=k_eff,
    )


async def query_many(
    collections: Sequence[tuple[str, str]],
    needle: str,
    *,
    k: int = DEFAULT_TOP_K,
    embed_fn: Callable[[str], Any] | None = None,
) -> list[Hit]:
    """Query several (collection, fingerprint) pairs; merge by score, keep top-*k*."""
    text = str(needle or "").strip()
    if not text or not collections:
        return []

    for coll_name, fp in collections:
        await load(coll_name, fp)

    if embed_fn is None:
        q = await embed_query(text)
    else:
        result = embed_fn(text)
        if asyncio.iscoroutine(result):
            result = await result
        q = np.asarray(result, dtype=np.float32).reshape(-1)
        n = np.linalg.norm(q)
        q = q / max(n, 1e-12)

    async def _hits(coll_name: str, fp: str) -> list[Hit]:
        return await query(
            coll_name,
            needle,
            expected_fingerprint=fp,
            k=k,
            embed_fn=lambda _t: q,
        )

    merged: list[Hit] = []
    for coll_name, fp in collections:
        merged.extend(await _hits(coll_name, fp))
    return _dedupe_hits(merged, k=k)
