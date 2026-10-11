"""Tests for the default leaderboard chart.

The padding tests exist because the first version of this design drew the score ink
0.009in from the top of its card and ran the magnitude bar flush to the card's right
edge — both invisible in the code, obvious in the render.
"""
from __future__ import annotations

import warnings

import pytest
from conftest import result_with
from matplotlib.figure import Figure

from cwlbonus.chart import SKINS, fmt, render_chart
from cwlbonus.config import Weights
from cwlbonus.i18n import Translator
from cwlbonus.ranking import build_ranking

ROW_CARD_MIN_W = 700     # px at figure dpi: row cards only (bars ~310, pills ~80)
MIN_INSET_Y = 5.0        # px, ~0.05in clearance above/below the text ink
MIN_INSET_X = 15.0       # px, ~0.15in clearance left/right of text and bars


CUT_LABELS_ES = ("CORTE", "EMPATE")
CUT_LABELS_EN = ("CUT -", "TIE:")


def make_ranking(n: int, *, bonuses: int = 7, tie: bool = False, wars: int = 7,
                 totals=None):
    if totals is None:
        totals = [40.0 - i * 1.5 for i in range(n)]
    specs = [(f"Player{i + 1:02d}", totals[i], wars) for i in range(n)]
    if tie and n >= 2:
        specs[1] = (specs[1][0], specs[0][1], wars)
    return build_ranking(result_with(specs), bonuses=bonuses)


def measure(fig, cut_labels=CUT_LABELS_EN) -> dict[str, float]:
    """Clipping extents, card insets and cut-band collisions, in pixels.

    ``cut_labels`` must match the active language: detecting the band by a Spanish
    marker while rendering English would find nothing and make the collision
    assertion pass vacuously.
    """
    renderer = fig.canvas.get_renderer()
    cards = [p for ax in fig.axes for p in ax.patches
             if p.get_window_extent(renderer).width > ROW_CARD_MIN_W]
    boxes = [t.get_window_extent(renderer) for ax in fig.axes for t in ax.texts]
    boxes += [p.get_window_extent(renderer) for ax in fig.axes for p in ax.patches
              if p not in cards]

    insets = {"top": 1e9, "bottom": 1e9, "left": 1e9, "right": 1e9}
    for card in cards:
        cb = card.get_window_extent(renderer)
        inside = [b for b in boxes
                  if b.x0 >= cb.x0 - 1 and b.x1 <= cb.x1 + 1
                  and b.y0 >= cb.y0 - 1 and b.y1 <= cb.y1 + 1]
        if not inside:
            continue
        insets["top"] = min(insets["top"], min(cb.y1 - b.y1 for b in inside))
        insets["bottom"] = min(insets["bottom"], min(b.y0 - cb.y0 for b in inside))
        insets["left"] = min(insets["left"], min(b.x0 - cb.x0 for b in inside))
        insets["right"] = min(insets["right"], min(cb.x1 - b.x1 for b in inside))

    cut = [t for ax in fig.axes for t in ax.texts
           if any(marker in t.get_text() for marker in cut_labels)]
    collisions = sum(1 for lb in cut for card in cards
                     if lb.get_window_extent(renderer).overlaps(
                         card.get_window_extent(renderer)))

    return {
        "min_y0": min(b.y0 for b in boxes), "max_y1": max(b.y1 for b in boxes),
        "min_x0": min(b.x0 for b in boxes), "max_x1": max(b.x1 for b in boxes),
        "height": fig.bbox.height, "width": fig.bbox.width,
        "cut_labels_found": len(cut), "collisions": collisions, **insets,
    }


