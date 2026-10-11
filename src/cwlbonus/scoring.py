"""The scoring core: pure functions, no I/O, no printing, no clock.

Everything here is deterministic and unit testable. The rules it implements are
documented in docs/SCORING.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import Weights
from .model import Member, Season, War


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class RusherCorrection:
    """One enemy base whose TH was counted down because it looks rushed."""
    war_tag: str
    round_index: int
    tag: str
    name: str
    lineup_slot: int
    town_hall: int
    counted_as: int


def effective_town_halls(opponents: list[Member], max_cut: int
                         ) -> tuple[dict[str, int], list[tuple[Member, int, int]]]:
    """Rushed-base detector.

    The CWL map is ordered by war weight, so a base sitting below a weaker Town
    Hall than its own has been carrying less weight than that weaker base - i.e.
    it is rushed. Its effective TH becomes the weakest TH at or above its slot,
    which is what the map order already implies.

    ``max_cut`` bounds how many levels may be removed, so one strange lineup can
    never collapse the difficulty of a whole map.

    Returns ({tag: effective_th}, [(member, real_th, effective_th), ...]).
    """
    effective: dict[str, int] = {}
    corrections: list[tuple[Member, int, int]] = []
    weakest_above = 99
    for slot, member in enumerate(sorted(opponents, key=lambda m: m.map_position), start=1):
        weakest_above = min(weakest_above, member.town_hall)
        counted = max(weakest_above, member.town_hall - max(0, int(max_cut)))
        if counted < member.town_hall:
            corrections.append((member, member.town_hall, counted))
        effective[member.tag] = counted
    return effective, corrections


@dataclass
class AttackDetail:
    round_index: int
    war_tag: str
    defender_tag: str
    defender_name: str
    defender_th: int
    defender_th_effective: int
    own_th: int
    lineup_drift: int
    difficulty_raw: float
    difficulty_used: float
    stars: int
    destruction: float
    points: float


@dataclass
class DefenseDetail:
    round_index: int
    attacker_tag: str
    attacker_name: str
    attacker_th: int
    stars_conceded: int


@dataclass
class PlayerScore:
    tag: str
    name: str
    town_hall: int
    wars_played: int = 0
    attacks_used: int = 0
    attacks_missed: int = 0
    stars: int = 0
    destruction_total: float = 0.0
    attack_points: float = 0.0
    difficulty_raw_sum: float = 0.0
    difficulty_used_sum: float = 0.0
    difficulty_points: float = 0.0
    lineup_drift_sum: int = 0
    lineup_drift_points: float = 0.0
    penalty_points: float = 0.0
    defense_points: float = 0.0
    defense_count: int = 0
    defense_per_star: float | None = None
    defense_policy_applied: str = "neutral"
    total: float = 0.0
    attacks: list[AttackDetail] = field(default_factory=list)
    defenses: list[DefenseDetail] = field(default_factory=list)


@dataclass
class SeasonResult:
    season: Season
    weights: Weights
    players: list[PlayerScore]
    rusher_corrections: list[RusherCorrection] = field(default_factory=list)
    attacks_processed: int = 0
    wars_processed: int = 0
    skipped_war_tags: list[str] = field(default_factory=list)


def _defense_score(defenses: list[DefenseDetail], own_th: int, w: Weights
                   ) -> tuple[float, float | None, str]:
    """Per-defense defensive efficiency.

    The metric is stars SAVED PER DEFENSE, not stars saved in total, so being
    attacked six times is not automatically worth six times being attacked once.
    """
    n = len(defenses)
    if n == 0:
        # Nobody attacked you. This is an explicit policy, never silently equal
        # to having been 3-starred every round.
        return 0.0, None, w.no_defense_policy

    per_defense = sum(3.0 - d.stars_conceded for d in defenses) / n
    avg_attacker_th = sum(d.attacker_th for d in defenses) / n
    multiplier = w.defense_per_star + max(0.0, avg_attacker_th - own_th) * w.defense_th_bonus
    return per_defense * multiplier, per_defense, w.no_defense_policy


def _apply_no_defense_policy(players: list[PlayerScore], w: Weights) -> None:
    """Gives never-attacked players a score once the season-wide best/worst is known."""
    observed = [p.defense_per_star for p in players if p.defense_per_star is not None]
    if not observed or w.no_defense_policy == "neutral":
        return
    value = min(observed) if w.no_defense_policy == "min" else max(observed, default=0.0)
    for p in players:
        if p.defense_count == 0:
            p.defense_points = value * w.defense_per_star
            p.defense_per_star = value
            p.defense_policy_applied = w.no_defense_policy


def score_season(season: Season, weights: Weights) -> SeasonResult:
    """Scores every player who appeared in at least one war of ``season``."""
    players: dict[str, PlayerScore] = {}
    rushers: list[RusherCorrection] = []
    attacks_processed = 0
    wars_processed = 0
    skipped: list[str] = []

    for war in season.wars:
        my_lineup = war.mine.lineup()
        their_lineup = war.theirs.lineup()
        if not my_lineup or not their_lineup:
            skipped.append(war.war_tag)
            continue
        wars_processed += 1

        my_slot = {m.tag: i for i, m in enumerate(my_lineup, start=1)}
        their_slot = {m.tag: i for i, m in enumerate(their_lineup, start=1)}
        their_tags = set(their_slot)

        eff_th, corrections = effective_town_halls(their_lineup, weights.rusher_max_cut)
        for member, real_th, counted in corrections:
            rushers.append(RusherCorrection(
                war_tag=war.war_tag, round_index=war.round_index, tag=member.tag,
                name=member.name, lineup_slot=their_slot[member.tag],
                town_hall=real_th, counted_as=counted))

        # ---- our players: participation and attacks -----------------------
        for member in my_lineup:
            p = players.get(member.tag)
            if p is None:
                p = PlayerScore(tag=member.tag, name=member.name,
                                town_hall=member.town_hall)
                players[member.tag] = p
            p.name = member.name
            p.town_hall = member.town_hall
            p.wars_played += 1

            for atk in member.attacks:
                attacks_processed += 1
                p.attacks_used += 1
                p.stars += atk.stars
                p.destruction_total += atk.destruction

                defender = None
                for cand in their_lineup:
                    if cand.tag == atk.defender_tag:
                        defender = cand
                        break
                defender_th_eff = eff_th.get(atk.defender_tag, member.town_hall)
                raw = float(defender_th_eff - member.town_hall)
                used = clamp(raw, *weights.difficulty_clamp)
                drift = 0
                if atk.defender_tag in their_slot:
                    drift = their_slot[atk.defender_tag] - my_slot[member.tag]

                points = (atk.stars + atk.destruction / 100.0
                          + weights.difficulty * used)
                p.attack_points += points
                p.difficulty_raw_sum += raw
                p.difficulty_used_sum += used
                p.lineup_drift_sum += drift
                p.attacks.append(AttackDetail(
                    round_index=war.round_index, war_tag=war.war_tag,
                    defender_tag=atk.defender_tag,
                    defender_name=defender.name if defender else atk.defender_tag,
                    defender_th=defender.town_hall if defender else member.town_hall,
                    defender_th_effective=defender_th_eff, own_th=member.town_hall,
                    lineup_drift=drift, difficulty_raw=raw, difficulty_used=used,
                    stars=atk.stars, destruction=atk.destruction, points=points))

        # ---- our players: defenses received ------------------------------
        our_tags = set(my_slot)
        for attacker in their_lineup:
            for atk in attacker.attacks:
                if atk.defender_tag not in our_tags:
                    continue
                players[atk.defender_tag].defenses.append(DefenseDetail(
                    round_index=war.round_index, attacker_tag=attacker.tag,
                    attacker_name=attacker.name, attacker_th=attacker.town_hall,
                    stars_conceded=atk.stars))

    # ---- finalise ---------------------------------------------------------
    out: list[PlayerScore] = []
    for p in players.values():
        p.attacks_missed = max(0, p.wars_played - p.attacks_used)
        p.difficulty_points = p.difficulty_used_sum * weights.difficulty
        p.penalty_points = p.attacks_missed * weights.missed_attack
        if weights.lineup_drift and p.lineup_drift_sum > 0:
            p.lineup_drift_points = p.lineup_drift_sum * weights.lineup_drift

        if weights.use_defense:
            pts, per_star, policy = _defense_score(p.defenses, p.town_hall, weights)
            p.defense_points = pts
            p.defense_per_star = per_star
            p.defense_policy_applied = policy
            p.defense_count = len(p.defenses)

        total = (p.attack_points + p.defense_points + p.penalty_points
                 + p.lineup_drift_points)
        p.total = total if weights.total_floor is None else max(total, weights.total_floor)
        out.append(p)

    if weights.use_defense:
        _apply_no_defense_policy(out, weights)

    out.sort(key=lambda x: (-x.total, x.name.lower()))
    return SeasonResult(season=season, weights=weights, players=out,
                        rusher_corrections=rushers,
                        attacks_processed=attacks_processed,
                        wars_processed=wars_processed, skipped_war_tags=skipped)
