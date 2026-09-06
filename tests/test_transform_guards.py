"""The transforms' and TLF's guards, each shown to fail when its guard is removed.

`transforms/interpolate.py`, `transforms/filter.py` and `analyzers/tlf.py` had no tests at
all. What they now assert is one property: a step hands downstream either a value the
instrument produced or nothing, never a value invented to stand in for one.

Scope is deliberately the GUARDS, not the numbers. Whether a pchip through a reduced support
set is the right estimate, or whether the sigma factor is well chosen, is a question for an
oracle and a synthetic generator. Whether a failed fit can silently become 0.0 Hz on a
uniform grid is answerable here, and the answer has to stay answered.

Every assertion here was checked by mutating the guard it covers and confirming the test goes
red. A guard whose test passes either way is a claim, not a check - and one test in the first
draft of this file was exactly that, passing against a mutant whose generic column loop was
reduced to `out[key] = value`.
"""

from __future__ import annotations

import numpy as np
import pytest

from quebra.analyzers.tlf import run as run_tlf
from quebra.transforms.filter import run as run_filter
from quebra.transforms.interpolate import run as run_interpolate

pytestmark = pytest.mark.unit


def _norm(**overrides) -> dict[str, object]:
    """A minimal well-formed Norm: 10 reads, a clean linear detuning."""
    n = 10
    norm: dict[str, object] = {
        "t_rel_s": np.arange(n, dtype=float) * 10.0,
        "delta_hz": np.linspace(100.0, 200.0, n),
        "meta": {"dataset_id": "unit"},
    }
    norm.update(overrides)
    return norm


_FILTER_CFG = {
    "filter": {
        "apply_chi_squared": False,
        "apply_frequency_window": False,
        "apply_sigma": True,
        "sigma_factor": 3.5,
    },
    "dataset_profile": "unit",
}


# --- interpolate: no fabricated value reaches the grid ----------------------


def test_a_failed_fit_is_dropped_not_zero_filled():
    """The load-bearing one.

    Zero-filling put a real, wrong detuning on the grid - exactly 0 Hz - and pchip passes
    through its data, so the fabricated point dragged its neighbours too. Nothing downstream
    could reject any of it, because no non-finite value survived to be seen.
    """
    values = np.linspace(100.0, 200.0, 10)
    values[4] = np.nan
    out = run_interpolate(_norm(delta_hz=values), {})
    grid = np.asarray(out["delta_hz"], dtype=float)

    assert out["meta"]["n_nonfinite_dropped"] == {"delta_hz": 1}
    assert not np.any(grid == 0.0), "a dropped read was zero-filled"
    # Bracketed by its surviving neighbours rather than pulled toward zero.
    assert 100.0 < float(grid[4]) < 200.0


def test_a_clean_input_is_untouched_by_the_masking():
    """The negative control. A guard that mangled every input would pass the test above."""
    out = run_interpolate(_norm(), {})
    grid = np.asarray(out["delta_hz"], dtype=float)
    assert "n_nonfinite_dropped" not in out["meta"]
    assert np.all(np.isfinite(grid))
    # Endpoints coincide with real reads, so they must be the measured values exactly.
    assert float(grid[0]) == pytest.approx(100.0)
    assert float(grid[-1]) == pytest.approx(200.0)


def test_grid_points_outside_the_finite_support_are_nan_not_extrapolated():
    """Dropping an edge read shortens the support while the grid still spans the interval.

    pchip would extrapolate into the difference, which substitutes one fabricated value for
    another. Only the edges go NaN - an interior drop leaves the grid fully finite, which the
    third assertion pins so this cannot be satisfied by NaN-ing everything.
    """
    values = np.linspace(100.0, 200.0, 10)
    values[0] = np.nan
    values[-1] = np.nan
    grid = np.asarray(
        run_interpolate(_norm(delta_hz=values), {})["delta_hz"], dtype=float
    )

    assert np.isnan(grid[0]) and np.isnan(grid[-1])
    finite = grid[np.isfinite(grid)]
    assert finite.min() >= 100.0 and finite.max() <= 200.0, (
        "extrapolated past the support"
    )

    interior = np.linspace(100.0, 200.0, 10)
    interior[5] = np.nan
    assert np.all(
        np.isfinite(
            np.asarray(run_interpolate(_norm(delta_hz=interior), {})["delta_hz"])
        )
    )


