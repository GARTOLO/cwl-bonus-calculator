"""Leaderboard chart — the default graphic for the clan chat.

Design goals, driven by how a clan actually reads this on a phone:

* **"Am I in?" is answered instantly.** Recipients get a raised card, an emerald bar
  and full-brightness text; everyone else is visibly dimmed. No legend needed.
* **Legible when scaled down.** A narrow canvas (10.4in) with large type keeps each
  glyph readable once the chat app fits the image to the screen width.
* **A list of people, not a bar chart with a side table.** Name and score share a
  line; the supporting numbers sit subordinate underneath.
* **Nothing touches a card edge.** Text ink and the magnitude bar each keep a measured
  inner margin (`CARD_PAD_X`, `LINE1_DY`, `LINE2_DY`) so the rounded frame never
  crowds the content it contains.

The previous bar-chart design is preserved verbatim in ``chart_classic.py`` and is
available with ``--style classic``.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless: charts go straight to disk
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

WIDTH_IN = 10.4
PAD_X = 0.30
PAD_TOP = 0.28
PAD_BOTTOM = 0.24
HEADER_IN = 1.18
ROW_IN = 0.68
BAND_IN = 0.50
FOOTER_IN = 0.84
MAX_ROWS = 30

CARD_GAP_IN = 0.07
CARD_PAD_X = 0.24      # inner horizontal padding: keeps text/bars off the card edge
BADGE_R_IN = 0.20
BAR_W_IN = 3.10
BAR_H_IN = 0.09
LINE1_DY = 0.115       # name + score line, relative to the card centre
LINE2_DY = -0.145      # meta + magnitude bar line

SKINS: dict[str, dict[str, str]] = {
    "dark": {
        "page": "#0e1420",
        "card_in": "#18222f",
        "card_out": "#121a26",
        "edge_in": "#2c4055",
        "edge_out": "#1a2431",
        "text": "#f2f6fc",
        "text_out": "#7f92ab",
        "muted": "#8497b0",
        "muted_out": "#5d6d84",
        "bar_in": "#34d399",
        "bar_out": "#2c3c52",
        "track": "#0b111b",
        "accent": "#34d399",
        "warn": "#f2b455",
        "gold": "#ffc94d",
        "silver": "#c9d3e0",
        "bronze": "#dd8f52",
        "neutral": "#233246",
        "on_medal": "#16120a",
        "on_neutral": "#a9bcd6",
        "line": "#f0b429",
        "pill_text": "#04231a",
        "title": "#ffffff",
    },
    "light": {
        "page": "#f6f8fc",
        "card_in": "#ffffff",
        "card_out": "#eef2f8",
        "edge_in": "#cddced",
        "edge_out": "#e1e8f1",
        "text": "#15202e",
        "text_out": "#8593a6",
        "muted": "#66788e",
        "muted_out": "#9aa8ba",
        "bar_in": "#10b981",
        "bar_out": "#d5dde9",
        "track": "#e7edf5",
        "accent": "#10b981",
        "warn": "#c9791f",
        "gold": "#d9a300",
        "silver": "#94a3b4",
        "bronze": "#b9712f",
        "neutral": "#e6ecf4",
        "on_medal": "#ffffff",
        "on_neutral": "#6d7d92",
        "line": "#d98324",
        "pill_text": "#ffffff",
        "title": "#16202e",
    },
}

MEDAL_KEYS = {1: "gold", 2: "silver", 3: "bronze"}


def fmt(value: float, decimals: int = 2) -> str:
    """Number formatting that never emits '-0.00'."""
    if abs(value) < 10 ** (-decimals) / 2:
        value = 0.0
    return f"{value:.{decimals}f}"


def _card(ax, x, y, w, h, *, face, edge, rounding=0.06, lw=1.0, alpha=1.0, z=1):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0,rounding_size={rounding}",
        linewidth=lw, facecolor=face, edgecolor=edge, alpha=alpha,
        mutation_aspect=1, zorder=z)
    ax.add_patch(patch)
    return patch


def _pill(ax, x, y, text, *, face, color, fontsize=9.5, pad=0.16, z=6):
    """A rounded label sized from the text, using an estimate (no render pass)."""
    width = len(text) * fontsize * 0.60 / 72.0 + 2 * pad
    height = fontsize * 1.85 / 72.0
    _card(ax, x, y - height / 2, width, height, face=face, edge=face,
          rounding=height / 2, z=z)
    ax.text(x + width / 2, y, text, ha="center", va="center", fontsize=fontsize,
            fontweight="bold", color=color, zorder=z + 1)
    return width


def _meta_line(rp, weights, t) -> str:
    """Supporting numbers, kept short so they can stay large enough to read."""
    p = rp.player
    bits = [f"TH{int(p.town_hall)}", f"{int(p.stars)}★",
            f"{int(p.attacks_used)}/{int(p.wars_played)}"]
    if weights.difficulty:
        bits.append(f"{t('v2.difficulty_short')} {p.difficulty_points:+.1f}")
    if p.attacks_missed:
        key = "v2.missed_one" if p.attacks_missed == 1 else "v2.missed_many"
        bits.append(f"{int(p.attacks_missed)} {t(key)} ({fmt(p.penalty_points)})")
    return "   ·   ".join(bits)


def render_chart(ranking, weights, t, output_dir: str | Path, *,
                 clan_name: str | None = None, clan_tag: str = "",
                 season: str | None = None, rounds: int | None = None,
                 filename: str = "ranking_final_api.png") -> Path:
    skin = getattr(weights, "skin", "dark")
    colours = SKINS.get(skin, SKINS["dark"])

    rows = ranking.ranked[:MAX_ROWS]
    n = len(rows)
    last_in = max((i for i, rp in enumerate(rows) if rp.gets_bonus), default=-1)
    show_band = 0 <= last_in < n - 1
    bonus_count = sum(1 for rp in rows if rp.gets_bonus)

    fig_h = (PAD_TOP + HEADER_IN + n * ROW_IN + (BAND_IN if show_band else 0.0)
             + FOOTER_IN + PAD_BOTTOM)
    fig = plt.figure(figsize=(WIDTH_IN, fig_h))
    fig.patch.set_facecolor(colours["page"])
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, WIDTH_IN)
    ax.set_ylim(0, fig_h)          # data units are INCHES: circles stay circular
    ax.set_axis_off()

    card_x0 = PAD_X
    card_x1 = WIDTH_IN - PAD_X
    content_w = card_x1 - card_x0
    inner_x0 = card_x0 + CARD_PAD_X
    inner_x1 = card_x1 - CARD_PAD_X
    badge_cx = inner_x0 + BADGE_R_IN * 0.86
    text_x = badge_cx + BADGE_R_IN * 0.86 + 0.18

    # ---------------------------------------------------------------- header
    top = fig_h - PAD_TOP
    ax.text(card_x0, top - 0.26, (clan_name or t("app.name")).upper(), ha="left",
            va="center", fontsize=21, fontweight="bold", color=colours["title"])
    subtitle = "   ·   ".join(filter(None, [
        t("v2.league"), t.season_label(season) or None,
        t("v2.rounds", rounds=rounds) if rounds else None]))
    ax.text(card_x0, top - 0.60, f"{clan_tag}   ·   {subtitle}", ha="left", va="center",
            fontsize=9.5, color=colours["muted"])
    ax.plot([card_x0, card_x1], [top - 0.80, top - 0.80], color=colours["edge_out"],
            linewidth=1.0, zorder=1)

    # ------------------------------------------------- summary strip (pills)
    strip_y = top - 1.00
    cursor = card_x0
    cursor += _pill(ax, cursor, strip_y, t("v2.bonus_pill", n=ranking.bonuses),
                    face=colours["accent"], color=colours["pill_text"], fontsize=9.5) + 0.12
    cursor += _pill(ax, cursor, strip_y, t("v2.players_pill", n=n),
                    face=colours["neutral"], color=colours["on_neutral"], fontsize=9.5) + 0.12
    if weights.difficulty:
        cursor += _pill(ax, cursor, strip_y, t("v2.weight_pill",
                                               weight=fmt(weights.difficulty, 2)),
                        face=colours["neutral"], color=colours["on_neutral"],
                        fontsize=9.5) + 0.12
    if ranking.cut_margin is not None:
        ax.text(inner_x1, strip_y, t("v2.cut_margin", margin=f"{ranking.cut_margin:+.2f}"),
                ha="right", va="center", fontsize=9.5, fontweight="bold",
                color=colours["muted"])

    # ------------------------------------------------------------------ rows
    max_score = max((rp.player.total for rp in rows), default=1.0) or 1.0
    rows_top = top - HEADER_IN

    def row_center(index: int) -> float:
        """Centre of row ``index``. Rows after the cut drop by the band height.

        The band needs its OWN space: without the offset the cut line and its
        label are drawn inside the first excluded card, and the label lands on
        top of that row's magnitude bar.
        """
        shifted = BAND_IN if (show_band and index > last_in) else 0.0
        return rows_top - index * ROW_IN - ROW_IN / 2 - shifted

    for i, rp in enumerate(rows):
        p = rp.player
        inside = rp.gets_bonus
        cy = row_center(i)
        card_h = ROW_IN - CARD_GAP_IN
        y1 = cy + LINE1_DY
        y2 = cy + LINE2_DY

        _card(ax, card_x0, cy - card_h / 2, content_w, card_h,
              face=colours["card_in"] if inside else colours["card_out"],
              edge=colours["edge_in"] if inside else colours["edge_out"],
              lw=1.1 if inside else 0.9, z=1)

        # rank badge
        if rp.rank in MEDAL_KEYS and not rp.tied:
            face, ink = colours[MEDAL_KEYS[rp.rank]], colours["on_medal"]
        elif inside:
            face, ink = colours["neutral"], colours["on_neutral"]
        else:
            face, ink = colours["card_out"], colours["text_out"]
        ax.add_patch(plt.Circle((badge_cx, cy), BADGE_R_IN * 0.86, facecolor=face,
                                edgecolor=colours["edge_in"] if inside else colours["edge_out"],
                                linewidth=1.0, zorder=3))
        ax.text(badge_cx, cy, f"{rp.rank}º", ha="center", va="center",
                fontsize=10.5 if rp.rank < 10 else 9.5, fontweight="bold",
                color=ink, zorder=4)

        # name and score share a line, both inset from the card edges
        name = p.name + (f"  ({t('table.note_tie')})" if rp.tied else "")
        ax.text(text_x, y1, name, ha="left", va="center", fontsize=13.5,
                fontweight="bold", color=colours["text"] if inside else colours["text_out"],
                zorder=4)
        ax.text(inner_x1, y1, fmt(p.total), ha="right", va="center", fontsize=16,
                fontweight="bold",
                color=colours["text"] if inside else colours["text_out"], zorder=4)

        # supporting numbers, deliberately subordinate
        ax.text(text_x, y2, _meta_line(rp, weights, t), ha="left", va="center",
                fontsize=8.7, color=colours["muted"] if inside else colours["muted_out"],
                zorder=4)

        # magnitude bar, right aligned under the score and inset from the edge
        bar_x1 = inner_x1
        bar_x0 = bar_x1 - BAR_W_IN
        bar_y = y2 - BAR_H_IN / 2
        _card(ax, bar_x0, bar_y, BAR_W_IN, BAR_H_IN, face=colours["track"],
              edge=colours["track"], rounding=BAR_H_IN / 2, z=2)
        ratio = max(0.0, min(1.0, p.total / max_score))
        fill_w = max(ratio * BAR_W_IN, BAR_H_IN)
        _card(ax, bar_x0, bar_y, fill_w, BAR_H_IN,
              face=colours["bar_in"] if inside else colours["bar_out"],
              edge=colours["bar_in"] if inside else colours["bar_out"],
              rounding=BAR_H_IN / 2, z=3)

        if weights.use_defense and p.defense_points:
            ax.text(bar_x0 - 0.12, y2, f"+{fmt(p.defense_points)} {t('table.defense').lower()}",
                    ha="right", va="center", fontsize=7.8, color=colours["muted_out"],
                    zorder=4)

    # ------------------------------------------------------------ bonus cut
    if show_band:
        # Centre of the reserved band: exactly between the last card that gets a
        # bonus and the first that does not.
        band_cy = rows_top - (last_in + 1) * ROW_IN - BAND_IN / 2
        ax.plot([card_x0, card_x1], [band_cy, band_cy], color=colours["line"],
                linewidth=1.6, linestyle=(0, (5, 3)), zorder=5, alpha=0.85)
        if ranking.has_cut_tie:
            label = t("warn.tie_at_cut_short", players=" / ".join(ranking.cut_tie),
                      score=fmt(ranking.cut_tie_score or 0.0))
            ink = colours["warn"]
        else:
            label = t("v2.cut_band", n=bonus_count)
            ink = colours["line"]
        # Centred: right-aligning it would cover the next row's magnitude bar.
        ax.text(card_x0 + content_w / 2, band_cy, f"  {label}  ", ha="center",
                va="center", fontsize=9.4, fontweight="bold", color=ink, zorder=6,
                bbox={"boxstyle": "round,pad=0.36", "facecolor": colours["page"],
                      "edgecolor": ink, "linewidth": 1.2})

    # --------------------------------------------------------------- footer
    foot_y = rows_top - n * ROW_IN - (BAND_IN if show_band else 0.0)
    legend_y = foot_y - 0.20
    swatch = 0.16
    x = card_x0
    for colour_key, label in (("bar_in", t("v2.legend_in")), ("bar_out", t("v2.legend_out"))):
        _card(ax, x, legend_y - swatch / 2, swatch * 1.9, swatch,
              face=colours[colour_key], edge=colours[colour_key],
              rounding=swatch / 2.6, z=3)
        ax.text(x + swatch * 1.9 + 0.10, legend_y, label, ha="left", va="center",
                fontsize=9.0, color=colours["muted"])
        x += swatch * 1.9 + 0.10 + len(label) * 0.062 + 0.34

    ax.text(card_x0, legend_y - 0.27, t("v2.formula", weight=fmt(weights.difficulty, 2),
                                        penalty=fmt(weights.missed_attack, 2)),
            ha="left", va="center", fontsize=8.5, color=colours["muted_out"])
    ax.text(inner_x1, legend_y - 0.27, t("app.name"), ha="right", va="center",
            fontsize=8.5, color=colours["muted_out"])

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / filename
    fig.savefig(out, facecolor=fig.get_facecolor(), edgecolor="none", dpi=160)
    plt.close(fig)
    return out
