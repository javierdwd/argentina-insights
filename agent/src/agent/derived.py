"""Deterministic derived datasets for compose (values, overlays, spreads)."""

from __future__ import annotations

import re

from .series_util import (
    _PERIOD_END_KEYS,
    _PERIOD_NAME_KEYS,
    _PERIOD_START_KEYS,
    _PERSON_NAME_KEYS,
    _PROVINCE_NAME_KEYS,
    _SERIES_VALUE_KEYS,
    _SERIES_X_HINTS,
    _dataset_date_range,
    _dataset_id,
    _first_key,
    _iso_day,
    _measure_axes,
    _normalize_axis_value,
    _series_label_for_dataset,
    _slug_series_key,
)

_VALUES_BLOCK_RE = re.compile(
    r"\[\[values\]\](.*?)\[\[/values\]\]",
    re.IGNORECASE | re.DOTALL,
)

def _parse_values_table(note: str) -> list[dict]:
    """Parse the analyst ``[[values]]`` block into bar-ready rows.

    Expected lines: ``label | value | unit`` (header optional). Rows with a
    non-numeric value are skipped. This is the generic bridge from respond
    aggregates → a Chart kind=bar dataset (not domain-specific).
    """
    if not note:
        return []
    match = _VALUES_BLOCK_RE.search(note)
    if not match:
        return []

    rows: list[dict] = []
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or set(line) <= {"-", "|", " "}:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            continue
        label, raw_value = parts[0], parts[1]
        unit = parts[2] if len(parts) > 2 else ""
        if label.lower() in {"label", "nombre", "presidente"}:
            continue
        try:
            value = float(raw_value.replace(",", "").replace(" ", ""))
        except ValueError:
            continue
        # Fake placeholder for "no coverage" — respond should omit these; if it
        # still emits 0, drop it so the bar chart is not skewed.
        if value == 0:
            continue
        row: dict = {"label": label, "value": value}
        if unit:
            row["unit"] = unit
        rows.append(row)
    return rows

def _values_dataset_from_note(note: str) -> dict | None:
    """Materialize ``[[values]]`` as a small categorical dataset for bind_data."""
    rows = _parse_values_table(note)
    if not rows:
        return None
    path = "derived/values"
    params = {"n": len(rows)}
    ds_id = _dataset_id(path, params)
    keys = list(rows[0].keys())
    return {
        "id": ds_id,
        "path": path,
        "params": params,
        "rows": rows,
        "keys": keys,
        "N": len(rows),
        "date_range": None,
    }


def _find_period_and_series(
    datasets: dict,
) -> tuple[dict, dict, str, str, str | None, str] | None:
    """Locate a period table + dated measure series for period joins.

    Returns (period_ds, series_ds, name_key, start_key, end_key, value_key)
    or None. Same pairing used for evolution overlays and level aggregates.
    """
    period_ds = None
    for ds in datasets.values():
        if str(ds.get("path") or "").startswith("derived/"):
            continue
        keys = list(ds.get("keys") or [])
        if not _first_key(keys, _PERIOD_NAME_KEYS):
            continue
        if not _first_key(keys, _PERIOD_START_KEYS):
            continue
        if (ds.get("N") or 0) < 1:
            continue
        period_ds = ds
        break
    if not period_ds:
        return None

    series_candidates = []
    for ds in datasets.values():
        if str(ds.get("path") or "").startswith("derived/"):
            continue
        if ds is period_ds:
            continue
        keys = list(ds.get("keys") or [])
        if "fecha" not in keys:
            continue
        if not _first_key(keys, _SERIES_VALUE_KEYS):
            continue
        if (ds.get("N") or 0) < 2:
            continue
        series_candidates.append(ds)
    if not series_candidates:
        return None

    series_candidates.sort(
        key=lambda ds: (
            0 if "/dolares/" in str(ds.get("path") or "") else 1,
            -(ds.get("N") or 0),
        )
    )
    series_ds = series_candidates[0]
    pkeys = list(period_ds.get("keys") or [])
    skeys = list(series_ds.get("keys") or [])
    name_key = _first_key(pkeys, _PERIOD_NAME_KEYS)
    start_key = _first_key(pkeys, _PERIOD_START_KEYS)
    end_key = _first_key(pkeys, _PERIOD_END_KEYS)
    value_key = _first_key(skeys, _SERIES_VALUE_KEYS)
    if not name_key or not start_key or not value_key:
        return None
    return period_ds, series_ds, name_key, start_key, end_key, value_key

