"""Tier 2: reproduce the numbers Kvaloy and Lindqvist print, from their own data.

This is the tier the suite was missing, and it is the one that catches transcription
errors nothing else catches. The bench measures how a routine BEHAVES - a mis-transcribed
equation that behaves plausibly passes every size and power test we have. Only a published
worked example pins the arithmetic itself.

The record is the load-haul-dump machine of their Section 6.1, time censored at 2000 hours,
with the resulting statistics printed in their Table 2.

**What is a direct pin and what is a composition.** `gamma_hat`, `gamma_tilde` and `LR`
are returned by shipped functions. `mu_hat`, `sigma_tilde` and the Laplace statistic are
not exposed by the API and are reconstructed here from shipped outputs:

    sigma_tilde = gamma_tilde * tau / N        (definition of gamma_tilde)
    laplace     = LR * gamma_hat               (LR is the Laplace statistic / gamma_hat)

Those two are still genuine checks - they assert that shipped outputs COMPOSE to an
independently published number - but they are weaker than a direct pin and this docstring
says so rather than letting a reader assume otherwise.

**The divisor divergence, stated as what is actually sourced.** The paper's Table 2 prints
sigma_hat = 48.61 and gamma_hat = 0.888; this code returns 47.93 and 0.876.

What is OBSERVED: all three of Table 2's complete-gap numbers (48.61, 0.888, 0.681) land
simultaneously on the sample (1/(N-1)) divisor. Three independent agreements at once is
what identifies the cause as the divisor rather than the formula - not the Bessel
arithmetic in `test_the_divergence_is_the_divisor`, which is a rescaling of one number by
a factor that at a single N cannot be told apart from any nearby constant.

What is OURS: the population (1/N) form, chosen deliberately and for a stated reason -
`_multiprocess.gamma_hat` uses it "to match eq (10)'s divisor so the two estimators differ
ONLY by the residual term". The reference document's Section 2.3 describes the paper's
estimator 1 as the "sample mean and standard deviation" of the complete gaps, which reads
as 1/(N-1), and makes no claim about Appendix 1's divisor. An earlier draft of this file
asserted that Appendix 1 defines 1/N; that claim is not supported by any source in hand
and has been withdrawn.

CONSEQUENCE, recorded rather than buried: our gamma_hat is smaller than the paper's by
sqrt((N-1)/N), so our C1 statistic is LARGER by sqrt(N/(N-1)) - 1.4% at N = 36, and about
12% on a five-event segment. That direction is anti-conservative. It is a divisor choice,
not an error, but it is a difference from the source and the instrument report says so.
"""

from __future__ import annotations

import numpy as np
import pytest

import analyzers.checks.c1_lewis_robinson as c1
from analyzers.checks._multiprocess import (
    GAMMA_COMPLETE,
    GAMMA_TRUNCATED,
    gamma_hat,
)
from analyzers.checks.result import Segment, validate_segment
from tests.fixtures.load_haul_dump import PUBLISHED, TAU_H, gaps_h

X = gaps_h()
N = len(X)
SEGMENT = Segment(x=X, tau=TAU_H, n_censored_dropped=1)


def test_the_published_record_is_a_well_posed_segment():
    """It must survive our own guards before any number it produces means anything."""
    validate_segment(SEGMENT, require_strict_tau=True)
    assert N == 36
    assert np.all(X > 0.0)
    assert SEGMENT.tau > float(np.cumsum(X)[-1])


# --------------------------------------------------------------- direct pins


def test_gamma_tilde_eq10_matches_the_paper():
    """Eq (10), the estimator that uses the censored time. Direct pin."""
    assert gamma_hat(X, TAU_H, GAMMA_TRUNCATED) == pytest.approx(
        PUBLISHED["gamma_tilde"], abs=0.001
    )


def test_gamma_hat_complete_gaps_is_the_population_form():
    """Our value, which is the paper's Appendix 1 definition rather than its Table 2."""
    assert gamma_hat(X, TAU_H, GAMMA_COMPLETE) == pytest.approx(0.876, abs=0.001)


def test_lewis_robinson_matches_the_paper_up_to_the_divisor():
    """LR with the population gamma_hat. The paper's 0.681 uses the sample divisor."""
    assert c1.statistic([SEGMENT], gamma_estimator=GAMMA_COMPLETE) == pytest.approx(
        0.691, abs=0.001
    )


# ------------------------------------------------------- composed quantities


def test_mu_hat_matches_the_paper():
    """Composition: the mean gap is not returned by any shipped function."""
    assert float(np.mean(X)) == pytest.approx(PUBLISHED["mu_hat"], abs=0.01)


def test_sigma_tilde_eq10_matches_the_paper():
    """Composition: `gamma_tilde * tau / N`, since gamma_hat returns only the ratio."""
    sigma_tilde = gamma_hat(X, TAU_H, GAMMA_TRUNCATED) * TAU_H / N
    assert sigma_tilde == pytest.approx(PUBLISHED["sigma_tilde"], abs=0.01)


def test_the_laplace_statistic_matches_the_paper():
    """Composition: `LR * gamma_hat`.

    Not circular. LR and gamma_hat are computed independently by shipped code; asserting
    their product equals a number printed in the paper tests that the eq (16) numerator
    scaling is right, because the Laplace statistic is exactly that numerator before the
    gamma division. A transcription error in the `sqrt(12)/(tau*sqrt(N))` factor would
    show up here and nowhere else in this file.
    """
    lr = c1.statistic([SEGMENT], gamma_estimator=GAMMA_COMPLETE)
    laplace = lr * gamma_hat(X, TAU_H, GAMMA_COMPLETE)
    assert laplace == pytest.approx(PUBLISHED["laplace"], abs=0.001)


