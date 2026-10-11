"""Shared builders so tests read as scenarios rather than as data plumbing."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cwlbonus.model import AttackRecord, Member, Season, War, WarSide

FIXTURES = Path(__file__).parent / "fixtures"


def member(tag: str, name: str, th: int, pos: int, attacks=()) -> Member:
    """attacks: iterable of (defender_tag, stars, destruction)."""
    return Member(tag=tag, name=name, town_hall=th, map_position=pos,
                  attacks=[AttackRecord(d, s, float(p)) for d, s, p in attacks])


def side(clan_tag: str, clan_name: str, members) -> WarSide:
    return WarSide(clan_tag=clan_tag, clan_name=clan_name, members=list(members))


def make_war(round_index: int, mine, theirs, war_tag: str | None = None) -> War:
    """mine/theirs: iterables of Member."""
    return War(round_index=round_index, war_tag=war_tag or f"#W{round_index}",
               state="warEnded",
               mine=side("#TESTCLAN", "Test Clan", mine),
               theirs=side("#OPP", "Opponent", theirs))


def make_season(wars, *, clan_tag="#TESTCLAN", clan_name="Test Clan",
                season="2026-10-02", number_of_rounds=None) -> Season:
    return Season(clan_tag=clan_tag, clan_name=clan_name, season=season,
                  number_of_rounds=number_of_rounds or len(wars), wars=list(wars))


def result_with(specs) -> "SeasonResult":
    """specs: [(name, total, wars_played), ...] -> a SeasonResult ready to rank.

    Lets ranking, table and chart tests set exact totals without going through the
    whole scoring pipeline.
    """
    from cwlbonus.config import Weights
    from cwlbonus.scoring import PlayerScore, SeasonResult

    players = [PlayerScore(tag=f"#{name}", name=name, town_hall=16,
                           wars_played=wars, total=total)
               for name, total, wars in specs]
    return SeasonResult(season=Season(clan_tag="#TESTCLAN", clan_name="Test Clan",
                                      season="2026-10-02", number_of_rounds=7),
                        weights=Weights(), players=players)


def mirror_war(round_index: int, roster, attacks, *, war_tag=None) -> War:
    """A mirror-based war: both sides use the same TH ladder and slot layout.

    roster: [(tag, th)] in lineup order. attacks: [(attacker_tag, defender_tag,
    stars, destruction)].
    """
    mine = [member(tag, tag.lstrip("#"), th, i, []) for i, (tag, th) in enumerate(roster, 1)]
    theirs = [member(f"{tag}-E", f"{tag}-E", th, i, []) for i, (tag, th) in enumerate(roster, 1)]
    by_tag = {m.tag: m for m in mine}
    by_enemy = {m.tag: m for m in theirs}
    for attacker, defender, stars, pct in attacks:
        target = by_tag.get(attacker) or by_enemy.get(attacker)
        target.attacks.append(AttackRecord(defender, stars, float(pct)))
    return make_war(round_index, mine, theirs, war_tag=war_tag)


@pytest.fixture(scope="session")
def sample_season() -> Season:
    """A real 7-round CWL season, anonymised (see tools/make_fixture.py)."""
    data = json.loads((FIXTURES / "season_sample.json").read_text(encoding="utf-8"))
    return Season.from_dict(data)
