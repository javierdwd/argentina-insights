"""Tests for bounded Statistical Analyst context construction."""

from __future__ import annotations

import json

from agent.analytics.report import build_football_analysis_context


def _row(team: str, season: str, won: int, played: int) -> dict:
    return {
        "team": team,
        "season": season,
        "played": played,
        "won": won,
        "drawn": 2,
        "lost": max(0, played - won - 2),
        "winRate": won / played,
        "goalDifferencePerGame": 0.5,
        "evidenceMatches": [
            {
                "id": f"{team}-{season}",
                "date": f"{season}-06-01",
                "opponent": "Opponent",
                "goalsFor": 3,
                "goalsAgainst": 0,
                "result": "W",
                "venue": "home",
            }
        ],
    }


def test_context_contains_diagnostics_comparison_and_evidence() -> None:
    payload = json.loads(
        build_football_analysis_context(
            question="Compará River y Boca",
            rows=[
                _row("River Plate", "2023", 8, 12),
                _row("Boca Juniors", "2023", 5, 12),
                _row("River Plate", "2024", 9, 12),
                _row("Boca Juniors", "2024", 6, 12),
            ],
        )
    )
    assert payload["question"] == "Compará River y Boca"
    assert len(payload["aggregateRows"]) == 4
    assert len(payload["teamDiagnostics"]) == 2
    assert payload["rateComparison"]["teamA"] == "River Plate"
    assert payload["rateComparison"]["descriptiveOnly"] is True
    assert payload["representativeMatches"]


def test_context_budget_drops_match_evidence_before_aggregates() -> None:
    rows = [_row("River Plate", str(year), 8, 12) for year in range(2018, 2026)]
    payload = json.loads(
        build_football_analysis_context(
            question="Evolución",
            rows=rows,
            max_chars=4_000,
        )
    )
    assert len(payload["aggregateRows"]) == len(rows)
    assert len(json.dumps(payload, ensure_ascii=False, separators=(",", ":"))) <= 4_000