def test_a_non_finite_timestamp_raises():
    """The time axis is the one column with nothing to interpolate it from."""
    t = np.arange(10, dtype=float) * 10.0
    t[3] = np.nan
    with pytest.raises(ValueError, match="non-finite timestamp"):
        run_interpolate(_norm(t_rel_s=t), {})


def test_too_few_finite_values_to_interpolate_raises():
    values = np.full(10, np.nan)
    values[0] = 1.0
    with pytest.raises(ValueError, match="cannot interpolate"):
        run_interpolate(_norm(delta_hz=values), {})


def test_a_row_aligned_companion_column_is_resampled_to_the_grid():
    """Asserted on VALUES against a NON-UNIFORM clock, because length proves nothing here.

    `x_uniform` is built with `num=len(t_rel_s)`, so the grid always has the input's length -
    a length assertion passes even for `out[key] = value`, the exact passthrough this forbids.
    And on the uniform clock `_norm` provides, resampling is the identity, so a value
    assertion would pass too. An uneven clock is what makes the two distinguishable.
    """
    uneven = np.array([0.0, 1.0, 2.0, 3.0, 40.0, 41.0, 42.0, 43.0, 44.0, 90.0])
    companion = np.linspace(1.0, 10.0, 10)
    out = run_interpolate(
        _norm(
            t_rel_s=uneven, delta_hz=np.linspace(100.0, 200.0, 10), T2star_s=companion
        ),
        {},
    )
    resampled = np.asarray(out["T2star_s"], dtype=float)

    assert len(resampled) == len(np.asarray(out["t_rel_s"]))
    assert not np.allclose(resampled, companion), (
        "the companion column came back at its input sampling, unresampled"
    )
    # Endpoints coincide with real reads either way, so those must be preserved exactly.
    assert resampled[0] == pytest.approx(companion[0])
    assert resampled[-1] == pytest.approx(companion[-1])


def test_a_mismatched_raw_frequency_raises_rather_than_being_dropped():
    """Silently omitting it reads as "this dataset has no raw frequency"."""
    with pytest.raises(ValueError, match="raw_frequency_hz length"):
        run_interpolate(_norm(raw_frequency_hz=np.ones(4)), {})


# --- filter: every column keeps its alignment with t_rel_s ------------------


def test_filter_raises_on_a_column_it_cannot_keep_aligned():
    """A column left at full length while its siblings shrink is index-misaligned for every
    step downstream, and no consumer raises on it."""
    with pytest.raises(ValueError, match="filter cannot mask"):
        run_filter(_norm(T2star_s=np.ones(4)), _FILTER_CFG, None)


def test_filter_keeps_every_row_aligned_column_the_same_length():
    """The negative control: a Norm that loses a row keeps every column in step.

    The dropped row is a non-finite value rather than a sigma outlier. A single outlier among
    ten reads inflates the sigma it is measured against, so 3.5 sigma does not remove it -
    the masking effect, and not what this test is about.
    """
    values = np.linspace(100.0, 200.0, 10)
    values[4] = np.nan
    result = run_filter(
        _norm(delta_hz=values, T2star_s=np.linspace(1e-6, 2e-6, 10)),
        _FILTER_CFG,
        None,
    )
    lengths = {
        key: len(np.asarray(value))
        for key, value in result.final_norm.items()
        if key != "meta" and np.asarray(value).ndim
    }
    assert len(set(lengths.values())) == 1, lengths
    assert lengths["t_rel_s"] == 9, "the non-finite read should have been dropped"


def test_a_single_failed_fit_does_not_empty_the_dataset():
    """`np.mean`/`np.std` propagate, so one NaN made both NaN, every comparison False, and
    the mask all-False - the dataset reached the analyzer empty and was reported as empty."""
    values = np.linspace(100.0, 200.0, 10)
    values[4] = np.nan
    final = run_filter(_norm(delta_hz=values), _FILTER_CFG, None).final_norm
    kept = len(np.asarray(final["t_rel_s"]))
    assert kept == 9, f"expected the one non-finite read dropped, kept {kept}"


