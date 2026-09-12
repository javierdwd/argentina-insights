"""Match legislator names with the fast model (id + display name)."""

from __future__ import annotations

from .match import match_directory
from .routes import RosterFamily


def _label(row: dict, fields: tuple[str, ...]) -> str:
    return " ".join(str(row.get(f) or "").strip() for f in fields if row.get(f)).strip()


async def match_roster(
    rows: list[dict],
    needles: list[str],
    family: RosterFamily,
) -> list[dict]:
    """Keep roster *rows* whose names the fast model maps to *needles*."""
    by_id: dict[str, dict] = {}
    lines: list[str] = []
    for row in rows:
        rid = str(row.get(family.id_field) or "").strip()
        nombre = _label(row, family.name_fields)
        if not rid or not nombre:
            continue
        by_id[rid] = row
        lines.append(f"{rid}\t{nombre}")

    return await match_directory(
        kind=f"roster-{family.chamber}",
        lines=lines,
        queries=needles,
        by_id=by_id,
    )
