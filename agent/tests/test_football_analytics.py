"""Tests for pure football statistics."""

from __future__ import annotations

import pytest

from agent.analytics.football import (
    compare_rates,
    compute_team_season_stats,
    select_evidence,
    trend,
    volatility,
    wilson_interval,
)


def _match(
    date: str,
    home: str,
    away: str,
    home_score: int | None,
    away_score: int | None,
    status: str = "finished",
) -> dict:
    return {
        "date": date,
        "homeTeam": home,
        "homeTeamId": home.lower(),
        "homeScore": home_score,
        "awayTeam": away,
        "awayTeamId": away.lower(),
        "awayScore": away_score,
        "status": status,
    }


def test_team_stats_use_correct_perspective_and_finished_matches() -> None:
    rows = [
        _match("2024-01-01", "River", "Boca", 2, 0),
        _match("2024-01-08", "Boca", "River", 1, 1),
        _match("2024-01-15", "River", "Racing", None, None, "scheduled"),
        _match("2024-01-22", "Racing", "River", 3, 1),
    ]
    stats = compute_team_season_stats(
        rows, team="River", team_id="river", logo="river.png", season="2024"
    )
    assert stats["played"] == 3
    assert (stats["won"], stats["drawn"], stats["lost"]) == (1, 1, 1)
    assert (stats["goalsFor"], stats["goalsAgainst"]) == (4, 4)
    assert stats["points"] == 4
    assert stats["homePlayed"] == 1
    assert stats["awayPlayed"] == 2
    assert stats["currentStreak"] == "L1"
    assert stats["longestUnbeatenStreak"] == 2
    assert stats["smallSample"] is True


def test_wilson_comparison_trend_and_volatility() -> None:
    low, high = wilson_interval(5, 10)
    assert low == pytest.approx(0.2366, abs=0.001)
    assert high == pytest.approx(0.7634, abs=0.001)
    comparison = compare_rates(8, 10, 4, 10)
    assert comparison["difference"] == pytest.approx(0.4)
    assert comparison["descriptiveOnly"] is True
    assert trend([1, 3, 5]) == pytest.approx({"slope": 2.0, "r2": 1.0})
    assert volatility([1, 2, 3]) == pytest.approx((2 / 3) ** 0.5)


def test_evidence_selection_respects_budget() -> None:
    candidates = [
        {"id": "large", "score": 10, "cost": 5},
        {"id": "efficient", "score": 6, "cost": 2},
        {"id": "small", "score": 2, "cost": 1},
    ]
    assert [item["id"] for item in select_evidence(candidates, 3)] == [
        "efficient",
        "small",
    ]
