"""Unit tests for the six checks: identities, oracles, and the guards.

The two tests that matter most are the ones that pin a statistic against something
INDEPENDENT of the implementation:

- `test_eq7_is_the_classical_anderson_darling` compares eq (7) at `gamma_hat = 1` with the
  textbook `-N - (1/N) sum (2i-1)[ln u_i + ln(1-u_{N+1-i})]`. Two unrelated algebraic
  forms agreeing to float precision is strong evidence the transcription from the PDF is
  right.
- `test_eq7_at_gamma_one_matches_the_limiting_ad_null` checks the same statistic against
  Marsaglia's limiting AD distribution over 6000 replicates.

Both force `gamma = 1`, so both pin the TRANSCRIPTION and neither pins the shipped path,
which divides by an estimated `gamma_hat`. The distinction matters: reading the gate as
proof of the whole implementation hides that the shipped asymptotic path is measurably
oversized at small n (0.0634 against 0.05 at n = 20).
`test_shipped_c2_asymptotic_is_oversized_at_small_n` pins that separately, so the known
gap is a recorded fact rather than an unmeasured one.

The third group at the bottom of the file covers `statistic_batch` and
`segments_from_windows`. The second is where a defect merging renewal segments across
unobserved read gaps is invisible to inspection.
"""

from __future__ import annotations

import numpy as np
import pytest

import quebra.analyzers.checks.c1_lewis_robinson as c1
import quebra.analyzers.checks.c2_anderson_darling as c2
import quebra.analyzers.checks.c5_rank_autocorr as c5
import quebra.analyzers.checks.c6_exchangeability as c6
from quebra.analyzers.checks._multiprocess import (
    GAMMA_COMPLETE,
    GAMMA_TRUNCATED,
    gamma_hat,
)
from quebra.analyzers import windows
from quebra.analyzers.checks._multiprocess import segments_from_windows
from quebra.analyzers.checks._permutation import (
    PermutationSet,
    block_permutations,
    permutation_p_value,
)
from quebra.analyzers.checks.battery import ROW_KEYS, row_key, run_battery
from quebra.analyzers.checks.result import (
    CALIB_ASYMPTOTIC,
    CALIB_PERMUTATION,
    CLOCK_CALENDAR,
    CLOCK_IN_SPEC,
    Segment,
)


def exponential_segment(n: int, rng: np.random.Generator, rate: float = 1.0) -> Segment:
    """A genuinely time-truncated exponential segment: tau fixed, event count random."""
    tau = float(n) / rate
    gaps = rng.exponential(1.0 / rate, size=int(n + 10 * np.sqrt(n) + 50))
    kept = gaps[: int(np.searchsorted(np.cumsum(gaps), tau, side="left"))]
    return Segment(x=kept, tau=tau, n_censored_dropped=1)


# --------------------------------------------------------------------------- C2


def _classical_ad(x: np.ndarray, tau: float) -> float:
    u = np.cumsum(x) / tau
    n = len(u)
    i = np.arange(1, n + 1)
    return float(-n - np.sum((2 * i - 1) * (np.log(u) + np.log(1 - u[::-1]))) / n)


@pytest.mark.parametrize("n", [3, 5, 20, 60, 200])
def test_eq7_is_the_classical_anderson_darling(n):
    rng = np.random.default_rng(n)
    gaps = rng.exponential(size=n + 1)
    tau = float(gaps.sum())
    x = gaps[:n]
    assert c2._eq7(x, tau, 1.0) == pytest.approx(_classical_ad(x, tau), rel=1e-9)


def test_ad_limiting_cdf_reproduces_published_critical_values():
    """Marsaglia & Marsaglia's adinf, against the standard AD table."""
    for statistic, alpha in [
        (1.933, 0.10),
        (2.492, 0.05),
        (3.070, 0.025),
        (3.857, 0.01),
    ]:
        assert 1.0 - c2.ad_limiting_cdf(statistic) == pytest.approx(alpha, abs=5e-4)


