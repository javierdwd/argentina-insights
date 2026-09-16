"""Curated finance products — plazos fijos, hipotecarios UVA, FCI.

Upstream (ArgentinaDatos) returns nested / wrapped snapshots. This module
exposes flat, ComparisonTable- and Chart-ready rows:

  /v1/plazos                 aliases
  /v1/plazos/ranking         banks ranked by best TNA (%)
  /v1/hipotecarios-uva       UVA mortgage TNAs (% + metadata)
  /v1/fci                    curated fund aliases
  /v1/fci/search?q=          search fondos by name
  /v1/fci/{slug}             one fund detail
  /v1/fci/{slug}/historico   {fecha, valor=valorCuotaparte} series
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from . import filters, upstream
from .upstream import UpstreamError

TTL_SNAPSHOT = 6 * 60 * 60
TTL_FCI_LIST = 12 * 60 * 60
TTL_FCI_HIST = 12 * 60 * 60

_PLAZO_PATH = "/v1/finanzas/tasas/plazoFijo"
_HIPOTECARIO_PATH = "/v1/finanzas/creditos/hipotecariosUva"
_FCI_LIST_PATH = "/v1/finanzas/fci/fondos"
_FCI_DETAIL_PATH = "/v1/finanzas/fci/fondos/{nombre}"
_FCI_HIST_PATH = "/v1/finanzas/fci/fondos/{nombre}/historico"

SEARCH_CAP = 20
RANKING_CAP = 25


@dataclass(frozen=True)
class FciAlias:
    alias: str
    slug: str
    titulo: str
    tipo: str


# Stable popular funds for starters / destinations (verified live).
FCI_ALIASES: tuple[FciAlias, ...] = (
    FciAlias(
        alias="delta_pesos_a",
        slug="delta-pesos-clase-a",
        titulo="Delta Pesos — Clase A",
        tipo="Renta Mixta",
    ),
    FciAlias(
        alias="mercado_fondo_a",
        slug="mercado-fondo-clase-a",
        titulo="Mercado Fondo — Clase A",
        tipo="Mercado de Dinero",
    ),
)

_FCI_BY_ALIAS: dict[str, FciAlias] = {a.alias: a for a in FCI_ALIASES}
_FCI_BY_SLUG: dict[str, FciAlias] = {a.slug: a for a in FCI_ALIASES}


def list_plazos_aliases() -> list[dict[str, Any]]:
    return [
        {
            "alias": "ranking",
            "path": "/v1/plazos/ranking",
            "titulo": "Plazos fijos — ranking por TNA",
            "unidad": "% TNA",
        }
    ]


def list_fci_aliases() -> list[dict[str, Any]]:
    return [
        {
            "alias": a.alias,
            "slug": a.slug,
            "titulo": a.titulo,
            "tipo": a.tipo,
        }
        for a in FCI_ALIASES
    ]


def get_fci_alias(alias: str) -> FciAlias | None:
    key = str(alias or "").strip().lower()
    return _FCI_BY_ALIAS.get(key) or _FCI_BY_SLUG.get(key)


def slugify_fondo(nombre: str) -> str:
    """Match ArgentinaDatos path convention: lowercase, ascii, hyphens."""
    text = unicodedata.normalize("NFKD", str(nombre or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def _as_pct(value: Any) -> float | None:
    """Normalize TNA that may arrive as fraction (0.18) or percent (18)."""
    if value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if not (n == n):  # NaN
        return None
    if abs(n) <= 1.5:
        return round(n * 100.0, 4)
    return round(n, 4)


def _best_plazo_tna(row: dict[str, Any]) -> tuple[float | None, int | None]:
    """Pick the highest TNA across top-level + nested tasas[], with its plazo."""
    best: float | None = None
    plazo: int | None = None

    top = _as_pct(row.get("tnaClientes"))
    if top is not None:
        best = top

    nested = row.get("tasas")
    if isinstance(nested, list):
        for item in nested:
            if not isinstance(item, dict):
                continue
            tna = _as_pct(item.get("tna"))
            if tna is None:
                continue
            if best is None or tna > best:
                best = tna
                plazo_raw = item.get("plazoMinDias") or item.get("plazoMaxDias")
                try:
                    plazo = int(plazo_raw) if plazo_raw is not None else None
                except (TypeError, ValueError):
                    plazo = None
    return best, plazo


def flatten_plazos(raw: Any, *, limit: int = RANKING_CAP) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        entidad = str(item.get("entidad") or "").strip()
        if not entidad:
            continue
        tna, plazo = _best_plazo_tna(item)
        if tna is None:
            continue
        rows.append(
            {
                "entidad": entidad,
                "tna": tna,
                "valor": tna,
                "plazoDias": plazo,
                "tnaNoClientes": _as_pct(item.get("tnaNoClientes")),
                "logo": item.get("logo"),
                "enlace": item.get("enlace"),
                "unidad": "% TNA",
            }
        )
    rows.sort(key=lambda r: float(r["tna"]), reverse=True)
    return rows[:limit]


def flatten_hipotecarios(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        entidad = str(
            item.get("nombreComercial") or item.get("entidad") or ""
        ).strip()
        if not entidad:
            continue
        tna = _as_pct(item.get("tna"))
        if tna is None:
            continue
        meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        rows.append(
            {
                "entidad": entidad,
                "banco": str(item.get("entidad") or entidad).strip(),
                "tna": tna,
                "valor": tna,
                "plazoMaxAnios": meta.get("plazo_max_anios"),
                "relacionCuotaIngreso": meta.get("relacion_cuota_ingreso"),
                "financiamiento": meta.get("financiamiento"),
                "unidad": "% TNA UVA",
            }
        )
    rows.sort(key=lambda r: float(r["tna"]))
    return rows


def _normalize_fondo_row(item: dict[str, Any]) -> dict[str, Any]:
    nombre = str(item.get("nombre") or "").strip()
    slug = str(item.get("slug") or "").strip() or slugify_fondo(nombre)
    return {
        "slug": slug,
        "nombre": nombre,
        "fondoId": item.get("fondoId"),
        "claseId": item.get("claseId"),
        "tipoRenta": item.get("tipoRenta"),
        "horizonte": item.get("horizonte"),
        "administradora": item.get("administradora"),
        "moneda": item.get("moneda") or item.get("monedaInversion"),
        "patrimonio": item.get("patrimonio"),
        "fecha": item.get("fecha"),
    }


async def fetch_plazos_ranking(
    *, limit: int = RANKING_CAP, refresh: bool = False
) -> list[dict[str, Any]]:
    raw = await upstream.get(_PLAZO_PATH, ttl=TTL_SNAPSHOT, refresh=refresh)
    return flatten_plazos(raw, limit=limit)


async def fetch_hipotecarios(*, refresh: bool = False) -> list[dict[str, Any]]:
    raw = await upstream.get(_HIPOTECARIO_PATH, ttl=TTL_SNAPSHOT, refresh=refresh)
    return flatten_hipotecarios(raw)


async def _fondos_catalog(*, refresh: bool = False) -> list[dict[str, Any]]:
    raw = await upstream.get(_FCI_LIST_PATH, ttl=TTL_FCI_LIST, refresh=refresh)
    fondos = raw.get("fondos") if isinstance(raw, dict) else raw
    if not isinstance(fondos, list):
        return []
    return [
        _normalize_fondo_row(item)
        for item in fondos
        if isinstance(item, dict) and item.get("nombre")
    ]


async def search_fci(
    q: str, *, limit: int = SEARCH_CAP, refresh: bool = False
) -> list[dict[str, Any]]:
    query = filters.normalize(q)
    if not query:
        return []
    words = [w for w in query.split() if w]
    rows = await _fondos_catalog(refresh=refresh)
    hits: list[dict[str, Any]] = []
    for row in rows:
        hay = filters.normalize(f"{row.get('nombre')} {row.get('slug')}")
        if words and all(w in hay for w in words):
            hits.append(row)
            if len(hits) >= limit:
                break
    return hits


def resolve_fci_slug(slug_or_alias: str) -> str:
    key = str(slug_or_alias or "").strip()
    alias = get_fci_alias(key)
    if alias:
        return alias.slug
    # Already a slug, or display name → slugify.
    if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", key.lower()):
        return key.lower()
    return slugify_fondo(key)


async def fetch_fci_detail(
    slug_or_alias: str, *, refresh: bool = False
) -> dict[str, Any]:
    slug = resolve_fci_slug(slug_or_alias)
    if not slug:
        raise UpstreamError("FCI slug is required.")
    path = _FCI_DETAIL_PATH.replace("{nombre}", slug)
    try:
        raw = await upstream.get(path, ttl=TTL_FCI_LIST, refresh=refresh)
    except UpstreamError as exc:
        raise UpstreamError(
            f"FCI {slug!r} not found. Search /v1/fci/search?q= first."
        ) from exc
    if not isinstance(raw, dict):
        raise UpstreamError(f"Unexpected FCI detail shape for {slug!r}.")
    row = _normalize_fondo_row(raw)
    # Keep a few useful extras for MetricRow / Text.
    for key in ("rendimientos", "honorarios", "inversionMinima", "codigoCNV"):
        if key in raw:
            row[key] = raw[key]
    row["slug"] = slug
    return row


async def fetch_fci_historico(
    slug_or_alias: str,
    *,
    desde: str | None = None,
    hasta: str | None = None,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    slug = resolve_fci_slug(slug_or_alias)
    if not slug:
        raise UpstreamError("FCI slug is required.")
    path = _FCI_HIST_PATH.replace("{nombre}", slug)
    try:
        raw = await upstream.get(path, ttl=TTL_FCI_HIST, refresh=refresh)
    except UpstreamError as exc:
        raise UpstreamError(
            f"FCI historico for {slug!r} not found. "
            "Use /v1/fci/search?q= to resolve the slug."
        ) from exc
    hist = raw.get("historico") if isinstance(raw, dict) else raw
    if not isinstance(hist, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in hist:
        if not isinstance(item, dict):
            continue
        fecha = item.get("fecha")
        valor = item.get("valorCuotaparte")
        if not isinstance(fecha, str) or valor is None:
            continue
        try:
            v = float(valor)
        except (TypeError, ValueError):
            continue
        rows.append(
            {
                "fecha": fecha[:10],
                "valor": v,
                "valorCuotaparte": v,
                "slug": slug,
                "nombre": item.get("nombre"),
                "unidad": "ARS / cuotaparte",
            }
        )
    if desde or hasta:
        rows = filters.filter_by_date(rows, desde, hasta)
    return rows
