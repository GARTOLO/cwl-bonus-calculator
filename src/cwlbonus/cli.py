"""Command line entry point.

Usage:
    cwl-bonus --bonuses 7 --preset balanced
    python -m cwlbonus --lang es -d
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from . import __version__
from .config import PRESETS, Weights, resolve_weights
from .fetch import FetchError, dump_season, fetch_season, normalise_tag
from .i18n import Translator, available_languages, resolve_lang
from .ranking import build_ranking
from .scoring import score_season
from .table import build_report
from .chart import render_chart

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_CANCELLED = 130


def _pre_parser() -> argparse.ArgumentParser:
    """Lets --lang be read before the translated help text is built."""
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--lang", default=None)
    pre.add_argument("--list-langs", action="store_true")
    return pre


def build_parser(t: Translator) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cwl-bonus", description=t("cli.description"))
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--bonuses", type=int, default=None, help=t("cli.bonuses"))
    parser.add_argument("-d", "--defense", action="store_true", help=t("cli.defense"))
    parser.add_argument("--output", default="./output", help=t("cli.output"))
    parser.add_argument("--lang", default=None, help=t("cli.lang"))
    parser.add_argument("--min-wars", type=int, default=None, help=t("cli.min_wars"))
    parser.add_argument("--preset", choices=sorted(PRESETS), default=None,
                        help=f"{t('cli.preset')} {t('cli.preset_help')}")
    parser.add_argument("--difficulty", type=float, default=None, help=t("cli.difficulty"))
    parser.add_argument("--rusher-cap", type=int, default=None, help=t("cli.rusher_cap"))
    parser.add_argument("--no-defense-policy", dest="no_defense_policy", default=None,
                        choices=["neutral", "min", "max"], help=t("cli.no_defense_policy"))
    parser.add_argument("--config", default=None, help=t("cli.config"))
    parser.add_argument("--debug", action="store_true", help=t("cli.debug"))
    parser.add_argument("--list-langs", action="store_true", help=t("cli.list_langs"))
    return parser


def _weights_from_args(args, t: Translator) -> Weights:
    overrides = {
        "bonuses": args.bonuses,
        "use_defense": True if args.defense else None,
        "min_wars": args.min_wars,
        "difficulty": args.difficulty,
        "rusher_max_cut": args.rusher_cap,
        "no_defense_policy": args.no_defense_policy,
    }
    return resolve_weights(preset=args.preset, config_path=args.config, overrides=overrides)


async def _run(args, weights: Weights, t: Translator) -> int:
    import coc  # imported late so --help works without the SDK present

    email = os.getenv("COC_EMAIL")
    password = os.getenv("COC_PASSWORD")
    clan_tag_raw = os.getenv("CLAN_TAG")
    missing = [name for name, value in (("COC_EMAIL", email), ("COC_PASSWORD", password),
                                        ("CLAN_TAG", clan_tag_raw)) if not value]
    if missing:
        print("!!  " + t("error.missing_env", vars=", ".join(missing)), file=sys.stderr)
        return EXIT_ERROR

    print(t("log.logging_in"))
    async with coc.Client() as client:
        try:
            await client.login(email, password)
        except coc.InvalidCredentials:
            print("!!  " + t("error.bad_credentials"), file=sys.stderr)
            return EXIT_ERROR

        print(t("log.fetching"))
        try:
            season = await fetch_season(client, clan_tag_raw)
        except FetchError as exc:
            print("!!  " + t(exc.key, **exc.kwargs), file=sys.stderr)
            return EXIT_ERROR

    if not season.wars:
        print("!!  " + t("error.no_players"), file=sys.stderr)
        return EXIT_ERROR

    result = score_season(season, weights)
    if not result.players:
        print("!!  " + t("error.no_players"), file=sys.stderr)
        return EXIT_ERROR

    ranking = build_ranking(result, bonuses=weights.bonuses, min_wars=weights.min_wars)

    print(t("log.attacks_processed", attacks=result.attacks_processed,
            wars=result.wars_processed))
    print(t("log.scoring", players=len(result.players)))
    print()
    print(build_report(ranking, result, weights, t))

    chart_path = render_chart(ranking, weights, t, args.output,
                              clan_name=season.clan_name, clan_tag=season.clan_tag,
                              season=season.season, rounds=result.wars_processed)
    print()
    print(t("log.chart_saved", path=chart_path))

    if args.debug:
        debug_path = dump_season(season, Path(args.output) / "season_debug.json")
        print(t("log.debug_saved", path=debug_path))

    if ranking.has_cut_tie:
        # A tie on the cut is a policy decision, not something to guess at.
        return EXIT_ERROR
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    load_dotenv()

    pre = _pre_parser()
    pre_args, _ = pre.parse_known_args(argv)

    if pre_args.list_langs:
        langs = available_languages()
        t = Translator(resolve_lang(pre_args.lang))
        print(t("log.langs_available",
                langs=", ".join(f"{code} ({name})" for code, name in langs.items())))
        return EXIT_OK

    requested = pre_args.lang or os.getenv("CWL_LANG")
    lang = resolve_lang(pre_args.lang)
    t = Translator(lang)
    if requested and requested != lang and str(requested).split("_")[0] != lang:
        print("!!  " + t("error.unknown_lang", lang=requested), file=sys.stderr)

    args = build_parser(t).parse_args(argv)
    try:
        weights = _weights_from_args(args, t)
    except ValueError as exc:
        print(f"!!  {exc}", file=sys.stderr)
        return EXIT_ERROR

    try:
        return asyncio.run(_run(args, weights, t))
    except KeyboardInterrupt:
        print("\n" + t("error.cancelled"), file=sys.stderr)
        return EXIT_CANCELLED


if __name__ == "__main__":
    raise SystemExit(main())