@pytest.mark.parametrize("n", [20, 50])
def test_eq7_at_gamma_one_matches_the_limiting_ad_null(n):
    """Transcription pin for eq (7) - and narrower than it looks, deliberately.

    This forces `gamma = 1`. Conditional on N, exponential gaps under a pre-chosen `tau`
    make `T_i/tau` exactly uniform order statistics, so the statistic's null is the
    classical Anderson-Darling one; `ad_limiting_cdf` is Marsaglia's LIMITING function, so
    the agreement below is excellent-at-this-N rather than exact. Together with
    `test_eq7_is_the_classical_anderson_darling` it pins the transcription.

    It does NOT pin the shipped path, which divides by an estimated `gamma_hat` - see
    `test_shipped_c2_asymptotic_is_oversized_at_small_n` for that, and the bench's size
    table for what it costs.
    """
    rng = np.random.default_rng(90210 + n)
    reps = 6000
    statistics = np.array(
        [
            c2._eq7(s.x, s.tau, 1.0)
            for s in (exponential_segment(n, rng) for _ in range(reps))
        ]
    )
    p = 1.0 - c2.ad_limiting_cdf(statistics)
    for alpha in (0.10, 0.05, 0.01):
        rate = float(np.mean(p < alpha))
        se = float(np.sqrt(alpha * (1 - alpha) / reps))
        assert abs(rate - alpha) < 4 * se, (
            f"n={n} alpha={alpha}: rejection {rate:.4f}, expected {alpha} +/- {4 * se:.4f}"
        )


@pytest.mark.parametrize("n, expected", [(20, 0.0634), (50, 0.0514)])
def test_shipped_c2_asymptotic_is_oversized_at_small_n(n, expected):
    """The gap between the transcription pin and what `c2.run` actually does.

    Dividing by an ESTIMATED `gamma_hat` fattens the upper tail: at n = 20 the shipped
    asymptotic path rejects at 0.0634 against a nominal 0.05, converging to 0.0514 by
    n = 50. Both figures are MEASURED on this generator at 40,000 replicates (MC SE
    0.0012), not borrowed from a nearby run - a borrowed value would pass anyway, because
    the tolerance is 4 SE wide. This
    is not a defect - `ad_limiting_cdf` is the limiting null and the finite-N cost of
    estimating gamma is exactly what the bench measures - but it is pinned here so it
    cannot drift unnoticed, and so nobody reads the gamma = 1 test as covering production.
    """
    rng = np.random.default_rng(5150 + n)
    reps = 4000
    p = np.array(
        [
            c2.run([exponential_segment(n, rng)], calibration=CALIB_ASYMPTOTIC).p_value
            for _ in range(reps)
        ]
    )
    rate = float(np.mean(p < 0.05))
    se = float(np.sqrt(0.05 * 0.95 / reps))
    assert abs(rate - expected) < 4 * se, (
        f"shipped C2 asymptotic size at n={n} is {rate:.4f}, expected ~{expected}"
    )
    assert rate > 0.05, "the shipped path is oversized at these n; that is the point"


