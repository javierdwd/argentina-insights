"""Historical football data for Argentina via Live Football API.

The public proxy intentionally exposes only two curated entities:
Liga Profesional Argentina and the Argentina men's national team.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
import unicodedata
from datetime import date
from typing import Any

from agent.analytics.football import compute_team_season_stats

from . import upstream
from .upstream import UpstreamError

BASE_URL = "https://live-football-api.com/api/v1"
ARGENTINE_LEAGUE_ID = "581t4mywybx21wcpmpykhyzr3"
ARGENTINA_TEAM_ID = "ak48fkypnql8y4n69cvcq5ghc"
TTL_HISTORICAL = 30 * 24 * 60 * 60
TTL_CURRENT = 6 * 60 * 60
MAX_MATCHES = 500
MAX_STATS_TEAMS = 2
MAX_STATS_SEASONS = 10


class _TokenBucket:
    """Process-wide async-compatible limiter for upstream request starts."""

    def __init__(self, rate: float, capacity: int) -> None:
        self.rate = rate
        self.capacity = float(capacity)
        self._tokens = float(capacity)
        self._updated_at = time.monotonic()
        self._lock = threading.Lock()

    async def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = max(0.0, now - self._updated_at)
                self._tokens = min(
                    self.capacity,
                    self._tokens + elapsed * self.rate,
                )
                self._updated_at = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                wait_seconds = (1 - self._tokens) / self.rate
            await asyncio.sleep(wait_seconds)


# Live Football API contract: 2 req/s sustained, burst 5. The hook is invoked
# only on cache misses by proxy.upstream, so cached reads do not spend tokens.
_RATE_LIMITER = _TokenBucket(rate=2.0, capacity=5)


def _credentials() -> dict[str, Any]:
    key = (os.environ.get("LIVE_FOOTBALL_API_KEY") or "").strip()
    if not key:
        raise UpstreamError(
            "Live Football API credentials missing: set "
            "LIVE_FOOTBALL_API_KEY in the environment."
        )
    return {"api_key": key, "lang": "en"}


async def _get(
    endpoint: str,
    *,
    query: dict[str, Any] | None = None,
    ttl: float = TTL_CURRENT,
    refresh: bool = False,
) -> dict[str, Any]:
    raw = await upstream.get(
        f"/{endpoint}",
        query={**_credentials(), **(query or {})},
        ttl=ttl,
        refresh=refresh,
        base_url=BASE_URL,
        before_fetch=_RATE_LIMITER.acquire,
    )
    if not isinstance(raw, dict):
        raise UpstreamError(
            f"Live Football API returned an invalid {endpoint!r} response."
        )
    if not raw.get("success"):
        raise UpstreamError(
            f"Live Football API {endpoint!r} failed: "
            f"{raw.get('message') or 'unknown error'}"
        )
    data = raw.get("data")
    if not isinstance(data, dict):
        raise UpstreamError(
            f"Live Football API {endpoint!r} response has no data object."
        )
    return data


def _ttl_for_season(season: str | None) -> float:
    if season and not season.startswith(("2025", "2026")):
        return TTL_HISTORICAL
    return TTL_CURRENT


def _score(value: Any) -> int | None:
    try:
        return int(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _normalize_match(
    match: dict[str, Any],
    *,
    week: Any = None,
    perspective_team_id: str | None = None,
) -> dict[str, Any]:
    home = match.get("home") if isinstance(match.get("home"), dict) else {}
    away = match.get("away") if isinstance(match.get("away"), dict) else {}
    league = match.get("league") if isinstance(match.get("league"), dict) else {}
    status = match.get("status")
    status_value = (
        status.get("status") or status.get("display")
        if isinstance(status, dict)
        else status
    )
    home_score = _score(home.get("score"))
    away_score = _score(away.get("score"))
    result = None
    if (
        perspective_team_id
        and home_score is not None
        and away_score is not None
    ):
        own, rival = (
            (home_score, away_score)
            if str(home.get("id")) == perspective_team_id
            else (away_score, home_score)
        )
        result = "won" if own > rival else "drew" if own == rival else "lost"

    date = str(match.get("date") or "")
    return {
        "id": match.get("id"),
        "date": date[:10] or None,
        "time": match.get("kickoff") or (date[11:16] if len(date) >= 16 else None),
        "competition": league.get("name"),
        "competitionId": league.get("id"),
        "week": week or match.get("week") or match.get("round"),
        "homeTeam": home.get("name"),
        "homeTeamId": home.get("id"),
        "homeTeamLogo": home.get("logo"),
        "homeScore": home_score,
        "awayTeam": away.get("name"),
        "awayTeamId": away.get("id"),
        "awayTeamLogo": away.get("logo"),
        "awayScore": away_score,
        "status": status_value,
        "argentinaResult": result,
    }


def _season_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    seasons = data.get("available_seasons")
    if not isinstance(seasons, list):
        return []
    return [{"season": str(season)} for season in seasons]


def _formation(value: Any) -> str | None:
    """Normalize 433 / '4-3-3' into the display-safe '4-3-3' form."""
    if value is None or value == "":
        return None
    digits = [character for character in str(value) if character.isdigit()]
    return "-".join(digits) if 2 <= len(digits) <= 5 else str(value)


def _lineup_person(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or not value.get("name"):
        return None
    return {
        "id": value.get("id"),
        "name": str(value["name"]),
        "photoUrl": value.get("image") or value.get("photo"),
        "number": value.get("number"),
        "position": value.get("position"),
        "rating": value.get("rating"),
    }


async def match_lineup(
    match_id: str,
    *,
    home_team: str | None = None,
    away_team: str | None = None,
    home_team_logo: str | None = None,
    away_team_logo: str | None = None,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    """Return one normalized lineup row per side for a historical match."""
    data = await _get(
        "lineups",
        query={"match_id": match_id},
        ttl=TTL_HISTORICAL,
        refresh=refresh,
    )
    formations = (
        data.get("formation") if isinstance(data.get("formation"), dict) else {}
    )
    rows: list[dict[str, Any]] = []
    for side in ("home", "away"):
        raw_team = data.get(side)
        if not isinstance(raw_team, dict):
            continue
        starting = [
            person
            for value in raw_team.get("starting") or []
            if (person := _lineup_person(value)) is not None
        ]
        substitutes = [
            person
            for value in raw_team.get("subs") or []
            if (person := _lineup_person(value)) is not None
        ]
        rows.append(
            {
                "matchId": data.get("match_id") or match_id,
                "side": side,
                "team": (
                    home_team or "Local"
                    if side == "home"
                    else away_team or "Visitante"
                ),
                "logo": home_team_logo if side == "home" else away_team_logo,
                "formation": _formation(formations.get(side)),
                "isProjected": bool(data.get("is_projected")),
                "starting": starting,
                "substitutes": substitutes,
                "coach": _lineup_person(raw_team.get("coach")),
            }
        )
    return rows


def _filter_by_date(
    rows: list[dict[str, Any]],
    start_date: str | None,
    end_date: str | None,
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if (not start_date or str(row.get("date") or "")[:10] >= start_date)
        and (not end_date or str(row.get("date") or "")[:10] <= end_date)
    ]


async def league_seasons(*, refresh: bool = False) -> list[dict[str, Any]]:
    data = await _get(
        "league_fixtures",
        query={"league_id": ARGENTINE_LEAGUE_ID},
        refresh=refresh,
    )
    return _season_rows(data)


async def league_matches(
    season: str,
    *,
    week: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {
        "league_id": ARGENTINE_LEAGUE_ID,
        "season": season,
    }
    if week:
        query["week"] = week
    data = await _get(
        "league_fixtures",
        query=query,
        ttl=_ttl_for_season(season),
        refresh=refresh,
    )
    rows: list[dict[str, Any]] = []
    for group in data.get("weeks") or []:
        if not isinstance(group, dict):
            continue
        for match in group.get("matches") or []:
            if isinstance(match, dict):
                rows.append(_normalize_match(match, week=group.get("week")))
    if start_date or end_date:
        rows = _filter_by_date(rows, start_date, end_date)
    return rows[:MAX_MATCHES]


async def league_standings(
    season: str,
    *,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    data = await _get(
        "league_standings",
        query={"league_id": ARGENTINE_LEAGUE_ID, "season": season},
        ttl=_ttl_for_season(season),
        refresh=refresh,
    )
    rows: list[dict[str, Any]] = []
    for group in data.get("standings") or []:
        if not isinstance(group, dict):
            continue
        title = group.get("title")
        for item in group.get("table") or []:
            if not isinstance(item, dict):
                continue
            team = item.get("team") if isinstance(item.get("team"), dict) else {}
            zone = item.get("zone") if isinstance(item.get("zone"), dict) else {}
            rows.append(
                {
                    "group": title,
                    "rank": item.get("rank"),
                    "team": team.get("name"),
                    "teamId": team.get("id"),
                    "logo": team.get("logo"),
                    "played": item.get("played"),
                    "won": item.get("won"),
                    "drawn": item.get("drawn"),
                    "lost": item.get("lost"),
                    "goalsFor": item.get("goals_for"),
                    "goalsAgainst": item.get("goals_against"),
                    "goalDifference": item.get("goal_diff"),
                    "points": item.get("points"),
                    "form": item.get("form"),
                    "zone": zone.get("name"),
                }
            )
    return rows


def _fold_name(value: Any) -> str:
    text = " ".join(str(value or "").split()).casefold()
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )


def _resolve_team(
    rows: list[dict[str, Any]],
    requested: str,
) -> dict[str, Any]:
    """Resolve a unique team from standings, accepting common short names."""
    candidates: dict[str, dict[str, Any]] = {}
    for row in rows:
        team_id = row.get("teamId")
        team = row.get("team")
        if not team:
            continue
        key = str(team_id or _fold_name(team))
        candidates[key] = {
            "team": str(team),
            "teamId": team_id,
            "logo": row.get("logo"),
        }

    folded = _fold_name(requested)
    exact = [
        candidate
        for candidate in candidates.values()
        if _fold_name(candidate["team"]) == folded
    ]
    if len(exact) == 1:
        return exact[0]

    partial = [
        candidate
        for candidate in candidates.values()
        if folded and folded in _fold_name(candidate["team"])
    ]
    if len(partial) == 1:
        return partial[0]

    available = ", ".join(
        sorted(candidate["team"] for candidate in candidates.values())
    )
    if not partial:
        raise ValueError(
            f"Team {requested!r} was not found in the selected season. "
            f"Available teams: {available}"
        )
    matches = ", ".join(sorted(candidate["team"] for candidate in partial))
    raise ValueError(
        f"Team name {requested!r} is ambiguous. Matching teams: {matches}"
    )


async def team_matches(
    team_id: str,
    season: str,
    *,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    """Fetch one team's matches directly instead of scanning league fixtures."""
    data = await _get(
        "team_matches",
        query={"team_id": team_id, "season": season},
        ttl=_ttl_for_season(season),
        refresh=refresh,
    )
    return [
        _normalize_match(match, perspective_team_id=team_id)
        for match in data.get("matches") or []
        if isinstance(match, dict)
    ]


