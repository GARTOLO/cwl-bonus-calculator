"""Number formatting shared by the terminal report and both chart designs.

Kept out of the chart modules so printing a table does not pull matplotlib in,
and so the two designs cannot drift apart on how a score is written.
"""
from __future__ import annotations


def fmt(value: float, decimals: int = 2) -> str:
    """Number formatting that never emits '-0.00'."""
    if abs(value) < 10 ** (-decimals) / 2:
        value = 0.0
    return f"{value:.{decimals}f}"


def fmt_signed(value: float, decimals: int = 2) -> str:
    """Like :func:`fmt`, but always carries an explicit ``+`` or ``-``."""
    text = fmt(value, decimals)
    return text if text.startswith("-") else f"+{text}"
