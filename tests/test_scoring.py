"""The scoring rules, one test per rule that matters."""
from __future__ import annotations

from conftest import make_season, make_war, member

from cwlbonus.config import Weights
from cwlbonus.scoring import effective_town_halls, score_season


def single_attack(mine_th: int, their_th: int, *, stars: int = 3, pct: float = 100.0,
                  weights: Weights | None = None) -> float:
    """Points from one attack by a TH``mine_th`` player into a TH``their_th`` base."""
    season = make_season([make_war(
        0, [member("#ME", "Me", mine_th, 1, [("#E1", stars, pct)])],
        [member("#E1", "E1", their_th, 1)])])
    return score_season(season, weights or Weights()).players[0].attack_points


def defense_case(defenses, *, weights: Weights | None = None, own_th: int = 17):
    """defenses: [(stars_conceded, attacker_th), ...], one enemy attack per entry."""
    me = member("#ME", "Me", own_th, 1)
    enemies = [member(f"#E{i}", f"E{i}", th, i, [("#ME", stars, 100.0)])
               for i, (stars, th) in enumerate(defenses, start=1)]
    if not enemies:
        # A war always has opponents; "never attacked" means they attacked others.
        enemies = [member("#E1", "E1", own_th, 1)]
    season = make_season([make_war(0, [me], enemies)])
    return score_season(season, weights or Weights(use_defense=True)).players[0]


# ---------------------------------------------------------------- attack rules
def test_mirror_attack_scores_stars_plus_destruction():
    # TH17 into TH17: no difficulty term, so 3 stars + 100% = 4.00
    assert single_attack(17, 17) == 4.0


def test_attacking_a_stronger_base_is_rewarded():
    # TH17 into TH18: +1 town hall at weight 0.5 -> +0.50
    assert single_attack(17, 18) == 4.5


def test_attacking_a_weaker_base_costs_points():
    assert single_attack(17, 16) == 3.5


def test_difficulty_floor_makes_deep_drops_indistinguishable():
    """Documents the deliberate limit, and why it is deliberate.

    Everything below one town hall is charged the same -1, which doubles as
    opponent-strength normalisation: when the whole enemy clan is weaker, every
    player takes the same small charge instead of an unavoidable deep penalty.
    """
    assert single_attack(17, 16) == single_attack(17, 10) == 3.5


def test_difficulty_ceiling_caps_runaway_rewards():
    assert single_attack(17, 21) == single_attack(17, 20) == 4.0 + 1.5


def test_difficulty_weight_zero_ignores_town_halls():
    w = Weights(difficulty=0.0)
    assert single_attack(17, 18, weights=w) == 4.0
    assert single_attack(17, 13, weights=w) == 4.0


def test_higher_weight_makes_hard_targets_worth_more():
    assert (single_attack(17, 18, weights=Weights(difficulty=1.0))
            > single_attack(17, 18, weights=Weights(difficulty=0.3)))


def test_stars_and_destruction_still_dominate():
    """A weak attack on a hard base must not beat a clean hit on an easy one."""
    hero = single_attack(17, 19, stars=1, pct=60)
    sniper = single_attack(17, 13, stars=3, pct=100)
    assert sniper > hero


# ---------------------------------------------------------- participation rules
def _no_show_and_zero_scorer():
    """One player never attacks; another attacks three times for nothing."""
    wars = []
    for i in range(3):
        wars.append(make_war(i, [
            member("#NOSHOW", "NoShow", 17, 1, []),
            member("#ZERO", "ZeroScorer", 17, 2, [("#E2", 0, 0.0)]),
        ], [
            member("#E1", "E1", 17, 1, []),
            member("#E2", "E2", 17, 2, []),
        ]))
    return make_season(wars)


def test_missed_attacks_are_charged_and_not_clipped_away():
    result = score_season(_no_show_and_zero_scorer(), Weights())
    no_show = next(p for p in result.players if p.tag == "#NOSHOW")
    assert no_show.attacks_missed == 3
    assert no_show.penalty_points == -6.0
    assert no_show.total == -6.0          # NOT clipped up to 0
    assert no_show.total < 0


