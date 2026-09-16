"""Structured statistical-analysis contracts and context budgeting."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .football import compare_rates, select_evidence, trend, volatility


class StatisticalFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    conclusion: str
    strength: Literal["weak", "moderate", "strong"]
    evidence: list[str] = Field(min_length=1, max_length=4)
    caveat: str | None = None


class StatisticalReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    findings: list[StatisticalFinding] = Field(min_length=1, max_length=4)
    limitations: list[str] = Field(default_factory=list, max_length=4)
    nextSteps: list[str] = Field(default_factory=list, max_length=3)


_AGGREGATE_KEYS = (
    "team",
    "season",
    "played",
    "won",
    "drawn",
    "lost",
    "goalsFor",
    "goalsAgainst",
    "goalDifference",
    "points",
    "winRate",
    "unbeatenRate",
    "pointsPerGame",
    "goalsForPerGame",
    "goalsAgainstPerGame",
    "goalDifferencePerGame",
    "homeWinRate",
    "awayWinRate",
    "homePointsPerGame",
    "awayPointsPerGame",
    "homeGoalDifference",
    "awayGoalDifference",
    "homeGoalsForPerGame",
    "awayGoalsForPerGame",
    "homeGoalsAgainstPerGame",
    "awayGoalsAgainstPerGame",
    "homeGoalDifferencePerGame",
    "awayGoalDifferencePerGame",
    "longestWinStreak",
    "longestUnbeatenStreak",
    "winRateConfidenceLow",
    "winRateConfidenceHigh",
    "sampleSize",
    "smallSample",
)


def _compact_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row.get(key) for key in _AGGREGATE_KEYS if key in row}


def _team_diagnostics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("team"):
            grouped[str(row["team"])].append(row)

    diagnostics: list[dict[str, Any]] = []
    for team, team_rows in grouped.items():
        win_rates = [float(row.get("winRate") or 0) for row in team_rows]
        goal_diffs = [
            float(row.get("goalDifferencePerGame") or 0) for row in team_rows
        ]
        diagnostics.append(
            {
                "team": team,
                "seasons": len(team_rows),
                "totalMatches": sum(int(row.get("played") or 0) for row in team_rows),
                "winRateTrend": trend(win_rates),
                "goalDifferenceTrend": trend(goal_diffs),
                "winRateVolatility": volatility(win_rates),
            }
        )
    return diagnostics


def _overall_rate_comparison(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    grouped: dict[str, tuple[int, int]] = {}
    for row in rows:
        team = str(row.get("team") or "")
        if not team:
            continue
        won, played = grouped.get(team, (0, 0))
        grouped[team] = (
            won + int(row.get("won") or 0),
            played + int(row.get("played") or 0),
        )
    if len(grouped) != 2:
        return None
    (team_a, (won_a, played_a)), (team_b, (won_b, played_b)) = grouped.items()
    return {
        "teamA": team_a,
        "teamB": team_b,
        **compare_rates(won_a, played_a, won_b, played_b),
    }


def build_football_analysis_context(
    *,
    question: str,
    rows: list[dict[str, Any]],
    max_chars: int = 14_000,
) -> str:
    """Build bounded JSON with all aggregates and representative raw matches."""
    compact_rows = [_compact_row(row) for row in rows]
    core: dict[str, Any] = {
        "question": question,
        "aggregateRows": compact_rows,
        "teamDiagnostics": _team_diagnostics(rows),
        "rateComparison": _overall_rate_comparison(rows),
        "rules": {
            "descriptiveOnly": True,
            "confidenceLevel": 0.95,
            "pointsRule": "3 for a win, 1 for a draw",
        },
    }
    base = json.dumps(core, ensure_ascii=False, separators=(",", ":"))
    evidence_candidates: list[dict[str, Any]] = []
    for row in rows:
        for match in row.get("evidenceMatches") or []:
            if not isinstance(match, dict):
                continue
            evidence = {
                "team": row.get("team"),
                "season": row.get("season"),
                **match,
            }
            margin = abs(
                int(evidence.get("goalsFor") or 0)
                - int(evidence.get("goalsAgainst") or 0)
            )
            evidence["score"] = float(1 + margin)
            evidence["cost"] = max(
                1,
                len(json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))),
            )
            evidence_candidates.append(evidence)

    remaining = max(0, max_chars - len(base) - 30)
    selected = select_evidence(evidence_candidates, remaining)
    for item in selected:
        item.pop("score", None)
        item.pop("cost", None)
    core["representativeMatches"] = selected
    serialized = json.dumps(core, ensure_ascii=False, separators=(",", ":"))
    if len(serialized) <= max_chars:
        return serialized

    # Aggregates are the irreducible evidence. If an unusually large request
    # still exceeds the budget, omit match examples rather than truncating JSON.
    core["representativeMatches"] = []
    return json.dumps(core, ensure_ascii=False, separators=(",", ":"))
