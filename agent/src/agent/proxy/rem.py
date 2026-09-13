"""BCRA Relevamiento de Expectativas de Mercado (REM) — curated + vs-real.

Upstream (via ArgentinaDatos):
  ``/v1/finanzas/rem``            index of informe paths
  ``/v1/finanzas/rem/ultimo``     latest survey
  ``/v1/finanzas/rem/{año}/{mes}`` one informe

Curated proxy surface:
  ``/v1/rem``                 aliases
  ``/v1/rem/ultimo``          latest rows (optional alias / muestra)
  ``/v1/rem/informe``         one informe (año+mes required)
  ``/v1/rem/{alias}``         nowcast mediana across informes (chartable)
  ``/v1/rem/vs-real/{alias}`` expected vs realized + error
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any

from . import series, upstream
from .upstream import UpstreamError

TTL_INDEX = 24 * 60 * 60
TTL_INFORME = 24 * 60 * 60
TTL_REAL = 12 * 60 * 60

# Cap how many past informes we walk for series / vs-real (≈3 years).
MAX_INFORMES = 36

_INDEX_PATH = "/v1/finanzas/rem"
_ULTIMO_PATH = "/v1/finanzas/rem/ultimo"
_YM_RE = re.compile(r"^/finanzas/rem/(\d{4})/(\d{2})$")


@dataclass(frozen=True)
class RemAlias:
    alias: str
    indicador: str
    #: Which REM ``periodoTipo`` rows to keep for series / vs-real.
    periodo_tipo: str
    titulo: str
    unidad: str
    #: How to load realized values: argentinadatos path or series alias.
    real_kind: str  # "inflacion" | "oficial" | "series"
    real_ref: str  # path or series alias
    #: Multiply realized values (e.g. desempleo 0–1 → %).
    real_scale: float = 1.0
    #: For oficial FX: which quote field.
    real_value_key: str = "valor"


ALIASES: tuple[RemAlias, ...] = (
    RemAlias(
        alias="ipc",
        indicador="Precios minoristas (IPC nivel general-Nacional; INDEC)",
        periodo_tipo="mensual",
        titulo="IPC nivel general — expectativa REM vs inflación mensual",
        unidad="var. % mensual",
        real_kind="inflacion",
        real_ref="/v1/finanzas/indices/inflacion",
    ),
    RemAlias(
        alias="ipc_nucleo",
        indicador="Precios minoristas (IPC núcleo-Nacional; INDEC)",
        periodo_tipo="mensual",
        titulo="IPC núcleo — expectativa REM vs inflación mensual (aprox.)",
        unidad="var. % mensual",
        # Nucleus CPI has no separate ArgentinaDatos series; compare to
        # headline monthly inflation as a rough realized benchmark.
        real_kind="inflacion",
        real_ref="/v1/finanzas/indices/inflacion",
    ),
    RemAlias(
        alias="tc",
        indicador="Tipo de cambio nominal",
        periodo_tipo="mensual",
        titulo="Tipo de cambio nominal — REM vs dólar oficial (venta fin de mes)",
        unidad="$/USD",
        real_kind="oficial",
        real_ref="/v1/cotizaciones/dolares/oficial",
        real_value_key="venta",
    ),
    RemAlias(
        alias="desempleo",
        indicador="Desocupación abierta",
        periodo_tipo="trimestral",
        titulo="Desocupación — REM vs EPH (Series de Tiempo)",
        unidad="% de la PEA",
        real_kind="series",
        real_ref="desempleo",
        real_scale=100.0,
    ),
)

_BY_ALIAS: dict[str, RemAlias] = {a.alias: a for a in ALIASES}


def list_aliases() -> list[dict[str, Any]]:
    return [
        {
            "alias": a.alias,
            "indicador": a.indicador,
            "periodoTipo": a.periodo_tipo,
            "titulo": a.titulo,
            "unidad": a.unidad,
            "real": a.real_ref,
        }
        for a in ALIASES
    ]


def get_alias(alias: str) -> RemAlias | None:
    return _BY_ALIAS.get(str(alias or "").strip().lower())


def _ym(fecha: str | None) -> str | None:
    if not fecha:
        return None
    text = str(fecha).strip()
    if len(text) >= 7 and text[4] == "-":
        return text[:7]
    return None


def _parse_informe_token(token: str) -> tuple[int, str] | None:
    """``2024-06`` or ``2024/06`` → (2024, '06')."""
    text = str(token).strip().replace("/", "-")
    parts = text.split("-")
    if len(parts) < 2:
        return None
    try:
        year = int(parts[0])
        month = int(parts[1])
    except ValueError:
        return None
    if not (1 <= month <= 12):
        return None
    return year, f"{month:02d}"


def _months_back(year: int, month: int, count: int) -> list[tuple[int, str]]:
    """``count`` calendar months ending at ``year-month``, newest-first."""
    out: list[tuple[int, str]] = []
    y, m = year, month
    for _ in range(max(0, count)):
        out.append((y, f"{m:02d}"))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return out


def _month_span(older_ym: str, newer: tuple[int, int]) -> int:
    """Inclusive month count from ``YYYY-MM`` through ``(year, month)``."""
    try:
        oy, om = int(older_ym[:4]), int(older_ym[5:7])
    except ValueError:
        return MAX_INFORMES
    return max(1, (newer[0] - oy) * 12 + (newer[1] - om) + 1)


async def list_informes(
    *,
    refresh: bool = False,
    cover_desde: str | None = None,
) -> list[tuple[int, str]]:
    """Return ``(año, mes)`` newest-first for series / vs-real walks.

    Upstream ``/v1/finanzas/rem`` only indexes ~12 recent paths, but older
    informes remain fetchable by year/month. We take the newest listed
    month and walk backward ``MAX_INFORMES`` months (or farther when
    ``cover_desde`` requires it). Missing months 404 and are skipped by
    callers.
    """
    raw = await upstream.get(_INDEX_PATH, ttl=TTL_INDEX, refresh=refresh)
    indexed: list[tuple[int, str]] = []
    if isinstance(raw, list):
        for item in raw:
            text = str(item)
            # Absolute or relative: /v1/finanzas/rem/2024/06 or /finanzas/rem/…
            m = _YM_RE.search(text.replace("/v1/", "/"))
            if m:
                indexed.append((int(m.group(1)), m.group(2)))
                continue
            parsed = _parse_informe_token(
                text.rsplit("/", 2)[-1] if "/" in text else text
            )
            if parsed:
                indexed.append(parsed)

    if not indexed:
        return []

    # Index is usually newest-first; pick the max calendar month defensively.
    newest = max(indexed, key=lambda p: (p[0], int(p[1])))
    count = MAX_INFORMES
    desde_ym = _ym(cover_desde)
    if desde_ym:
        count = max(count, _month_span(desde_ym, (newest[0], int(newest[1]))))
    return _months_back(newest[0], int(newest[1]), count)


async def fetch_informe(
    year: int,
    month: str | int,
    *,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    mes = f"{int(month):02d}"
    path = f"/v1/finanzas/rem/{year}/{mes}"
    raw = await upstream.get(path, ttl=TTL_INFORME, refresh=refresh)
    if not isinstance(raw, list):
        return []
    return [r for r in raw if isinstance(r, dict)]


async def fetch_ultimo(*, refresh: bool = False) -> list[dict[str, Any]]:
    raw = await upstream.get(_ULTIMO_PATH, ttl=TTL_INFORME, refresh=refresh)
    if not isinstance(raw, list):
        return []
    return [r for r in raw if isinstance(r, dict)]


def filter_rows(
    rows: list[dict[str, Any]],
    *,
    alias: RemAlias | None = None,
    indicador: str | None = None,
    muestra: str | None = "todos",
    periodo_tipo: str | None = None,
) -> list[dict[str, Any]]:
    ind = (alias.indicador if alias else None) or indicador
    ptipo = (alias.periodo_tipo if alias and periodo_tipo is None else periodo_tipo)
    out: list[dict[str, Any]] = []
    for row in rows:
        if muestra and str(row.get("muestra") or "").lower() != str(muestra).lower():
            # Some older informes omit muestra — keep those.
            if row.get("muestra") not in (None, ""):
                continue
        if ind and str(row.get("indicador") or "") != ind:
            # Accent/case-insensitive substring fallback for typos.
            needle = ind.casefold()
            hay = str(row.get("indicador") or "").casefold()
            if needle not in hay and hay not in needle:
                continue
        if ptipo and str(row.get("periodoTipo") or "") != ptipo:
            continue
        out.append(row)
    return out


def _nowcast_row(rows: list[dict[str, Any]], informe_ym: str) -> dict[str, Any] | None:
    """Prefer the monthly/quarterly row whose periodo starts in the informe month."""
    for row in rows:
        if _ym(row.get("periodoDesde")) == informe_ym:
            return row
    # Fallback: first row (already filtered by periodoTipo).
    return rows[0] if rows else None


async def series_for_alias(
    alias: str,
    *,
    desde: str | None = None,
    hasta: str | None = None,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    """Nowcast mediana per informe — one point per survey month."""
    spec = get_alias(alias)
    if spec is None:
        known = ", ".join(a.alias for a in ALIASES)
        raise UpstreamError(
            f"Unknown REM alias {alias!r}. Curated aliases: {known}."
        )

    desde_ym = _ym(desde)
    hasta_ym = _ym(hasta)
    informes = await list_informes(refresh=refresh, cover_desde=desde_ym)

    async def one(year: int, mes: str) -> dict[str, Any] | None:
        informe_ym = f"{year}-{mes}"
        if desde_ym and informe_ym < desde_ym:
            return None
        if hasta_ym and informe_ym > hasta_ym:
            return None
        try:
            rows = await fetch_informe(year, mes, refresh=refresh)
        except UpstreamError:
            return None
        filtered = filter_rows(rows, alias=spec, muestra="todos")
        pick = _nowcast_row(filtered, informe_ym)
        if not pick:
            return None
        mediana = pick.get("mediana")
        try:
            med = float(mediana)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        return {
            "fecha": f"{informe_ym}-01",
            "informe": pick.get("informe") or informe_ym,
            "periodo": pick.get("periodo"),
            "periodoDesde": pick.get("periodoDesde"),
            "periodoHasta": pick.get("periodoHasta"),
            "mediana": med,
            "promedio": pick.get("promedio"),
            "minimo": pick.get("minimo"),
            "maximo": pick.get("maximo"),
            "valor": med,  # Chart-friendly
            "unidad": pick.get("unidad") or spec.unidad,
            "indicador": spec.indicador,
            "alias": spec.alias,
        }

    chunks = await asyncio.gather(*(one(y, m) for y, m in informes))
    rows = [r for r in chunks if r]
    rows.sort(key=lambda r: r["fecha"])
    return rows


async def _real_by_ym(
    spec: RemAlias,
    *,
    refresh: bool = False,
) -> dict[str, float]:
    """Map ``YYYY-MM`` → realized value for *spec*."""
    if spec.real_kind == "inflacion":
        raw = await upstream.get(spec.real_ref, ttl=TTL_REAL, refresh=refresh)
        rows = [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []
        return _month_end_map(rows, "valor", scale=spec.real_scale)

    if spec.real_kind == "oficial":
        raw = await upstream.get(spec.real_ref, ttl=TTL_REAL, refresh=refresh)
        rows = [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []
        return _month_end_map(rows, spec.real_value_key, scale=spec.real_scale)

    if spec.real_kind == "series":
        rows = await series.fetch_by_alias(spec.real_ref, refresh=refresh)
        return _period_start_map(rows, "valor", scale=spec.real_scale)

    return {}


def _month_end_map(
    rows: list[dict[str, Any]],
    value_key: str,
    *,
    scale: float = 1.0,
) -> dict[str, float]:
    """Last observation per calendar month wins (assumes chronological)."""
    out: dict[str, float] = {}
    for row in sorted(rows, key=lambda r: str(r.get("fecha") or "")):
        ym = _ym(row.get("fecha"))
        if not ym:
            continue
        try:
            out[ym] = float(row[value_key]) * scale
        except (TypeError, ValueError, KeyError):
            continue
    return out


def _period_start_map(
    rows: list[dict[str, Any]],
    value_key: str,
    *,
    scale: float = 1.0,
) -> dict[str, float]:
    """Map by observation month (EPH quarters land on period start)."""
    return _month_end_map(rows, value_key, scale=scale)


def _prev_ym(ym: str) -> str | None:
    try:
        year, month = int(ym[:4]), int(ym[5:7])
    except ValueError:
        return None
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


async def vs_real(
    alias: str,
    *,
    horizon: str = "1m",
    desde: str | None = None,
    hasta: str | None = None,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    """Join REM expectations with realized outcomes.

    ``horizon``:
      - ``1m`` — forecast published the month *before* the target period
      - ``nowcast`` — forecast published in the same month as the target
      - ``all`` — every past forecast that has a realized value
    """
    spec = get_alias(alias)
    if spec is None:
        known = ", ".join(a.alias for a in ALIASES)
        raise UpstreamError(
            f"Unknown REM alias {alias!r}. Curated aliases: {known}."
        )

    hz = (horizon or "1m").strip().lower()
    if hz not in {"1m", "nowcast", "all"}:
        raise UpstreamError(
            f"Invalid horizon {horizon!r}. Use 1m, nowcast, or all."
        )

    desde_ym = _ym(desde)
    hasta_ym = _ym(hasta)
    # 1m forecasts live in the informe published the month before the target.
    cover = _prev_ym(desde_ym) if (hz == "1m" and desde_ym) else desde_ym
    informes = await list_informes(refresh=refresh, cover_desde=cover)
    real = await _real_by_ym(spec, refresh=refresh)

    async def one(year: int, mes: str) -> list[dict[str, Any]]:
        informe_ym = f"{year}-{mes}"
        try:
            rows = await fetch_informe(year, mes, refresh=refresh)
        except UpstreamError:
            return []
        filtered = filter_rows(rows, alias=spec, muestra="todos")
        hits: list[dict[str, Any]] = []
        for row in filtered:
            target_ym = _ym(row.get("periodoDesde"))
            if not target_ym:
                continue
            if desde_ym and target_ym < desde_ym:
                continue
            if hasta_ym and target_ym > hasta_ym:
                continue
            if target_ym not in real:
                continue
            # Only evaluate periods that are not after the informe (still
            # forward-looking without a fair realized match yet is ok if
            # real exists — but skip pure futures with no real).
            if hz == "1m" and _prev_ym(target_ym) != informe_ym:
                continue
            if hz == "nowcast" and target_ym != informe_ym:
                continue
            try:
                esperado = float(row["mediana"])
            except (TypeError, ValueError, KeyError):
                continue
            realizado = real[target_ym]
            error = esperado - realizado
            error_pct = (error / realizado * 100.0) if realizado else None
            hits.append(
                {
                    "fecha": f"{target_ym}-01",
                    "informe": row.get("informe") or informe_ym,
                    "informeFecha": f"{informe_ym}-01",
                    "periodo": row.get("periodo"),
                    "periodoDesde": row.get("periodoDesde"),
                    "periodoHasta": row.get("periodoHasta"),
                    "esperado": esperado,
                    "real": realizado,
                    "error": round(error, 4),
                    "error_abs": round(abs(error), 4),
                    "error_pct": (
                        round(error_pct, 2) if error_pct is not None else None
                    ),
                    "unidad": row.get("unidad") or spec.unidad,
                    "indicador": spec.indicador,
                    "alias": spec.alias,
                    "horizon": hz,
                    "valor": round(error, 4),  # Chart default series
                }
            )
        return hits

    chunks = await asyncio.gather(*(one(y, m) for y, m in informes))
    out: list[dict[str, Any]] = []
    for chunk in chunks:
        out.extend(chunk)

    # For 1m/nowcast there should be ~one row per target month; prefer the
    # earliest informe match if duplicates slip through.
    if hz in {"1m", "nowcast"}:
        best: dict[str, dict[str, Any]] = {}
        for row in sorted(out, key=lambda r: str(r.get("informeFecha") or "")):
            key = str(row.get("fecha") or "")
            best.setdefault(key, row)
        out = list(best.values())

    out.sort(key=lambda r: str(r.get("fecha") or ""))
    return out