def _category_entity(name_key: str) -> str | None:
    """Generic axis kind from the period table's name column — not president-only."""
    key = name_key.strip().casefold()
    if key in _PERSON_NAME_KEYS:
        return "persona"
    if key in _PROVINCE_NAME_KEYS:
        return "provincia"
    return None

def _period_row_extras(term: dict, skip: set[str]) -> dict:
    extras: dict = {}
    for key, raw in term.items():
        if key in skip:
            continue
        if raw is None or raw == "":
            continue
        if isinstance(raw, bool):
            extras[key] = raw
            continue
        if isinstance(raw, (int, float, str)):
            extras[key] = raw
    return extras

def _iter_intersecting_periods(
    period_ds: dict,
    name_key: str,
    start_key: str,
    end_key: str | None,
    series_lo: str,
    series_hi: str,
) -> list[tuple[str, str, str, dict]]:
    """(label, start, end, term) for periods that intersect [series_lo, series_hi]."""
    out: list[tuple[str, str, str, dict]] = []
    for term in period_ds.get("rows") or []:
        if not isinstance(term, dict):
            continue
        label = str(term.get(name_key) or "").strip()
        start = _iso_day(term.get(start_key))
        if not label or not start:
            continue
        end = _iso_day(term.get(end_key)) if end_key else None
        end = end or "9999-12-31"
        if end < start:
            continue
        if end < series_lo or start > series_hi:
            continue
        out.append((label, start, end, term))
    return out

def _period_overlay_from_datasets(datasets: dict) -> dict | None:
    """Wide overlay: fecha + one column per period (null outside each window).

    Generic join when both shapes exist:
      - periods: name + inicio (+ optional fin)
      - series: fecha + numeric measure
    Used for "evolution during each period" on one shared time axis.
    """
    pair = _find_period_and_series(datasets)
    if not pair:
        return None
    period_ds, series_ds, name_key, start_key, end_key, value_key = pair

    series_rows = [
        r for r in (series_ds.get("rows") or [])
        if isinstance(r, dict) and _iso_day(r.get("fecha"))
    ]
    series_rows.sort(key=lambda r: _iso_day(r.get("fecha")) or "")
    if len(series_rows) < 2:
        return None

    series_lo = _iso_day(series_rows[0].get("fecha")) or ""
    series_hi = _iso_day(series_rows[-1].get("fecha")) or ""
    if not series_lo or not series_hi:
        return None

    raw_periods = _iter_intersecting_periods(
        period_ds, name_key, start_key, end_key, series_lo, series_hi
    )
    if not raw_periods:
        return None

    used_keys: set[str] = {"fecha"}
    periods: list[tuple[str, str, str, str]] = []  # label, slug, start, end
    for label, start, end, _term in raw_periods:
        slug = _slug_series_key(label, used_keys)
        periods.append((label, slug, start, end))

    # Clip X to the union of kept periods ∩ series span; downsample if huge.
    min_start = max(min(p[2] for p in periods), series_lo)
    max_end = min(max(p[3] for p in periods), series_hi)
    filtered = []
    for row in series_rows:
        fecha = _iso_day(row.get("fecha")) or ""
        if fecha < min_start or fecha > max_end:
            continue
        filtered.append(row)
    if len(filtered) > 400:
        step = len(filtered) / 400
        filtered = [filtered[int(i * step)] for i in range(400)]
    if len(filtered) < 2:
        return None

    wide: list[dict] = []
    hits: dict[str, int] = {slug: 0 for _l, slug, _s, _e in periods}
    for row in filtered:
        fecha = _iso_day(row.get("fecha")) or ""
        try:
            raw = float(row.get(value_key))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        out: dict = {"fecha": fecha}
        for _label, slug, start, end in periods:
            if start <= fecha <= end:
                out[slug] = raw
                hits[slug] += 1
            else:
                out[slug] = None
        wide.append(out)

    # Drop period columns that never got a point (edge intersection only).
    periods = [p for p in periods if hits.get(p[1], 0) > 0]
    if not periods:
        return None
    keep = {"fecha", *[slug for _l, slug, _s, _e in periods]}
    wide = [{k: v for k, v in row.items() if k in keep} for row in wide]

    path = "derived/period_overlay"
    params = {
        "series": series_ds["id"],
        "periods": period_ds["id"],
        "value": value_key,
        "n_periods": len(periods),
        "series_span": f"{series_lo}..{series_hi}",
    }
    ds_id = _dataset_id(path, params)
    keys = ["fecha", *[slug for _l, slug, _s, _e in periods]]
    label_map = {slug: label for label, slug, _s, _e in periods}
    return {
        "id": ds_id,
        "path": path,
        "params": {**params, "labels": label_map},
        "rows": wide,
        "keys": keys,
        "N": len(wide),
        "date_range": _dataset_date_range(wide),
    }

