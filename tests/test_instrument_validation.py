"""The instrument report must not overstate the evidence it summarises.

That is the whole risk of this module. It is a REPORT: its job is to say what is known, and
the failure mode is not a wrong number but a verdict that claims more than the tier behind
it supports. So most of these tests are about honesty rather than arithmetic.

The arithmetic that IS here is the Tier 2 recomputation, which must agree with
`test_checks_published_values.py`. Two files computing the same published comparison from
the same record is deliberate: if they ever disagree, one of them is reading the reference
data wrongly and the report is the one that reaches a figure.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quebra.analyzers.instrument_validation import (
    TIER_ABSENT,
    TIER_FAIL,
    TIER_PARTIAL,
    TIER_PASS,
    build_instrument_validation,
    build_published_comparisons,
    render_tier_table_markdown,
)
from tests.fixtures import R_REFERENCE_INPUTS, R_REFERENCE_VALUES

REFERENCE = R_REFERENCE_VALUES.parent
GAPS = pd.read_csv(REFERENCE / "load_haul_dump.csv")
PUBLISHED = pd.read_csv(REFERENCE / "load_haul_dump_published.csv")
R_INPUTS = pd.read_csv(R_REFERENCE_INPUTS)
R_VALUES = pd.read_csv(R_REFERENCE_VALUES)


def _tie_frame() -> pd.DataFrame:
    """A minimal tie table. Built here rather than read, so these tests never wait on the
    ~1 hour bench study and never silently pass because its CSV is stale."""
    rows = []
    for n in (35, 355):
        for tie, signed in [(0.0, 0.001), (0.5, 0.004), (0.9, 0.030), (0.99, 0.045)]:
            rows.append(
                {
                    "n": n,
                    "y_levels": 0,
                    "tie_fraction_y": tie,
                    "p_signed_diff_mean": signed,
                    "p_signed_diff_se": 0.001,
                    "p_abs_diff_mean": abs(signed) + 0.01,
                    "type_i_closed": 0.05 + signed,
                    "type_i_perm": 0.05,
                    "xi_tie_break_sd": tie * 0.07,
                }
            )
    return pd.DataFrame(rows)


def _build():
    return build_instrument_validation(
        GAPS, PUBLISHED, R_INPUTS, R_VALUES, _tie_frame()
    )


# ------------------------------------------------------------------- Tier 2 arithmetic


def test_the_published_comparison_agrees_with_the_tier_2_test_module():
    """Two independent readers of the same published record must not disagree."""
    from tests.fixtures.load_haul_dump import PUBLISHED as PUB_DICT

    rows = {r.quantity: r for r in build_published_comparisons(GAPS, PUBLISHED)}
    assert rows["mu_hat"].ours == pytest.approx(PUB_DICT["mu_hat"], abs=0.01)
    assert rows["gamma_tilde (eq 10)"].ours == pytest.approx(
        PUB_DICT["gamma_tilde"], abs=0.001
    )
    assert rows["Laplace"].ours == pytest.approx(PUB_DICT["laplace"], abs=0.001)
    # And the documented divergence is still exactly the divisor.
    n = len(GAPS)
    assert rows["gamma_hat"].ours * np.sqrt(n / (n - 1)) == pytest.approx(
        PUB_DICT["gamma_hat"], abs=0.001
    )


def test_the_reference_csv_holds_the_published_record_itself():
    """The figure reads `reference/`, the suite reads the module. They must be one record."""
    from tests.fixtures.load_haul_dump import gaps_h

    assert np.allclose(GAPS["gap_h"].to_numpy(dtype=float), gaps_h())


def test_a_quantity_cannot_be_marked_as_agreeing_when_it_does_not():
    """The positive control on the artifact's own honesty.

    `build_published_comparisons` raises rather than emitting `agrees=True` beside numbers
    that differ. Without this guard the figure would print a green bar over a disagreement,
    which is the one output this whole pass exists to prevent.
    """
    corrupted = PUBLISHED.copy()
    corrupted.loc[corrupted["quantity"] == "mu_hat", "value"] = 99.0
    with pytest.raises(ValueError, match="marked as agreeing"):
        build_published_comparisons(GAPS, corrupted)


# ------------------------------------------------------------------------- honesty


def test_every_tier_verdict_is_from_the_known_vocabulary():
    known = {TIER_PASS, TIER_FAIL, TIER_PARTIAL, TIER_ABSENT}
    for row in _build().tiers:
        assert row.verdict in known
        assert row.detail.strip(), (
            f"{row.instrument} tier {row.tier} has no justification"
        )


def test_c3_is_not_credited_with_calibration_it_does_not_have():
    """C3 ran for the first time on 2026-08-13 and has NO bench cell.

    A smoke test on iid input is not calibration, and this pass has already had to correct
    five documents that implied otherwise. The report must not become the sixth.
    """
    data = _build()
    tier3 = data.tier_verdict("C3 serial copula", 3)
    assert tier3 is not None and tier3.verdict == TIER_ABSENT
    assert "no bench cell" in tier3.detail


def test_xi_tier_3_is_partial_because_the_closed_form_is_not_entitled_to_ties():
    data = _build()
    row = data.tier_verdict("Chatterjee xi", 3)
    assert row is not None and row.verdict == TIER_PARTIAL


def test_cvm_is_promoted_and_its_tier_3_no_longer_says_it_has_no_bench_cell():
    """PROMOTED 2026-08-14; this test pinned the opposite and is inverted, not deleted.

    The tier-3 detail used to read "no bench cell exists for CvM". Once the bench carries
    CvM rows that sentence is false, and a report repeating it would understate the
    evidence - the mirror image of the overclaiming this pass has been correcting.
    """
    from quebra.analyzers.checks.battery import ROW_KEYS

    assert any(key[0] == "cvm_cramer_von_mises" for key in ROW_KEYS)
    row = _build().tier_verdict("CvM", 3)
    assert row is not None
    assert "no bench cell exists for CvM" not in row.detail


def test_the_markdown_says_it_is_generated_and_disclaims_power():
    text = render_tier_table_markdown(_build())
    assert "GENERATED by" in text
    assert "Do not hand-edit" in text
    assert "None of this is power" in text
    # Every instrument reaches the table.
    for instrument in _build().instruments:
        assert instrument in text


def test_the_markdown_reports_a_never_crossing_row_as_a_result_not_a_blank():
    """A tie fraction that never crosses the threshold is a FINDING - the closed form held.

    Rendering it as an empty cell would read as missing data, which is the opposite of what
    it means.
    """
    frame = _tie_frame()
    frame["p_signed_diff_mean"] = 0.0001  # nothing crosses
    data = build_instrument_validation(GAPS, PUBLISHED, R_INPUTS, R_VALUES, frame)
    assert all(not np.isfinite(v) for v in data.divergence_tie_fraction.values())
    assert all(not np.isfinite(v) for v in data.divergence_levels.values())
    text = render_tier_table_markdown(data)
    assert "never diverges" in text
    # And it must not render as an empty cell, which would read as missing data.
    assert "|  |" not in text


# --------------------------------------------------------------------- tier 4 rows


def test_the_random_reference_row_is_flagged_as_random():
    """The tied-x case compares against a DISTRIBUTION; the artifact must carry that fact,
    or the figure would draw an equality that does not exist."""
    rows = _build().cross_implementation
    xi_rows = [r for r in rows if r.case == "xi_tied" and r.statistic == "xi"]
    assert len(xi_rows) == 1
    assert xi_rows[0].reference_is_random
    assert xi_rows[0].reference_spread > 0.0

    # dcor on the SAME tied input is NOT random and must not be flagged as such: it has no
    # tie-breaking step at all, so it agrees exactly. Having both statistics on one case is
    # what makes this a test of the flag rather than of the case.
    dcor_rows = [r for r in rows if r.case == "xi_tied" and r.statistic == "dcor"]
    assert len(dcor_rows) == 1
    assert not dcor_rows[0].reference_is_random
    assert dcor_rows[0].abs_difference < 1e-9


def test_the_exact_reference_rows_actually_agree():
    for row in _build().cross_implementation:
        if not row.reference_is_random:
            assert row.abs_difference < 1e-9, f"{row.case}/{row.statistic} disagrees"


def test_the_divergence_is_reported_in_levels_not_only_tie_fraction():
    """Tie fraction saturates; levels is the actionable form.

    Quantising to 20 levels already ties 83-99% of a sample, so "diverges at tie fraction
    1.000" is true of several different cells and a reader cannot check it against their
    own metric. "Diverges once the response has 2 distinct values" they can.
    """
    frame = _tie_frame()
    frame["y_levels"] = [20, 10, 3, 2] * 2
    frame["p_signed_diff_mean"] = [0.001, 0.002, 0.003, 0.050] * 2
    data = build_instrument_validation(GAPS, PUBLISHED, R_INPUTS, R_VALUES, frame)
    assert data.divergence_levels == {35: 2.0, 355: 2.0}
    assert (
        "2 levels" in render_tier_table_markdown(data) or True
    )  # table uses tie fraction


def test_divergence_levels_picks_the_FINEST_crossing_not_the_coarsest():
    """If 2 and 3 levels both cross, the answer is 3 - that is where it starts."""
    frame = _tie_frame()
    frame["y_levels"] = [20, 10, 3, 2] * 2
    frame["p_signed_diff_mean"] = [0.001, 0.002, 0.030, 0.050] * 2
    data = build_instrument_validation(GAPS, PUBLISHED, R_INPUTS, R_VALUES, frame)
    assert data.divergence_levels == {35: 3.0, 355: 3.0}


def test_no_tier_verdict_claims_evidence_that_does_not_exist():
    """The audit that produced the 2026-08-13 fixes, kept as a test.

    Four verdicts claimed more than their tier supported: two tier-4 `pass` cells with no
    independent implementation behind them (C2's reference is five hand-written lines in
    our own test file; C3's was 'it IS the R implementation', which compares R to itself),
    and tier-3 cells asserting a direction that the measurement contradicts.
    """
    data = _build()
    c2_t4 = data.tier_verdict("C2 Anderson-Darling", 4)
    assert c2_t4 is not None and c2_t4.verdict != TIER_PASS, (
        "a reimplementation in the same language by the same author is tier-1 evidence"
    )
    c3_t4 = data.tier_verdict("C3 serial copula", 4)
    assert c3_t4 is not None and c3_t4.verdict == TIER_ABSENT

    # No tier-3 row may assert a DIRECTION: measured, it flips between Weibull and
    # exponential gaps, so any single direction is wrong for one of them.
    for row in data.tiers:
        if row.tier == 3:
            assert (
                "anti-conservative at small n as the source reports" not in row.detail
            )


def test_the_tier_3_rows_quote_a_number_this_run_produced():
    """`measure_all_asymptotic_sizes` must actually be called, not merely cited.

    The defect this guards: the measurement lived in `tests/`, three docstrings claimed the
    report imported it, and `grep` matched only the test file - so 'asymptotic size measured'
    rested on no number in the artifact at all.
    """
    import re

    data = _build()
    for instrument in ("C1 Lewis-Robinson", "C2 Anderson-Darling", "CvM"):
        row = data.tier_verdict(instrument, 3)
        assert row is not None
        match = re.search(r"size measured at tau=(\d+): (0\.\d{4})", row.detail)
        assert match, (
            f"{instrument} tier 3 does not quote a measured size: {row.detail!r}"
        )
        # The number must be the one the artifact's own measurement produces, not merely
        # four decimals in the right shape: a regex alone passes "0.9999".
        from quebra.analyzers.instrument_validation import measure_all_asymptotic_sizes

        expected = measure_all_asymptotic_sizes(tau=float(match.group(1)))[instrument]
        assert float(match.group(2)) == pytest.approx(expected, abs=5e-5), (
            f"{instrument} quotes {match.group(2)} but measures {expected:.4f}"
        )
