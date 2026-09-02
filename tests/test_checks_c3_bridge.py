"""C3's R bridge must degrade to `None`, never to a wrong number and never to a crash.

R is absent on this machine, so this file pins the ONLY behaviour that can be exercised
here: every entry point returns a result whose `p_value` is None and whose `notes` say
why, and nothing raises. The code past `_invoke_rscript` has never run - see the module
docstring in `checks/c3_serial_copula.py`.
"""

from __future__ import annotations

import numpy as np
import pytest

import quebra.analyzers.checks.c3_serial_copula as c3
from quebra.analyzers.checks.result import Segment


def _segment(n: int = 30, seed: int = 3) -> Segment:
    rng = np.random.default_rng(seed)
    gaps = rng.exponential(size=n + 40)
    tau = float(n)
    kept = gaps[: int(np.searchsorted(np.cumsum(gaps), tau, side="left"))]
    return Segment(x=kept, tau=tau)


def test_missing_r_returns_none_without_raising(monkeypatch):
    monkeypatch.setattr(c3, "rscript_path", lambda: None)
    result = c3.run([_segment()])
    assert result.p_value is None
    assert "R unavailable" in result.notes
    assert result.n_events > 0


def test_multiple_segments_are_declined_with_a_reason(monkeypatch):
    monkeypatch.setattr(c3, "rscript_path", lambda: "/usr/bin/Rscript")
    result = c3.run([_segment(20, 1), _segment(20, 2)])
    assert result.p_value is None
    assert "multi-process" in result.notes


def test_a_series_too_short_for_the_lag_is_declined(monkeypatch):
    monkeypatch.setattr(c3, "rscript_path", lambda: "/usr/bin/Rscript")
    rng = np.random.default_rng(0)
    short = Segment(x=rng.exponential(size=3), tau=99.0)
    result = c3.run([short], max_lag=5)
    assert result.p_value is None
    assert "too short" in result.notes


def test_invalid_segments_still_raise():
    """Graceful R handling must not soften the ordinary data guards."""
    with pytest.raises(ValueError, match="strictly positive"):
        c3.run([Segment(x=np.array([1.0, 0.0, 2.0]), tau=99.0)])


def test_r_is_genuinely_absent_here():
    """Documents the environment the promotion report rests on.

    Skips rather than fails where R exists: a machine with R is a healthier machine, and a
    red test there would punish the fix. The skip message is the actionable part.
    """
    if c3.rscript_path() is not None:
        pytest.skip(
            "Rscript is on PATH here - C3 is assessable, and the promotion "
            "report's four-check scope needs revisiting on this machine."
        )
    assert c3.rscript_path() is None


def test_the_r_script_ships_next_to_its_wrapper():
    assert c3.R_SCRIPT.exists(), f"missing {c3.R_SCRIPT}"
    body = c3.R_SCRIPT.read_text()
    assert "serialIndepTest" in body and "commandArgs" in body
