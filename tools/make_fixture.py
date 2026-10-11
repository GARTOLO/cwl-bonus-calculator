"""Generates tests/fixtures/season_sample.json from a real season dump.

All names, tags and clan identities are replaced; only the *shape* of the data is
kept (town hall distribution, the mirror pattern, a no-show, a benched player, a
rushed base). This gives the test suite realistic input without publishing anyone's
roster.

    python tools/make_fixture.py live_data.json tests/fixtures/season_sample.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def anonymise(src: dict) -> dict:
    """Replaces every identity with a stable placeholder, keeps every number."""
    aliases: dict[str, str] = {}

    def alias(raw: str) -> str:
        if raw not in aliases:
            aliases[raw] = f"#P{len(aliases) + 1:03d}"
        return aliases[raw]

    def label(raw: str, prefix: str) -> str:
        return f"{prefix} {int(alias(raw)[2:]):02d}"

    def encode_member(member: dict, prefix: str) -> dict:
        return {
            "tag": alias(member["tag"]),
            "name": label(member["tag"], prefix),
            "town_hall": member["th"],
            "map_position": member["pos"],
            "attacks": [
                {"defender_tag": alias(a["d"]), "stars": a["s"],
                 "destruction": a["pct"]}
                for a in member["atk"]
            ],
        }

    wars = []
    for index, war in enumerate(src["wars"], start=1):
        wars.append({
            "round_index": war.get("round", index - 1),
            "war_tag": f"#WAR{index:02d}",
            "state": "warEnded",
            "mine": {
                "clan_tag": "#TESTCLAN",
                "clan_name": "Test Clan",
                "members": [encode_member(m, "Player") for m in war["mine"]],
            },
            "theirs": {
                "clan_tag": f"#OPP{index:02d}",
                "clan_name": f"Opponent {index:02d}",
                "members": [encode_member(m, "Enemy") for m in war["theirs"]],
            },
        })

    return {
        "clan_tag": "#TESTCLAN",
        "clan_name": "Test Clan",
        "season": src.get("season"),
        "number_of_rounds": src.get("number_of_rounds", 0),
        "wars": wars,
    }


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    source, destination = Path(sys.argv[1]), Path(sys.argv[2])
    data = anonymise(json.loads(source.read_text(encoding="utf-8")))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")

    players = {m["tag"] for w in data["wars"] for m in w["mine"]["members"]}
    attacks = sum(len(m["attacks"]) for w in data["wars"] for m in w["mine"]["members"])
    print(f"wrote {destination}: {len(data['wars'])} wars, {len(players)} players, "
          f"{attacks} clan attacks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
