"""CWL Bonus Calculator - fair bonus distribution for Clan War Leagues.

Quick start::

    from cwlbonus import Season, Weights, score_season, build_ranking

    season = Season.from_dict(json.loads(Path("season.json").read_text()))
    result = score_season(season, Weights(difficulty=0.5))
    ranking = build_ranking(result, bonuses=7)
    for rp in ranking.ranked:
        print(rp.rank, rp.player.name, rp.player.total)

The command line entry point is :func:`cwlbonus.cli.main`.
"""

__version__ = "1.0.0"

from .config import PRESETS, Weights, resolve_weights
from .model import AttackRecord, Member, Season, War, WarSide
from .ranking import Ranking, RankedPlayer, build_ranking
from .scoring import (AttackDetail, DefenseDetail, PlayerScore, RusherCorrection,
                      SeasonResult, effective_town_halls, score_season)

__all__ = [
    "__version__",
    "Weights", "PRESETS", "resolve_weights",
    "Season", "War", "WarSide", "Member", "AttackRecord",
    "score_season", "effective_town_halls", "SeasonResult", "PlayerScore",
    "AttackDetail", "DefenseDetail", "RusherCorrection",
    "build_ranking", "Ranking", "RankedPlayer",
]
