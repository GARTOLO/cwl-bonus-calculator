"""Chart rendering, with the regression that motivated the rewrite.

The original layout put the footer text at a fixed fraction of a figure whose
height grew with the number of players, so the formula block was clipped for any
roster below about nine players. These tests measure the rendered text boxes at
save time and assert they stay inside the image, across the whole range.
"""
from __future__ import annotations

import warnings

import pytest
from conftest import result_with
from matplotlib.figure import Figure

from cwlbonus.chart import fmt, render_chart
from cwlbonus.config import Weights
from cwlbonus.i18n import Translator
from cwlbonus.ranking import build_ranking


def make_ranking(n: int, *, bonuses: int = 7, tie: bool = False, wars: int = 7,
                 totals=None):
    if totals is None:
        totals = [40.0 - i * 1.5 for i in range(n)]
    specs = [(f"Player{i + 1:02d}", totals[i], wars) for i in range(n)]
    if tie and n >= 2:
        specs[1] = (specs[1][0], specs[0][1], wars)
    return build_ranking(result_with(specs), bonuses=bonuses)


def drawn_tick_labels(axis, limits):
    """Tick labels that are actually inside the view interval.

    Matplotlib keeps Text objects for ticks just outside the limits; they are not
    drawn, but their transform still yields a box, which would read as phantom
    overflow.
    """
    low, high = sorted(limits)
    return [label for loc, label in zip(axis.get_ticklocs(), axis.get_ticklabels())
            if low <= loc <= high and label.get_text()]


def collect_boxes(fig):
    """Every visible piece of text, plus legend frames, in display pixels."""
    renderer = fig.canvas.get_renderer()
    boxes = []
    for ax in fig.axes:
        boxes += [t.get_window_extent(renderer) for t in ax.texts]
        if ax.axison:
            for axis, limits in ((ax.xaxis, ax.get_xlim()), (ax.yaxis, ax.get_ylim())):
                boxes += [t.get_window_extent(renderer)
                          for t in drawn_tick_labels(axis, limits)]
            for label in (ax.xaxis.label, ax.yaxis.label, ax.title):
                if label.get_text():
                    boxes.append(label.get_window_extent(renderer))
        legend = ax.get_legend()
        if legend is not None:
            boxes.append(legend.get_window_extent(renderer))
    return boxes


def render_and_measure(tmp_path, ranking, *, weights=None, t=None, **kwargs):
    """Renders the chart and returns (path, measured extents in pixels)."""
    measured: dict[str, float] = {}
    original = Figure.savefig

    def spy(self, *args, **kw):
        self.canvas.draw()
        boxes = collect_boxes(self)
        if boxes:
            measured["min_y0"] = min(b.y0 for b in boxes)
            measured["max_y1"] = max(b.y1 for b in boxes)
            measured["min_x0"] = min(b.x0 for b in boxes)
            measured["max_x1"] = max(b.x1 for b in boxes)
        measured["height"] = self.bbox.height
        measured["width"] = self.bbox.width
        return original(self, *args, **kw)

    Figure.savefig = spy
    try:
        path = render_chart(ranking, weights or Weights(), t or Translator("en"),
                            tmp_path, clan_name="Test Clan", clan_tag="#TESTCLAN",
                            season="2026-10-02", rounds=7, **kwargs)
    finally:
        Figure.savefig = original
    return path, measured


# ------------------------------------------------------------ the regression
@pytest.mark.parametrize("n", [1, 2, 3, 5, 8, 9, 10, 12, 15, 20, 30])
@pytest.mark.parametrize("defense", [False, True])
def test_nothing_is_clipped_for_any_roster_size(tmp_path, n, defense):
    """The exact failure the original shipped: a clipped footer on small rosters."""
    ranking = make_ranking(n, bonuses=min(7, n))
    _, measured = render_and_measure(tmp_path, ranking,
                                     weights=Weights(use_defense=defense))
    assert measured["min_y0"] >= -0.5, f"content clipped at the bottom (n={n})"
    assert measured["max_y1"] <= measured["height"] + 0.5, f"content clipped (n={n})"


@pytest.mark.parametrize("n", [1, 3, 9, 15, 30])
def test_nothing_is_clipped_horizontally(tmp_path, n):
    """Player names are drawn outside the axes and used to run off the left edge."""
    _, measured = render_and_measure(tmp_path, make_ranking(n, bonuses=min(7, n)))
    assert measured["min_x0"] >= -0.5, "content clipped off the left edge"
    assert measured["max_x1"] <= measured["width"] + 0.5, "content clipped off the right"


def test_long_player_names_are_given_room(tmp_path):
    ranking = build_ranking(result_with([
        ("A_Very_Long_Player_Name_Indeed", 30.0, 7),
        ("~sweet_puppy~♥", 20.0, 7)]), bonuses=2)
    _, measured = render_and_measure(tmp_path, ranking)
    assert measured["min_x0"] >= -0.5


def test_axis_title_does_not_overlap_the_legend(tmp_path):
    """The x axis label lives under the plot; the legend must not cover it."""
    overlaps = []
    original = Figure.savefig

    def spy(self, *args, **kw):
        self.canvas.draw()
        renderer = self.canvas.get_renderer()
        legends = [ax.get_legend() for ax in self.axes if ax.get_legend() is not None]
        labels = [ax.xaxis.label for ax in self.axes if ax.xaxis.label.get_text()]
        for label in labels:
            lb = label.get_window_extent(renderer)
            for legend in legends:
                if lb.overlaps(legend.get_window_extent(renderer)):
                    overlaps.append((label.get_text(), legend))
        return original(self, *args, **kw)

    Figure.savefig = spy
    try:
        render_chart(make_ranking(15), Weights(use_defense=True), Translator("en"),
                     tmp_path, clan_name="C", clan_tag="#T", season="2026-10-02",
                     rounds=7)
    finally:
        Figure.savefig = original
    assert not overlaps, f"the x axis label is covered by the legend: {overlaps}"