def test_no_show_never_ties_with_someone_who_scored_zero():
    result = score_season(_no_show_and_zero_scorer(), Weights())
    totals = {p.tag: p.total for p in result.players}
    assert totals["#NOSHOW"] != totals["#ZERO"]


def test_total_floor_is_a_display_floor_not_a_reset():
    """A heavy penalty stays visible instead of being flattened onto the floor."""
    w = Weights(total_floor=-10.0)
    wars = [make_war(i, [member("#A", "A", 17, 1, [])],
                     [member("#E", "E", 17, 1, [])]) for i in range(12)]
    result = score_season(make_season(wars), w)
    a = result.players[0]
    assert a.attacks_missed == 12
    assert a.penalty_points == -24.0
    assert a.total == -10.0               # floored for display only
    assert a.penalty_points < a.total     # the real penalty is still reported


def test_benched_player_is_not_charged_for_wars_they_missed():
    wars = [
        make_war(0, [member("#A", "A", 17, 1, [("#E1", 3, 100)])],
                 [member("#E1", "E1", 17, 1, [])]),
        make_war(1, [member("#A", "A", 17, 1, [("#E1", 3, 100)])],
                 [member("#E1", "E1", 17, 1, [])]),
        make_war(2, [member("#B", "B", 17, 1, [])], [member("#E1", "E1", 17, 1, [])]),
    ]
    result = score_season(make_season(wars), Weights())
    a = next(p for p in result.players if p.tag == "#A")
    assert a.wars_played == 2
    assert a.attacks_missed == 0
    assert a.total > 0


def test_late_joiner_who_missed_their_only_attack_is_charged():
    season = make_season([make_war(0, [member("#NEW", "New", 17, 1, [])],
                                   [member("#E1", "E1", 17, 1, [])])])
    new = score_season(season, Weights()).players[0]
    assert new.wars_played == 1
    assert new.attacks_missed == 1
    assert new.total == -2.0


# ------------------------------------------------------------- rusher detector
def test_rusher_detector_is_a_no_op_on_an_ordered_map():
    """The normal case: the game orders the map by weight, nothing changes."""
    ordered = [member(f"#E{i}", f"E{i}", th, i)
               for i, th in enumerate([18, 18, 17, 16, 16, 15], start=1)]
    effective, corrections = effective_town_halls(ordered, max_cut=2)
    assert corrections == []
    assert effective == {m.tag: m.town_hall for m in ordered}


def test_rusher_detector_counts_a_high_th_sitting_below_a_lower_one():
    opponents = [member("#E1", "E1", 16, 1), member("#E2", "E2", 18, 2),
                 member("#E3", "E3", 15, 3)]
    effective, corrections = effective_town_halls(opponents, max_cut=2)
    assert effective["#E2"] == 16
    assert len(corrections) == 1
    assert corrections[0][1:] == (18, 16)


def test_rusher_correction_is_capped():
    opponents = [member("#E1", "E1", 15, 1), member("#E2", "E2", 18, 2)]
    capped, _ = effective_town_halls(opponents, max_cut=2)
    uncapped, _ = effective_town_halls(opponents, max_cut=99)
    assert capped["#E2"] == 16          # 18 - 2
    assert uncapped["#E2"] == 15        # down to the weakest TH above it
    assert capped["#E2"] > uncapped["#E2"]


def test_rusher_cap_zero_disables_the_correction():
    opponents = [member("#E1", "E1", 15, 1), member("#E2", "E2", 18, 2)]
    effective, corrections = effective_town_halls(opponents, max_cut=0)
    assert corrections == []
    assert effective["#E2"] == 18


