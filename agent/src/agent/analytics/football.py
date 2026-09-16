"""Pure football statistics.

Functions in this module perform no I/O and make no causal claims.  Match
rows are expected in the normalized proxy shape (homeTeam, awayTeam, scores).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

FINISHED_STATUSES = {
    "completed",
    "ended",
    "finished",
    "ft",
    "full time",
    "full-time",
    "after extra time",
    "aet",
    "after penalties",
    "pen",
}


def wilson_interval(
    successes: int,
    total: int,
    *,
    z: float = 1.959963984540054,
) -> tuple[float, float]:
    """Return a Wilson score interval for a binomial proportion."""
    if total <= 0:
        return (0.0, 0.0)
    if successes < 0 or successes > total:
        raise ValueError("successes must be between 0 and total")
    proportion = successes / total
    z2 = z * z
    denominator = 1 + z2 / total
    center = (proportion + z2 / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            proportion * (1 - proportion) / total + z2 / (4 * total * total)
        )
        / denominator
    )
    return (max(0.0, center - margin), min(1.0, center + margin))


def effect_size(
    value_a: float,
    value_b: float,
    *,
    scale: float | None = None,
) -> dict[str, float | None]:
    """Describe a difference without implying that either value caused it."""
    difference = float(value_a) - float(value_b)
    denominator = abs(float(value_b))
    relative = difference / denominator if denominator else None
    standardized = difference / scale if scale and scale > 0 else None
    return {
        "difference": difference,
        "relativeDifference": relative,
        "standardizedDifference": standardized,
    }


def compare_rates(
    successes_a: int,
    total_a: int,
    successes_b: int,
    total_b: int,
) -> dict[str, Any]:
    """Compare two observed rates and include their uncertainty intervals."""
    rate_a = successes_a / total_a if total_a else 0.0
    rate_b = successes_b / total_b if total_b else 0.0
    low_a, high_a = wilson_interval(successes_a, total_a)
    low_b, high_b = wilson_interval(successes_b, total_b)
    return {
        "rateA": rate_a,
        "rateB": rate_b,
        **effect_size(rate_a, rate_b),
        "confidenceIntervalA": {"low": low_a, "high": high_a},
        "confidenceIntervalB": {"low": low_b, "high": high_b},
        "intervalsOverlap": max(low_a, low_b) <= min(high_a, high_b),
        "descriptiveOnly": True,
    }


def trend(values: Sequence[float]) -> dict[str, float]:
    """Return ordinary-least-squares slope and R² over equally spaced values."""
    count = len(values)
    if count < 2:
        return {"slope": 0.0, "r2": 0.0}
    ys = [float(value) for value in values]
    mean_x = (count - 1) / 2
    mean_y = sum(ys) / count
    ss_x = sum((index - mean_x) ** 2 for index in range(count))
    slope = (
        sum((index - mean_x) * (value - mean_y) for index, value in enumerate(ys))
        / ss_x
    )
    intercept = mean_y - slope * mean_x
    residual = sum(
        (value - (intercept + slope * index)) ** 2
        for index, value in enumerate(ys)
    )
    total = sum((value - mean_y) ** 2 for value in ys)
    r2 = 1 - residual / total if total else 1.0
    return {"slope": slope, "r2": max(0.0, min(1.0, r2))}


def volatility(values: Sequence[float], *, sample: bool = False) -> float:
    """Return population (or sample) standard deviation."""
    count = len(values)
    divisor = count - 1 if sample else count
    if divisor <= 0:
        return 0.0
    mean = sum(float(value) for value in values) / count
    return math.sqrt(sum((float(value) - mean) ** 2 for value in values) / divisor)


def select_evidence(
    candidates: Iterable[Mapping[str, Any]],
    budget: int,
    *,
    cost: Callable[[Mapping[str, Any]], int] | None = None,
    score: Callable[[Mapping[str, Any]], float] | None = None,
) -> list[dict[str, Any]]:
    """Select the highest-scoring evidence set under an integer budget.

    Candidate defaults are ``cost=1`` and ``score`` (or ``relevance``) ``=0``.
    A deterministic 0/1 knapsack keeps this correct where a greedy ratio would
    discard a better combination.
    """
    if budget <= 0:
        return []
    cost_fn = cost or (lambda item: int(item.get("cost", 1)))
    score_fn = score or (
        lambda item: float(item.get("score", item.get("relevance", 0.0)))
    )
    items: list[tuple[Mapping[str, Any], int, float]] = []
    for item in candidates:
        item_cost = max(1, cost_fn(item))
        item_score = score_fn(item)
        if item_cost > budget or item_score < 0:
            continue
        items.append((item, item_cost, item_score))

    # budget used -> (total score, selected item indices). Keeping the existing
    # state on ties makes input order the stable tie-breaker.
    states: dict[int, tuple[float, tuple[int, ...]]] = {0: (0.0, ())}
    for index, (_, item_cost, item_score) in enumerate(items):
        updated = dict(states)
        for spent, (total_score, selected) in states.items():
            new_spent = spent + item_cost
            if new_spent > budget:
                continue
            candidate = (total_score + item_score, (*selected, index))
            existing = updated.get(new_spent)
            if existing is None or candidate[0] > existing[0]:
                updated[new_spent] = candidate
        states = updated
    _, best_indices = max(
        states.values(),
        key=lambda state: (state[0], -len(state[1])),
    )
    return [dict(items[index][0]) for index in best_indices]


def _is_finished(match: Mapping[str, Any]) -> bool:
    if match.get("homeScore") is None or match.get("awayScore") is None:
        return False
    status = str(match.get("status") or "").strip().lower()
    return status in FINISHED_STATUSES


def _streaks(results: Sequence[str]) -> dict[str, Any]:
    longest_win = 0
    longest_unbeaten = 0
    win_run = 0
    unbeaten_run = 0
    for result in results:
        win_run = win_run + 1 if result == "W" else 0
        unbeaten_run = unbeaten_run + 1 if result != "L" else 0
        longest_win = max(longest_win, win_run)
        longest_unbeaten = max(longest_unbeaten, unbeaten_run)

    current_type = results[-1] if results else None
    current_length = 0
    if current_type:
        for result in reversed(results):
            if result != current_type:
                break
            current_length += 1
    return {
        "currentStreak": (
            f"{current_type}{current_length}" if current_type else None
        ),
        "currentStreakType": current_type,
        "currentStreakLength": current_length,
        "longestWinStreak": longest_win,
        "longestUnbeatenStreak": longest_unbeaten,
    }


def _split_stats(matches: Sequence[dict[str, Any]], venue: str) -> dict[str, Any]:
    selected = [match for match in matches if match["venue"] == venue]
    prefix = venue
    won = sum(match["result"] == "W" for match in selected)
    drawn = sum(match["result"] == "D" for match in selected)
    lost = sum(match["result"] == "L" for match in selected)
    played = len(selected)
    goals_for = sum(match["goalsFor"] for match in selected)
    goals_against = sum(match["goalsAgainst"] for match in selected)
    points = won * 3 + drawn
    return {
        f"{prefix}Played": len(selected),
        f"{prefix}Won": won,
        f"{prefix}Drawn": drawn,
        f"{prefix}Lost": lost,
        f"{prefix}GoalsFor": goals_for,
        f"{prefix}GoalsAgainst": goals_against,
        f"{prefix}GoalDifference": goals_for - goals_against,
        f"{prefix}Points": points,
        f"{prefix}WinRate": won / played if played else 0.0,
        f"{prefix}PointsPerGame": points / played if played else 0.0,
        f"{prefix}GoalsForPerGame": goals_for / played if played else 0.0,
        f"{prefix}GoalsAgainstPerGame": goals_against / played if played else 0.0,
        f"{prefix}GoalDifferencePerGame": (
            (goals_for - goals_against) / played if played else 0.0
        ),
    }


def _representative_matches(
    matches: Sequence[dict[str, Any]],
    *,
    limit: int = 4,
) -> list[dict[str, Any]]:
    """Keep boundary and largest-margin matches as compact traceable evidence."""
    if not matches or limit <= 0:
        return []
    candidates = [
        matches[0],
        matches[-1],
        max(matches, key=lambda item: item["goalsFor"] - item["goalsAgainst"]),
        min(matches, key=lambda item: item["goalsFor"] - item["goalsAgainst"]),
    ]
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in candidates:
        identity = str(match.get("id") or (
            match.get("date"),
            match.get("opponent"),
            match.get("goalsFor"),
            match.get("goalsAgainst"),
        ))
        if identity in seen:
            continue
        seen.add(identity)
        output.append(dict(match))
        if len(output) >= limit:
            break
    return output


def compute_team_season_stats(
    matches: Sequence[Mapping[str, Any]],
    *,
    team: str,
    team_id: str | None,
    logo: str | None,
    season: str,
) -> dict[str, Any]:
    """Aggregate finished normalized matches from one team's perspective."""
    perspective: list[dict[str, Any]] = []
    for match in matches:
        if not _is_finished(match):
            continue
        is_home = (
            str(match.get("homeTeamId")) == team_id
            if team_id
            else str(match.get("homeTeam")) == team
        )
        is_away = (
            str(match.get("awayTeamId")) == team_id
            if team_id
            else str(match.get("awayTeam")) == team
        )
        if not is_home and not is_away:
            continue
        goals_for = int(match["homeScore"] if is_home else match["awayScore"])
        goals_against = int(match["awayScore"] if is_home else match["homeScore"])
        perspective.append(
            {
                "id": match.get("id"),
                "date": str(match.get("date") or ""),
                "venue": "home" if is_home else "away",
                "opponent": (
                    match.get("awayTeam") if is_home else match.get("homeTeam")
                ),
                "goalsFor": goals_for,
                "goalsAgainst": goals_against,
                "result": (
                    "W" if goals_for > goals_against
                    else "D" if goals_for == goals_against
                    else "L"
                ),
            }
        )
    perspective.sort(key=lambda match: match["date"])
    played = len(perspective)
    won = sum(match["result"] == "W" for match in perspective)
    drawn = sum(match["result"] == "D" for match in perspective)
    lost = sum(match["result"] == "L" for match in perspective)
    goals_for = sum(match["goalsFor"] for match in perspective)
    goals_against = sum(match["goalsAgainst"] for match in perspective)
    points = won * 3 + drawn
    win_low, win_high = wilson_interval(won, played)

    per_game = lambda value: value / played if played else 0.0
    return {
        "team": team,
        "teamId": team_id,
        "logo": logo,
        "season": season,
        "played": played,
        "won": won,
        "drawn": drawn,
        "lost": lost,
        "goalsFor": goals_for,
        "goalsAgainst": goals_against,
        "goalDifference": goals_for - goals_against,
        "points": points,
        "winRate": per_game(won),
        "unbeatenRate": per_game(won + drawn),
        "pointsPerGame": per_game(points),
        "goalsForPerGame": per_game(goals_for),
        "goalsAgainstPerGame": per_game(goals_against),
        "goalDifferencePerGame": per_game(goals_for - goals_against),
        **_split_stats(perspective, "home"),
        **_split_stats(perspective, "away"),
        **_streaks([match["result"] for match in perspective]),
        "winRateConfidenceLow": win_low,
        "winRateConfidenceHigh": win_high,
        "sampleSize": played,
        "smallSample": played < 10,
        "sufficientSample": played >= 10,
        "evidenceMatches": _representative_matches(perspective),
    }
