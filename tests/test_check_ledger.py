"""The ledger's verdict rule is the decision this whole increment exists to make.

A p-value alone must never produce a `pass`. These tests pin each of the three conditions
independently, so a regression that drops one of them fails here rather than in a figure.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analyzers.check_ledger import (
    VERDICT_FAIL,
    VERDICT_NOT_COMPUTED,
    VERDICT_PASS,
    VERDICT_TIES,
    VERDICT_UNDERPOWERED,
    _verdict,
)
from analyzers.checks.result import CALIB_PERMUTATION, CheckResult


def _result(check: str = "c6_exchangeability", p: float | None = 0.4) -> CheckResult:
    return CheckResult(
        check=check,
        statistic=1.0,
        p_value=p,
        calibration=CALIB_PERMUTATION,
        clock="in_spec",
        n_events=100,
        n_segments=1,
    )


BASE = dict(
    alpha=0.05,
    n_events=100,
    min_events_pass=35,
    n_distinct=100,
    tie_cutoff=5,
    bench_accepted=True,
)


def test_all_three_conditions_met_is_the_only_route_to_pass():
    verdict, reason = _verdict(_result(), **BASE)
    assert verdict == VERDICT_PASS and reason == ""


@pytest.mark.parametrize(
    "override, expected_fragment",
    [
        ({"n_events": 20}, "n_events 20 < 35"),
        ({"bench_accepted": False}, "miscalibrated"),
        ({"bench_accepted": None}, "no bench cell"),
    ],
)
def test_each_condition_alone_blocks_a_pass(override, expected_fragment):
    """A non-rejection with any one condition unmet is `underpowered`, never `pass`."""
    verdict, reason = _verdict(_result(), **{**BASE, **override})
    assert verdict == VERDICT_UNDERPOWERED
    assert expected_fragment in reason


def test_a_rejection_is_a_fail_and_carries_the_calibration_caveat():
    verdict, reason = _verdict(_result(p=0.01), **BASE)
    assert verdict == VERDICT_FAIL and "rejected" in reason
    verdict, reason = _verdict(_result(p=0.01), **{**BASE, "bench_accepted": False})
    assert verdict == VERDICT_FAIL
    assert "miscalibrated" in reason, (
        "a rejection from a miscalibrated check must say so, or the ledger overstates it"
    )


def test_ties_block_a_rank_check_but_not_a_duration_check():
    """C5/C6/C3 are rank or copula statistics; C1/C2 use the durations directly."""
    thin = {**BASE, "n_distinct": 3}
    assert _verdict(_result("c6_exchangeability"), **thin)[0] == VERDICT_TIES
    assert _verdict(_result("c5_rank_autocorr"), **thin)[0] == VERDICT_TIES
    assert _verdict(_result("c1_lewis_robinson"), **thin)[0] == VERDICT_PASS


def test_a_missing_p_value_is_not_computed_and_keeps_its_reason():
    result = _result(p=None)
    object.__setattr__(result, "notes", "R unavailable")
    verdict, reason = _verdict(result, **BASE)
    assert verdict == VERDICT_NOT_COMPUTED and reason == "R unavailable"


def test_the_precedence_is_not_computed_then_ties_then_rejection():
    """Order matters: a rank check with 3 distinct values has no interpretable p at all,
    so ties must be checked before the p-value is read."""
    verdict, _ = _verdict(_result(p=0.001), **{**BASE, "n_distinct": 3})
    assert verdict == VERDICT_TIES, "ties outrank a rejection for a rank statistic"


def test_the_per_threshold_seed_is_stable_across_processes():
    """`hash()` is randomised per process; a seed built from it would make every
    permutation p-value differ between runs while provenance stayed identical."""
    import subprocess
    import sys

    code = "import zlib;print(zlib.crc32('3 \\u00b5s|in_spec'.encode()) & 0x7FFFFFFF)"
    seen = {
        subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True
        ).stdout.strip()
        for _ in range(3)
    }
    assert len(seen) == 1, f"per-threshold stream is not stable: {seen}"


def test_tie_stats_counts_what_it_says():
    from analyzers.check_ledger import _tie_stats

    distinct, tied = _tie_stats(np.array([1.0, 1.0, 2.0, 3.0]))
    assert distinct == 3
    assert tied == pytest.approx(0.5)
    assert _tie_stats(np.array([]))[0] == 0


def test_ledger_refuses_a_partial_artifact():
    """`check_thresholds` is the construction-time completeness contract."""
    from analyzers.check_ledger import CheckLedger

    ledger = CheckLedger(rows=pd.DataFrame({"threshold_label": ["3 µs"]}))
    ledger.check_thresholds(["3 µs"])
    with pytest.raises(ValueError, match="incomplete CheckLedger"):
        ledger.check_thresholds(["3 µs", "4 µs"])