def test_both_transforms_reject_a_length_mismatched_column():
    """The half of the parity that was still silent.

    `filter._subset_norm` raised on a length mismatch; `interpolate` passed the column
    through, so it came out at its input length against the new grid - misaligned, with no
    error and no diagnostic. Same input class, same verdict now.
    """
    short = np.linspace(0.1, 0.3, 3)
    with pytest.raises(ValueError, match="filter cannot mask"):
        run_filter(_norm(chi_squared=short), _FILTER_CFG, None)
    with pytest.raises(ValueError, match="interpolate cannot resample"):
        run_interpolate(_norm(chi_squared=short), {})


def test_both_transforms_reject_an_unusable_column_the_same_way():
    """They took opposite decisions on this class: filter raised, interpolate passed through.

    `interpolate` has one wiring site in `recipes.py` and `filter` is always upstream of it
    there, but a job written against `docs/WRITING_A_JOB.md` can wire either step alone, so
    neither may lean on that ordering.
    """
    ragged = [[1, 2], [3]]
    with pytest.raises(ValueError, match="filter cannot mask"):
        run_filter(_norm(odd=ragged), _FILTER_CFG, None)
    with pytest.raises(ValueError, match="interpolate cannot resample"):
        run_interpolate(_norm(odd=ragged), {})


def test_an_all_non_finite_series_raises_naming_its_own_cause():
    with pytest.raises(ValueError, match="no finite 'delta_hz'"):
        run_filter(_norm(delta_hz=np.full(10, np.nan)), _FILTER_CFG, None)


# --- tlf: reproducible under a fixed identity ------------------------------


def _bimodal(n: int = 400) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(11)
    values = np.concatenate(
        [rng.normal(1.0e6, 300.0, n), rng.normal(1.002e6, 300.0, n)]
    )
    return values, np.arange(values.size, dtype=float) * 24.0


def test_the_seed_reaches_both_estimators():
    """Asserted on `random_state`, not on two runs agreeing.

    Agreement is the wrong oracle: `GaussianMixture` initialises by k-means, and on
    well-separated lobes it converges to the same solution from any start - so two unseeded
    runs agree too, and a test of agreement passes with `random_state=None`. Checked by
    removing the seed: the agreement form stayed green. What has to hold is that the seed
    reaches sklearn, which is observable directly.
    """
    values, timestamps = _bimodal()
    result = run_tlf(values, timestamps, seed=4242)
    assert result.gmm1.random_state == 4242
    assert result.gmm2.random_state == 4242, (
        "the 2-component fit is the one whose init decides is_bimodal"
    )


def test_the_same_seed_gives_the_same_verdict():
    """Weaker than the check above and kept as a sanity floor: whatever the seed does, it
    must not make one input give two answers."""
    values, timestamps = _bimodal()
    first = run_tlf(values, timestamps, seed=20260902)
    second = run_tlf(values, timestamps, seed=20260902)
    assert first.bic_delta == second.bic_delta
    assert first.is_bimodal == second.is_bimodal
    assert first.mean_dwell_s0 == second.mean_dwell_s0


def test_the_seed_is_required():
    """Not defaulted, so a caller cannot omit it and get an irreproducible answer."""
    values, timestamps = _bimodal()
    with pytest.raises(TypeError):
        run_tlf(values, timestamps)


def test_a_failed_fit_reports_fit_failed_rather_than_a_verdict(monkeypatch):
    """`bic_delta = 0.0` with `gmm2` aliased to `gmm1` let a consumer read "no evidence of
    bimodality" off a comparison that never happened."""
    import quebra.analyzers.tlf as tlf_module

    real = tlf_module.GaussianMixture

    class _FailsOnTwo:
        def __init__(self, *args, n_components: int = 1, **kwargs):
            self._n = n_components
            self._inner = real(*args, n_components=n_components, **kwargs)

        def fit(self, *args, **kwargs):
            if self._n == 2:
                raise ValueError("singular covariance")
            return self._inner.fit(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._inner, name)

    monkeypatch.setattr(tlf_module, "GaussianMixture", _FailsOnTwo)
    values, timestamps = _bimodal()
    result = run_tlf(values, timestamps, seed=1)

    assert result.fit_failed is True
    assert result.bic_delta is None, (
        "a comparison that did not happen reported a number"
    )
    assert result.gmm2 is None, "gmm2 aliased to the 1-component fit"
    assert result.is_bimodal is False
