"""Curated historical football proxy tests."""

from __future__ import annotations

from typing import Any

import pytest

from agent.catalog import catalog
from agent.proxy import ProxyError, resolve
from agent.proxy import football
from agent.proxy.cache import cache
from agent.proxy.upstream import UpstreamError


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch):
    cache.clear()
    monkeypatch.setenv("LIVE_FOOTBALL_API_KEY", "test-football-key")
    yield
    cache.clear()


def test_catalog_lists_only_curated_argentina_routes() -> None:
    paths = set(catalog.paths())
    assert "/v1/football/league/seasons" in paths
    assert "/v1/football/league/matches" in paths
    assert "/v1/football/league/standings" in paths
    assert "/v1/football/league/team-stats" in paths
    assert "/v1/football/league/latest-lineup" in paths
    assert "/v1/football/matches/{matchId}/lineup" in paths
    assert "/v1/football/national-team/seasons" in paths
    assert "/v1/football/national-team/matches" in paths
    assert "/v1/football/leagues" not in paths
    assert "/v1/football/teams/search" not in paths


def test_missing_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIVE_FOOTBALL_API_KEY", raising=False)
    with pytest.raises(UpstreamError, match="credentials missing"):
        football._credentials()


@pytest.mark.asyncio
async def test_league_seasons(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(path: str, **kwargs: Any) -> dict[str, Any]:
        assert path == "/league_fixtures"
        assert kwargs["query"]["api_key"] == "test-football-key"
        assert kwargs["query"]["league_id"] == football.ARGENTINE_LEAGUE_ID
        return {
            "success": True,
            "data": {"available_seasons": ["2026", "2023", "1999/2000"]},
        }

    monkeypatch.setattr(football.upstream, "get", fake_get)
    assert await resolve("/v1/football/league/seasons", {}) == [
        {"season": "2026"},
        {"season": "2023"},
        {"season": "1999/2000"},
    ]


@pytest.mark.asyncio
async def test_league_matches_normalize_and_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(path: str, **kwargs: Any) -> dict[str, Any]:
        assert path == "/league_fixtures"
        assert kwargs["query"]["season"] == "2023"
        return {
            "success": True,
            "data": {
                "weeks": [
                    {
                        "week": "1",
                        "matches": [
                            {
                                "id": "m1",
                                "date": "2023-01-27",
                                "kickoff": "22:15",
                                "status": {"status": "finished"},
                                "league": {
                                    "id": football.ARGENTINE_LEAGUE_ID,
                                    "name": "Liga Profesional Argentina",
                                },
                                "home": {
                                    "id": "central",
                                    "name": "Rosario Central",
                                    "score": "1",
                                },
                                "away": {
                                    "id": "argentinos",
                                    "name": "Argentinos Juniors",
                                    "score": "0",
                                },
                            }
                        ],
                    }
                ]
            },
        }

    monkeypatch.setattr(football.upstream, "get", fake_get)
    rows = await resolve(
        "/v1/football/league/matches",
        {
            "season": "2023",
            "startDate": "2023-01-01",
            "endDate": "2023-02-01",
        },
    )
    assert rows[0]["date"] == "2023-01-27"
    assert rows[0]["week"] == "1"
    assert rows[0]["homeTeam"] == "Rosario Central"
    assert rows[0]["homeScore"] == 1


@pytest.mark.asyncio
async def test_national_team_result_from_argentina_perspective(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(path: str, **kwargs: Any) -> dict[str, Any]:
        assert path == "/team_matches"
        assert kwargs["query"]["team_id"] == football.ARGENTINA_TEAM_ID
        return {
            "success": True,
            "data": {
                "matches": [
                    {
                        "id": "final",
                        "date": "2022-12-18 15:00",
                        "status": "FT",
                        "league": {"name": "FIFA World Cup"},
                        "home": {
                            "id": football.ARGENTINA_TEAM_ID,
                            "name": "Argentina",
                            "score": "3",
                        },
                        "away": {
                            "id": "france",
                            "name": "France",
                            "score": "3",
                        },
                    }
                ]
            },
        }

    monkeypatch.setattr(football.upstream, "get", fake_get)
    rows = await resolve(
        "/v1/football/national-team/matches", {"season": "2022"}
    )
    assert rows[0]["argentinaResult"] == "drew"
    assert rows[0]["competition"] == "FIFA World Cup"


@pytest.mark.asyncio
async def test_season_is_required() -> None:
    with pytest.raises(ProxyError, match="requires season"):
        await resolve("/v1/football/league/matches", {})


@pytest.mark.asyncio
async def test_team_stats_resolve_names_and_head_to_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_matches(season: str, **kwargs: Any) -> list[dict[str, Any]]:
        assert kwargs["start_date"] == "2024-01-01"
        return [
            {
                "id": f"{season}-direct",
                "date": f"{season}-01-10",
                "status": "finished",
                "homeTeam": "Atlético Tucumán",
                "homeTeamId": "atletico",
                "homeTeamLogo": "atletico.png",
                "homeScore": 2,
                "awayTeam": "River Plate",
                "awayTeamId": "river",
                "awayTeamLogo": "river.png",
                "awayScore": 1,
            },
            {
                "id": f"{season}-other",
                "date": f"{season}-01-20",
                "status": "finished",
                "homeTeam": "River Plate",
                "homeTeamId": "river",
                "homeScore": 3,
                "awayTeam": "Racing Club",
                "awayTeamId": "racing",
                "awayScore": 0,
            },
        ]

    monkeypatch.setattr(football, "league_matches", fake_matches)
    rows = await resolve(
        "/v1/football/league/team-stats",
        {
            "teams": "atletico tucuman|RIVER PLATE",
            "seasons": "2023|2024",
            "startDate": "2024-01-01",
            "headToHead": True,
        },
    )
    assert len(rows) == 4
    assert [row["season"] for row in rows] == ["2023", "2023", "2024", "2024"]
    atletico = rows[0]
    river = rows[1]
    assert atletico["team"] == "Atlético Tucumán"
    assert (atletico["played"], atletico["won"], atletico["homePlayed"]) == (1, 1, 1)
    assert (river["played"], river["lost"], river["awayPlayed"]) == (1, 1, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"seasons": "2024"}, "requires teams"),
        ({"teams": "River"}, "requires seasons"),
        (
            {"teams": "River|Boca|Racing", "seasons": "2024"},
            "between 1 and 2",
        ),
        (
            {"teams": "River", "seasons": "2024", "headToHead": True},
            "requires exactly 2",
        ),
    ],
)
async def test_team_stats_validate_params(
    params: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(ProxyError, match=message):
        await resolve("/v1/football/league/team-stats", params)


@pytest.mark.asyncio
async def test_match_lineup_normalizes_both_sides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(path: str, **kwargs: Any) -> dict[str, Any]:
        assert path == "/lineups"
        assert kwargs["query"]["match_id"] == "match-1"
        return {
            "success": True,
            "data": {
                "match_id": "match-1",
                "formation": {"home": 3412, "away": "4-3-3"},
                "is_projected": False,
                "home": {
                    "starting": [
                        {
                            "id": "keeper",
                            "name": "Goal Keeper",
                            "image": "keeper.png",
                            "number": "1",
                            "position": "Goalkeeper",
                            "rating": 7.1,
                        }
                    ],
                    "subs": [],
                    "coach": {"id": "coach", "name": "Home Coach"},
                },
                "away": {
                    "starting": [{"id": "forward", "name": "Away Forward"}],
                    "subs": [{"id": "sub", "name": "Away Sub"}],
                    "coach": None,
                },
            },
        }

    monkeypatch.setattr(football.upstream, "get", fake_get)
    rows = await resolve(
        "/v1/football/matches/{matchId}/lineup",
        {
            "matchId": "match-1",
            "homeTeam": "River Plate",
            "awayTeam": "Boca Juniors",
            "homeTeamLogo": "river.png",
        },
    )
    assert len(rows) == 2
    assert rows[0]["side"] == "home"
    assert rows[0]["team"] == "River Plate"
    assert rows[0]["logo"] == "river.png"
    assert rows[0]["formation"] == "3-4-1-2"
    assert rows[0]["starting"][0]["position"] == "Goalkeeper"
    assert rows[0]["starting"][0]["photoUrl"] == "keeper.png"
    assert rows[1]["team"] == "Boca Juniors"
    assert rows[1]["formation"] == "4-3-3"
    assert rows[1]["substitutes"][0]["name"] == "Away Sub"


@pytest.mark.asyncio
async def test_latest_team_lineup_uses_team_matches_and_walks_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_seasons(**kwargs: Any) -> list[dict[str, Any]]:
        return [{"season": "2026"}]

    async def fake_standings(
        season: str, **kwargs: Any
    ) -> list[dict[str, Any]]:
        assert season == "2026"
        return [
            {"team": "River Plate", "teamId": "river", "logo": "river.png"},
            {"team": "River Plate", "teamId": "river", "logo": "river.png"},
            {"team": "Racing Club", "teamId": "racing"},
        ]

    async def fake_team_matches(
        team_id: str, season: str, **kwargs: Any
    ) -> list[dict[str, Any]]:
        assert (team_id, season) == ("river", "2026")
        return [
            {
                "id": "future",
                "date": "2026-09-20",
                "homeTeam": "River Plate",
                "awayTeam": "Racing Club",
            },
            {
                "id": "latest",
                "date": "2026-09-12",
                "competition": "Liga Profesional",
                "homeTeam": "Atlético Tucumán",
                "awayTeam": "River Plate",
            },
            {
                "id": "older",
                "date": "2026-09-06",
                "competition": "Liga Profesional",
                "homeTeam": "River Plate",
                "awayTeam": "Independiente",
            },
        ]

    lineup_calls: list[str] = []

    async def fake_lineup(match_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        lineup_calls.append(match_id)
        if match_id == "latest":
            return []
        return [
            {
                "matchId": match_id,
                "side": "home",
                "team": "River Plate",
                "starting": [{"name": "Jugador"}],
                "substitutes": [],
            }
        ]

    monkeypatch.setattr(football, "league_seasons", fake_seasons)
    monkeypatch.setattr(football, "league_standings", fake_standings)
    monkeypatch.setattr(football, "team_matches", fake_team_matches)
    monkeypatch.setattr(football, "match_lineup", fake_lineup)

    rows = await resolve(
        "/v1/football/league/latest-lineup",
        {"team": "River", "asOf": "2026-09-16"},
    )

    assert lineup_calls == ["latest", "older"]
    assert rows[0]["matchId"] == "older"
    assert rows[0]["matchDate"] == "2026-09-06"
    assert rows[0]["competition"] == "Liga Profesional"


@pytest.mark.asyncio
async def test_upstream_rate_limit_hook_is_passed_on_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    acquisitions = 0
    network_calls = 0

    class FakeLimiter:
        async def acquire(self) -> None:
            nonlocal acquisitions
            acquisitions += 1

    async def fake_http_get(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal network_calls
        network_calls += 1
        return {"success": True, "data": {"available_seasons": []}}

    monkeypatch.setattr(football, "_RATE_LIMITER", FakeLimiter())
    monkeypatch.setattr(football.upstream, "_get", fake_http_get)
    await football.league_seasons()
    await football.league_seasons()
    assert acquisitions == 1
    assert network_calls == 1
