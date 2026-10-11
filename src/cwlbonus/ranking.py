"""Ranking: deterministic order, real tie handling, eligibility and the bonus cut.

The original tool sorted on a float and let equal scores fall wherever the sort
left them, so two players on 26.50 were shown as 3rd and 4th in an order that
depended on the order rows came back from the API. If that tie ever lands on the
bonus cut, a bonus is awarded effectively at random. Here equal totals share a
rank and a tie spanning the cut is reported for a human to settle.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .scoring import PlayerScore, SeasonResult


@dataclass
class RankedPlayer:
    position: int          # 1-based ordinal position in the deterministic order
    rank: int              # competition rank: equal totals share a rank
    player: PlayerScore
    eligible: bool
    tied: bool
    gets_bonus: bool


@dataclass
class Ranking:
    ranked: list[RankedPlayer] = field(default_factory=list)
    bonuses: int = 7
    min_wars: int = 0
    #: Players sharing the same score across the bonus boundary (needs a human).
    cut_tie: list[str] = field(default_factory=list)
    cut_tie_score: float | None = None
    #: Last included score minus first excluded score. None when everyone is in.
    cut_margin: float | None = None
    ineligible: list[str] = field(default_factory=list)
    recipients: list[str] = field(default_factory=list)

    @property
    def has_cut_tie(self) -> bool:
        return bool(self.cut_tie)


def build_ranking(result: SeasonResult, bonuses: int = 7, min_wars: int = 0) -> Ranking:
    """Ranks players, resolves eligibility, and detects a tie on the bonus cut."""
    # Deterministic order: score desc, then name. Never rely on input order.
    ordered = sorted(result.players, key=lambda p: (-p.total, p.name.lower()))

    rank_of: dict[str, int] = {}
    ranks: list[int] = []
    for i, p in enumerate(ordered):
        if i > 0 and abs(p.total - ordered[i - 1].total) < 1e-9:
            ranks.append(ranks[-1])
        else:
            ranks.append(i + 1)
        rank_of[p.tag] = ranks[-1]
    tie_counts: dict[int, int] = {}
    for r in ranks:
        tie_counts[r] = tie_counts.get(r, 0) + 1

    eligible_flags = [p.wars_played >= min_wars for p in ordered]
    ineligible = [p.name for p, ok in zip(ordered, eligible_flags) if not ok]

    ranked: list[RankedPlayer] = []
    recipients: list[str] = []
    bonus_slots = max(0, bonuses)
    for i, (p, r, ok) in enumerate(zip(ordered, ranks, eligible_flags)):
        gets_bonus = ok and len(recipients) < bonus_slots
        if gets_bonus:
            recipients.append(p.name)
        ranked.append(RankedPlayer(position=i + 1, rank=r, player=p, eligible=ok,
                                   tied=tie_counts[r] > 1, gets_bonus=gets_bonus))

    # Tie spanning the bonus boundary?
    cut_tie: list[str] = []
    cut_tie_score: float | None = None
    cut_margin: float | None = None
    # The LAST player to receive a bonus, not the first: `next()` here would
    # compare rank 1 against rank 2 and report the wrong margin entirely.
    last_in = max((i for i, rp in enumerate(ranked) if rp.gets_bonus), default=None)
    if last_in is not None:
        last = ranked[last_in]
        first_out = next((rp for rp in ranked[last_in + 1:] if rp.eligible), None)
        if first_out is not None:
            if abs(first_out.player.total - last.player.total) < 1e-9:
                cut_tie_score = last.player.total
                cut_tie = [rp.player.name for rp in ranked
                           if abs(rp.player.total - cut_tie_score) < 1e-9
                           and rp.eligible]
            cut_margin = last.player.total - first_out.player.total

    return Ranking(ranked=ranked, bonuses=bonus_slots, min_wars=min_wars,
                   cut_tie=cut_tie, cut_tie_score=cut_tie_score,
                   cut_margin=cut_margin, ineligible=ineligible,
                   recipients=recipients)