def render_and_measure(tmp_path, ranking, *, weights=None, t=None,
                       cut_labels=CUT_LABELS_EN, **kwargs):
    measured: dict[str, float] = {}
    original = Figure.savefig

    def spy(self, *args, **kw):
        self.canvas.draw()
        measured.update(measure(self, cut_labels))
        return original(self, *args, **kw)

    Figure.savefig = spy
    try:
        path = render_chart(ranking, weights or Weights(), t or Translator("en"),
                            tmp_path, clan_name="Test Clan", clan_tag="#TESTCLAN",
                            season="2026-10-02", rounds=7, **kwargs)
    finally:
        Figure.savefig = original
    return path, measured


def rendered_text(tmp_path, ranking, *, weights=None, t=None) -> str:
    seen: dict[str, str] = {}
    original = Figure.savefig

    def spy(self, *args, **kw):
        seen["text"] = " ".join(x.get_text() for ax in self.axes for x in ax.texts)
        return original(self, *args, **kw)

    Figure.savefig = spy
    try:
        render_chart(ranking, weights or Weights(), t or Translator("en"), tmp_path,
                     clan_name="C", clan_tag="#T", season="2026-10-02", rounds=7)
    finally:
        Figure.savefig = original
    return seen["text"]


# ------------------------------------------------------ the reported padding bug
@pytest.mark.parametrize("n", [1, 3, 8, 15, 30])
def test_nothing_touches_a_card_edge(tmp_path, n):
    """Text and bars must stay clear of the rounded frame that contains them."""
    _, m = render_and_measure(tmp_path, make_ranking(n, bonuses=min(7, n)))
    assert m["top"] >= MIN_INSET_Y, f"text too close to the card top ({m['top']:.1f}px)"
    assert m["bottom"] >= MIN_INSET_Y, f"text too close to the card bottom ({m['bottom']:.1f}px)"
    assert m["left"] >= MIN_INSET_X, f"content too close to the card left ({m['left']:.1f}px)"
    assert m["right"] >= MIN_INSET_X, f"bar/score too close to the card right ({m['right']:.1f}px)"


def test_magnitude_bar_is_inset_from_the_right_edge(tmp_path):
    """The specific defect: the bar ran flush to the card's right edge."""
    _, m = render_and_measure(tmp_path, make_ranking(12, bonuses=7))
    assert m["right"] >= MIN_INSET_X


def test_padding_holds_with_long_names_and_defense(tmp_path):
    ranking = build_ranking(result_with([
        ("A_Very_Long_Player_Name_Indeed_Yes", 30.0, 7),
        ("~sweet_puppy~♥", 20.0, 7)]), bonuses=2)
    _, m = render_and_measure(tmp_path, ranking, weights=Weights(use_defense=True))
    assert m["left"] >= MIN_INSET_X and m["right"] >= MIN_INSET_X
    assert m["top"] >= MIN_INSET_Y and m["bottom"] >= MIN_INSET_Y


# ------------------------------------------------------------------- geometry
@pytest.mark.parametrize("n", [1, 2, 3, 5, 8, 9, 10, 12, 15, 20, 30])
@pytest.mark.parametrize("skin", sorted(SKINS))
def test_nothing_is_clipped_for_any_roster_size(tmp_path, n, skin):
    _, m = render_and_measure(tmp_path, make_ranking(n, bonuses=min(7, n)),
                              weights=Weights(skin=skin))
    assert m["min_y0"] >= -0.5, f"clipped at the bottom (n={n})"
    assert m["max_y1"] <= m["height"] + 0.5, f"clipped at the top (n={n})"
    assert m["min_x0"] >= -0.5, "clipped off the left edge"
    assert m["max_x1"] <= m["width"] + 0.5, "clipped off the right"


@pytest.mark.parametrize(("lang", "labels"), [("en", CUT_LABELS_EN), ("es", CUT_LABELS_ES)])
def test_cut_band_does_not_overlap_any_card(tmp_path, lang, labels):
    """The cut label used to be right-aligned on top of the next row's bar."""
    _, m = render_and_measure(tmp_path, make_ranking(15, bonuses=7),
                              t=Translator(lang), cut_labels=labels)
    # Guard against a vacuous pass: the label must actually have been found.
    assert m["cut_labels_found"] >= 1, f"cut label not detected in {lang}"
    assert m["collisions"] == 0


