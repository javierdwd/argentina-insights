"""Match people names via the offline vector index + a small LLM pick.

No exact/substring pre-filter: chat queries are messy (typos, name order).
Retrieve top-k from the precomputed index, then let the fast model choose
among those candidates only.
"""

from __future__ import annotations

from . import collections as coll
from . import vector_index as vx
from .match import match_directory
from .routes import RosterFamily


def _roster_by_id(rows: list[dict], family: RosterFamily) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows:
        raw = row.get(family.id_field)
        if raw is None or raw == "":
            continue
        out[coll.composite_id(family.chamber, raw)] = row
    return out


def _presidentes_by_id(rows: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for cid, _text, _label in coll.presidentes_docs(rows):
        # recover row by scanning — lists are tiny
        _, raw = coll.parse_composite_id(cid)
        nombre, _, inicio = raw.partition("|")
        for row in rows:
            if str(row.get("nombre") or "").strip() != nombre:
                continue
            if inicio and str(row.get("inicio") or "").strip() != inicio:
                continue
            out[cid] = row
            break
    return out


async def _pick_from_index(
    *,
    collection: str,
    expected_fingerprint: str,
    needles: list[str],
    filtered_by_id: dict[str, dict],
    kind: str,
) -> list[dict]:
    clean = [str(n).strip() for n in needles if str(n).strip()]
    if not clean:
        return list(filtered_by_id.values())

    candidate_lines: dict[str, str] = {}
    for needle in clean:
        hits = await vx.query(
            collection,
            needle,
            expected_fingerprint=expected_fingerprint,
            k=vx.DEFAULT_TOP_K,
        )
        for hit in hits:
            candidate_lines.setdefault(hit.id, hit.label)

    if not candidate_lines:
        return []

    lines = [f"{cid}\t{label}" for cid, label in candidate_lines.items()]
    stubs = {cid: {"id": cid} for cid in candidate_lines}
    picked = await match_directory(
        kind=kind,
        lines=lines,
        queries=clean,
        by_id=stubs,
    )

    out: list[dict] = []
    seen: set[str] = set()
    for stub in picked:
        cid = str(stub.get("id") or "")
        row = filtered_by_id.get(cid)
        if row is None or cid in seen:
            continue
        seen.add(cid)
        out.append(row)
    return out


async def match_roster(
    rows: list[dict],
    needles: list[str],
    family: RosterFamily,
    *,
    expected_fingerprint: str,
) -> list[dict]:
    """Keep roster *rows* whose names match *needles* via RAG + LLM pick."""
    collection = coll.ROSTER_COLLECTION[family.chamber]
    return await _pick_from_index(
        collection=collection,
        expected_fingerprint=expected_fingerprint,
        needles=needles,
        filtered_by_id=_roster_by_id(rows, family),
        kind=f"roster-{family.chamber}",
    )


async def match_presidentes(
    rows: list[dict],
    needles: list[str],
    *,
    expected_fingerprint: str,
) -> list[dict]:
    """Keep president rows matching *needles* via RAG + LLM pick."""
    return await _pick_from_index(
        collection=coll.PRESIDENTES,
        expected_fingerprint=expected_fingerprint,
        needles=needles,
        filtered_by_id=_presidentes_by_id(rows),
        kind="presidentes",
    )
