"""Pure domain analytics used by proxy integrations."""

from .football import (
    compare_rates,
    compute_team_season_stats,
    effect_size,
    select_evidence,
    trend,
    volatility,
    wilson_interval,
)

__all__ = [
    "compare_rates",
    "compute_team_season_stats",
    "effect_size",
    "select_evidence",
    "trend",
    "volatility",
    "wilson_interval",
]
