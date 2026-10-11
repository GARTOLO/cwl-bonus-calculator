"""LEGACY chart design: the original horizontal bar chart with a side table.

Kept verbatim behind ``--style classic`` so a clan can compare the two designs, and
so the regression that motivated the layout rewrite stays covered by tests: the
original positioned its footer at a fraction of a figure whose height depended on
the number of players, which truncated the formula block for any roster smaller
than about nine players.

The default is now the leaderboard design in ``chart.py``.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless: charts go straight to disk
import matplotlib.pyplot as plt

PALETTE = {
    "base": "#f4f6fb", "mantle": "#e7ebf3", "surface": "#ffffff",
    "overlay": "#c9d2e0", "grid": "#dde3ee", "text": "#2b3a55",
    "subtext": "#6b7a92", "green": "#3aa272", "blue": "#5b8def",
    "red": "#e8836f", "peach": "#e0955a", "gold": "#c99700",
    "title": "#3a4a75", "gray": "#aab4c4",
}
MEDALS = {1: "#d9a300", 2: "#8a94a6", 3: "#bf7a3a"}

WIDTH_IN = 16.0
ROW_H_IN = 0.42
HEADER_IN = 1.20
LEGEND_IN = 0.62
XLABEL_IN = 0.52          # room for the x tick labels + axis title under the plot
PAD_BOTTOM_IN = 0.14
PAD_TOP_IN = 0.18
MIN_AXES_IN = 3.2
FOOTER_BASE_IN = 0.40
FOOTER_LINE_IN = 0.28
MAX_ROWS = 30

PLOT_LEFT_MIN = 0.075
PLOT_LEFT_MAX = 0.36
PLOT_RIGHT = 0.975


def fmt(value: float, decimals: int = 2) -> str:
    """Number formatting that never emits '-0.00'."""
    if abs(value) < 10 ** (-decimals) / 2:
        value = 0.0
    return f"{value:.{decimals}f}"


def _formula_lines(t, w) -> list[tuple[str, str]]:
    lo, hi = w.difficulty_clamp
    lines = [
        (t("chart.formula_attack", weight=fmt(w.difficulty, 2)), PALETTE["text"]),
        (t("chart.formula_difficulty", cap=w.rusher_max_cut,
           lo=fmt(lo, 0), hi=fmt(hi, 0)), PALETTE["subtext"]),
    ]
    if w.use_defense:
        lines.append((t("chart.formula_defense"), PALETTE["text"]))
    lines.append((t("chart.formula_penalty", penalty=fmt(w.missed_attack, 2)),
                  PALETTE["red"]))
    return lines


def render_chart(ranking, weights, t, output_dir: str | Path, *,
                 clan_name: str | None = None, clan_tag: str = "",
                 season: str | None = None, rounds: int | None = None,
                 filename: str = "ranking_final_api.png") -> Path:
    rows = ranking.ranked[:MAX_ROWS]
    n = len(rows)
    bonus_count = max(0, min(ranking.bonuses, n))

    # Ascending order so the best player sits at the top of a barh plot.
    plot = list(reversed(rows))
    scores = [rp.player.total for rp in rows]
    max_score = max(scores) if scores else 0.0
    for_zero = max_score <= 0.0
    scale = max_score if not for_zero else 1.0

    formula = _formula_lines(t, weights)
    axes_h = max(MIN_AXES_IN, ROW_H_IN * max(n, 3))
    footer_h = FOOTER_BASE_IN + FOOTER_LINE_IN * len(formula)
    fig_h = (PAD_BOTTOM_IN + footer_h + LEGEND_IN + XLABEL_IN + axes_h
             + HEADER_IN + PAD_TOP_IN)

    def frac(inches: float) -> float:
        return inches / fig_h

    fig = plt.figure(figsize=(WIDTH_IN, fig_h))
    fig.patch.set_facecolor(PALETTE["base"])

    y_legend = frac(PAD_BOTTOM_IN + footer_h)
    y_axes = frac(PAD_BOTTOM_IN + footer_h + LEGEND_IN + XLABEL_IN)
    y_header = frac(PAD_BOTTOM_IN + footer_h + LEGEND_IN + XLABEL_IN + axes_h)
    ax = fig.add_axes([0.085, y_axes, 0.80, frac(axes_h)])
    ax_leg = fig.add_axes([0.0, y_legend, 1.0, frac(LEGEND_IN)])
    ax_foot = fig.add_axes([0.0, frac(PAD_BOTTOM_IN), 1.0, frac(footer_h)])
    ax_head = fig.add_axes([0.0, y_header, 1.0, frac(HEADER_IN)])
    for spare in (ax_leg, ax_foot, ax_head):
        spare.set_axis_off()

    ax.set_facecolor(PALETTE["base"])

    # ---- header -----------------------------------------------------------
    ax_head.text(0.5, 0.74, (clan_name or t("app.name")).upper(), ha="center", va="center",
                 fontsize=24, fontweight="bold", color=PALETTE["title"],
                 transform=ax_head.transAxes)
    subtitle = t("chart.subtitle", bonuses=ranking.bonuses,
                 weight=fmt(weights.difficulty, 2),
                 rounds=rounds if rounds else "-",
                 season=t.season_label(season) or "-")
    ax_head.text(0.5, 0.18, f"{clan_tag}   -   {subtitle}", ha="center", va="center",
                 fontsize=12.5, fontweight="bold", color=PALETTE["green"],
                 transform=ax_head.transAxes)

    if n == 0:
        ax.text(0.5, 0.5, t("error.no_players"), ha="center", va="center",
                fontsize=14, color=PALETTE["subtext"], transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
    else:
        y = list(range(n))
        ylim_lo, ylim_hi = -0.75, n - 0.25

        if bonus_count > 0:
            ax.axhspan(n - bonus_count - 0.5, ylim_hi, color=PALETTE["green"],
                       alpha=0.09, zorder=0)
            ax.axhspan(ylim_lo, n - bonus_count - 0.5, color=PALETTE["mantle"],
                       alpha=0.75, zorder=0)

        atk = [rp.player.attack_points for rp in plot]
        colors = [PALETTE["blue"] if i >= n - bonus_count else PALETTE["gray"]
                  for i in range(n)]
        ax.barh(y, atk, color=colors, height=0.62, edgecolor=PALETTE["base"],
                linewidth=0.8, zorder=3)
        if weights.use_defense:
            defense = [rp.player.defense_points for rp in plot]
            dcol = [PALETTE["red"] if i >= n - bonus_count else "#d9b0a6"
                    for i in range(n)]
            ax.barh(y, defense, left=atk, color=dcol, height=0.62,
                    edgecolor=PALETTE["base"], linewidth=0.8, zorder=3)

        # ---- stat columns -------------------------------------------------
        x_total = scale * 1.03
        x_stars = scale * 1.20
        x_atq = scale * 1.33
        x_th = scale * 1.44
        x_miss = scale * 1.53

        any_miss = any(rp.player.attacks_missed for rp in rows)
        headers = [(x_total, t("table.total"), PALETTE["gold"]),
                   (x_stars, t("table.stars"), PALETTE["text"]),
                   (x_atq, t("table.attacks"), PALETTE["text"]),
                   (x_th, t("table.th"), PALETTE["text"])]
        if any_miss:
            headers.append((x_miss, t("table.missed"), PALETTE["red"]))
        for xpos, label, colour in headers:
            ax.text(xpos, n - 0.36, label, ha="left", va="center", fontsize=10,
                    fontweight="bold", color=colour, zorder=5)

        for i, rp in enumerate(plot):
            inside = i >= n - bonus_count
            colour = PALETTE["text"] if inside else PALETTE["subtext"]
            p = rp.player
            ax.text(x_total, i, fmt(p.total), ha="left", va="center", fontsize=11.5,
                    fontweight="bold", color=PALETTE["gold"] if inside else PALETTE["subtext"],
                    zorder=5)
            ax.text(x_stars, i, str(int(p.stars)), ha="left", va="center", fontsize=11,
                    color=colour, zorder=5)
            ax.text(x_atq, i, f"{int(p.attacks_used)}/{int(p.wars_played)}", ha="left",
                    va="center", fontsize=11, color=colour, zorder=5)
            ax.text(x_th, i, f"TH{int(p.town_hall)}", ha="left", va="center", fontsize=11,
                    color=colour, zorder=5)
            if any_miss and p.attacks_missed:
                ax.text(x_miss, i, fmt(p.penalty_points), ha="left", va="center",
                        fontsize=10.5, fontweight="bold", color=PALETTE["red"], zorder=5)

        # ---- names with rank, medals and tie markers ----------------------
        labels = []
        for rp in plot:
            label = f"{rp.rank}\u00ba   {rp.player.name}"
            if rp.tied:
                label += f"  ({t('table.note_tie')})"
            labels.append(label)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=12)
        for tick, rp in zip(ax.get_yticklabels(), plot):
            if rp.rank in MEDALS and not rp.tied:
                tick.set_color(MEDALS[rp.rank])
                tick.set_fontweight("bold")
            elif rp.tied:
                tick.set_color(PALETTE["peach"])
                tick.set_fontweight("bold")
            elif rp.gets_bonus:
                tick.set_color(PALETTE["text"])
            else:
                tick.set_color(PALETTE["subtext"])

        # ---- bonus cut line ----------------------------------------------
        if 0 < bonus_count < len([r for r in rows if r.eligible]):
            cut_y = n - bonus_count - 0.5
            ax.axhline(y=cut_y, color=PALETTE["peach"], linestyle=(0, (6, 4)),
                       linewidth=2.2, alpha=0.9, zorder=4)
            margin = ranking.cut_margin if ranking.cut_margin is not None else 0.0
            note = t("chart.cut", n=bonus_count, next=bonus_count + 1,
                     margin=f"{margin:+.2f}")
            if ranking.has_cut_tie:
                note = t("warn.tie_at_cut", players=", ".join(ranking.cut_tie),
                         score=fmt(ranking.cut_tie_score or 0.0),
                         bonuses=bonus_count)
            ax.text(scale * 0.985, cut_y - 0.12, note, ha="right", va="top", fontsize=10.5,
                    fontweight="bold", color=PALETTE["peach"], zorder=5,
                    bbox={"boxstyle": "round,pad=0.35", "facecolor": PALETTE["base"],
                          "edgecolor": PALETTE["peach"], "linewidth": 1.2, "alpha": 0.95})

        if for_zero:
            ax.text(0.5, 0.5, t("chart.all_zero"), ha="center", va="center",
                    fontsize=13, color=PALETTE["red"], fontweight="bold",
                    transform=ax.transAxes, zorder=6)

        # ---- axes furniture ----------------------------------------------
        ax.set_xlim(0, scale * 1.62)
        ax.set_ylim(ylim_lo, ylim_hi)
        ax.grid(axis="x", linestyle="--", alpha=0.30, color=PALETTE["grid"], zorder=1)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(PALETTE["grid"])
        ax.tick_params(axis="x", colors=PALETTE["subtext"])
        ax.tick_params(axis="y", length=0)
        ax.set_xlabel(t("chart.x_label"), color=PALETTE["subtext"], fontsize=11, labelpad=8)

    # ---- two pass left margin --------------------------------------------
    # y tick labels are drawn OUTSIDE the axes, so a fixed left margin clips long
    # player names. Measure the widest label, then widen the margin to fit it.
    fig.canvas.draw()
    widest = max((lbl.get_window_extent(fig.canvas.get_renderer()).width
                  for lbl in ax.get_yticklabels()), default=0.0)
    left = min(PLOT_LEFT_MAX, max(PLOT_LEFT_MIN, (widest / fig.dpi + 0.18) / WIDTH_IN))
    ax.set_position([left, y_axes, PLOT_RIGHT - left, frac(axes_h)])

    # ---- legend (own band: cannot overlap the footer) --------------------
    handles = [plt.Rectangle((0, 0), 1, 1, color=PALETTE["blue"])]
    labels = [t("chart.legend_attack")]
    if weights.use_defense:
        handles.append(plt.Rectangle((0, 0), 1, 1, color=PALETTE["red"]))
        labels.append(t("chart.legend_defense"))
    handles.append(plt.Rectangle((0, 0), 1, 1, color=PALETTE["green"], alpha=0.35))
    labels.append(t("chart.bonus_zone"))
    legend = ax_leg.legend(handles, labels, loc="center", ncol=len(labels), frameon=True,
                           facecolor=PALETTE["surface"], edgecolor=PALETTE["overlay"],
                           fontsize=10.5, labelcolor=PALETTE["text"])
    legend.get_frame().set_alpha(0.97)

    # ---- footer formula block (own band: cannot be clipped) --------------
    body = "\n".join(text for text, _ in formula)
    ax_foot.text(0.5, 0.5, f"{t('chart.formula_title')}\n{body}", ha="center", va="center",
                 fontsize=10.5, linespacing=1.7, color=PALETTE["text"],
                 bbox={"boxstyle": "round,pad=0.6", "facecolor": PALETTE["surface"],
                       "edgecolor": PALETTE["overlay"], "linewidth": 1.5, "alpha": 0.97})

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / filename
    fig.savefig(out, facecolor=fig.get_facecolor(), edgecolor="none", dpi=150)
    plt.close(fig)
    return out
