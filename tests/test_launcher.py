"""The no-install launcher.

`run.py` exists so a fresh checkout works without `pip install -e .` — that is the
difference between `python run.py --bonuses 7` and an ImportError on Windows.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUN_PY = ROOT / "run.py"


def run_launcher(*args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    return subprocess.run([sys.executable, str(RUN_PY), *args],
                          capture_output=True, text=True, cwd=ROOT, env=env,
                          timeout=120)


def test_launcher_exists():
    assert RUN_PY.is_file()


def test_launcher_puts_src_on_the_path():
    """Without this the package is only importable after an editable install."""
    source = RUN_PY.read_text(encoding="utf-8")
    assert "sys.path.insert" in source
    assert '"src"' in source


def test_launcher_prints_help():
    result = run_launcher("--help")
    assert result.returncode == 0, result.stderr
    assert "bonuses" in result.stdout
    assert "preset" in result.stdout


def test_launcher_lists_languages():
    result = run_launcher("--list-langs")
    assert result.returncode == 0, result.stderr
    assert "en (English)" in result.stdout
    assert "es (Español)" in result.stdout


def test_launcher_reports_a_missing_dependency_usefully():
    """If a runtime dependency is absent the message must name the fix.

    Blocks a module that cli.py imports at module level (dotenv), so the failure
    happens inside run.py's import guard rather than mid-run.
    """
    code = """
import builtins, runpy, sys
real_import = builtins.__import__
def fake(name, *a, **k):
    if name == "dotenv":
        raise ModuleNotFoundError("No module named 'dotenv'", name="dotenv")
    return real_import(name, *a, **k)
builtins.__import__ = fake
sys.argv = ["run.py"]
runpy.run_path("run.py", run_name="__main__")
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True,
                            text=True, cwd=ROOT, timeout=120)
    output = result.stderr + result.stdout
    assert result.returncode != 0
    assert "dotenv" in output
    assert "requirements.txt" in output


@pytest.mark.parametrize("flag", ["--version", "--list-langs"])
def test_launcher_flags_do_not_need_credentials(flag):
    """Nothing here should require a .env, so it is safe to run anywhere."""
    result = run_launcher(flag)
    assert result.returncode == 0, result.stderr
    assert "COC_EMAIL" not in result.stderr
