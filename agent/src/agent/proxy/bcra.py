"""BCRA estadísticas monetarias v4 — curated stock series.

Upstream: ``https://api.bcra.gob.ar/estadisticas/v4.0/Monetarias``.
No API key. Rows normalized to ``{fecha, valor}`` so period joins work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import upstream
from .upstream import UpstreamError

BASE_URL = "https://api.bcra.gob.ar"
LIST_PATH = "/estadisticas/v4.0/Monetarias"
TTL_LIST = 24 * 60 * 60
TTL_SERIES = 6 * 60 * 60


@dataclass(frozen=True)
class BcraVariable:
    alias: str
    id_variable: int
    descripcion: str
    unidad: str
    #: ``stock`` → period_levels uses last/delta; ``flow`` → max (FX-like).
    kind: str = "stock"


# Ids pinned against the live Monetarias catalog (2026-09). Prefer the
# "Principales Variables" daily series that users actually ask about.
VARIABLES: tuple[BcraVariable, ...] = (
    BcraVariable(
        alias="reservas",
        id_variable=1,
        descripcion="Reservas internacionales",
        unidad="millones USD",
        kind="stock",
    ),
    BcraVariable(
        alias="base_monetaria",
        id_variable=15,
        descripcion="Base monetaria",
        unidad="millones ARS",
        kind="stock",
    ),
    BcraVariable(
        alias="depositos_privados",
        id_variable=106,
        descripcion="Depósitos del sector privado no financiero",
        unidad="millones ARS",
        kind="stock",
    ),
    BcraVariable(
        alias="depositos_plazo",
        id_variable=24,
        descripcion=(
            "Depósitos a plazo en efectivo en las entidades financieras"
        ),
        unidad="millones ARS",
        kind="stock",
    ),
    BcraVariable(
        alias="tasa_depositos_30d",
        id_variable=12,
        descripcion=(
            "Tasa de interés de depósitos a 30 días de plazo en entidades "
            "financieras"
        ),
        unidad="% TNA",
        kind="flow",
    ),
)

_BY_ALIAS: dict[str, BcraVariable] = {v.alias: v for v in VARIABLES}


def list_variables() -> list[dict[str, Any]]:
    return [
        {
            "alias": v.alias,
            "id": v.id_variable,
            "descripcion": v.descripcion,
            "unidad": v.unidad,
            "kind": v.kind,
        }
        for v in VARIABLES
    ]


def get_variable(alias: str) -> BcraVariable | None:
    return _BY_ALIAS.get(str(alias or "").strip().lower())


def series_kind_for_path(path: str) -> str | None:
    """Return ``stock`` / ``flow`` when *path* is a curated BCRA series."""
    if not path.startswith("/v1/bcra/"):
        return None
    alias = path.rsplit("/", 1)[-1]
    if alias in ("variables",):
        return None
    var = get_variable(alias)
    return var.kind if var else None


async def fetch_series(
    alias: str,
    *,
    desde: str | None = None,
    hasta: str | None = None,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    var = get_variable(alias)
    if var is None:
        known = ", ".join(v.alias for v in VARIABLES)
        raise UpstreamError(
            f"Unknown BCRA alias {alias!r}. Curated aliases: {known}."
        )

    query: dict[str, Any] = {"limit": 3000, "offset": 0}
    if desde:
        query["desde"] = str(desde)[:10]
    if hasta:
        query["hasta"] = str(hasta)[:10]

    raw = await upstream.get(
        f"{LIST_PATH}/{var.id_variable}",
        query=query,
        ttl=TTL_SERIES,
        refresh=refresh,
        base_url=BASE_URL,
    )
    return _normalize_series(raw, var)


def _normalize_series(raw: Any, var: BcraVariable) -> list[dict[str, Any]]:
    """Flatten BCRA's ``results[].detalle[]`` into ``{fecha, valor, …}``."""
    results = []
    if isinstance(raw, dict):
        results = raw.get("results") or []
    elif isinstance(raw, list):
        results = raw

    detalle: list = []
    for block in results:
        if not isinstance(block, dict):
            continue
        chunk = block.get("detalle")
        if isinstance(chunk, list):
            detalle.extend(chunk)
        elif "fecha" in block and "valor" in block:
            detalle.append(block)

    rows: list[dict[str, Any]] = []
    for item in detalle:
        if not isinstance(item, dict):
            continue
        fecha = item.get("fecha")
        valor = item.get("valor")
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
                "alias": var.alias,
                "descripcion": var.descripcion,
                "unidad": var.unidad,
                "kind": var.kind,
            }
        )
    rows.sort(key=lambda r: r["fecha"])
    return rows
