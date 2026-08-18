"""C6 - permutation exchangeability test with a portmanteau rank statistic.

    Q = sum_{h=1..H} m_h * r_h^2

where `m_h` is the number of within-segment pairs at lag `h`. Calibrated by within-segment
permutation, upper tail.

The null is exchangeability of the duration sequence, which is what a permutation test
tests directly - no distributional assumption enters, so this is the one check in the set
whose validity does not rest on an approximation or a citation. That makes it the natural
reference for criterion 4: if a check disagrees with C6 on a cell, the burden is on the
check.

Against C5: the `m_h` weighting spreads the statistic's attention across lags in proportion
to how much evidence each one rests on, so Q gains where dependence is spread thinly over
several lags and loses where it sits entirely in one. That is the opposite trade to C5's
max, which is why both ship rather than one standing in for the other.

Q is a sum of squares, so it is one-sided by construction and says nothing about the
DIRECTION of any dependence it finds. C5's `extra["r_lag1"]` carries the sign.
"""

from __future__ import annotations

import numpy as np

from analyzers.checks._permutation import (
    DEFAULT_N_PERM,
    PermutationSet,
    block_permutations,
    permutation_p_value,
)
from analyzers.checks._rank_serial import (
    MAX_LAG_CAP,
    autocorrelations,
    global_ranks,
    lag_layout,
)
from analyzers.checks.result import (
    CALIB_PERMUTATION,
    CLOCK_IN_SPEC,
    CheckResult,
    Segment,
    concatenated_gaps,
    segment_sizes,
    validate_segment,
)

CHECK_NAME = "c6_exchangeability"


def run(
    segments: list[Segment],
    *,
    clock: str = CLOCK_IN_SPEC,
    perm: PermutationSet | None = None,
    n_perm: int = DEFAULT_N_PERM,
    max_lag: int = MAX_LAG_CAP,
    rng: np.random.Generator | None = None,
    autocorr: tuple[np.ndarray, np.ndarray, object] | None = None,
) -> CheckResult:
    """`autocorr` is `(observed_r, null_r, layout)` shared with C5 - see `c5.run`."""
    if not segments:
        raise ValueError("C6 needs at least one segment")
    for segment in segments:
        validate_segment(segment, require_strict_tau=False)

    sizes = segment_sizes(segments)

    if autocorr is None:
        layout = lag_layout(sizes, max_lag)
        ranks = global_ranks(concatenated_gaps(segments))
        if perm is None:
            perm = block_permutations(sizes, n_perm, rng)
        elif perm.sizes != tuple(sizes):
            raise ValueError(
                f"permutation set is blocked as {perm.sizes} but the segments are "
                f"{tuple(sizes)}"
            )
        observed_r = autocorrelations(ranks, layout)[0]
        null_r = autocorrelations(perm.apply(ranks), layout)
    else:
        observed_r, null_r, layout = autocorr
    n_perm_used = int(null_r.shape[0])

    weights = np.asarray(layout.n_pairs, dtype=float)
    observed = float(np.sum(weights * observed_r**2))
    null = (weights * null_r**2).sum(axis=1)
    p_value = permutation_p_value(observed, null)

    return CheckResult(
        check=CHECK_NAME,
        statistic=observed,
        p_value=p_value,
        calibration=CALIB_PERMUTATION,
        clock=clock,
        n_events=int(sum(sizes)),
        n_segments=len(segments),
        n_censored_dropped=int(sum(s.n_censored_dropped for s in segments)),
        notes=f"lags={list(layout.lags)} B={n_perm_used}",
        extra={"lags": list(layout.lags), "n_pairs_per_lag": list(layout.n_pairs)},
    )