def _period_levels_from_datasets(datasets: dict) -> dict | None:
    """One row per period: aggregate of the measure inside that window.

    Same period+series pairing as ``derived/period_overlay``, but shaped like
    ``derived/values`` (label / value / sublabel) so PeriodBars and bar Charts
    bind without inventing column names.

    Aggregation:
      - FX-like / flow series → **max** (peak in the mandate)
      - stock series (BCRA reservas/depósitos, EMAE, …) → **last** value in
        the window, with optional ``delta`` (end − start) on the row
    """
    pair = _find_period_and_series(datasets)
    if not pair:
        return None
    period_ds, series_ds, name_key, start_key, end_key, value_key = pair

    series_rows = [
        r for r in (series_ds.get("rows") or [])
        if isinstance(r, dict) and _iso_day(r.get("fecha"))
    ]
    series_rows.sort(key=lambda r: _iso_day(r.get("fecha")) or "")
    if len(series_rows) < 2:
        return None

    series_lo = _iso_day(series_rows[0].get("fecha")) or ""
    series_hi = _iso_day(series_rows[-1].get("fecha")) or ""
    if not series_lo or not series_hi:
        return None

    periods = _iter_intersecting_periods(
        period_ds, name_key, start_key, end_key, series_lo, series_hi
    )
    if not periods:
        return None

    op = _period_aggregate_op(series_ds)

    # Pre-parse measure points once.
    points: list[tuple[str, float]] = []
    for row in series_rows:
        fecha = _iso_day(row.get("fecha")) or ""
        try:
            points.append((fecha, float(row.get(value_key))))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
    if len(points) < 2:
        return None

    skip = {name_key, start_key, "label", "value", "sublabel", "delta", "entity"}
    if end_key:
        skip.add(end_key)
    entity = _category_entity(name_key)

    rows: list[dict] = []
    for label, start, end, term in periods:
        window = [(fecha, v) for fecha, v in points if start <= fecha <= end]
        if not window:
            continue
        values = [v for _f, v in window]
        end_label = "hoy" if end >= "9999-01-01" else end
        extras = _period_row_extras(term, skip)
        if op == "last":
            value = window[-1][1]
            delta = window[-1][1] - window[0][1]
            row = {
                "label": label,
                "value": value,
                "delta": delta,
                "sublabel": f"{start} → {end_label}",
                **extras,
            }
        else:
            row = {
                "label": label,
                "value": max(values),
                "sublabel": f"{start} → {end_label}",
                **extras,
            }
        if entity:
            row["entity"] = entity
        rows.append(row)
    if len(rows) < 2:
        return None

    path = "derived/period_levels"
    params = {
        "series": series_ds["id"],
        "periods": period_ds["id"],
        "value": value_key,
        "op": op,
        "n_periods": len(rows),
    }
    if entity:
        params["entity"] = entity
    ds_id = _dataset_id(path, params)
    core = ["label", "value", "delta", "sublabel"] if op == "last" else [
        "label",
        "value",
        "sublabel",
    ]
    extra_keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in core and key not in extra_keys:
                extra_keys.append(key)
    keys = [*core, *extra_keys]
    return {
        "id": ds_id,
        "path": path,
        "params": params,
        "rows": rows,
        "keys": keys,
        "N": len(rows),
        "date_range": None,
    }

