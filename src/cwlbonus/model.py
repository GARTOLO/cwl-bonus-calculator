"""Plain data model for one CWL season.

Deliberately free of coc.py types so that scoring and charting can be unit tested
against hand written fixtures, and so a season can be dumped to JSON and replayed
without touching the network.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AttackRecord:
    defender_tag: str
    stars: int
    destruction: float


@dataclass
class Member:
    tag: str
    name: str
    town_hall: int
    # NOTE: in a CWL war this is a SPARSE index into the clan's 30 man league
    # roster, not the 1..15 war lineup slot. Observed values range up to 27.
    # Always derive the lineup slot by ranking this field.
    map_position: int
    attacks: list[AttackRecord] = field(default_factory=list)


@dataclass
class WarSide:
    clan_tag: str
    clan_name: str
    members: list[Member] = field(default_factory=list)

    def by_tag(self) -> dict[str, Member]:
        return {m.tag: m for m in self.members}

    def lineup(self) -> list[Member]:
        """Members in war lineup order (strongest first)."""
        return sorted(self.members, key=lambda m: m.map_position)


@dataclass
class War:
    round_index: int
    war_tag: str
    state: str
    mine: WarSide
    theirs: WarSide


@dataclass
class Season:
    clan_tag: str
    clan_name: str
    season: str | None
    number_of_rounds: int
    wars: list[War] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Season":
        wars = []
        for w in data.get("wars", []):
            sides = {}
            for key in ("mine", "theirs"):
                s = w[key]
                sides[key] = WarSide(
                    clan_tag=s["clan_tag"],
                    clan_name=s["clan_name"],
                    members=[
                        Member(
                            tag=m["tag"], name=m["name"], town_hall=m["town_hall"],
                            map_position=m["map_position"],
                            attacks=[AttackRecord(**a) for a in m.get("attacks", [])],
                        )
                        for m in s.get("members", [])
                    ],
                )
            wars.append(War(round_index=w["round_index"], war_tag=w["war_tag"],
                            state=w.get("state", ""), **sides))
        return Season(
            clan_tag=data["clan_tag"], clan_name=data.get("clan_name", ""),
            season=data.get("season"), number_of_rounds=data.get("number_of_rounds", 0),
            wars=wars,
        )
