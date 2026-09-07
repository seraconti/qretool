"""Algebraic invariants of `kaplan_meier.run` under generated inputs.

Oracle: algebra. These hold for every admissible input, not for a case someone chose, which
is the one thing the fixed oracles in `tests/test_kaplan_meier.py` cannot give.

Separate from that file because `AGENTS.md` section 7 indexes by oracle AND subject: the
subject is shared but the oracle is not, and the two carry different tier markers. The
constructor is duplicated in four lines rather than imported, so neither file can silently
change what the other tests.

`quebraplan.md` 5.4 lists five property classes. Three are declined and the reasons are
recorded rather than left as absences:

- **Cumulative hazard non-decreasing** has no subject. No Nelson-Aalen module ships;
  `AGENTS.md's not-implemented list` says so, and `reliability_band.py:70` declares a `cumulative_hazard`
  field that nothing anywhere writes, which is what makes the absence easy to miss.
- **Permutation invariance** is already covered on the real permutation machinery by
  `tests/test_checks_statistics.py`, on the estimator that actually permutes.
- **Shape and type preservation** is what the typed dataclasses and `make types` do. A
  property asserting an array's dtype restates its annotation.

Kaplan-Meier is the subject because a hand-rolled product-limit loop with a tie sort and a
while-loop over tied times has an input space that hand-picked cases sample thinly, and that
loop is exactly where the fixed cases stop.

One invariant that looks obvious is NOT written here, because it is false: "adding a censored
observation later than every death does not change S(t) below that time". It does. Such a
subject is at risk at every death, so `n_j` rises at each: deaths at t = 1 and t = 2 with
n = 2 give S(1) = 1/2, and adding a censored observation at t = 3 gives S(1) = 2/3.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from quebra.analyzers import kaplan_meier as km

pytestmark = pytest.mark.properties

# Bounds are stated rather than left at strategy defaults: durations are minutes on a real
# record and non-finite or negative values are rejected by `run` itself, so generating them
# would test the guard, not the algebra.
_durations = st.lists(
    st.floats(min_value=0.0, max_value=1e4, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=40,
)


@st.composite
def _records_with_a_late_censoring(draw):
    """A record guaranteed to hold a death and a censored window at or beyond the last one.

    CONSTRUCTED, not filtered. An earlier version drew freely and used two `assume()` calls
    to reach this shape, which rejected 119 of every 219 draws. That is WASTE, not risk: the
    `filter_too_much` health check needs 50 invalid draws before 10 valid ones, which at this
    rate has probability about 8e-07, so an earlier claim that it was near tripping was wrong
    by six orders of magnitude. Building the shape is right because every example then counts
    and the interesting cases are reached deliberately, not because the filter was dangerous.
    """
    deaths = draw(
        st.lists(
            st.floats(
                min_value=0.0, max_value=1e4, allow_nan=False, allow_infinity=False
            ),
            min_size=1,
            max_size=20,
        )
    )
    last = max(deaths)
    late = draw(
        st.lists(
            st.floats(
                min_value=last,
                max_value=last + 1e4,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=1,
            max_size=10,
        )
    )
    durations = np.asarray(deaths + late, dtype=float)
    observed = np.asarray([True] * len(deaths) + [False] * len(late), dtype=bool)
    return durations, observed


@st.composite
def _records(draw, force_uncensored: bool = False):
    durations = draw(_durations)
    if force_uncensored:
        observed = [True] * len(durations)
    else:
        observed = draw(
            st.lists(st.booleans(), min_size=len(durations), max_size=len(durations))
        )
    return np.asarray(durations, dtype=float), np.asarray(observed, dtype=bool)


def _run(durations, observed):
    return km.run(km.KaplanMeierInputs(duration_min=durations, death_observed=observed))


@given(_records())
def test_survival_is_non_increasing_and_stays_in_the_unit_interval(record) -> None:
    """Oracle: `S` is a product of factors in [0, 1], so it can only fall."""
    durations, observed = record
    curve = _run(durations, observed)

    assert np.all(np.diff(curve.survival) <= 1e-12)
    assert np.all(curve.survival >= 0.0) and np.all(curve.survival <= 1.0)
    assert curve.survival[0] == 1.0


@given(_records())
def test_the_band_contains_the_point_estimate_wherever_both_are_defined(record) -> None:
    """Oracle: the log-log band is `S**exp(+/- z se)`, which brackets `S` for `0 < S < 1`."""
    durations, observed = record
    curve = _run(durations, observed)

    both = np.isfinite(curve.band_lower) & np.isfinite(curve.band_upper)
    assert np.all(curve.band_lower[both] <= curve.survival[both] + 1e-12)
    assert np.all(curve.survival[both] <= curve.band_upper[both] + 1e-12)
    assert np.all(curve.band_lower[both] >= 0.0)
    assert np.all(curve.band_upper[both] <= 1.0)


@given(_records(force_uncensored=True))
def test_with_no_censoring_it_equals_one_minus_the_empirical_cdf_everywhere(
    record,
) -> None:
    """Oracle: the empirical survival function, as a property rather than a chosen case.

    `tests/test_kaplan_meier.py` pins this at three fixed sizes on evenly spaced durations.
    Here it must hold for arbitrary draws, including heavy ties and repeated zeros, which is
    where the tie block does its work.

    Stated per DISTINCT time, taking the last emitted value. `run` seeds the curve with a
    synthetic `t = 0, S = 1` row, so a zero-duration observed death emits `0.0` TWICE: once
    as the seed and once as its own step. Hypothesis found that on the first run, with the
    minimal case `durations=[0.0], observed=[True]` giving `time_min=[0.0, 0.0]` and
    `survival=[1.0, 0.0]`. Comparing elementwise would demand `S(0) = 1` and `S(0) = 0` of
    the same point. A zero-duration OBSERVED death is unreachable from a carve - only a
    censored window can have one - but `run` accepts hand-built inputs, so the property has
    to hold for them.
    """
    durations, observed = record
    curve = _run(durations, observed)
    n = len(durations)

    last_at_time: dict[float, float] = {}
    for t, s in zip(curve.time_min, curve.survival):
        last_at_time[float(t)] = float(s)

    for t, s in last_at_time.items():
        expected = float(np.count_nonzero(durations > t)) / n
        assert s == pytest.approx(expected, abs=1e-9), f"S({t})"


@given(_records_with_a_late_censoring())
def test_moving_a_censored_observation_past_the_last_death_changes_no_risk_set(
    record,
) -> None:
    """Oracle: a censored observation enters only the risk sets of deaths it outlives.

    If a window is censored at or after the last observed death, then for every death time
    `d` the predicate `duration >= d` is already true and stays true however much later the
    censoring is moved. Every `n_j` is therefore unchanged and so is `S`. Move it earlier
    than a death and the property genuinely fails, which is why the shift is upward only.

    Named for the risk sets rather than "changes nothing", because other fields DO change:
    `censor_time_min`, `max_observed_min`, and `n_zero_duration` when the moved window had
    duration 0. The three asserted below are the ones the invariance covers.

    This is an EXACT algebraic equality, not a statistical comparison: two deterministic
    computations must agree to 1e-12. There is no tolerance on a random quantity to tune,
    and nothing here can be flaky - either the invariance holds or a risk set is wrong.

    The shape is CONSTRUCTED by the strategy, not filtered for: see
    `_records_with_a_late_censoring`. The old `assume()` version wasted about half its draws;
    it was not in danger of tripping a health check.

    This is the only property here whose arithmetic depends on censoring at all. The other
    three hold on a record with no censored observation, so without this one the module
    could pass with `death_observed` ignored entirely - which was measured: stubbing it to
    all-True left the file green.

    It replaces an order-invariance property that duplicated
    `tests/test_kaplan_meier.py::test_the_estimate_is_invariant_to_input_order` - same
    oracle, same assertions, failing together under both sort mutations - rather than being
    added alongside it, because R6.6's envelope is +3 to +4.
    """
    durations, observed = record
    last_death = float(durations[observed].max())
    movable = (~observed) & (durations >= last_death)
    assert movable.any(), "the strategy must construct this shape, not hope for it"

    reference = _run(durations, observed)
    shifted = durations.copy()
    shifted[movable] = shifted[movable] + 17.5  # any upward shift; it clears no death
    moved = _run(shifted, observed)

    assert moved.time_min.tolist() == reference.time_min.tolist()
    assert moved.survival == pytest.approx(reference.survival, abs=1e-12)
    assert moved.n_at_risk.tolist() == reference.n_at_risk.tolist()