def _period_aggregate_op(series_ds: dict) -> str:
    """Choose max (FX peaks) vs last (stocks) for period_levels."""
    params = series_ds.get("params") or {}
    if isinstance(params, dict) and params.get("kind") == "stock":
        return "last"
    path = str(series_ds.get("path") or "")
    # BCRA curated stocks + Series aliases marked stock in the row sample.
    if path.startswith("/v1/bcra/") and path != "/v1/bcra/variables":
        alias = path.rsplit("/", 1)[-1]
        if alias != "tasa_depositos_30d":
            return "last"
    if path.startswith("/v1/series/") and "search" not in path:
        rows = series_ds.get("rows") or []
        if rows and isinstance(rows[0], dict) and rows[0].get("kind") == "stock":
            return "last"
        # Curated stock aliases even if kind was projected away.
        alias = path.rsplit("/", 1)[-1]
        if alias in {
            "emae",
            "desempleo",
            "pobreza",
            "ripte",
            "ipc",
        }:
            return "last"
    rows = series_ds.get("rows") or []
    if rows and isinstance(rows[0], dict) and rows[0].get("kind") == "stock":
        return "last"
    return "max"


def _pick_shared_x(axes_list: list[dict]) -> tuple[str, str] | None:
    """Choose one X key shared by ≥2 measure datasets (same role).

    Prefers temporal axes, then hint-named categoricals, then any shared
    categorical. Categorical X needs ≥2 identical values; temporal X only
    needs overlapping date *ranges* (daily FX vs monthly inflación rarely
    share exact calendar days).
    """
    if len(axes_list) < 2:
        return None

    # key -> list of axes that offer it, with role
    by_key: dict[str, list[dict]] = {}
    for axes in axes_list:
        for key in axes["x_candidates"]:
            by_key.setdefault(key, []).append(axes)

    scored: list[tuple[int, int, int, int, str, str]] = []
    for key, group in by_key.items():
        if len(group) < 2:
            continue
        roles = {axes["x_roles"].get(key) for axes in group}
        roles.discard(None)
        if len(roles) != 1:
            continue
        role = next(iter(roles))
        if role is None:
            continue
        value_sets: list[set[str]] = []
        for axes in group:
            vals: set[str] = set()
            for row in axes["ds"].get("rows") or []:
                if not isinstance(row, dict):
                    continue
                norm = _normalize_axis_value(row.get(key), role)
                if norm:
                    vals.add(norm)
            value_sets.append(vals)
        if not value_sets or any(len(v) < 2 for v in value_sets):
            continue

        if role == "temporal":
            ranges = [(min(vals), max(vals)) for vals in value_sets]
            lo = max(r[0] for r in ranges)
            hi = min(r[1] for r in ranges)
            if lo > hi:
                continue
            # Points that fall inside the overlapping window (any series).
            in_window = sum(
                1 for vals in value_sets for v in vals if lo <= v <= hi
            )
            if in_window < 2:
                continue
            overlap_score = in_window
        else:
            shared = set.intersection(*value_sets)
            if len(shared) < 2:
                continue
            overlap_score = len(shared)

        role_rank = 0 if role == "temporal" else 1
        hint_rank = (
            0 if key.casefold() in {h.casefold() for h in _SERIES_X_HINTS} else 1
        )
        # Prefer temporal + hint names; then more sources / overlap.
        scored.append(
            (role_rank, hint_rank, -len(group), -overlap_score, key, role)
        )

    if not scored:
        return None
    scored.sort()
    _rr, _hr, _ng, _ns, key, role = scored[0]
    return key, role

def _downsample_wide_prefer_filled(
    rows: list[dict],
    measure_keys: list[str],
    max_points: int,
) -> list[dict]:
    """Even buckets; pick the row with most non-null measures in each bucket.

    Outer-joins (e.g. blue daily + riesgo sparsér) leave many one-sided rows.
    Stride sampling would drop the sparser series; preferring filled rows keeps
    both lines continuous after connectNulls on the Chart.
    """
    if len(rows) <= max_points or max_points < 2:
        return rows
    n = len(rows)
    out: list[dict] = []
    for i in range(max_points):
        start = int(i * n / max_points)
        end = max(start + 1, int((i + 1) * n / max_points))
        chunk = rows[start:end]
        best = max(
            chunk,
            key=lambda r: sum(
                1 for k in measure_keys if r.get(k) is not None and r.get(k) != ""
            ),
        )
        if not out or out[-1] is not best:
            out.append(best)
    return out

