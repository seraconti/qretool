"""Permutation calibration for statistics of PAIRED data.

A step-shaped utility, usable by any analyzer that needs a p-value for a dependence
measure whose null distribution is unknown, non-pivotal, or invalid under ties.

**Not to be confused with `analyzers/checks/_permutation.py`.** That module permutes
DURATIONS within carved segments, is blocked by segment so a permutation never crosses a
read gap, and exists to calibrate C1/C2/C5/C6. This one permutes one member of an (x, y)
PAIR against the other, which is the null of independence rather than exchangeability of a
sequence. Different null, different data shape, different consumer.

**Why a library rather than a loop.** `scipy.stats.permutation_test` with
`permutation_type="pairings"` already implements exactly this: it resamples by permuting
the pairing between x and y, which holds both marginals fixed and destroys only the
association. Writing the loop again would be a second convention to keep in step with the
first, and this repo already has one such pair.

**A seed is required, not defaulted.** Defaulting to OS entropy is precisely the defect
that made permutation p-values irreproducible across runs while the provenance record
stayed identical - see `analyzers/checks/_permutation.block_permutations`. The seed is
expected to arrive as a step kwarg so it reaches the Mermaid label.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from scipy.stats import permutation_test

# Enough resolution for the alpha levels this project reads (0.01 is the smallest), while
# staying cheap at the window sizes it runs on - a window here is 3 to a few dozen reads.
DEFAULT_N_RESAMPLES = 999


@dataclass(frozen=True)
class PairedPermutationResult:
    """A permutation p-value with the things needed to read it honestly."""

    statistic: float
    p_value: float
    n_resamples: int
    n_pairs: int
    seed: int
    alternative: str
    # True when scipy enumerated every distinct pairing instead of sampling. It does so
    # when `(n!)^2 <= n_resamples`, which at the default B is n <= 4.
    # NOT reachable from the shipped pipeline: the only consumer, `shape_stats.for_windows`,
    # filters to `n_reads >= shape_min_reads = 5`, and 0 of the 234 windows on 0704 have
    # n <= 4. It is recorded because a DIRECT caller can land there, and because a p-value
    # whose floor is 1/36 must not be read as though it were 1/1000.
    exact: bool

    @property
    def resolution(self) -> float:
        """The smallest p-value this run could have produced.

        `1/B` for an enumerated null and `1/(B+1)` for a sampled one: scipy drops the
        plus-one adjustment on an exact test, because there is no Monte Carlo error to
        guard against. Measured at n = 3: 36 draws and a floor of 1/36 = 0.02778, not the
        0.02703 that `1/(B+1)` would claim.

        A p-value equal to this is "the smallest reportable", not "this small".
        """
        if self.exact:
            return 1.0 / self.n_resamples
        return 1.0 / (self.n_resamples + 1.0)


def paired_permutation_test(
    x: np.ndarray,
    y: np.ndarray,
    statistic: Callable[[np.ndarray, np.ndarray], float],
    *,
    seed: int,
    n_resamples: int = DEFAULT_N_RESAMPLES,
    alternative: str = "greater",
) -> PairedPermutationResult:
    """Calibrate `statistic(x, y)` against the independence null by permuting the pairing.

    `alternative="greater"` is the default because the statistics this serves - Chatterjee's
    xi, distance correlation - are non-negative measures of association where only the upper
    tail is evidence. A two-sided test on them would spend half its significance budget on
    an impossible direction.

    Exact under independence: permuting the pairing generates the exact conditional null
    given the two marginals, so the p-value needs no asymptotic argument and no assumption
    about ties. That is the whole reason it replaces a closed form whose null is derived
    for continuous data.

    The null is sampled when the space is large and ENUMERATED when it is small. scipy's
    "pairings" type permutes each sample independently, so the exhaustive space is `(n!)^2`
    - 36 at n = 3, 576 at n = 4, 518,400 at n = 6 - and scipy enumerates whenever that
    fits inside `n_resamples`. At the default B that means n <= 4 gives an EXACT p-value.
    That regime is UNREACHABLE through `shape_stats.for_windows`, which admits only windows
    of at least `shape_min_reads` reads (5 today), so within this project it is a property
    of the utility rather than a path the pipeline takes. `exact` records which happened and
    `resolution` reports the floor that actually applied.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.shape != y.shape:
        raise ValueError(
            f"x and y must have the same shape; got {x.shape} and {y.shape}"
        )
    finite = np.isfinite(x) & np.isfinite(y)
    x, y = x[finite], y[finite]
    n = int(len(x))
    if n < 3:
        raise ValueError(f"a paired permutation test needs at least 3 pairs; got {n}")

    def _wrapped(a: np.ndarray, b: np.ndarray) -> float:
        value = statistic(a, b)
        if not np.isfinite(value):
            # Substituting -inf here would be ANTI-CONSERVATIVE: a -inf null draw can
            # never exceed the observed statistic, so it inflates significance. Measured
            # on a statistic degenerate on about half its pairings, -inf gave p = 0.034
            # where +inf gave 0.506. Neither is a p-value; a statistic that cannot be
            # evaluated on a resample of the observed data is a broken statistic, and the
            # caller has to know rather than receive a number.
            raise ValueError(
                "the statistic returned a non-finite value on a permuted resample; the "
                "permutation null is undefined for it. Guard the degenerate case in the "
                "statistic itself and decide there what it should mean."
            )
        return float(value)

    result = permutation_test(
        (x, y),
        _wrapped,
        permutation_type="pairings",
        n_resamples=n_resamples,
        alternative=alternative,
        rng=np.random.default_rng(seed),
        vectorized=False,
    )
    return PairedPermutationResult(
        statistic=float(result.statistic),
        p_value=float(result.pvalue),
        n_resamples=int(len(result.null_distribution)),
        n_pairs=n,
        seed=int(seed),
        alternative=alternative,
        exact=bool(math.factorial(n) ** 2 <= n_resamples),
    )
