"""Load-haul-dump machine failure times, as analysed by Kvaloy and Lindqvist.

Original source: Kumar, Klefsjo and Granholm (1989), reproduced in Kvaloy and
Lindqvist, "A class of tests for trend in time censored recurrent event data",
Technometrics 62(1):101-115 (preprint arXiv:1802.08339). The paper analyses this record in
its Section 6.1 and prints the resulting statistics in its Table 2, which is what makes it
usable as a transcription fixture: it is the only single-process worked example with
published intermediate quantities.

TIMES are cumulative failure times in hours from the start of observation, NOT gaps. The
record is TIME censored at tau = 2000 hours, so the trailing 30 hours after the last
failure at 1970 is an incomplete gap - which is the whole point of the time-censored
formulation and the reason this fixture exercises `Segment` rather than a plain array.
"""

from __future__ import annotations

import numpy as np

# 36 cumulative failure times, hours.
FAILURE_TIMES_H = np.array(
    [
        16,
        39,
        71,
        95,
        98,
        110,
        114,
        226,
        294,
        344,
        555,
        599,
        757,
        822,
        963,
        1077,
        1167,
        1202,
        1257,
        1317,
        1345,
        1372,
        1402,
        1536,
        1625,
        1643,
        1675,
        1726,
        1736,
        1772,
        1796,
        1799,
        1814,
        1868,
        1894,
        1970,
    ],
    dtype=float,
)

# Time censoring point, hours. tau > T_N by 30 hours.
TAU_H = 2000.0


def gaps_h() -> np.ndarray:
    """Inter-failure gaps, hours. `T_1` is itself a gap from the origin at t = 0."""
    return np.diff(np.concatenate([[0.0], FAILURE_TIMES_H]))


# Kvaloy and Lindqvist Table 2, single process. Values as printed in the paper, taken from
# the brief; the bibliographic details come from the reference document's own
# bibliography and the table/section numbers have not been checked against the journal.
#
# The first four are reproduced by this code; the last three diverge by a known and
# documented amount - see `tests/test_checks_published_values.py`, which asserts both the
# agreement and the cause of the divergence.
PUBLISHED = {
    "mu_hat": 54.72,  # mean of the complete gaps
    "sigma_tilde": 47.23,  # eq (10), uses the censored time
    "gamma_tilde": 0.850,  # eq (10)
    "laplace": 0.605,  # eq (4) numerator scaling, before dividing by gamma
    "lr_sigma_star": 0.774,  # eq (11) successive-difference estimator - NOT shipped
    "sigma_hat": 48.61,  # complete gaps, paper's Table 2 (1/(N-1) divisor)
    "gamma_hat": 0.888,  # complete gaps, paper's Table 2
    "lr_gamma_hat": 0.681,  # follows from gamma_hat
}


# ---------------------------------------------------------------------------
# Small bowel motility, m = 19. NOT PRESENT - see tests/test_checks_published_values.py
# ---------------------------------------------------------------------------
#
# Kvaloy and Lindqvist Section 6.2 analyse migrating-motor-complex period lengths from
# Aalen, O. O. and Husebye, E. (1991), "Statistical analysis of repeated events forming
# renewal processes", Statistics in Medicine 10(8):1227-1240. Nineteen healthy subjects,
# each contributing one to nine complete fasting cycles, 80 complete periods in total,
# each subject time censored at the end of their own recording.
#
# This is the ONLY published worked example of eq (16) in its multi-process form, which
# makes it the only external check in existence on our m > 1 path. Everything else we have
# for m > 1 is self-consistency.
#
# The raw periods are in neither the Kvaloy-Lindqvist paper nor any repository or R package
# located. The published summary statistics are recorded here
# so the test activates the day the data arrive.
SMALL_BOWEL_PUBLISHED = {
    "n_subjects": 19,
    "n_complete_periods": 80,
    "mu_hat": 98.76,
    "sigma_hat": 52.62,
    "gamma_hat": 0.533,
    "laplace": 1.95,
    "lr_multiprocess": 3.67,
    "p_value": 0.00024,
}
