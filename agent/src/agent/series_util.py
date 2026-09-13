"""Shared series/axis helpers for graph compose and derived datasets."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata

_PERIOD_NAME_KEYS = ("nombre", "label", "presidente", "name", "periodo")
_PERIOD_START_KEYS = ("inicio", "start", "desde", "fecha_inicio")
_PERIOD_END_KEYS = ("fin", "end", "hasta", "fecha_fin")
_PERSON_NAME_KEYS = {
    "nombre",
    "presidente",
    "name",
    "persona",
    "diputado",
    "senador",
    "legislador",
}
_PROVINCE_NAME_KEYS = {"provincia", "province"}
_SERIES_VALUE_KEYS = (
    "venta",
    "valor",
    "compra",
    "value",
    "precio",
    "monto",
    "tasa",
    "indice",
    "cantidad",
    "y",
)
_SERIES_X_HINTS = (
    "fecha",
    "date",
    "periodo",
    "mes",
    "anio",
    "año",
    "timestamp",
    "x",
    "label",
    "categoria",
    "categoría",
    "casa",
    "entidad",
    "provincia",
    "nombre",
)
_SERIES_SKIP_KEYS = {
    "id",
    "uuid",
    "foto",
    "imagen",
    "url",
    "email",
    "telefono",
    "redes",
    "votos",
    "params",
}


def _iso_day(value: object) -> str | None:
    if not value:
        return None
    text = str(value)[:10]
    return text if len(text) >= 10 and text[0].isdigit() else None

def _dataset_date_range(rows: list) -> str | None:
    """Span of ISO days in the rows, from ``fecha`` or term ``inicio``/``fin``."""
    days: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in ("fecha", "inicio", "fin"):
            day = _iso_day(row.get(key))
            if day:
                days.append(day)
    if not days:
        return None
    lo, hi = min(days), max(days)
    return lo if lo == hi else f"{lo}..{hi}"

def _dataset_id(path: str, params: dict) -> str:
    key_str = f"{path}:{json.dumps(params, sort_keys=True)}"
    return "ds_" + hashlib.md5(key_str.encode()).hexdigest()[:8]


_VALUES_BLOCK_RE = re.compile(
    r"\[\[values\]\]\s*(.*?)\s*\[\[/values\]\]",
    re.IGNORECASE | re.DOTALL,
)


def _first_key(keys: list[str], candidates: tuple[str, ...]) -> str | None:
    keyset = set(keys)
    for candidate in candidates:
        if candidate in keyset:
            return candidate
    return None

def _slug_series_key(label: str, used: set[str]) -> str:
    folded = unicodedata.normalize("NFKD", label)
    folded = "".join(c for c in folded if not unicodedata.combining(c)).casefold()
    base = re.sub(r"[^a-z0-9]+", "_", folded).strip("_") or "serie"
    base = base[:40]
    key = base
    n = 2
    while key in used:
        key = f"{base}_{n}"
        n += 1
    used.add(key)
    return key

def _looks_numeric(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if not text or _iso_day(text):
            return False
        try:
            float(text)
            return True
        except ValueError:
            return False
    return False

def _looks_temporal(value: object) -> bool:
    return _iso_day(value) is not None

def _column_role(key: str, samples: list[object]) -> str:
    """Classify a column as temporal | numeric | categorical | skip."""
    lowered = key.casefold()
    if lowered in _SERIES_SKIP_KEYS or lowered.endswith("_id"):
        return "skip"
    non_null = [v for v in samples if v is not None and v != ""]
    if not non_null:
        return "skip"
    if any(isinstance(v, (dict, list)) for v in non_null):
        return "skip"
    n = len(non_null)
    temporal_n = sum(1 for v in non_null if _looks_temporal(v))
    numeric_n = sum(1 for v in non_null if _looks_numeric(v))
    if temporal_n / n >= 0.7:
        return "temporal"
    if numeric_n / n >= 0.7:
        return "numeric"
    return "categorical"

def _sample_column_values(ds: dict, key: str, limit: int = 40) -> list[object]:
    out: list[object] = []
    for row in ds.get("rows") or []:
        if not isinstance(row, dict):
            continue
        if key not in row:
            continue
        out.append(row.get(key))
        if len(out) >= limit:
            break
    return out

def _normalize_axis_value(value: object, role: str) -> str | None:
    if role == "temporal":
        return _iso_day(value) or (str(value).strip()[:10] if value else None)
    if value is None or value == "":
        return None
    text = str(value).strip()
    return text or None

def _measure_axes(ds: dict) -> dict | None:
    """Detect shared-axis candidates + one numeric Y for a measure dataset.

    Uses row samples (not hard-coded ``fecha``): temporal X preferred, then
    categorical X; Y prefers known measure names among numeric columns.
    """
    if str(ds.get("path") or "").startswith("derived/"):
        return None
    if (ds.get("N") or 0) < 2:
        return None
    keys = [str(k) for k in (ds.get("keys") or [])]
    if len(keys) < 2:
        return None
    # Period tables (name + inicio/fin) are not measure series.
    if _first_key(keys, _PERIOD_NAME_KEYS) and _first_key(keys, _PERIOD_START_KEYS):
        return None

    roles: dict[str, str] = {
        key: _column_role(key, _sample_column_values(ds, key)) for key in keys
    }
    temporal = [k for k, r in roles.items() if r == "temporal"]
    categorical = [k for k, r in roles.items() if r == "categorical"]
    numeric = [k for k, r in roles.items() if r == "numeric"]
    if not numeric:
        return None

    y_key = _first_key(numeric, _SERIES_VALUE_KEYS) or numeric[0]
    x_ranked: list[tuple[int, str]] = []
    for key in temporal:
        # Prefer well-known timeline names, then any temporal column.
        hint = 0 if key.casefold() in {h.casefold() for h in _SERIES_X_HINTS} else 1
        x_ranked.append((hint, key))
    for key in categorical:
        if key == y_key:
            continue
        hint = 0 if key.casefold() in {h.casefold() for h in _SERIES_X_HINTS} else 2
        x_ranked.append((hint + 10, key))  # temporal always beats categorical
    if not x_ranked:
        return None
    x_ranked.sort()
    x_candidates = [key for _score, key in x_ranked]
    return {
        "ds": ds,
        "x_candidates": x_candidates,
        "x_roles": {k: roles[k] for k in x_candidates},
        "y_key": y_key,
    }


def _series_label_for_dataset(ds: dict) -> str:
    """Human label for a measure dataset (casa, path tail, or path)."""
    params = ds.get("params") or {}
    for key in ("casa", "entidad", "indice", "label", "name"):
        val = params.get(key)
        if val:
            return str(val)
    path = str(ds.get("path") or "")
    tail = path.rstrip("/").split("/")[-1]
    return tail or path or "serie"

