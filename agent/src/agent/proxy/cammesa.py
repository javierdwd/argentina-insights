"""CAMMESA electricity demand — monthly series from datos.gob.ar / SSPM.

Source CSV (CAMMESA via Subsecretaría de Programación Macroeconómica):
  ``https://infra.datos.gob.ar/catalog/sspm/dataset/367/distribution/367.3/
    download/demanda-de-electricidad-datos-mensuales.csv``

Columns used: demanda_total, demanda_residencial, comercio_e_industria,
grandes_usuarios, temperatura_promedio, potencia_maxima.

No API key. Attribution: CAMMESA / datos.gob.ar.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from . import upstream
from .upstream import UpstreamError

BASE_URL = "https://infra.datos.gob.ar"
CSV_PATH = (
    "/catalog/sspm/dataset/367/distribution/367.3/"
    "download/demanda-de-electricidad-datos-mensuales.csv"
)
TTL = 12 * 60 * 60


@dataclass(frozen=True)
class CammesaAlias:
    alias: str
    column: str
    titulo: str
    unidad: str
    kind: str = "flow"


ALIASES: tuple[CammesaAlias, ...] = (
    CammesaAlias(
        alias="demanda",
        column="demanda_total",
        titulo="Demanda eléctrica total (CAMMESA / SSPM)",
        unidad="GWh",
    ),
    CammesaAlias(
        alias="residencial",
        column="demanda_residencial",
        titulo="Demanda eléctrica residencial",
        unidad="GWh",
    ),
    CammesaAlias(
        alias="comercio",
        column="comercio_e_industria",
        titulo="Demanda comercio e industria",
        unidad="GWh",
    ),
    CammesaAlias(
        alias="grandes_usuarios",
        column="grandes_usuarios",
        titulo="Demanda grandes usuarios",
        unidad="GWh",
    ),
    CammesaAlias(
        alias="temperatura",
        column="temperatura_promedio",
        titulo="Temperatura promedio (serie CAMMESA junto a demanda)",
        unidad="°C",
        kind="stock",
    ),
    CammesaAlias(
        alias="potencia_maxima",
        column="potencia_maxima",
        titulo="Potencia máxima requerida",
        unidad="MW",
    ),
)

_BY_ALIAS: dict[str, CammesaAlias] = {a.alias: a for a in ALIASES}

#: Wide table columns for /v1/cammesa/demanda (chart-friendly names).
WIDE_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("demanda_total", "demanda_total", "GWh"),
    ("demanda_residencial", "demanda_residencial", "GWh"),
    ("comercio_e_industria", "comercio_industria", "GWh"),
    ("grandes_usuarios", "grandes_usuarios", "GWh"),
    ("temperatura_promedio", "temperatura", "°C"),
    ("potencia_maxima", "potencia_maxima", "MW"),
)


def list_aliases() -> list[dict[str, Any]]:
    return [
        {
            "alias": a.alias,
            "column": a.column,
            "titulo": a.titulo,
            "unidad": a.unidad,
            "kind": a.kind,
            "fuente": "CAMMESA / SSPM (datos.gob.ar)",
        }
        for a in ALIASES
    ]


def get_alias(alias: str) -> CammesaAlias | None:
    return _BY_ALIAS.get(str(alias or "").strip().lower())


def _parse_num(raw: str | None) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _ym(fecha: str | None) -> str | None:
    if not fecha:
        return None
    text = str(fecha).strip()
    if len(text) >= 7 and text[4] == "-":
        return text[:7]
    return None


async def _load_monthly(*, refresh: bool = False) -> list[dict[str, str]]:
    raw = await upstream.get(
        CSV_PATH,
        ttl=TTL,
        refresh=refresh,
        base_url=BASE_URL,
    )
    if isinstance(raw, (bytes, bytearray)):
        text = raw.decode("utf-8-sig")
    else:
        text = str(raw)
    # Strip BOM if present as text.
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise UpstreamError("CAMMESA demanda CSV has no header.")
    rows = [row for row in reader if isinstance(row, dict)]
    if not rows:
        raise UpstreamError("CAMMESA demanda CSV returned 0 rows.")
    return rows


def _filter_ym(
    rows: list[dict[str, str]],
    *,
    desde: str | None,
    hasta: str | None,
) -> list[dict[str, str]]:
    desde_ym = _ym(desde)
    hasta_ym = _ym(hasta)
    out: list[dict[str, str]] = []
    for row in rows:
        ym = _ym(row.get("indice_tiempo"))
        if not ym:
            continue
        if desde_ym and ym < desde_ym:
            continue
        if hasta_ym and ym > hasta_ym:
            continue
        out.append(row)
    return out


async def fetch_wide(
    *,
    desde: str | None = None,
    hasta: str | None = None,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    """One row per month with demanda + temperatura + potencia."""
    raw_rows = _filter_ym(
        await _load_monthly(refresh=refresh),
        desde=desde,
        hasta=hasta,
    )
    out: list[dict[str, Any]] = []
    for row in raw_rows:
        fecha_raw = str(row.get("indice_tiempo") or "")[:10]
        if len(fecha_raw) == 7:
            fecha = f"{fecha_raw}-01"
        else:
            fecha = fecha_raw
        item: dict[str, Any] = {
            "fecha": fecha,
            "fuente": "CAMMESA",
        }
        for src, dest, _unit in WIDE_COLUMNS:
            num = _parse_num(row.get(src))
            if num is not None:
                item[dest] = num
        # Chart default measure
        if "demanda_total" in item:
            item["valor"] = item["demanda_total"]
        out.append(item)
    out.sort(key=lambda r: str(r.get("fecha") or ""))
    return out


async def fetch_by_alias(
    alias: str,
    *,
    desde: str | None = None,
    hasta: str | None = None,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    spec = get_alias(alias)
    if spec is None:
        known = ", ".join(a.alias for a in ALIASES)
        raise UpstreamError(
            f"Unknown CAMMESA alias {alias!r}. Curated: {known}."
        )
    wide = await fetch_wide(desde=desde, hasta=hasta, refresh=refresh)
    # Map wide dest names back — alias column → wide key
    col_to_wide = {src: dest for src, dest, _u in WIDE_COLUMNS}
    key = col_to_wide.get(spec.column, spec.column)
    out: list[dict[str, Any]] = []
    for row in wide:
        if key not in row:
            continue
        val = row[key]
        out.append(
            {
                "fecha": row["fecha"],
                "valor": val,
                "alias": spec.alias,
                "titulo": spec.titulo,
                "unidad": spec.unidad,
                "kind": spec.kind,
                "fuente": "CAMMESA",
            }
        )
    return out
