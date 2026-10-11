"""i18n: catalog integrity and translator behaviour."""
from __future__ import annotations

import json

from cwlbonus.i18n import (LOCALES_DIR, META_KEY, Translator, available_languages,
                          catalog, resolve_lang)

EXPECTED_LANGUAGES = {"en", "es"}


def catalog_keys(code: str) -> set[str]:
    data = json.loads((LOCALES_DIR / f"{code}.json").read_text(encoding="utf-8"))
    return {k for k in data if k != META_KEY}


def test_expected_languages_ship():
    assert EXPECTED_LANGUAGES.issubset(set(available_languages()))


def test_every_catalog_has_identical_keys():
    """A missing key falls back to English, but it is still a bug to ship one."""
    reference = catalog_keys("en")
    for code in available_languages():
        missing = reference - catalog_keys(code)
        extra = catalog_keys(code) - reference
        assert not missing, f"{code} is missing keys: {sorted(missing)}"
        assert not extra, f"{code} has unknown keys: {sorted(extra)}"


def test_meta_block_holds_the_display_name():
    assert available_languages()["en"] == "English"
    assert available_languages()["es"] == "Español"


def test_translator_returns_localised_text():
    assert Translator("es")("table.player") == "Jugador"
    assert Translator("en")("table.player") == "Player"


def test_translator_interpolates():
    got = Translator("en")("warn.missed", count=2, penalty="-2.00")
    assert "2" in got and "-2.00" in got
    assert "{" not in got


def test_unknown_key_returns_the_key_instead_of_crashing():
    assert Translator("en")("does.not.exist") == "does.not.exist"


def test_bad_placeholder_does_not_crash():
    """A catalog typo must not take down a run mid-season."""
    t = Translator("en")
    assert t("warn.missed") != ""          # no kwargs supplied


def test_missing_key_falls_back_to_english(monkeypatch, tmp_path):
    from cwlbonus import i18n
    monkeypatch.setattr(i18n, "LOCALES_DIR", tmp_path)
    (tmp_path / "en.json").write_text(json.dumps({"a": "english", "b": "english"}),
                                     encoding="utf-8")
    (tmp_path / "xx.json").write_text(json.dumps({"a": "other"}), encoding="utf-8")
    i18n.catalog.cache_clear()
    assert i18n.catalog("xx")["b"] == "english"
    assert i18n.catalog("xx")["a"] == "other"
    i18n.catalog.cache_clear()


def test_season_label_is_localised():
    assert Translator("en").season_label("2026-10-02") == "October 2026"
    assert Translator("es").season_label("2026-10-02") == "Octubre 2026"


def test_season_label_survives_junk():
    assert Translator("en").season_label(None) == ""
    assert Translator("en").season_label("nonsense") == "nonsense"
    assert Translator("en").season_label("2026-99-01") == "2026-99-01"


def test_resolve_lang_prefers_the_cli_flag(monkeypatch):
    monkeypatch.setenv("CWL_LANG", "es")
    assert resolve_lang("en") == "en"
    assert resolve_lang(None) == "es"


def test_resolve_lang_ignores_unknown_codes(monkeypatch):
    monkeypatch.delenv("CWL_LANG", raising=False)
    assert resolve_lang("klingon") in EXPECTED_LANGUAGES
    assert resolve_lang("pt_BR") in EXPECTED_LANGUAGES


def test_cjk_and_accents_round_trip():
    """Names in the chart come from the API; the catalogs must be real UTF-8."""
    assert "Español" in available_languages().values()
    assert "ó" in Translator("es")("chart.x_label")
    catalog.cache_clear()
