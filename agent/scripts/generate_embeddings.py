#!/usr/bin/env python3
"""Build on-disk vector indexes for actas, rosters, and presidents.

Offline only — the agent runtime loads these files and never batch-embeds
the catalogs. Re-run when ArgentinaDatos lists change or EMBEDDING_MODEL does.

Usage (from the agent/ directory, with .env loaded)::

    python scripts/generate_embeddings.py
    python scripts/generate_embeddings.py --force
    python scripts/generate_embeddings.py --only actas-diputados,presidentes
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import httpx
import numpy as np
from dotenv import load_dotenv

# agent/src on path when run as ``python scripts/generate_embeddings.py``
_AGENT_ROOT = Path(__file__).resolve().parents[1]
_SRC = _AGENT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

load_dotenv(_AGENT_ROOT / ".env")

from agent.proxy import collections as coll  # noqa: E402
from agent.proxy import vector_index as vx  # noqa: E402

BASE_URL = "https://api.argentinadatos.com"
BATCH_SIZE = 64
TIMEOUT = 60.0


async def _fetch(path: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(BASE_URL + path)
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, list):
        raise RuntimeError(f"{path} did not return a list")
    return [r for r in data if isinstance(r, dict)]


async def _embed_texts(texts: list[str], model: str) -> np.ndarray:
    from openai import AsyncOpenAI

    client = AsyncOpenAI()
    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH_SIZE):
        chunk = texts[start : start + BATCH_SIZE]
        response = await client.embeddings.create(model=model, input=chunk)
        # API may not preserve order in pathological cases; sort by index
        by_idx = sorted(response.data, key=lambda d: d.index)
        vectors.extend(d.embedding for d in by_idx)
        print(f"  embedded {min(start + BATCH_SIZE, len(texts))}/{len(texts)}")
    return np.asarray(vectors, dtype=np.float32)


async def build_one(collection: str, path: str, *, force: bool) -> None:
    model = vx.embedding_model()
    print(f"\n=== {collection} ({path}) model={model} ===")
    rows = await _fetch(path)
    docs = coll.docs_for_collection(collection, rows)
    if not docs:
        print("  skip: no documents")
        return

    ids = [d[0] for d in docs]
    texts = [d[1] for d in docs]
    labels = [d[2] for d in docs]
    fp = vx.fingerprint([(i, t) for i, t, _ in docs])
    npy_path, json_path = vx.artifact_paths(collection, fp, model)

    if npy_path.is_file() and json_path.is_file() and not force:
        print(f"  skip: already on disk fingerprint={fp}")
        print(f"  {npy_path}")
        return

    print(f"  {len(docs)} docs fingerprint={fp}")
    matrix = await _embed_texts(texts, model)
    vx.write_collection(
        collection=collection,
        fingerprint=fp,
        model=model,
        ids=ids,
        labels=labels,
        matrix=matrix,
    )
    print(f"  wrote {npy_path}")
    print(f"  wrote {json_path}")


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-embed even when fingerprint artifacts already exist",
    )
    parser.add_argument(
        "--only",
        type=str,
        default="",
        help="Comma-separated collection names to build",
    )
    args = parser.parse_args(argv)

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is required", file=sys.stderr)
        return 1

    only = {p.strip() for p in args.only.split(",") if p.strip()}
    sources = coll.SCRIPT_SOURCES
    if only:
        sources = tuple((c, p) for c, p in sources if c in only)
        missing = only - {c for c, _ in sources}
        if missing:
            print(f"Unknown collections: {sorted(missing)}", file=sys.stderr)
            return 1

    print(f"Index root: {vx.index_root()}")
    for collection, path in sources:
        await build_one(collection, path, force=args.force)
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
