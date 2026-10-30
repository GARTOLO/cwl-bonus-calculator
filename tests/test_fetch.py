"""Pure helpers from the API layer, tested without a network call."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from cwlbonus.fetch import FetchError, fetch_season, normalise_tag


@pytest.mark.parametrize("raw, expected", [
    ("#2PP0JCCCV", "#2PP0JCCCV"),
    ("2pp0jcccv", "#2PP0JCCCV"),
    ("%232PP0JCCCV", "#2PP0JCCCV"),
    ('" #2pp0jcccv "', "#2PP0JCCCV"),
    ("'#2PP0JCCCV'", "#2PP0JCCCV"),
])
def test_normalise_tag_accepts_every_form_the_setup_docs_allow(raw, expected):
    assert normalise_tag(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_normalise_tag_rejects_an_empty_value(raw):
    with pytest.raises(FetchError):
        normalise_tag(raw)


class _Side:
    def __init__(self, tag: str, name: str) -> None:
        self.tag = tag
        self.name = name
        self.members = []


class _Group:
    def __init__(self, rounds) -> None:
        self.season = "2026-10-02"
        self.number_of_rounds = 1
        self.rounds = rounds


class _CurrentWar:
    def __init__(self, group) -> None:
        self.is_cwl = True
        self.league_group = group


class _FakeClient:
    def __init__(self, league_war=None, fail: bool = False) -> None:
        self.league_war = league_war
        self.fail = fail

    async def get_current_war(self, tag):
        return _CurrentWar(_Group([["#W1"]]))

    async def get_clan(self, tag):
        return _Side("#CLAN", "Test Clan")

    async def get_league_war(self, war_tag):
        if self.fail:
            raise RuntimeError("transient API failure")
        return self.league_war


def test_fetch_season_normalises_the_api_war_state():
    war = SimpleNamespace(
        clan=_Side("#CLAN", "Test Clan"),
        opponent=_Side("#OPP", "Opponent"),
        state=SimpleNamespace(value="inWar"),
        members=[],
    )
    season = asyncio.run(fetch_season(_FakeClient(war), "#clan"))
    assert season.wars[0].state == "inWar"
    assert season.wars[0].finished is False


def test_fetch_season_reports_a_total_api_failure_instead_of_no_players():
    with pytest.raises(FetchError) as caught:
        asyncio.run(fetch_season(_FakeClient(fail=True), "#CLAN"))
    assert caught.value.key == "error.no_data"
