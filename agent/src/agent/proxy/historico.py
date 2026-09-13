"""Curated Argentine historical days (last ~10 years) + Wikipedia context.

Each day maps to a Spanish Wikipedia article. The proxy stamps the REST
summary (extract, thumbnail, url) so compose can pair PersonCard + Text + WeatherUnit + Chart without
a separate wiki tool.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import wiki


@dataclass(frozen=True)
class HistoricalDay:
    fecha: str
    titulo: str
    wiki: str
    categoria: str
    series: tuple[str, ...]
    #: President / figure to fetch as a PersonCard alongside the day.
    persona: str | None = None
    #: Province capital for same-day weather (national events → CABA).
    provincia: str = "CABA"


# fmt: off
DAYS: tuple[HistoricalDay, ...] = (
    HistoricalDay(
        fecha="2016-03-01",
        titulo="Acuerdo con los holdouts",
        wiki="Acuerdo entre Argentina y los holdouts de 2016",
        categoria="economia",
        series=("blue", "riesgo"),
    ),
    HistoricalDay(
        fecha="2017-10-22",
        titulo="Elecciones legislativas 2017",
        wiki="Elecciones legislativas de Argentina de 2017",
        categoria="politica",
        series=("blue",),
    ),
    HistoricalDay(
        fecha="2018-05-08",
        titulo="Acuerdo stand-by con el FMI",
        wiki="Acuerdo entre Argentina y el Fondo Monetario Internacional de 2018",
        categoria="economia",
        series=("blue", "riesgo"),
    ),
    HistoricalDay(
        fecha="2018-08-30",
        titulo="Corralito cambiario",
        wiki="Crisis cambiaria argentina de 2018",
        categoria="economia",
        series=("blue", "mep"),
    ),
    HistoricalDay(
        fecha="2019-08-11",
        titulo="PASO 2019 (shock electoral)",
        wiki="Elecciones primarias abiertas, simultáneas y obligatorias de Argentina de 2019",
        categoria="politica",
        series=("blue", "riesgo"),
    ),
    HistoricalDay(
        fecha="2019-10-27",
        titulo="Elecciones generales 2019",
        wiki="Elecciones generales de Argentina de 2019",
        categoria="politica",
        series=("blue",),
    ),
    HistoricalDay(
        fecha="2020-03-20",
        titulo="Inicio de la cuarentena COVID",
        wiki="Cuarentena en Argentina por la pandemia de COVID-19",
        categoria="ambos",
        series=("blue", "mep"),
    ),
    HistoricalDay(
        fecha="2020-05-22",
        titulo="Oferta de canje de deuda",
        wiki="Restructuración de la deuda argentina de 2020",
        categoria="economia",
        series=("riesgo", "blue"),
    ),
    HistoricalDay(
        fecha="2021-09-12",
        titulo="PASO 2021",
        wiki="Elecciones primarias abiertas, simultáneas y obligatorias de Argentina de 2021",
        categoria="politica",
        series=("blue",),
    ),
    HistoricalDay(
        fecha="2021-11-14",
        titulo="Elecciones legislativas 2021",
        wiki="Elecciones legislativas de Argentina de 2021",
        categoria="politica",
        series=("blue", "riesgo"),
    ),
    HistoricalDay(
        fecha="2022-09-01",
        titulo="Atentado a Cristina Fernández",
        wiki="Atentado a Cristina Fernández de Kirchner",
        categoria="politica",
        series=("blue", "riesgo"),
        persona="Cristina Fernández de Kirchner",
    ),
    HistoricalDay(
        fecha="2023-08-13",
        titulo="PASO 2023",
        wiki="Elecciones primarias abiertas, simultáneas y obligatorias de Argentina de 2023",
        categoria="politica",
        series=("blue", "mep"),
    ),
    HistoricalDay(
        fecha="2023-11-19",
        titulo="Ballotage presidencial 2023",
        wiki="Elecciones presidenciales de Argentina de 2023",
        categoria="politica",
        series=("blue", "riesgo"),
    ),
    HistoricalDay(
        fecha="2023-12-10",
        titulo="Asunción de Javier Milei",
        wiki="Presidencia de Javier Milei",
        categoria="politica",
        series=("blue", "reservas"),
        persona="Javier Milei",
    ),
    HistoricalDay(
        fecha="2023-12-20",
        titulo="DNU de deregulación económica",
        wiki="Decreto de necesidad y urgencia de diciembre de 2023",
        categoria="politica",
        series=("blue", "riesgo"),
        persona="Javier Milei",
    ),
    HistoricalDay(
        fecha="2024-06-12",
        titulo="Senado: Ley Bases",
        wiki="Ley Bases y Puntos de Partida para la Libertad de los Argentinos",
        categoria="politica",
        series=("blue", "mep"),
    ),
)
# fmt: on

_BY_FECHA = {d.fecha: d for d in DAYS}


def list_days(
    *,
    desde: str | None = None,
    hasta: str | None = None,
) -> list[dict[str, Any]]:
    """Compact index — no Wikipedia body (cheap for browsing)."""
    out: list[dict[str, Any]] = []
    for day in DAYS:
        if desde and day.fecha < desde[:10]:
            continue
        if hasta and day.fecha > hasta[:10]:
            continue
        row: dict[str, Any] = {
            "fecha": day.fecha,
            "titulo": day.titulo,
            "categoria": day.categoria,
            "wiki": day.wiki,
            "series_sugeridas": list(day.series),
            "provincia": day.provincia,
        }
        if day.persona:
            row["persona"] = day.persona
        out.append(row)
    return out


def get_day(fecha: str) -> HistoricalDay | None:
    return _BY_FECHA.get(fecha[:10])


async def fetch_day(fecha: str, *, refresh: bool = False) -> dict[str, Any]:
    """One curated day with Wikipedia summary stamped in."""
    day = get_day(fecha)
    if day is None:
        return {}

    summary = await wiki.fetch_summary(day.wiki, refresh=refresh)
    row: dict[str, Any] = {
        "fecha": day.fecha,
        "titulo": day.titulo,
        "categoria": day.categoria,
        "wiki": day.wiki,
        "series_sugeridas": list(day.series),
        "provincia": day.provincia,
    }
    if day.persona:
        row["persona"] = day.persona
    if summary.get("extract"):
        row["extract"] = summary["extract"]
        row["bio"] = summary["extract"]
    if summary.get("foto"):
        row["foto"] = summary["foto"]
    if summary.get("url"):
        row["wikipedia_url"] = summary["url"]
    return row