def test_footer_and_legend_do_not_overlap(tmp_path):
    """The legend and the formula block each own a band, so they cannot collide."""
    ranking = make_ranking(15)
    overlaps = []
    original = Figure.savefig

    def spy(self, *args, **kw):
        self.canvas.draw()
        renderer = self.canvas.get_renderer()
        footers = [t for ax in self.axes for t in ax.texts
                   if "FORMULA" in t.get_text().upper() or "PENAL" in t.get_text().upper()]
        legends = [ax.get_legend() for ax in self.axes if ax.get_legend() is not None]
        for foot in footers:
            fb = foot.get_window_extent(renderer)
            for legend in legends:
                lb = legend.get_window_extent(renderer)
                if fb.overlaps(lb):
                    overlaps.append((fb, lb))
        return original(self, *args, **kw)

    Figure.savefig = spy
    try:
        render_chart(ranking, Weights(), Translator("en"), tmp_path,
                     clan_name="Test Clan", clan_tag="#T", season="2026-10-02", rounds=7)
    finally:
        Figure.savefig = original
    assert not overlaps


def test_chart_file_is_written(tmp_path):
    path, _ = render_and_measure(tmp_path, make_ranking(10))
    assert path.exists() and path.stat().st_size > 5000


# ------------------------------------------------------------- degenerate input
def test_all_zero_scores_do_not_warp_the_axis(tmp_path):
    """The original divided its column positions by a zero maximum."""
    ranking = make_ranking(5, totals=[0.0] * 5)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        render_and_measure(tmp_path, ranking)
    bad = [w for w in caught if "singular" in str(w.message).lower()]
    assert not bad, f"matplotlib complained about a degenerate axis: {bad}"


def test_empty_ranking_renders(tmp_path):
    ranking = build_ranking(result_with([]), bonuses=7)
    path, _ = render_and_measure(tmp_path, ranking)
    assert path.exists()


def test_single_player_renders(tmp_path):
    path, measured = render_and_measure(tmp_path, make_ranking(1, bonuses=1))
    assert path.exists()
    assert measured["min_y0"] >= -0.5


def test_more_bonuses_than_players_renders(tmp_path):
    path, _ = render_and_measure(tmp_path, make_ranking(3, bonuses=7))
    assert path.exists()


# ------------------------------------------------------------------ content
def test_tie_is_labelled_in_the_chart(tmp_path):
    ranking = make_ranking(6, bonuses=3, tie=True)
    assert any(rp.tied for rp in ranking.ranked)
    seen: dict[str, str] = {}
    original = Figure.savefig

    def spy(self, *args, **kw):
        seen["labels"] = " ".join(
            tick.get_text() for ax in self.axes for tick in ax.get_yticklabels())
        return original(self, *args, **kw)

    Figure.savefig = spy
    try:
        render_chart(ranking, Weights(), Translator("en"), tmp_path,
                     clan_name="C", clan_tag="#T", season="2026-10-02", rounds=7)
    finally:
        Figure.savefig = original
    assert "tie" in seen["labels"].lower()


def test_localised_chart_uses_the_spanish_catalog(tmp_path):
    ranking = make_ranking(5)
    seen: dict[str, str] = {}
    original = Figure.savefig

    def spy(self, *args, **kw):
        seen["text"] = " ".join(txt.get_text() for ax in self.axes for txt in ax.texts)
        return original(self, *args, **kw)

    Figure.savefig = spy
    try:
        render_chart(ranking, Weights(), Translator("es"), tmp_path,
                     clan_name="Clan", clan_tag="#T", season="2026-10-02", rounds=7)
    finally:
        Figure.savefig = original
    assert "PUNTUACIÓN" in seen["text"].upper()
    assert "penalización" in seen["text"].lower()


def test_cut_tie_note_replaces_the_margin_note(tmp_path):
    ranking = build_ranking(
        result_with([("A", 10.0, 7), ("B", 9.0, 7), ("T1", 8.0, 7), ("T2", 8.0, 7)]),
        bonuses=3)
    assert ranking.has_cut_tie
    seen: dict[str, str] = {}
    original = Figure.savefig

    def spy(self, *args, **kw):
        seen["text"] = " ".join(txt.get_text() for ax in self.axes for txt in ax.texts)
        return original(self, *args, **kw)

    Figure.savefig = spy
    try:
        render_chart(ranking, Weights(), Translator("en"), tmp_path,
                     clan_name="C", clan_tag="#T", season="2026-10-02", rounds=7)
    finally:
        Figure.savefig = original
    assert "TIE" in seen["text"].upper()
    assert "T1" in seen["text"] and "T2" in seen["text"]


# -------------------------------------------------------------------- helpers
def test_fmt_never_emits_negative_zero():
    assert fmt(-0.0) == "0.00"
    assert fmt(-0.001) == "0.00"
    assert fmt(-0.5) == "-0.50"
    assert fmt(26.495) == "26.50" or fmt(26.495) == "26.49"