# ------------------------------------------------- the documented divergence


def test_the_divergence_is_the_divisor_and_not_a_transcription_error():
    """The 1/N versus 1/(N-1) bridge, at three levels at once.

    The evidential weight is in the SIMULTANEITY, not in any one line: sigma, gamma and LR
    all land on their published values under the same single rescaling. Any one of them
    alone would be a factor of 1.0142 that, inside a 0.01 band at one N, cannot be
    distinguished from a neighbouring constant.
    """
    mu = float(np.mean(X))
    sigma_population = gamma_hat(X, TAU_H, GAMMA_COMPLETE) * mu

    assert sigma_population == pytest.approx(47.93, abs=0.01)
    assert sigma_population * np.sqrt(N / (N - 1)) == pytest.approx(
        PUBLISHED["sigma_hat"], abs=0.01
    )
    # And the same bridge at the level of gamma and of LR.
    assert sigma_population * np.sqrt(N / (N - 1)) / mu == pytest.approx(
        PUBLISHED["gamma_hat"], abs=0.001
    )
    lr_population = c1.statistic([SEGMENT], gamma_estimator=GAMMA_COMPLETE)
    assert lr_population * np.sqrt((N - 1) / N) == pytest.approx(
        PUBLISHED["lr_gamma_hat"], abs=0.001
    )


# ----------------------------------------------------- eq (11), not shipped


def _sigma_star_squared(x: np.ndarray) -> float:
    """Kvaloy and Lindqvist eq (11), the successive-difference estimator.

    DELIBERATELY LOCAL TO THIS TEST. Both the paper and the reference document decline
    this estimator: it is biased downward under positive dependence between neighbouring
    gaps, which inflates the trend statistic - and neighbour dependence is exactly what C5
    and C6 exist to detect, so shipping it would entangle the trend test with the
    dependence tests. `_multiprocess.GAMMA_ESTIMATORS` therefore offers estimators 1 and 2
    only. It is implemented here purely to reproduce the published number and confirm the
    transcription of the surrounding machinery.
    """
    return float(np.sum(np.diff(x) ** 2) / (2.0 * (len(x) - 1)))


def test_eq11_reproduces_the_papers_alternative_lr():
    """The paper's LR computed with sigma* / mu_hat, its Table 2 value 0.774."""
    mu = float(np.mean(X))
    gamma_star = np.sqrt(_sigma_star_squared(X)) / mu
    laplace = c1.statistic([SEGMENT], gamma_estimator=GAMMA_COMPLETE) * gamma_hat(
        X, TAU_H, GAMMA_COMPLETE
    )
    assert laplace / gamma_star == pytest.approx(PUBLISHED["lr_sigma_star"], abs=0.001)


def test_eq11_is_not_reachable_through_the_shipped_api():
    """Pins the decision: asking for it must fail, not silently pick another estimator."""
    from analyzers.checks._multiprocess import GAMMA_ESTIMATORS

    assert "eq11_successive_difference" not in GAMMA_ESTIMATORS
    assert set(GAMMA_ESTIMATORS) == {GAMMA_COMPLETE, GAMMA_TRUNCATED}
    with pytest.raises(ValueError, match="unknown gamma estimator"):
        gamma_hat(X, TAU_H, "eq11_successive_difference")


# ------------------------------------------- the m > 1 path has no external check yet


def test_small_bowel_motility_multiprocess():
    """Kvaloy and Lindqvist Section 6.2, m = 19. SKIPPED - the raw data is not in hand.

    This is the only published exercise of eq (16) in its multi-process form, so it is the
    only external evidence available anywhere for our m > 1 path. Everything else we have
    at m > 1 - the bench's multi-segment arms, the battery's per-segment sum - is internal
    consistency, which cannot catch a shared transcription error.

    Source of the data: Aalen, O. O. and Husebye, E. (1991), "Statistical analysis of
    repeated events forming renewal processes", Statistics in Medicine 10(8):1227-1240.
    Nineteen subjects, 80 complete fasting migrating-motor-complex periods, each subject
    censored at the end of its own recording.

    Targets, from Kvaloy and Lindqvist Section 6.2: mu_hat 98.76, sigma_hat 52.62,
    gamma_hat 0.533 over the 80 complete periods; Laplace 1.95; LR^m 3.67; p = 0.00024.

    TO ACTIVATE: add the per-subject period lengths and censoring times to
    `tests/fixtures/load_haul_dump.py` as `SMALL_BOWEL_SEGMENTS`, build one `Segment` per
    subject, and assert `c1.statistic(segments)` against `lr_multiprocess`. Expect the same
    divisor question as the single-process case: check whether 0.533 is the 1/N or the
    1/(N-1) form before recording a divergence.
    """
    from tests.fixtures import load_haul_dump as fx

    segments_data = getattr(fx, "SMALL_BOWEL_SEGMENTS", None)
    if segments_data is None:
        pytest.skip(
            "raw Aalen-Husebye (1991) period lengths not obtainable; searched "
            "2026-08-12. The m > 1 path therefore has no external validation. Add "
            "SMALL_BOWEL_SEGMENTS to tests/fixtures/load_haul_dump.py to activate."
        )
    published = fx.SMALL_BOWEL_PUBLISHED
    segments = [
        Segment(x=np.asarray(x, dtype=float), tau=float(t)) for x, t in segments_data
    ]
    assert len(segments) == published["n_subjects"]
    assert sum(s.n_events for s in segments) == published["n_complete_periods"]
    assert c1.statistic(segments) == pytest.approx(
        published["lr_multiprocess"], abs=0.01
    )
