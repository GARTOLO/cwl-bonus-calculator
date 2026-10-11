"""Terminal report: warnings, then the ranking table."""
from __future__ import annotations

from tabulate import tabulate

from .chart import fmt
from .config import Weights
from .ranking import Ranking
from .scoring import SeasonResult


def build_warnings(ranking: Ranking, result: SeasonResult, weights: Weights, t) -> list[str]:
    """Every caveat that a human needs to see BEFORE trusting the numbers."""
    warnings: list[str] = []

    if ranking.has_cut_tie:
        warnings.append("!!  " + t("warn.tie_at_cut",
                                   players=", ".join(ranking.cut_tie),
                                   score=fmt(ranking.cut_tie_score or 0.0),
                                   bonuses=ranking.bonuses))

    missed = [p for p in result.players if p.attacks_missed]
    if missed:
        warnings.append(t("warn.missed", count=len(missed),
                          penalty=fmt(weights.missed_attack)))

    if ranking.ineligible:
        warnings.append(t("warn.ineligible", count=len(ranking.ineligible),
                          min_wars=ranking.min_wars))

    if result.rusher_corrections:
        warnings.append(t("warn.rusher_correction",
                          count=len(result.rusher_corrections)))

    if not result.wars_processed:
        warnings.append(t("warn.empty_season"))
    return warnings


def build_table(ranking: Ranking, weights: Weights, t) -> str:
    headers = [t("table.rank"), t("table.player"), t("table.th"), t("table.total"),
               t("table.stars"), t("table.attacks"), t("table.difficulty")]
    if weights.use_defense:
        headers.append(t("table.defense"))
    headers += [t("table.missed"), t("table.penalty"), t("table.status")]

    rows = []
    for rp in ranking.ranked:
        p = rp.player
        if not rp.eligible:
            status = t("table.status_ineligible")
        elif rp.gets_bonus:
            status = t("table.status_bonus")
        else:
            status = t("table.status_out")
        if rp.tied:
            status = f"{status} ({t('table.note_tie')})"

        row = [rp.rank, p.name, f"TH{int(p.town_hall)}", fmt(p.total),
               int(p.stars), f"{int(p.attacks_used)}/{int(p.wars_played)}",
               f"{fmt(p.difficulty_points, 2)}"]
        if weights.use_defense:
            row.append(fmt(p.defense_points))
        row += [int(p.attacks_missed), fmt(p.penalty_points), status]
        rows.append(row)

    return tabulate(rows, headers=headers, tablefmt="fancy_grid", showindex=False,
                    stralign="center", numalign="center")


def build_report(ranking: Ranking, result: SeasonResult, weights: Weights, t) -> str:
    lines: list[str] = []
    for warning in build_warnings(ranking, result, weights, t):
        lines.append(warning)
    if lines:
        lines.append("")

    title = t("table.title")
    subtitle = t("table.subtitle", bonuses=ranking.bonuses,
                 rounds=result.wars_processed, weight=fmt(weights.difficulty, 2))
    width = max(len(title), len(subtitle)) + 8
    lines += [title.center(width), subtitle.center(width), ""]
    lines.append(build_table(ranking, weights, t))
    return "\n".join(lines)
