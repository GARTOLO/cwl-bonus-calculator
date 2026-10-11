"""Minimal i18n layer.

One JSON catalog per language under ``locales/``. Adding a language is adding a
file - no code changes. Keys are dotted namespaces (``table.player``); the
``_meta`` block holds the language code and its display name and is excluded
from key-parity checks.
"""
from __future__ import annotations

import json
import locale as _locale
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

LOCALES_DIR = Path(__file__).parent / "locales"
FALLBACK = "en"
META_KEY = "_meta"


def available_languages() -> dict[str, str]:
    """Returns {code: display_name} for every catalog on disk."""
    out: dict[str, str] = {}
    for path in sorted(LOCALES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        meta = data.get(META_KEY, {})
        out[path.stem] = meta.get("name", path.stem)
    return out


@lru_cache(maxsize=None)
def catalog(lang: str) -> dict[str, str]:
    """Loads a catalog, falling back to English for any missing key."""
    base: dict[str, str] = {}
    fb = LOCALES_DIR / f"{FALLBACK}.json"
    if fb.exists():
        base = json.loads(fb.read_text(encoding="utf-8"))
    if lang != FALLBACK:
        path = LOCALES_DIR / f"{lang}.json"
        if path.exists():
            base = {**base, **json.loads(path.read_text(encoding="utf-8"))}
    return base


def resolve_lang(cli_lang: str | None = None) -> str:
    """CLI flag > CWL_LANG env var > system locale > English."""
    langs = available_languages()
    candidates: list[str | None] = [cli_lang, os.getenv("CWL_LANG")]
    try:
        sysloc = _locale.getlocale()[0]
    except (ValueError, TypeError):
        sysloc = None
    if sysloc:
        candidates.append(sysloc)
    for cand in candidates:
        if not cand:
            continue
        code = str(cand).replace("-", "_").split("_")[0].strip().lower()
        if code in langs:
            return code
    return FALLBACK if FALLBACK in langs else next(iter(langs), FALLBACK)


class Translator:
    """Callable translator bound to one language."""

    def __init__(self, lang: str) -> None:
        self.lang = lang
        self._data = catalog(lang)

    def __call__(self, key: str, **kwargs: Any) -> str:
        text = self._data.get(key, key)
        if not kwargs:
            return text
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            # A catalog mistake must never crash a run mid-season.
            return text

    def month(self, number: int) -> str:
        return self(f"months.{int(number)}")

    def season_label(self, season: str | None) -> str:
        """'2026-10-02' -> 'October 2026' (localised). Falls back to the raw value."""
        if not season:
            return ""
        parts = str(season).split("-")
        if len(parts) < 2:
            return str(season)
        try:
            month = int(parts[1])
        except ValueError:
            return str(season)
        # A missing month key must fall back to the raw value, never leak the key.
        if f"months.{month}" not in self._data:
            return str(season)
        return f"{self.month(month)} {parts[0]}"
