"""Province capitals (lat/lon) for weather lookups.

Centroids on the map are for bubble placement; weather wants the capital
city. Keys are accent-folded lowercase, matching ``normalizeProvinceName``.
"""

from __future__ import annotations

import unicodedata

# (display_name, lat, lon) — capitals / AMBA seat.
_PROVINCE_CAPITALS: dict[str, tuple[str, float, float]] = {
    "buenos aires": ("La Plata", -34.9214, -57.9544),
    "ciudad autonoma de buenos aires": ("CABA", -34.6037, -58.3816),
    "caba": ("CABA", -34.6037, -58.3816),
    "capital federal": ("CABA", -34.6037, -58.3816),
    "catamarca": ("San Fernando del Valle de Catamarca", -28.4696, -65.7852),
    "chaco": ("Resistencia", -27.4514, -58.9867),
    "chubut": ("Rawson", -43.3002, -65.1023),
    "cordoba": ("Córdoba", -31.4201, -64.1888),
    "corrientes": ("Corrientes", -27.4692, -58.8306),
    "entre rios": ("Paraná", -31.7413, -60.5115),
    "formosa": ("Formosa", -26.1849, -58.1731),
    "jujuy": ("San Salvador de Jujuy", -24.1858, -65.2995),
    "la pampa": ("Santa Rosa", -36.6203, -64.2906),
    "la rioja": ("La Rioja", -29.4131, -66.8563),
    "mendoza": ("Mendoza", -32.8895, -68.8458),
    "misiones": ("Posadas", -27.3671, -55.8961),
    "neuquen": ("Neuquén", -38.9516, -68.0591),
    "rio negro": ("Viedma", -40.8135, -62.9967),
    "salta": ("Salta", -24.7821, -65.4232),
    "san juan": ("San Juan", -31.5375, -68.5364),
    "san luis": ("San Luis", -33.3017, -66.3378),
    "santa cruz": ("Río Gallegos", -51.6230, -69.2168),
    "santa fe": ("Santa Fe", -31.6333, -60.7000),
    "santiago del estero": ("Santiago del Estero", -27.7824, -64.2642),
    "tierra del fuego": ("Ushuaia", -54.8019, -68.3030),
    "tierra del fuego antartida e islas del atlantico sur": (
        "Ushuaia",
        -54.8019,
        -68.3030,
    ),
    "tucuman": ("San Miguel de Tucumán", -26.8083, -65.2176),
}

# Canonical province keys used when returning all-province payloads.
# Prefer the long CABA name for display consistency with the map.
_ALL_PROVINCE_KEYS: tuple[str, ...] = (
    "ciudad autonoma de buenos aires",
    "buenos aires",
    "catamarca",
    "chaco",
    "chubut",
    "cordoba",
    "corrientes",
    "entre rios",
    "formosa",
    "jujuy",
    "la pampa",
    "la rioja",
    "mendoza",
    "misiones",
    "neuquen",
    "rio negro",
    "salta",
    "san juan",
    "san luis",
    "santa cruz",
    "santa fe",
    "santiago del estero",
    "tierra del fuego",
    "tucuman",
)

_DISPLAY_NAME: dict[str, str] = {
    "ciudad autonoma de buenos aires": "CABA",
    "buenos aires": "Buenos Aires",
    "catamarca": "Catamarca",
    "chaco": "Chaco",
    "chubut": "Chubut",
    "cordoba": "Córdoba",
    "corrientes": "Corrientes",
    "entre rios": "Entre Ríos",
    "formosa": "Formosa",
    "jujuy": "Jujuy",
    "la pampa": "La Pampa",
    "la rioja": "La Rioja",
    "mendoza": "Mendoza",
    "misiones": "Misiones",
    "neuquen": "Neuquén",
    "rio negro": "Río Negro",
    "salta": "Salta",
    "san juan": "San Juan",
    "san luis": "San Luis",
    "santa cruz": "Santa Cruz",
    "santa fe": "Santa Fe",
    "santiago del estero": "Santiago del Estero",
    "tierra del fuego": "Tierra del Fuego",
    "tucuman": "Tucumán",
}


def normalize_province(name: str) -> str:
    text = unicodedata.normalize("NFD", name or "")
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(text.lower().replace(",", " ").split())


def resolve_province(name: str) -> tuple[str, str, float, float] | None:
    """Return (key, display_name, lat, lon) or None."""
    key = normalize_province(name)
    if key in _PROVINCE_CAPITALS:
        _capital, lat, lon = _PROVINCE_CAPITALS[key]
        display = _DISPLAY_NAME.get(key) or name.strip()
        # Collapse CABA aliases onto the canonical key.
        if key in ("caba", "capital federal"):
            key = "ciudad autonoma de buenos aires"
            display = "CABA"
        return key, display, lat, lon
    for candidate, (capital, lat, lon) in _PROVINCE_CAPITALS.items():
        if key in candidate or candidate in key:
            display = _DISPLAY_NAME.get(candidate) or capital
            canon = (
                "ciudad autonoma de buenos aires"
                if candidate in ("caba", "capital federal")
                else candidate
            )
            if canon in ("caba", "capital federal"):
                canon = "ciudad autonoma de buenos aires"
            return canon, _DISPLAY_NAME.get(canon, display), lat, lon
    return None


def all_province_capitals() -> list[tuple[str, str, float, float]]:
    """(key, display_name, lat, lon) for the 24 jurisdictions."""
    out: list[tuple[str, str, float, float]] = []
    for key in _ALL_PROVINCE_KEYS:
        capital, lat, lon = _PROVINCE_CAPITALS[key]
        display = _DISPLAY_NAME.get(key, capital)
        out.append((key, display, lat, lon))
    return out
