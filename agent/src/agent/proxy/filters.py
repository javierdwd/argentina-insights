"""Deterministic filtering, normalization and projection over cached payloads.

Everything here is pure: it takes an upstream list plus the params the LLM
supplied and returns a smaller/simpler list.  No HTTP, no model calls.  This
is where the complexity of "which rows, which fields, which votes" lives, so
neither the prompt nor the tool has to reason about it.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from .routes import ActasFamily, RosterFamily

# Hard cap on returned rows for a date-filtered series, with even decimation
# past it — a year of daily FX data is fine, ten years is not.
MAX_SERIES_POINTS = 400

_TRUE_TOKENS = {"true", "1", "si", "sí", "yes"}
_SPLIT = re.compile(r"[^\w]+", re.UNICODE)

EXACT_LIST_CAP = 20


def is_true(value: Any) -> bool:
    """Parse a boolean-ish param value coming from the model."""
    return str(value).strip().lower() in _TRUE_TOKENS


def normalize(text: str) -> str:
    """Lowercase + strip accents, for loose matching on Spanish text."""
    decomposed = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _dig(row: dict, path: tuple[str, ...]) -> Any:
    """Read a nested value by key path, tolerating missing/non-dict levels."""
    current: Any = row
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


# ── Row filters ───────────────────────────────────────────────────────────────


def filter_by_date(
    rows: list[dict],
    desde: str | None,
    hasta: str | None,
    *,
    max_points: int = MAX_SERIES_POINTS,
) -> list[dict]:
    """Keep rows whose ``fecha`` falls in [desde, hasta], then downsample.

    Bounds are ISO ``YYYY-MM-DD``; comparison is lexicographic, which is
    correct for ISO dates even when the row carries a full timestamp.
    """
    filtered = []
    for row in rows:
        fecha = str(row.get("fecha", ""))
        if desde and fecha[:10] < desde:
            continue
        if hasta and fecha[:10] > hasta:
            continue
        filtered.append(row)

    if len(filtered) > max_points:
        step = len(filtered) / max_points
        filtered = [filtered[int(i * step)] for i in range(max_points)]

    return filtered


def words(text: str) -> list[str]:
    """Alphanumeric tokens after accent-folding. Language-agnostic."""
    return [part for part in _SPLIT.split(normalize(text)) if part]


def _blob(row: dict, fields: tuple[str, ...]) -> str:
    return " ".join(str(row.get(f) or "") for f in fields)


def filter_by_text(rows: list[dict], needle: str, fields: tuple[str, ...]) -> list[dict]:
    """Keep rows where *fields* match *needle* (accent/case-insensitive).

    A row matches if the folded needle is a substring of the joined fields,
    or every needle word appears as a whole word in them.
    """
    tokens = words(needle)
    if not tokens:
        return rows
    target = " ".join(tokens)
    matched = []
    for row in rows:
        blob_words = words(_blob(row, fields))
        blob = " ".join(blob_words)
        if target in blob or all(tok in blob_words for tok in tokens):
            matched.append(row)
    return matched


def filter_active(rows: list[dict], family: RosterFamily, today: str) -> list[dict]:
    """Keep legislators whose term has not ended.

    The roster endpoints are historical (Senado goes back to the 1940s), so
    without this a province lookup returns every senator who ever held the
    seat.  A missing end date means "still serving".
    """
    kept = []
    for row in rows:
        end: Any = None
        for path in family.term_end_paths:
            end = _dig(row, path)
            if end:
                break
        if not end or str(end)[:10] >= today:
            kept.append(row)
    return kept


# ── Votes ─────────────────────────────────────────────────────────────────────


def normalize_votes(row: dict, family: ActasFamily) -> dict:
    """Rewrite an acta's ``votos[]`` entries into one shape across chambers.

    Senado gives ``{nombre, voto: si|no|…, banca}`` and Diputados
    ``{diputado, tipoVoto: afirmativo|negativo|…, imagen}``.  Both come out
    as ``{nombre, voto: afirmativo|negativo|abstencion|ausente, …}`` so a
    single List/PersonCard config works for either chamber.
    """
    votes = row.get(family.votes_field)
    if not isinstance(votes, list):
        return row

    raw_to_canonical = family.raw_to_canonical
    normalized = []
    for vote in votes:
        if not isinstance(vote, dict):
            continue
        raw = str(vote.get(family.vote_key, "")).strip().lower()
        entry = {
            "nombre": vote.get(family.voter_key),
            "voto": raw_to_canonical.get(raw, raw),
        }
        for key, value in vote.items():
            if key not in (family.voter_key, family.vote_key):
                entry[key] = value
        normalized.append(entry)

    return {**row, family.votes_field: normalized}


def filter_votes(row: dict, family: ActasFamily, vote: str) -> dict:
    """Keep only ``votos[]`` entries matching the canonical *vote* value."""
    votes = row.get(family.votes_field)
    if not isinstance(votes, list):
        return row

    target = normalize(vote)
    kept = [v for v in votes if isinstance(v, dict) and normalize(v.get("voto") or "") == target]
    return {**row, family.votes_field: kept}


def summarize_votes(row: dict, family: ActasFamily) -> dict:
    """Replace ``votos[]`` with a one-line note about how to get it.

    The array is one entry per legislator (~70 Senado / ~257 Diputados) and
    is the dominant byte cost of an acta (~175 KB observed).  The aggregate
    counts stay as top-level ints either way, so a plain "show me the actas"
    keeps everything that matters.
    """
    votes = row.get(family.votes_field)
    if not isinstance(votes, list) or not votes:
        return row
    return {
        **row,
        family.votes_field: (
            f"[{len(votes)} individual votes omitted — fetch "
            f"{family.detail_path} for this acta, or pass includeVotes=true / "
            "vote=<afirmativo|negativo|abstencion|ausente> here]"
        ),
    }


# ── Projection ────────────────────────────────────────────────────────────────


def project(rows: list[dict], fields: list[str]) -> list[dict]:
    """Keep only *fields* on each row, in the order the caller asked for.

    Pure projection with no domain knowledge: the model names the fields it
    wants (it can see them in the catalog hints and in earlier results), and
    this strips the rest.  Unknown field names are simply absent from the
    output rather than raising, so a near-miss still returns usable rows.
    """
    return [{f: row[f] for f in fields if f in row} for row in rows]


def cap(rows: list[dict], limit: int) -> list[dict]:
    """Keep the most recent *limit* rows (upstream lists are chronological)."""
    return rows[-limit:] if len(rows) > limit else rows