def _ffill_sparse_measure_columns(
    rows: list[dict],
    measure_keys: list[str],
) -> list[dict]:
    """Carry sparse measures across denser X (monthly inflación onto daily blue).

    Only columns with non-null density below 35% are filled — dense FX series
    stay untouched. Forward fill, then backfill leading gaps.
    """
    if not rows or not measure_keys:
        return rows
    n = len(rows)
    sparse: list[str] = []
    for key in measure_keys:
        filled = sum(
            1 for r in rows if r.get(key) is not None and r.get(key) != ""
        )
        if 0 < filled < n * 0.35:
            sparse.append(key)
    if not sparse:
        return rows

    out = [dict(r) for r in rows]
    for key in sparse:
        last = None
        for row in out:
            value = row.get(key)
            if value is not None and value != "":
                last = value
            elif last is not None:
                row[key] = last
        first = next(
            (
                row.get(key)
                for row in out
                if row.get(key) is not None and row.get(key) != ""
            ),
            None,
        )
        if first is None:
            continue
        for row in out:
            value = row.get(key)
            if value is not None and value != "":
                break
            row[key] = first
    return out

def _series_overlay_from_datasets(datasets: dict) -> dict | None:
    """Wide join of 2+ measure series that share the same X axis.

    X/Y are inferred from row samples (temporal / categorical / numeric), so
    overlays work for fecha+valor, mes+tasa, provincia+cantidad, etc. Compose
    needs ONE Chart — this builds ``derived/series_overlay`` with the shared
    X column + one measure column per source.
    """
    axes_list = [
        axes
        for ds in datasets.values()
        if (axes := _measure_axes(ds)) is not None
    ]
    picked = _pick_shared_x(axes_list)
    if not picked:
        return None
    x_key, x_role = picked

    sources = [axes for axes in axes_list if x_key in axes["x_candidates"]]
    if len(sources) < 2:
        return None

    # Stable order: FX paths first, then others by path.
    sources.sort(
        key=lambda axes: (
            0 if "dolares" in str(axes["ds"].get("path") or "") else 1,
            str(axes["ds"].get("path") or ""),
        )
    )

    used_keys: set[str] = {x_key}
    columns: list[tuple[str, str, str, dict]] = []  # label, slug, value_key, ds
    for axes in sources:
        ds = axes["ds"]
        value_key = axes["y_key"]
        label = _series_label_for_dataset(ds)
        slug = _slug_series_key(label, used_keys)
        columns.append((label, slug, value_key, ds))
    if len(columns) < 2:
        return None

    # Outer-join on normalized X.
    by_x_value: dict[str, dict] = {}
    for label, slug, value_key, ds in columns:
        for row in ds.get("rows") or []:
            if not isinstance(row, dict):
                continue
            x_val = _normalize_axis_value(row.get(x_key), x_role)
            if not x_val:
                continue
            wide = by_x_value.setdefault(x_val, {x_key: x_val})
            raw = row.get(value_key)
            try:
                wide[slug] = float(raw) if raw is not None and raw != "" else None
            except (TypeError, ValueError):
                wide[slug] = None

    ordered = sorted(by_x_value.keys())
    wide_rows = [by_x_value[k] for k in ordered]
    if len(wide_rows) < 2:
        return None

    measure_keys = [slug for _l, slug, _v, _d in columns]
    if x_role == "temporal":
        wide_rows = _ffill_sparse_measure_columns(wide_rows, measure_keys)
    wide_rows = _downsample_wide_prefer_filled(wide_rows, measure_keys, 400)

    path = "derived/series_overlay"
    labels = {slug: label for label, slug, _vk, _ds in columns}
    params = {
        "x": x_key,
        "x_role": x_role,
        "n_series": len(columns),
        "sources": [str(ds.get("path") or "") for _l, _s, _v, ds in columns],
        "labels": labels,
    }
    ds_id = _dataset_id(path, params)
    keys = [x_key, *[slug for _l, slug, _v, _d in columns]]
    return {
        "id": ds_id,
        "path": path,
        "params": params,
        "rows": wide_rows,
        "keys": keys,
        "N": len(wide_rows),
        "date_range": _dataset_date_range(wide_rows) if x_role == "temporal" else None,
    }

def _fx_casa_label(ds: dict) -> str:
    params = ds.get("params") or {}
    casa = params.get("casa")
    if casa:
        return str(casa).casefold()
    path = str(ds.get("path") or "").rstrip("/")
    return path.split("/")[-1].casefold() or "casa"

