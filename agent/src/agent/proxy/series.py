"""Series de Tiempo (datos.gob.ar) — curated aliases + text search.

Upstream:
  ``https://apis.datos.gob.ar/series/api/series/?ids=…``
  ``https://apis.datos.gob.ar/series/api/search/?q=…``

Thousands of series exist; the prompt only sees the curated aliases. Search
is the escape hatch (same pattern as ``search_actas``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import upstream
from .upstream import UpstreamError

BASE_URL = "https://apis.datos.gob.ar"
SERIES_PATH = "/series/api/series/"
SEARCH_PATH = "/series/api/search/"
TTL_SERIES = 12 * 60 * 60
TTL_SEARCH = 6 * 60 * 60
SEARCH_CAP = 10


@dataclass(frozen=True)
class SeriesAlias:
    alias: str
    serie_id: str
    titulo: str
    unidad: str
    frecuencia: str
    kind: str = "flow"  # most INDEC series are levels/rates → last for stocks


# Ids verified live against the Series API (2026-09). Prefer monthly /
# quarterly headline indicators users actually ask about.
ALIASES: tuple[SeriesAlias, ...] = (
    SeriesAlias(
        alias="emae",
        serie_id="143.3_NO_PR_2004_A_31",
        titulo="EMAE desestacionalizado (base 2004)",
        unidad="índice 2004=100",
        frecuencia="mensual",
        kind="stock",
    ),
    SeriesAlias(
        alias="emae_var",
        serie_id="143.3_ICE_SER_VM_2004_A_34",
        titulo="EMAE desestacionalizado — variación % mensual",
        unidad="%",
        frecuencia="mensual",
        kind="flow",
    ),
    SeriesAlias(
        alias="desempleo",
        serie_id="42.3_EPH_PUNTUATAL_0_M_30",
        titulo="Tasa de desocupación total (EPH)",
        unidad="proporción (0–1)",
        frecuencia="trimestral",
        kind="stock",
    ),
    SeriesAlias(
        alias="pobreza",
        serie_id="64.2_POBLACION_NUA_0_0_34_74",
        titulo="Población bajo la línea de pobreza (EPH continua)",
        unidad="proporción (0–1)",
        frecuencia="semestral",
        kind="stock",
    ),
    SeriesAlias(
        alias="ripte",
        serie_id="158.1_REPTE_0_0_5",
        titulo="Remuneración imponible promedio de trabajadores estables (RIPTE)",
        unidad="ARS",
        frecuencia="mensual",
        kind="stock",
    ),
    SeriesAlias(
        alias="ipc",
        serie_id="148.3_INIVELNAL_DICI_M_26",
        titulo="IPC Nacional nivel general (INDEC)",
        unidad="índice",
        frecuencia="mensual",
        kind="stock",
    ),
    SeriesAlias(
        alias="exportaciones",
        serie_id="77.3_IET_0_A_25",
        titulo="Exportaciones totales FOB",
        unidad="USD",
        frecuencia="mensual",
        kind="flow",
    ),
    SeriesAlias(
        alias="importaciones",
        serie_id="78.3_IIT_0_A_25",
        titulo="Importaciones totales",
        unidad="USD",
        frecuencia="mensual",
        kind="flow",
    ),
)

_BY_ALIAS: dict[str, SeriesAlias] = {a.alias: a for a in ALIASES}


def list_aliases() -> list[dict[str, Any]]:
    return [
        {
            "alias": a.alias,
            "serieId": a.serie_id,
            "titulo": a.titulo,
            "unidad": a.unidad,
            "frecuencia": a.frecuencia,
            "kind": a.kind,
        }
        for a in ALIASES
    ]


def get_alias(alias: str) -> SeriesAlias | None:
    return _BY_ALIAS.get(str(alias or "").strip().lower())


def series_kind_for_path(path: str) -> str | None:
    if not path.startswith("/v1/series"):
        return None
    if path in ("/v1/series", "/v1/series/search"):
        return None
    if path.startswith("/v1/series/id/"):
        return "flow"
    alias = path.rsplit("/", 1)[-1]
    meta = get_alias(alias)
    return meta.kind if meta else None


async def fetch_by_alias(
    alias: str,
    *,
    desde: str | None = None,
    hasta: str | None = None,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    meta = get_alias(alias)
    if meta is None:
        known = ", ".join(a.alias for a in ALIASES)
        raise UpstreamError(
            f"Unknown series alias {alias!r}. Curated: {known}. "
            "Or call /v1/series/search?q=… then /v1/series/id/{serieId}."
        )
    rows = await fetch_by_id(
        meta.serie_id,
        desde=desde,
        hasta=hasta,
        refresh=refresh,
    )
    for row in rows:
        row["alias"] = meta.alias
        row["titulo"] = meta.titulo
        row["unidad"] = meta.unidad
        row["kind"] = meta.kind
    return rows


async def fetch_by_id(
    serie_id: str,
    *,
    desde: str | None = None,
    hasta: str | None = None,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    sid = str(serie_id or "").strip()
    if not sid:
        raise UpstreamError("serieId is required.")

    query: dict[str, Any] = {
        "ids": sid,
        "format": "json",
        "header": "titles",
        "sort": "asc",
        "limit": 5000,
    }
    if desde:
        query["start_date"] = str(desde)[:10]
    if hasta:
        query["end_date"] = str(hasta)[:10]

    raw = await upstream.get(
        SERIES_PATH,
        query=query,
        ttl=TTL_SERIES,
        refresh=refresh,
        base_url=BASE_URL,
    )
    return _normalize_series(raw, sid)


async def search(q: str, *, refresh: bool = False) -> list[dict[str, Any]]:
    needle = str(q or "").strip()
    if not needle:
        raise UpstreamError("series search needs q (a Spanish indicator name).")

    raw = await upstream.get(
        SEARCH_PATH,
        query={"q": needle, "limit": SEARCH_CAP},
        ttl=TTL_SEARCH,
        refresh=refresh,
        base_url=BASE_URL,
    )
    data = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(data, list):
        return []

    out: list[dict[str, Any]] = []
    for item in data[:SEARCH_CAP]:
        if not isinstance(item, dict):
            continue
        field = item.get("field") or {}
        dataset = item.get("dataset") or {}
        if not isinstance(field, dict):
            continue
        serie_id = field.get("id")
        if not serie_id:
            continue
        out.append(
            {
                "serieId": serie_id,
                "titulo": field.get("description") or field.get("title") or serie_id,
                "unidades": field.get("units"),
                "frecuencia": field.get("frequency"),
                "dataset": (dataset.get("title") if isinstance(dataset, dict) else None),
                "fuente": (
                    dataset.get("source") if isinstance(dataset, dict) else None
                ),
            }
        )
    return out


def _normalize_series(raw: Any, serie_id: str) -> list[dict[str, Any]]:
    data = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(data, list):
        errors = raw.get("errors") if isinstance(raw, dict) else None
        failed = raw.get("failed_series") if isinstance(raw, dict) else None
        raise UpstreamError(
            f"Series {serie_id!r} returned no data"
            + (f" (errors={errors}, failed={failed})" if errors or failed else ".")
        )

    rows: list[dict[str, Any]] = []
    for item in data:
        fecha: Any
        valor: Any
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            fecha, valor = item[0], item[1]
        elif isinstance(item, dict):
            fecha = item.get("fecha") or item.get("index") or item.get("date")
            # title-header responses use the series title as the value key
            valor = item.get("valor") or item.get("value")
            if valor is None:
                for key, candidate in item.items():
                    if key in ("fecha", "index", "date", "timestamp"):
                        continue
                    valor = candidate
                    break
        else:
            continue
        if fecha is None or valor is None:
            continue
        try:
            num = float(valor)
        except (TypeError, ValueError):
            continue
        rows.append(
            {
                "fecha": str(fecha)[:10],
                "valor": num,
                "serieId": serie_id,
            }
        )
    rows.sort(key=lambda r: r["fecha"])
    return rows
