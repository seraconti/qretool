"""C1 - Lewis-Robinson test for trend, time-censored and multi-process.

Kvaloy & Lindqvist, arXiv:1802.08339. Single process, their eq (4):

    LR = (1/gamma_hat) * sqrt(12)/(tau*sqrt(N)) * [ sum_i T_i - (N/2)*tau ]

Multi-process, their eq (16) after substituting the optimal eq (15) weights:

    LR_m = sqrt(12) / sqrt( sum_k gamma_hat_k^2 * tau_k^2 * N_k )
           * sum_j [ sum_i T_ij - (N_j/2) * tau_j ]

Only eq (16) is implemented. Setting m = 1 in it gives
`sqrt(12)/sqrt(g^2 tau^2 N) * [sum T - N tau/2]` = `(1/g) sqrt(12)/(tau sqrt(N)) * [...]`,
which is eq (4) exactly - so a separate single-process path would be a second copy of the
same formula, free to drift. `test_checks_c1.py` asserts the identity numerically rather
than trusting the algebra above.

What the statistic is: `sum_i T_i` is the total of the event times, and `(N/2)*tau` is its
expectation when events are uniform on `[0, tau]` (the null of no trend). So LR is a
centred, scaled "are the events early or late" contrast - negative for a decreasing
intensity, positive for an increasing one - and it is two-sided here. The `1/gamma_hat`
is what makes it a test of TREND rather than a test of the Poisson assumption: dividing by
the estimated coefficient of variation removes the renewal distribution's dispersion,
which is the whole difference between Lewis-Robinson and the plain Laplace test.

Both calibrations ship. Asymptotic is N(0,1) per the paper. Permutation is EXACTLY valid
here, not merely asymptotically: `tau_j`, `N_j` and `gamma_hat_j` are all invariant to
reordering gaps within a segment, so the only thing a permutation moves is `sum_i T_ij`.
That makes the asymptotic-vs-permutation gap in the bench a clean measurement of
asymptotic error rather than a comparison of two approximations.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

from quebra.analyzers.checks._multiprocess import (
    GAMMA_COMPLETE,
    gamma_hat,
    gamma_hat_batch,
)
from quebra.analyzers.checks.result import (
    CALIB_ASYMPTOTIC,
    CALIB_PERMUTATION,
    CLOCK_IN_SPEC,
    CheckResult,
    Segment,
    concatenated_gaps,
    segment_sizes,
    validate_segment,
)
from quebra.analyzers.checks._permutation import (
    DEFAULT_N_PERM,
    PermutationSet,
    block_permutations,
    check_permuted,
    two_sided_p_value,
)

CHECK_NAME = "c1_lewis_robinson"

_SQRT12 = float(np.sqrt(12.0))


def _numerator_term(x: np.ndarray, tau: float) -> float:
    """`sum_i T_i - (N/2)*tau` for one segment."""
    return float(np.sum(np.cumsum(x)) - 0.5 * len(x) * tau)


def _numerator_term_batch(x_matrix: np.ndarray, tau: float) -> np.ndarray:
    n = x_matrix.shape[1]
    return np.cumsum(x_matrix, axis=1).sum(axis=1) - 0.5 * n * tau


def statistic(
    segments: list[Segment], *, gamma_estimator: str = GAMMA_COMPLETE
) -> float:
    """Eq (16). Raises via `validate_segment` on any ill-posed segment."""
    if not segments:
        raise ValueError("C1 needs at least one segment")
    numerator = 0.0
    denominator = 0.0
    for segment in segments:
        validate_segment(segment, require_strict_tau=False)
        x = np.asarray(segment.x, dtype=float)
        gamma = gamma_hat(x, segment.tau, gamma_estimator)
        numerator += _numerator_term(x, segment.tau)
        denominator += gamma**2 * segment.tau**2 * len(x)
    if denominator <= 0.0:
        raise ValueError("C1 denominator is not positive; every segment is degenerate")
    return _SQRT12 * numerator / float(np.sqrt(denominator))


def statistic_batch(
    segments: list[Segment],
    perm: PermutationSet,
    gamma_estimator: str = GAMMA_COMPLETE,
    permuted: np.ndarray | None = None,
) -> np.ndarray:
    """Eq (16) for every permutation, vectorised over the `(B, total)` index matrix.

    `permuted` lets a caller supply the `(B, total)` gathered matrix it already built.
    At n = 355 that gather is a 355k-element copy and four checks want the identical one,
    so `checks/battery.py` builds it once and hands it round; passing None rebuilds it.
    """
    check_permuted(perm, permuted, "c1.statistic_batch")
    if permuted is None:
        permuted = perm.apply(concatenated_gaps(segments))
    numerator = np.zeros(perm.n_perm, dtype=float)
    denominator = np.zeros(perm.n_perm, dtype=float)
    for segment, (lo, hi) in zip(segments, perm.blocks()):
        block = permuted[:, lo:hi]
        gamma = gamma_hat_batch(block, segment.tau, gamma_estimator)
        numerator += _numerator_term_batch(block, segment.tau)
        denominator += gamma**2 * segment.tau**2 * (hi - lo)
    return _SQRT12 * numerator / np.sqrt(denominator)


def run(
    segments: list[Segment],
    *,
    calibration: str = CALIB_ASYMPTOTIC,
    clock: str = CLOCK_IN_SPEC,
    gamma_estimator: str = GAMMA_COMPLETE,
    perm: PermutationSet | None = None,
    n_perm: int = DEFAULT_N_PERM,
    rng: np.random.Generator | None = None,
    permuted: np.ndarray | None = None,
) -> CheckResult:
    observed = statistic(segments, gamma_estimator=gamma_estimator)
    n_events = int(sum(len(s.x) for s in segments))
    n_censored = int(sum(s.n_censored_dropped for s in segments))
    notes = f"gamma={gamma_estimator}"

    if calibration == CALIB_ASYMPTOTIC:
        p_value = float(2.0 * stats.norm.sf(abs(observed)))
    elif calibration == CALIB_PERMUTATION:
        if perm is None:
            perm = block_permutations(segment_sizes(segments), n_perm, rng)
        elif perm.sizes != tuple(segment_sizes(segments)):
            raise ValueError(
                f"permutation set is blocked as {perm.sizes} but the segments are "
                f"{tuple(segment_sizes(segments))}"
            )
        null = statistic_batch(segments, perm, gamma_estimator, permuted)
        p_value = two_sided_p_value(observed, null)
        notes += f" B={perm.n_perm}"
    else:
        raise ValueError(
            f"C1 supports {CALIB_ASYMPTOTIC!r} and {CALIB_PERMUTATION!r}; "
            f"got {calibration!r}"
        )

    return CheckResult(
        check=CHECK_NAME,
        statistic=observed,
        p_value=p_value,
        calibration=calibration,
        clock=clock,
        n_events=n_events,
        n_segments=len(segments),
        n_censored_dropped=n_censored,
        notes=notes,
    )