def test_cut_band_is_omitted_when_everyone_gets_a_bonus(tmp_path):
    text = rendered_text(tmp_path, make_ranking(3, bonuses=5))
    assert "CUT -" not in text


def test_rows_below_the_cut_are_marked_outside(tmp_path):
    text = rendered_text(tmp_path, make_ranking(10, bonuses=4))
    assert "CUT - 4 BONUSES" in text


# ------------------------------------------------------------- degenerate input
def test_all_zero_scores_do_not_warp_the_axis(tmp_path):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        render_and_measure(tmp_path, make_ranking(5, totals=[0.0] * 5))
    assert not [w for w in caught if "singular" in str(w.message).lower()]


def test_empty_ranking_renders(tmp_path):
    path, _ = render_and_measure(tmp_path, build_ranking(result_with([]), bonuses=7))
    assert path.exists()


def test_single_player_renders(tmp_path):
    path, m = render_and_measure(tmp_path, make_ranking(1, bonuses=1))
    assert path.exists() and m["min_y0"] >= -0.5


def test_more_bonuses_than_players_renders(tmp_path):
    path, _ = render_and_measure(tmp_path, make_ranking(3, bonuses=7))
    assert path.exists()


# ------------------------------------------------------------------ content
def test_chart_file_is_written(tmp_path):
    path, _ = render_and_measure(tmp_path, make_ranking(10))
    assert path.exists() and path.stat().st_size > 5000


def test_tie_is_labelled_in_the_chart(tmp_path):
    ranking = make_ranking(6, bonuses=3, tie=True)
    assert any(rp.tied for rp in ranking.ranked)
    assert "tie" in rendered_text(tmp_path, ranking).lower()


def test_localised_chart_uses_the_spanish_catalog(tmp_path):
    text = rendered_text(tmp_path, make_ranking(5), t=Translator("es"))
    assert "BONOS" in text
    assert "Entra en el bono" in text


def test_cut_tie_replaces_the_cut_label(tmp_path):
    ranking = build_ranking(
        result_with([("A", 10.0, 7), ("B", 9.0, 7), ("T1", 8.0, 7), ("T2", 8.0, 7)]),
        bonuses=3)
    assert ranking.has_cut_tie
    text = rendered_text(tmp_path, ranking)
    assert "TIE" in text.upper()
    assert "T1" in text and "T2" in text


@pytest.mark.parametrize(("lang", "labels"), [("en", CUT_LABELS_EN), ("es", CUT_LABELS_ES)])
def test_cut_tie_label_does_not_collide_with_a_card(tmp_path, lang, labels):
    ranking = build_ranking(
        result_with([("A", 10.0, 7), ("B", 9.0, 7), ("T1", 8.0, 7), ("T2", 8.0, 7)]),
        bonuses=3)
    assert ranking.has_cut_tie
    _, m = render_and_measure(tmp_path, ranking, t=Translator(lang), cut_labels=labels)
    assert m["cut_labels_found"] >= 1
    assert m["collisions"] == 0


def test_both_skins_render_to_distinct_files(tmp_path):
    ranking = make_ranking(8, bonuses=4)
    dark, _ = render_and_measure(tmp_path, ranking, weights=Weights(skin="dark"),
                                 filename="d.png")
    light, _ = render_and_measure(tmp_path, ranking, weights=Weights(skin="light"),
                                  filename="l.png")
    assert dark.read_bytes() != light.read_bytes()


def test_score_is_formatted_without_negative_zero(tmp_path):
    assert fmt(-0.0) == "0.00"
    assert fmt(-0.001) == "0.00"
    assert fmt(-0.5) == "-0.50"
    text = rendered_text(tmp_path, make_ranking(4))
    assert "-0.00" not in text
