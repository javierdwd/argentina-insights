"""Open-Meteo weather — historical archive + forecast by province capital.

No API key for non-commercial use. Attribution: Open-Meteo (CC BY 4.0).
"""

from __future__ import annotations

from typing import Any

from . import provinces, upstream
from .upstream import UpstreamError

FORECAST_BASE = "https://api.open-meteo.com"
ARCHIVE_BASE = "https://archive-api.open-meteo.com"
TTL_HISTORICO = 30 * 24 * 60 * 60  # immutable past
TTL_FORECAST = 60 * 60
TIMEZONE = "America/Argentina/Buenos_Aires"


def _locations(
    provincia: str | None,
) -> list[tuple[str, str, float, float]]:
    if provincia:
        hit = provinces.resolve_province(str(provincia))
        if hit is None:
            raise UpstreamError(
                f"Unknown province {provincia!r}. Use an Argentine province "
                "name (e.g. 'Córdoba', 'CABA', 'Santa Fe')."
            )
        return [hit]
    return provinces.all_province_capitals()


def _multi_query(locs: list[tuple[str, str, float, float]]) -> dict[str, Any]:
    return {
        "latitude": ",".join(str(lat) for _k, _d, lat, _lon in locs),
        "longitude": ",".join(str(lon) for _k, _d, _lat, lon in locs),
        "timezone": TIMEZONE,
    }


def _as_list(payload: Any) -> list[dict]:
    """Open-Meteo returns a dict for one location, a list for many."""
    if isinstance(payload, list):
        return [p for p in payload if isinstance(p, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


async def historico(
    *,
    provincia: str | None,
    desde: str,
    hasta: str,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    if not desde or not hasta:
        raise UpstreamError(
            "/v1/clima/historico requires desde and hasta (ISO dates)."
        )
    locs = _locations(provincia)
    query = {
        **_multi_query(locs),
        "start_date": str(desde)[:10],
        "end_date": str(hasta)[:10],
        "daily": (
            "temperature_2m_min,temperature_2m_max,precipitation_sum,"
            "weather_code"
        ),
    }
    raw = await upstream.get(
        "/v1/archive",
        query=query,
        ttl=TTL_HISTORICO,
        refresh=refresh,
        base_url=ARCHIVE_BASE,
    )
    return _daily_rows(raw, locs, forecast=False)


async def pronostico(
    *,
    provincia: str | None = None,
    dias: int = 7,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    locs = _locations(provincia)
    days = max(1, min(int(dias or 7), 16))
    query = {
        **_multi_query(locs),
        "forecast_days": days,
        "daily": (
            "temperature_2m_min,temperature_2m_max,precipitation_sum,"
            "weather_code"
        ),
    }
    raw = await upstream.get(
        "/v1/forecast",
        query=query,
        ttl=TTL_FORECAST,
        refresh=refresh,
        base_url=FORECAST_BASE,
    )
    return _daily_rows(raw, locs, forecast=True)


async def actual(
    *,
    provincia: str | None = None,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    locs = _locations(provincia)
    query = {
        **_multi_query(locs),
        "current": "temperature_2m,precipitation,weather_code",
        "forecast_days": 1,
    }
    raw = await upstream.get(
        "/v1/forecast",
        query=query,
        ttl=TTL_FORECAST,
        refresh=refresh,
        base_url=FORECAST_BASE,
    )
    blocks = _as_list(raw)
    rows: list[dict[str, Any]] = []
    for loc, block in zip(locs, blocks, strict=False):
        _key, display, _lat, _lon = loc
        current = block.get("current") or {}
        if not isinstance(current, dict):
            continue
        temp = current.get("temperature_2m")
        precip = current.get("precipitation")
        rows.append(
            {
                "provincia": display,
                "temperatura": temp,
                "precipitacion": precip,
                "weather_code": current.get("weather_code"),
                "fecha": str(current.get("time") or "")[:10] or None,
                "fuente": "Open-Meteo",
            }
        )
    return rows


def _daily_rows(
    raw: Any,
    locs: list[tuple[str, str, float, float]],
    *,
    forecast: bool,
) -> list[dict[str, Any]]:
    blocks = _as_list(raw)
    rows: list[dict[str, Any]] = []
    for loc, block in zip(locs, blocks, strict=False):
        _key, display, _lat, _lon = loc
        daily = block.get("daily") or {}
        if not isinstance(daily, dict):
            continue
        times = daily.get("time") or []
        tmins = daily.get("temperature_2m_min") or []
        tmaxs = daily.get("temperature_2m_max") or []
        precs = daily.get("precipitation_sum") or []
        codes = daily.get("weather_code") or []
        for i, fecha in enumerate(times):
            tmin = tmins[i] if i < len(tmins) else None
            tmax = tmaxs[i] if i < len(tmaxs) else None
            precip = precs[i] if i < len(precs) else None
            code = codes[i] if i < len(codes) else None
            mid = None
            try:
                if tmin is not None and tmax is not None:
                    mid = (float(tmin) + float(tmax)) / 2.0
                elif tmax is not None:
                    mid = float(tmax)
                elif tmin is not None:
                    mid = float(tmin)
            except (TypeError, ValueError):
                mid = None
            row: dict[str, Any] = {
                "fecha": str(fecha)[:10],
                "provincia": display,
                "tmin": tmin,
                "tmax": tmax,
                "temperatura": mid,
                "precipitacion": precip,
                "weather_code": code,
                "valor": mid if mid is not None else precip,
                "fuente": "Open-Meteo",
            }
            if forecast:
                row["tipo"] = "pronostico"
            rows.append(row)
    rows.sort(key=lambda r: (r.get("fecha") or "", r.get("provincia") or ""))
    return rows