async def latest_team_lineup(
    team: str,
    *,
    season: str | None = None,
    as_of: str | None = None,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    """Resolve a team and return its newest available lineup on or before a date."""
    if not season:
        seasons = await league_seasons(refresh=refresh)
        if not seasons:
            return []
        season = str(seasons[0]["season"])

    identity = _resolve_team(
        await league_standings(season, refresh=refresh),
        team,
    )
    team_id = identity.get("teamId")
    if not team_id:
        raise ValueError(f"Team {identity['team']!r} has no upstream team id.")

    cutoff = as_of or date.today().isoformat()
    matches = await team_matches(str(team_id), season, refresh=refresh)
    candidates = sorted(
        (
            match
            for match in matches
            if match.get("id")
            and match.get("date")
            and str(match["date"]) <= cutoff
        ),
        key=lambda match: (
            str(match.get("date") or ""),
            str(match.get("time") or ""),
        ),
        reverse=True,
    )
    for match in candidates:
        rows = await match_lineup(
            str(match["id"]),
            home_team=match.get("homeTeam"),
            away_team=match.get("awayTeam"),
            home_team_logo=match.get("homeTeamLogo"),
            away_team_logo=match.get("awayTeamLogo"),
            refresh=refresh,
        )
        if not any(row.get("starting") for row in rows):
            continue
        return [
            {
                **row,
                "matchDate": match.get("date"),
                "competition": match.get("competition"),
                "status": match.get("status"),
            }
            for row in rows
        ]
    return []


def _team_directory(
    season_matches: list[tuple[str, list[dict[str, Any]]]],
) -> dict[str, dict[str, Any]]:
    directory: dict[str, dict[str, Any]] = {}
    for _, matches in season_matches:
        for match in matches:
            for side in ("home", "away"):
                name = match.get(f"{side}Team")
                if not name:
                    continue
                key = _fold_name(name)
                candidate = {
                    "team": str(name),
                    "teamId": match.get(f"{side}TeamId"),
                    "logo": match.get(f"{side}TeamLogo"),
                }
                existing = directory.get(key)
                if existing:
                    candidate = {
                        field: existing.get(field) or candidate.get(field)
                        for field in ("team", "teamId", "logo")
                    }
                directory[key] = candidate
    return directory


async def league_team_stats(
    teams: list[str],
    seasons: list[str],
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    head_to_head: bool = False,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    """Fetch seasons concurrently and return flat team-season aggregates."""
    if not 1 <= len(teams) <= MAX_STATS_TEAMS:
        raise ValueError("teams must contain between 1 and 2 names")
    if not 1 <= len(seasons) <= MAX_STATS_SEASONS:
        raise ValueError("seasons must contain between 1 and 10 labels")
    if head_to_head and len(teams) != 2:
        raise ValueError("headToHead=true requires exactly 2 teams")

    matches_by_season = await asyncio.gather(
        *(
            league_matches(
                season,
                start_date=start_date,
                end_date=end_date,
                refresh=refresh,
            )
            for season in seasons
        )
    )
    season_matches = list(zip(seasons, matches_by_season, strict=True))
    directory = _team_directory(season_matches)
    resolved: list[dict[str, Any]] = []
    for requested in teams:
        found = directory.get(_fold_name(requested))
        if found is None:
            available = sorted(item["team"] for item in directory.values())
            preview = ", ".join(available[:20])
            raise ValueError(
                f"Team {requested!r} was not found in the requested seasons. "
                f"Available teams include: {preview}"
            )
        resolved.append(found)

    identities = {
        str(team.get("teamId") or _fold_name(team["team"]))
        for team in resolved
    }
    if len(identities) != len(resolved):
        raise ValueError("teams must resolve to distinct teams")

    allowed_ids = {str(team["teamId"]) for team in resolved if team.get("teamId")}
    allowed_names = {_fold_name(team["team"]) for team in resolved}
    rows: list[dict[str, Any]] = []
    for season, matches in season_matches:
        if head_to_head:
            if len(allowed_ids) == 2:
                matches = [
                    match
                    for match in matches
                    if {
                        str(match.get("homeTeamId")),
                        str(match.get("awayTeamId")),
                    }
                    == allowed_ids
                ]
            else:
                matches = [
                    match
                    for match in matches
                    if {
                        _fold_name(match.get("homeTeam")),
                        _fold_name(match.get("awayTeam")),
                    }
                    == allowed_names
                ]
        for team in resolved:
            rows.append(
                compute_team_season_stats(
                    matches,
                    team=team["team"],
                    team_id=(
                        str(team["teamId"]) if team.get("teamId") is not None else None
                    ),
                    logo=team.get("logo"),
                    season=season,
                )
            )
    return rows


async def national_team_seasons(*, refresh: bool = False) -> list[dict[str, Any]]:
    data = await _get(
        "team_matches",
        query={"team_id": ARGENTINA_TEAM_ID},
        refresh=refresh,
    )
    return _season_rows(data)


async def national_team_matches(
    season: str,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    data = await _get(
        "team_matches",
        query={"team_id": ARGENTINA_TEAM_ID, "season": season},
        ttl=_ttl_for_season(season),
        refresh=refresh,
    )
    rows = [
        _normalize_match(match, perspective_team_id=ARGENTINA_TEAM_ID)
        for match in data.get("matches") or []
        if isinstance(match, dict)
    ]
    if start_date or end_date:
        rows = _filter_by_date(rows, start_date, end_date)
    return rows[:MAX_MATCHES]