def _fx_spread_from_datasets(datasets: dict) -> dict | None:
    """Join two FX house series on fecha → spread ARS + % vs the base house.

    Prefer pairing each non-oficial casa with oficial when both exist; otherwise
    the first two FX measure series. Used for "serie del spread blue vs oficial".
    """
    fx: list[dict] = []
    for ds in datasets.values():
        path = str(ds.get("path") or "")
        if "dolares" not in path or path.startswith("derived/"):
            continue
        axes = _measure_axes(ds)
        if not axes:
            continue
        # Need a temporal X (fecha) and a numeric venta-like Y.
        x_key = next(
            (k for k in axes["x_candidates"] if axes["x_roles"].get(k) == "temporal"),
            None,
        )
        if not x_key:
            continue
        fx.append({**axes, "x_key": x_key, "casa": _fx_casa_label(ds)})
    if len(fx) < 2:
        return None

    # Prefer oficial as the base (denominator / subtractand).
    by_casa = {item["casa"]: item for item in fx}
    pairs: list[tuple[dict, dict]] = []
    if "oficial" in by_casa:
        base = by_casa["oficial"]
        for casa, item in sorted(by_casa.items()):
            if casa == "oficial":
                continue
            pairs.append((item, base))
    else:
        ordered = sorted(fx, key=lambda item: item["casa"])
        pairs.append((ordered[0], ordered[1]))
    if not pairs:
        return None

    # One primary pair for the derived table (first non-oficial vs oficial).
    left, right = pairs[0]
    x_key = left["x_key"]
    if right["x_key"] != x_key:
        return None

    left_by: dict[str, float] = {}
    for row in left["ds"].get("rows") or []:
        if not isinstance(row, dict):
            continue
        x_val = _normalize_axis_value(row.get(x_key), "temporal")
        if not x_val:
            continue
        try:
            left_by[x_val] = float(row.get(left["y_key"]))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
    right_by: dict[str, float] = {}
    for row in right["ds"].get("rows") or []:
        if not isinstance(row, dict):
            continue
        x_val = _normalize_axis_value(row.get(x_key), "temporal")
        if not x_val:
            continue
        try:
            right_by[x_val] = float(row.get(right["y_key"]))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue

    shared = sorted(set(left_by) & set(right_by))
    if len(shared) < 2:
        return None

    wide_rows: list[dict] = []
    for day in shared:
        a = left_by[day]
        b = right_by[day]
        spread = a - b
        pct = (spread / b * 100.0) if b else None
        wide_rows.append(
            {
                x_key: day,
                left["casa"]: a,
                right["casa"]: b,
                "spread": spread,
                "spread_pct": pct,
            }
        )

    max_points = 400
    if len(wide_rows) > max_points:
        step = max(1, len(wide_rows) // max_points)
        wide_rows = wide_rows[::step][:max_points]

    path = "derived/fx_spread"
    params = {
        "x": x_key,
        "a": left["casa"],
        "b": right["casa"],
        "sources": [
            str(left["ds"].get("path") or ""),
            str(right["ds"].get("path") or ""),
        ],
        "labels": {
            "spread": f"Spread {left['casa']} vs {right['casa']} (ARS)",
            "spread_pct": f"Spread {left['casa']} vs {right['casa']} (%)",
            left["casa"]: left["casa"],
            right["casa"]: right["casa"],
        },
    }
    ds_id = _dataset_id(path, params)
    keys = [x_key, left["casa"], right["casa"], "spread", "spread_pct"]
    return {
        "id": ds_id,
        "path": path,
        "params": params,
        "rows": wide_rows,
        "keys": keys,
        "N": len(wide_rows),
        "date_range": _dataset_date_range(wide_rows),
    }

def _derived_datasets_for_compose(note: str, datasets: dict) -> dict:
    """Build bar-ready and/or overlay tables for this turn."""
    out: dict = {}
    values_ds = _values_dataset_from_note(note)
    if values_ds:
        out[values_ds["id"]] = values_ds
    merged = {**datasets, **out}
    series_overlay = _series_overlay_from_datasets(merged)
    if series_overlay:
        out[series_overlay["id"]] = series_overlay
        merged = {**merged, series_overlay["id"]: series_overlay}
    fx_spread = _fx_spread_from_datasets(merged)
    if fx_spread:
        out[fx_spread["id"]] = fx_spread
        merged = {**merged, fx_spread["id"]: fx_spread}
    overlay = _period_overlay_from_datasets(merged)
    if overlay:
        out[overlay["id"]] = overlay
        merged = {**merged, overlay["id"]: overlay}
    levels = _period_levels_from_datasets(merged)
    if levels:
        out[levels["id"]] = levels
    return out