def test_one_odd_base_cannot_collapse_the_whole_maps_difficulty():
    """An anomaly is corrected locally, never propagated down the map."""
    base = [18, 18, 17, 17, 16]
    ordered = [member(f"#E{i}", f"E{i}", th, i) for i, th in enumerate(base, start=1)]
    odd = [member(f"#E{i}", f"E{i}", th, i) for i, th in enumerate(base, start=1)]
    odd[3].town_hall = 18           # one TH18 dropped below two TH17s
    _, no_corrections = effective_town_halls(ordered, max_cut=2)
    effective_odd, corrections_odd = effective_town_halls(odd, max_cut=2)

    assert no_corrections == []
    # Exactly one base is touched, and only down to the weakest TH above it.
    assert len(corrections_odd) == 1
    assert corrections_odd[0][0].tag == "#E4"
    assert effective_odd["#E4"] == 17
    # Its neighbours keep their own TH: no propagation.
    assert effective_odd["#E1"] == 18
    assert effective_odd["#E3"] == 17
    assert effective_odd["#E5"] == 16


def test_rusher_correction_reaches_the_score():
    """A TH18 that counts as TH16 must not pay a TH18 difficulty reward."""
    ordered = single_attack(17, 18)
    season = make_season([make_war(
        0, [member("#ME", "Me", 17, 1, [("#E2", 3, 100)])],
        [member("#E1", "E1", 16, 1), member("#E2", "E2", 18, 2)])])
    result = score_season(season, Weights())
    assert result.players[0].attack_points < ordered
    assert len(result.rusher_corrections) == 1


# --------------------------------------------------------------- defense rules
def test_never_attacked_is_not_the_same_as_being_three_starred():
    never = defense_case([])
    smashed = defense_case([(3, 17), (3, 17), (3, 17)])
    assert never.defense_count == 0
    assert never.defense_per_star is None       # "no data", explicitly not a zero
    assert smashed.defense_per_star == 0.0


def test_defense_points_do_not_grow_with_exposure():
    """Being attacked six times is not worth six times being attacked once."""
    few = defense_case([(1, 17)] * 3)
    many = defense_case([(1, 17)] * 6)
    assert few.defense_per_star == many.defense_per_star
    assert few.defense_points == many.defense_points


def test_defense_points_track_quality():
    hold = defense_case([(0, 17)] * 3)     # never concedes a star
    leak = defense_case([(3, 17)] * 3)     # always 3-starred
    assert hold.defense_points > leak.defense_points
    assert leak.defense_points == 0.0


def test_defending_against_a_bigger_attacker_is_worth_more():
    small = defense_case([(1, 15)] * 3, own_th=17)
    big = defense_case([(1, 19)] * 3, own_th=17)
    assert big.defense_points > small.defense_points


def test_no_defense_policy_min_and_max_are_applied():
    """The policy is what decides a never-attacked player, and it is reported."""
    ghost = member("#GHOST", "Ghost", 17, 1)
    good = member("#GOOD", "Good", 17, 2)
    bad = member("#BAD", "Bad", 17, 3)
    enemies = [member("#E1", "E1", 17, 1, [("#GOOD", 0, 50), ("#BAD", 3, 100)])]
    season = make_season([make_war(0, [ghost, good, bad], enemies)])

    assert score_season(season, Weights(use_defense=True,
                                        no_defense_policy="neutral")).players
    for policy, expected in (("min", 0.0), ("max", 3.0)):
        result = score_season(season, Weights(use_defense=True, no_defense_policy=policy))
        ghost_score = next(p for p in result.players if p.tag == "#GHOST")
        assert ghost_score.defense_per_star == expected, policy
        assert ghost_score.defense_policy_applied == policy


def test_defense_is_off_by_default():
    assert Weights().use_defense is False
    scored = score_season(
        make_season([make_war(0, [member("#A", "A", 17, 1, [("#E1", 3, 100)])],
                              [member("#E1", "E1", 17, 1, [("#A", 0, 50)])])]),
        Weights())
    assert scored.players[0].defense_points == 0.0
