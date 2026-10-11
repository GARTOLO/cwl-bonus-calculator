#!/usr/bin/env python3
"""Run the calculator straight from a checkout, with no install step.

    python run.py --bonuses 8 --lang es

Handy on Windows, where the console script needs the virtualenv activated first.
It only needs the runtime dependencies to be present:

    pip install -r requirements.txt

If you have done `pip install -e .` you may prefer the installed entry point
(`cwl-bonus ...`) or `python -m cwlbonus ...`; all three run identical code.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

try:
    from cwlbonus.cli import main
except ModuleNotFoundError as exc:  # a dependency is missing, not the package
    missing = exc.name or "a dependency"
    sys.exit(
        f"\nCould not import {missing}.\n"
        "Install the runtime dependencies first:\n\n"
        "    pip install -r requirements.txt\n"
    )

if __name__ == "__main__":
    raise SystemExit(main())