def test_c2_refuses_a_segment_whose_last_event_lands_on_tau():
    x = np.array([1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="failure censoring"):
        c2.statistic([Segment(x=x, tau=float(x.sum()))])


def test_c2_refuses_an_asymptotic_calibration_for_multiple_segments():
    rng = np.random.default_rng(0)
    segments = [exponential_segment(20, rng) for _ in range(3)]
    with pytest.raises(ValueError, match="no asymptotic calibration"):
        c2.run(segments, calibration=CALIB_ASYMPTOTIC)


# --------------------------------------------------------------------------- C1


def test_eq16_reduces_to_eq4_for_a_single_segment():
    rng = np.random.default_rng(7)
    segment = exponential_segment(40, rng)
    x, tau = segment.x, segment.tau
    gamma = gamma_hat(x, tau, GAMMA_COMPLETE)
    eq4 = (
        (1.0 / gamma)
        * np.sqrt(12.0)
        / (tau * np.sqrt(len(x)))
        * (np.cumsum(x).sum() - len(x) * tau / 2.0)
    )
    assert c1.statistic([segment]) == pytest.approx(eq4, rel=1e-12)


def test_c1_detects_the_trend_it_is_built_for():
    """Events crowded early give a strongly negative statistic, crowded late a positive one.

    The two segments share one multiset of gaps and differ only in ORDER, so `gamma_hat`,
    `tau` and `N` are identical and the sign difference can only come from the trend term.
    (Equally-spaced gaps would be the sharper trend but have zero dispersion, which makes
    `gamma_hat` zero and the statistic undefined - the guard fires before the test can.)
    """
    rng = np.random.default_rng(3)
    gaps = np.sort(rng.exponential(size=25))
    tau = float(gaps.sum() + 5.0)
    early = c1.statistic([Segment(x=gaps, tau=tau)])  # small gaps first -> events early
    late = c1.statistic([Segment(x=gaps[::-1], tau=tau)])  # large gaps first -> late
    assert early < -2.0, f"expected a strong negative trend statistic, got {early}"
    assert late > 2.0, f"expected a strong positive trend statistic, got {late}"


def test_gamma_hat_eq10_goes_negative_where_the_complete_form_cannot():
    """Pins the reason `GAMMA_COMPLETE` is the default - see `_multiprocess.gamma_hat`.

    Both estimators get the SAME input, which the previous version of this test did not:
    it fed `GAMMA_COMPLETE` a perturbed vector and `GAMMA_TRUNCATED` a constant one, so it
    demonstrated nothing about the difference between them.
    """
    x = np.array([0.9, 1.0, 1.1, 1.0, 1.0])
    tau = 5.5
    # The complete-gap form is a genuine variance and cannot go negative.
    assert gamma_hat(x, tau, GAMMA_COMPLETE) > 0.0
    # Eq (10) on the identical vector is a difference of two large terms and does.
    with pytest.raises(ValueError, match="variance is negative"):
        gamma_hat(x, tau, GAMMA_TRUNCATED)


def test_gamma_hat_distinguishes_a_negative_variance_from_a_constant_vector():
    """The two failures have different causes and must not share a message.

    Clamping a materially negative eq (10) variance to zero would report it as "every
    gap is identical", which is a different and false diagnosis.
    """
    with pytest.raises(ValueError, match="every gap is identical"):
        gamma_hat(np.ones(5), 5.0, GAMMA_COMPLETE)
    with pytest.raises(ValueError, match="variance is negative"):
        gamma_hat(np.array([0.9, 1.0, 1.1, 1.0, 1.0]), 5.5, GAMMA_TRUNCATED)


# --------------------------------------------------------------------------- shared


def test_permutation_p_value_is_tie_corrected():
    """All-tied null must give p = 1, not p = 0: a tie supports the null."""
    assert permutation_p_value(1.0, np.ones(99)) == pytest.approx(1.0)
    # Strictly smaller null draws: the minimum attainable p is 1/(1+B), never 0.
    assert permutation_p_value(5.0, np.zeros(99)) == pytest.approx(1.0 / 100.0)


def test_permutations_stay_inside_their_segment():
    perm = block_permutations([3, 4, 2], n_perm=200, rng=np.random.default_rng(1))
    for lo, hi in perm.blocks():
        block = perm.indices[:, lo:hi]
        assert block.min() >= lo and block.max() < hi
        assert np.all(np.sort(block, axis=1) == np.arange(lo, hi))


@pytest.mark.parametrize(
    "check_module, kwargs",
    [
        (c5, {"variant": c5.VARIANT_STUDENTIZED}),
        (c5, {"variant": c5.VARIANT_RAW}),
        (c6, {}),
    ],
)
def test_rank_checks_are_calibrated_under_exchangeability(check_module, kwargs):
    """Size at alpha = 0.10 on iid gaps, which is these checks' exact null."""
    rng = np.random.default_rng(31415)
    reps = 600
    p = np.array(
        [
            check_module.run(
                [exponential_segment(30, rng)], n_perm=199, rng=rng, **kwargs
            ).p_value
            for _ in range(reps)
        ]
    )
    rate = float(np.mean(p < 0.10))
    se = float(np.sqrt(0.10 * 0.90 / reps))
    assert abs(rate - 0.10) < 4 * se, f"rejection {rate:.4f} at nominal 0.10"


def test_c5_and_c6_find_a_strongly_ordered_sequence():
    """A monotonically increasing duration sequence is maximally non-exchangeable."""
    x = np.linspace(1.0, 20.0, 40)
    segment = Segment(x=x, tau=float(x.sum() + 5.0))
    perm = block_permutations([len(x)], 999, np.random.default_rng(2))
    assert c5.run([segment], perm=perm).p_value <= 0.01
    assert c6.run([segment], perm=perm).p_value <= 0.01


def test_battery_returns_every_row_and_shares_one_permutation_set():
    rng = np.random.default_rng(11)
    segment = exponential_segment(40, rng)
    perm = block_permutations([segment.n_events], 199, rng)
    results = run_battery([segment], perm=perm)
    assert [row_key(r) for r in results] == list(ROW_KEYS)
    assert all(r.p_value is not None for r in results)
    # Standalone calls with the same permutation set must reproduce the battery exactly.
    standalone = c1.run([segment], calibration=CALIB_PERMUTATION, perm=perm)
    battery_c1 = next(
        r for r in results if row_key(r) == ("c1_lewis_robinson", CALIB_PERMUTATION, "")
    )
    assert standalone.p_value == pytest.approx(battery_c1.p_value)


def test_battery_drops_only_the_tau_checks_when_asked():
    rng = np.random.default_rng(12)
    segment = exponential_segment(30, rng)
    perm = block_permutations([segment.n_events], 99, rng)
    keys = [
        row_key(r) for r in run_battery([segment], perm=perm, include_tau_checks=False)
    ]
    # C5, C6 and CvM-by-permutation survive; C1, C2 and CvM-ASYMPTOTIC do not.
    # CvM is the one entitled to this case: its
    # statistic has no `1/(s(1-s))` weight so it stays finite when `tau == T_N`. Its
    # asymptotic row is still dropped here, because a limiting null needs a truncation
    # time chosen independently of the events and this one is not.
    assert all(key[0].startswith(("c5", "c6", "cvm")) for key in keys)
    assert ("cvm_cramer_von_mises", CALIB_PERMUTATION, "") in keys
    assert ("cvm_cramer_von_mises", CALIB_ASYMPTOTIC, "") not in keys
    assert not any(key[0].startswith(("c1", "c2")) for key in keys)
    assert len(keys) == 4


@pytest.mark.parametrize(
    "segment, match",
    [
        (Segment(x=np.array([1.0]), tau=3.0), "at least 2"),
        (Segment(x=np.array([1.0, 0.0, 2.0]), tau=9.0), "strictly positive"),
        (Segment(x=np.array([1.0, 2.0]), tau=1.0), "below the last event time"),
        (Segment(x=np.array([1.0, np.nan]), tau=9.0), "finite"),
    ],
)
def test_validate_segment_raises_rather_than_returning_nonsense(segment, match):
    with pytest.raises(ValueError, match=match):
        c1.statistic([segment])


# ------------------------------------------------------- the batch/segment paths


@pytest.mark.parametrize("sizes", [[6], [4, 5], [3, 3, 4]])
def test_statistic_batch_reproduces_the_statistic_under_the_identity_permutation(sizes):
    """A misalignment between `segments` and `perm.blocks()` would compute the observed
    statistic from one assembly and the null from another - silently, and it would corrupt
    every permutation p-value the bench produced. Pinned with an identity permutation, for
    which the batch answer must equal the scalar one exactly."""
    rng = np.random.default_rng(808)
    segments = [exponential_segment(size * 6, rng) for size in sizes]
    total = sum(s.n_events for s in segments)
    identity = PermutationSet(
        sizes=tuple(s.n_events for s in segments),
        indices=np.tile(np.arange(total), (3, 1)),
    )
    for module in (c1, c2):
        batch = module.statistic_batch(segments, identity)
        scalar = module.statistic(segments)
        assert np.allclose(batch, scalar, rtol=0, atol=1e-12), (
            f"{module.CHECK_NAME}: identity-permuted batch {batch[0]} != {scalar}"
        )


def _carve_windows(t, in_spec):
    result = windows.run(
        windows.WindowsInputs(
            t_rel_s=np.asarray(t, dtype=float),
            values=np.where(np.asarray(in_spec, dtype=bool), 1.0, -1.0),
            thresholds=[("thr", 0.0, True)],
        )
    )
    return result.windows, result.diagnostics.get("gap_spans_s")


def _gapped_record():
    """A record whose gap is flanked by OUT-of-spec reads on both sides.

    The carve cannot mark this: `gap_resume` is only emitted next to an in-spec read, so
    the window table contains no trace of the gap at all. That is the whole point.
    """
    pre = [1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 0]
    post = [0, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0]
    t = np.concatenate(
        [np.arange(len(pre), dtype=float), 500.0 + np.arange(len(post), dtype=float)]
    )
    return _carve_windows(t, pre + post)


def test_the_gapped_record_really_hides_its_gap_from_the_window_table():
    """Positive control for the two tests below: without this, they could pass because the
    carve marked the gap and `gap_spans_s` changed nothing."""
    frame, gaps = _gapped_record()
    assert gaps, "the carve must have detected a read gap"
    assert "gap_resume" not in set(frame["birth_type"]), (
        "this record is only interesting because the carve leaves no birth-type trace"
    )


@pytest.mark.parametrize("clock", [CLOCK_IN_SPEC, CLOCK_CALENDAR])
def test_segments_split_on_gap_spans_the_birth_taxonomy_cannot_see(clock):
    frame, gaps = _gapped_record()
    merged, _ = segments_from_windows(frame, clock=clock)
    split, _ = segments_from_windows(frame, clock=clock, gap_spans_s=gaps)
    assert len(merged) == 1, "birth types alone should merge this record"
    assert len(split) == 2, f"gap_spans_s should split it; got {len(split)}"


def test_the_merged_calendar_segment_contains_a_fabricated_inter_event_gap():
    """Names the damage: on the calendar clock the merged segment reports the 488 s of
    UNOBSERVED time as if it were an observed inter-event interval, and feeds it to
    eqs (4) and (7) as a renewal gap."""
    frame, gaps = _gapped_record()
    merged, _ = segments_from_windows(frame, clock=CLOCK_CALENDAR)
    split, _ = segments_from_windows(frame, clock=CLOCK_CALENDAR, gap_spans_s=gaps)
    gap_before, gap_after = gaps[0]
    unobserved_s = gap_after - gap_before
    assert merged[0].x.max() > unobserved_s, "the merged segment should span the gap"
    for segment in split:
        assert segment.x.max() < unobserved_s, (
            "no split segment may contain an interval longer than the read gap"
        )


def test_interior_segments_are_truncated_at_the_gap_start_not_at_an_event():
    """`tau` for an interior segment is when watching STOPPED. Taking it from the last
    window's death is the event-determined boundary eq (7) forbids."""
    frame, gaps = _gapped_record()
    split, _ = segments_from_windows(frame, clock=CLOCK_CALENDAR, gap_spans_s=gaps)
    gap_start_s = gaps[0][0]
    first_births = frame["t_birth_s"].to_numpy(dtype=float)
    assert split[0].tau == pytest.approx(gap_start_s - first_births[0]), (
        "the interior segment must be truncated at the gap start"
    )


def test_omitting_gap_spans_keeps_the_old_behaviour():
    """The parameter is optional, and its absence must degrade predictably rather than
    change results for callers that never had a gap."""
    rng = np.random.default_rng(3)
    t = np.arange(40, dtype=float)
    frame, gaps = _carve_windows(t, rng.random(40) > 0.4)
    assert not gaps, "a uniformly spaced record has no gaps"
    without, _ = segments_from_windows(frame, clock=CLOCK_IN_SPEC)
    with_empty, _ = segments_from_windows(frame, clock=CLOCK_IN_SPEC, gap_spans_s=gaps)
    assert len(without) == len(with_empty)
    for a, b in zip(without, with_empty):
        assert np.array_equal(a.x, b.x) and a.tau == b.tau
