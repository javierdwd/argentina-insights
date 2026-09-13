"""Collection names and (id, text, label) builders for the vector index."""

from __future__ import annotations

from typing import Any, Sequence

from .routes import (
    DIPUTADOS_ACTAS,
    DIPUTADOS_ROSTER,
    SENADO_ACTAS,
    SENADO_ROSTER,
    ActasFamily,
    RosterFamily,
)
from . import vector_index as vx

ACTAS_DIPUTADOS = "actas-diputados"
ACTAS_SENADO = "actas-senado"
ROSTER_DIPUTADOS = "roster-diputados"
ROSTER_SENADO = "roster-senado"
PRESIDENTES = "presidentes"

ACTAS_COLLECTION = {
    DIPUTADOS_ACTAS.chamber: ACTAS_DIPUTADOS,
    SENADO_ACTAS.chamber: ACTAS_SENADO,
}
ROSTER_COLLECTION = {
    DIPUTADOS_ROSTER.chamber: ROSTER_DIPUTADOS,
    SENADO_ROSTER.chamber: ROSTER_SENADO,
}

# Offline script fetches these paths in order.
SCRIPT_SOURCES: tuple[tuple[str, str], ...] = (
    (ACTAS_DIPUTADOS, DIPUTADOS_ACTAS.list_path),
    (ACTAS_SENADO, SENADO_ACTAS.list_path),
    (ROSTER_DIPUTADOS, DIPUTADOS_ROSTER.list_path),
    (ROSTER_SENADO, SENADO_ROSTER.list_path),
    (PRESIDENTES, "/v1/presidentes"),
)


def composite_id(prefix: str, raw: Any) -> str:
    return f"{prefix}:{raw}"


def parse_composite_id(cid: str) -> tuple[str, str]:
    prefix, _, rest = cid.partition(":")
    return prefix, rest


def actas_docs(family: ActasFamily, rows: Sequence[dict]) -> list[tuple[str, str, str]]:
    """Return (composite_id, embed_text, label) for each acta row."""
    out: list[tuple[str, str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw = row.get(family.id_field)
        if raw is None or raw == "":
            continue
        text = vx.row_text(row, family.text_fields)
        if not text:
            continue
        label = str(row.get("titulo") or text).strip()
        out.append((composite_id(family.chamber, raw), text, label))
    return out


def roster_docs(family: RosterFamily, rows: Sequence[dict]) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw = row.get(family.id_field)
        if raw is None or raw == "":
            continue
        text = vx.row_text(row, family.name_fields)
        if not text:
            continue
        out.append((composite_id(family.chamber, raw), text, text))
    return out


def presidentes_docs(rows: Sequence[dict]) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        nombre = str(row.get("nombre") or "").strip()
        if not nombre:
            continue
        inicio = str(row.get("inicio") or "").strip()
        raw = f"{nombre}|{inicio}" if inicio else nombre
        text = nombre
        out.append((composite_id("presidente", raw), text, nombre))
    return out


def docs_for_collection(collection: str, rows: Sequence[dict]) -> list[tuple[str, str, str]]:
    if collection == ACTAS_DIPUTADOS:
        return actas_docs(DIPUTADOS_ACTAS, rows)
    if collection == ACTAS_SENADO:
        return actas_docs(SENADO_ACTAS, rows)
    if collection == ROSTER_DIPUTADOS:
        return roster_docs(DIPUTADOS_ROSTER, rows)
    if collection == ROSTER_SENADO:
        return roster_docs(SENADO_ROSTER, rows)
    if collection == PRESIDENTES:
        return presidentes_docs(rows)
    raise ValueError(f"Unknown collection: {collection}")


def fingerprint_for(collection: str, rows: Sequence[dict]) -> str:
    docs = docs_for_collection(collection, rows)
    return vx.fingerprint([(i, t) for i, t, _ in docs])


def actas_family_for_collection(collection: str) -> ActasFamily | None:
    if collection == ACTAS_DIPUTADOS:
        return DIPUTADOS_ACTAS
    if collection == ACTAS_SENADO:
        return SENADO_ACTAS
    return None


def roster_family_for_collection(collection: str) -> RosterFamily | None:
    if collection == ROSTER_DIPUTADOS:
        return DIPUTADOS_ROSTER
    if collection == ROSTER_SENADO:
        return SENADO_ROSTER
    return None


__all__ = [
    "ACTAS_COLLECTION",
    "ACTAS_DIPUTADOS",
    "ACTAS_SENADO",
    "PRESIDENTES",
    "ROSTER_COLLECTION",
    "ROSTER_DIPUTADOS",
    "ROSTER_SENADO",
    "SCRIPT_SOURCES",
    "actas_docs",
    "actas_family_for_collection",
    "composite_id",
    "docs_for_collection",
    "fingerprint_for",
    "parse_composite_id",
    "presidentes_docs",
    "roster_docs",
    "roster_family_for_collection",
]
