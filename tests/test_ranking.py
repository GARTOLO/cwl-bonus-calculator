"""Tie handling, eligibility and the bonus cut."""
from __future__ import annotations

import pytest

from conftest import result_with

from cwlbonus.config import Weights
from cwlbonus.model import Season
from cwlbonus.ranking import build_ranking
from cwlbonus.scoring import PlayerScore, SeasonResult


def test_equal_totals_share_a_rank():
    ranking = build_ranking(result_with([("Ana", 30.0, 7), ("Bea", 20.0, 7),
                                         ("Cyd", 20.0, 7)]), bonuses=7)
    ranks = {rp.player.name: rp.rank for rp in ranking.ranked}
    assert ranks["Ana"] == 1
    assert ranks["Bea"] == ranks["Cyd"] == 2      # shared rank, not 2 and 3
    assert all(rp.tied for rp in ranking.ranked if rp.player.name in ("Bea", "Cyd"))


def test_order_is_deterministic_for_equal_totals():
    """The original sorted on a float and let input order decide. It must not."""
    specs = [("Zoe", 20.0, 7), ("Ana", 20.0, 7), ("Mia", 20.0, 7)]
    first = [rp.player.name for rp in build_ranking(result_with(specs), 7).ranked]
    for permutation in ([specs[1], specs[2], specs[0]],
                        [specs[2], specs[0], specs[1]],
                        [specs[1], specs[0], specs[2]]):
        other = [rp.player.name for rp in build_ranking(result_with(permutation), 7).ranked]
        assert other == first, permutation
    assert first == ["Ana", "Mia", "Zoe"]


def test_tie_at_the_bonus_cut_is_flagged():
    specs = [("P1", 30.0, 7), ("P2", 29.0, 7), ("P3", 28.0, 7),
             ("Tied1", 27.0, 7), ("Tied2", 27.0, 7), ("End", 10.0, 7)]
    ranking = build_ranking(result_with(specs), bonuses=4)
    assert ranking.has_cut_tie
    assert sorted(ranking.cut_tie) == ["Tied1", "Tied2"]
    assert ranking.cut_tie_score == 27.0
    # The tool does not silently pick one: exactly 4 bonuses were handed out.
    assert len(ranking.recipients) == 4


def test_no_tie_flag_when_scores_differ():
    specs = [("P1", 30.0, 7), ("P2", 29.0, 7), ("P3", 28.0, 7), ("P4", 20.0, 7)]
    ranking = build_ranking(result_with(specs), bonuses=3)
    assert not ranking.has_cut_tie
    assert ranking.cut_margin == pytest.approx(8.0)


def test_cut_margin_reports_the_gap_to_the_next_player():
    specs = [("P1", 30.0, 7), ("P2", 25.5, 7)]
    ranking = build_ranking(result_with(specs), bonuses=1)
    assert ranking.cut_margin == pytest.approx(4.5)


def test_min_wars_marks_players_ineligible():
    specs = [("Regular", 30.0, 7), ("Sub", 40.0, 1)]
    ranking = build_ranking(result_with(specs), bonuses=2, min_wars=4)
    by_name = {rp.player.name: rp for rp in ranking.ranked}
    assert by_name["Sub"].eligible is False
    assert by_name["Regular"].eligible is True
    assert ranking.ineligible == ["Sub"]


def test_bonus_flows_past_an_ineligible_player():
    """A sub who out-scored a regular must not take a bonus they are not eligible for."""
    specs = [("Sub", 40.0, 1), ("A", 30.0, 7), ("B", 20.0, 7)]
    ranking = build_ranking(result_with(specs), bonuses=2, min_wars=4)
    assert ranking.recipients == ["A", "B"]


def test_everyone_eligible_by_default():
    specs = [("Sub", 40.0, 1), ("A", 30.0, 7)]
    ranking = build_ranking(result_with(specs), bonuses=2)
    assert ranking.ineligible == []
    assert set(ranking.recipients) == {"Sub", "A"}


def test_bonuses_beyond_the_field_are_clamped():
    ranking = build_ranking(result_with([("A", 10.0, 7)]), bonuses=7)
    assert len(ranking.recipients) == 1
    assert not ranking.has_cut_tie
    assert ranking.cut_margin is None


def test_zero_bonuses_is_handled():
    ranking = build_ranking(result_with([("A", 10.0, 7), ("B", 5.0, 7)]), bonuses=0)
    assert ranking.recipients == []
    assert ranking.cut_margin is None


def test_ranked_positions_are_always_sequential():
    ranking = build_ranking(result_with([("A", 3.0, 7), ("B", 2.0, 7), ("C", 1.0, 7)]), 2)
    assert [rp.position for rp in ranking.ranked] == [1, 2, 3]
    assert [rp.rank for rp in ranking.ranked] == [1, 2, 3]
