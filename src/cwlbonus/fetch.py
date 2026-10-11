"""Clash of Clans API access. The only module that touches the network.

Keeps coc.py types entirely inside this file and hands back a :class:`Season`.
"""
from __future__ import annotations

import json
from pathlib import Path

import coc

from .model import AttackRecord, Member, Season, War, WarSide


class FetchError(Exception):
    """Carries an i18n key instead of a baked-in English sentence."""

    def __init__(self, key: str, **kwargs) -> None:
        super().__init__(key)
        self.key = key
        self.kwargs = kwargs


def normalise_tag(raw: str) -> str:
    """Accepts '#ABC', 'ABC' or the URL-encoded '%23ABC' from a .env file."""
    tag = (raw or "").replace("%23", "#").replace("%23", "#").strip().strip('"').strip("'")
    if not tag:
        raise FetchError("error.missing_env", vars="CLAN_TAG")
    return tag if tag.startswith("#") else f"#{tag}"


def _member(raw) -> Member:
    return Member(
        tag=raw.tag,
        name=raw.name,
        town_hall=raw.town_hall,
        map_position=raw.map_position,
        attacks=[AttackRecord(defender_tag=a.defender_tag, stars=a.stars,
                              destruction=a.destruction) for a in raw.attacks],
    )


def _side(clan, clan_tag: str) -> WarSide:
    return WarSide(clan_tag=clan.tag, clan_name=clan.name,
                   members=[_member(m) for m in clan.members])


async def _probe_private_war_log(client, clan_tag: str) -> bool:
    """coc.py swallows PrivateWarLog inside get_current_war and returns None.

    Probing get_clan_war is the only way left to tell "private war log" apart
    from "not in a war", so the user gets an accurate message.
    """
    try:
        await client.get_clan_war(clan_tag)
    except coc.PrivateWarLog:
        return True
    except (coc.NotFound, coc.Maintenance):
        return False
    except Exception:
        return False
    return False


async def fetch_season(client: coc.Client, clan_tag: str) -> Season:
    """Reads the clan's current (or just-finished) CWL season."""
    tag = normalise_tag(clan_tag)

    try:
        war = await client.get_current_war(tag)
    except coc.Maintenance as exc:
        raise FetchError("error.maintenance") from exc
    except coc.PrivateWarLog as exc:
        raise FetchError("error.private_war_log") from exc
    except Exception as exc:  # noqa: BLE001 - surfaced to the user, not swallowed
        raise FetchError("error.no_data") from exc

    if war is None:
        if await _probe_private_war_log(client, tag):
            raise FetchError("error.private_war_log")
        raise FetchError("error.not_in_cwl")

    if not war.is_cwl:
        raise FetchError("error.not_in_cwl")

    group = war.league_group
    if group is None:
        raise FetchError("error.no_group")

    clan_name = ""
    try:
        clan_name = (await client.get_clan(tag)).name
    except Exception:  # noqa: BLE001 - a nicer chart title is optional
        pass

    season = Season(clan_tag=tag, clan_name=clan_name,
                    season=getattr(group, "season", None),
                    # number_of_rounds is the real season length; group.rounds
                    # only contains rounds that have already started.
                    number_of_rounds=getattr(group, "number_of_rounds", len(group.rounds)))

    for round_index, war_tags in enumerate(group.rounds):
        for war_tag in war_tags:
            if war_tag == "#0":
                continue
            try:
                league_war = await client.get_league_war(war_tag)
            except coc.NotFound:
                continue
            except Exception:  # noqa: BLE001 - one bad war must not kill the run
                continue
            if tag not in (league_war.clan.tag, league_war.opponent.tag):
                continue
            mine = league_war.clan if league_war.clan.tag == tag else league_war.opponent
            theirs = league_war.opponent if league_war.clan.tag == tag else league_war.clan
            season.wars.append(War(
                round_index=round_index, war_tag=war_tag,
                state=str(getattr(league_war, "state", "")),
                mine=_side(mine, tag), theirs=_side(theirs, theirs.tag)))
    return season


def dump_season(season: Season, path: str | Path) -> Path:
    """Writes the raw season to JSON for debugging or offline replay.

    Never commit the result: it contains real player names.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(season.to_dict(), indent=1, ensure_ascii=False),
                    encoding="utf-8")
    return path
