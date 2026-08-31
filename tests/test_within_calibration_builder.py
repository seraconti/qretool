"""Regression gate for the WithinCalibration panel split (builder vs renderer).

The output-builder must produce a COMPLETE typed artifact (all derived fields
populated) and the renderer must be a pure function of it. These tests pin the
numeric invariants and the damage-seam behavior; the array-equality-vs-pre-split
parity was verified separately against golden baselines captured on the known-good
commit.
"""

from __future__ import annotations

import matplotlib
import numpy as np

matplotlib.use("Agg")

from quebra.analyzers import windows
from quebra.analyzers.within_calibration_compute import (
    build_within_calibration_panel_data,
)
from quebra.panels.within_calibration import (
    WithinCalibrationPanel,
    WithinCalibrationPanelData,
)


def _carved(t_h, series, thresholds):
    """Carve through the real analyzer, as a job does.

    The builder no longer carves: it consumes the window and read tables, so a test
    that constructs panel data has to produce them the same way production does.
    """
    result = windows.run(
        windows.WindowsInputs(
            t_rel_s=np.asarray(t_h, dtype=float) * 3600.0,
            values=np.asarray(series, dtype=float),
            thresholds=thresholds,
            dataset_id="unit",
        )
    )
    return result.windows, result.reads


_THRESHOLDS = [("2 µs", 2.0, True), ("3 µs", 3.0, True), ("4 µs", 4.0, True)]


def _t2star_like() -> WithinCalibrationPanelData:
    t_h = np.linspace(0.0, 12.0, 500)
    s = 3.0 + 0.6 * np.sin(t_h) + 0.3 * np.cos(3.0 * t_h)
    return build_within_calibration_panel_data(
        t_h=t_h,
        primary_series=s,
        primary_label="T2* (µs)",
        thresholds=_THRESHOLDS,
        meta={"dataset": "unit-test"},
        windows=_carved(t_h, s, _THRESHOLDS)[0],
        reads=_carved(t_h, s, _THRESHOLDS)[1],
    )


def test_builder_populates_all_derived_fields() -> None:
    d = _t2star_like()
    labels = {lbl for lbl, _, _ in d.thresholds}
    assert set(d.reliability.cumulative_time_per_threshold) == labels
    assert set(d.reliability.cumulative_damage_per_threshold) == labels
    assert set(d.reliability.ttf_per_threshold) == labels
    assert set(d.reliability.threshold_window_stats) == labels
    assert set(d.reliability.survival_curve_min) == labels
    assert set(d.reliability.occupancy) == labels
    assert set(d.reliability.threshold_summary) == labels
    assert np.isfinite(d.signal.cv)
    # band 2 and band 3 each carry a per-threshold entry for every rung
    assert set(d.distinguish.state_series_per_threshold) == labels
    assert set(d.distinguish.state_counts_per_threshold) == labels
    assert set(d.reliability.compliance_state_series) == labels


def test_cumulative_time_is_monotonic_and_bounded() -> None:
    d = _t2star_like()
    total_h = float(d.signal.t_h[-1] - d.signal.t_h[0])
    for arr in d.reliability.cumulative_time_per_threshold.values():
        assert len(arr) == len(d.signal.t_h)
        assert np.all(np.diff(arr) >= -1e-12)  # non-decreasing
        assert arr[0] == 0.0
        assert arr[-1] <= total_h + 1e-9


def test_in_spec_frac_matches_summary() -> None:
    d = _t2star_like()
    for label, summ in d.reliability.threshold_summary.items():
        assert summ is not None  # dense synthetic series
        expected_frac_oos = 100.0 * (1.0 - d.reliability.occupancy[label])
        assert abs(summ["frac_oos_pct"] - expected_frac_oos) < 1e-9
        assert 0.0 <= d.reliability.occupancy[label] <= 1.0


def test_default_damage_is_excess_integral_not_noop() -> None:
    # A series that spends time out of spec must accumulate non-zero default damage,
    # and a non-identity damage_fn must change the curve (the seam is live).
    t_h = np.linspace(0.0, 10.0, 400)
    s = np.linspace(1.0, 6.0, 400)  # rises through the T2* thresholds
    thr = [("3 µs", 3.0, True)]
    win, rd = _carved(t_h, s, thr)
    default = build_within_calibration_panel_data(
        t_h=t_h,
        primary_series=s,
        primary_label="T2* (µs)",
        thresholds=thr,
        meta={},
        windows=win,
        reads=rd,
    )
    squared = build_within_calibration_panel_data(
        t_h=t_h,
        primary_series=s,
        primary_label="T2* (µs)",
        thresholds=thr,
        meta={},
        windows=win,
        reads=rd,
        damage_fn=lambda x: x**2,
    )
    d_default = default.reliability.cumulative_damage_per_threshold["3 µs"]
    d_squared = squared.reliability.cumulative_damage_per_threshold["3 µs"]
    assert d_default[-1] > 0.0
    assert not np.allclose(d_default, d_squared)


def test_renderer_produces_figure_without_data_arithmetic() -> None:
    d = _t2star_like()
    fig = WithinCalibrationPanel(name="unit").build_matplotlib(d)
    assert len(fig.axes) >= 5
    matplotlib.pyplot.close(fig)


def test_renderer_rejects_wrong_type() -> None:
    import pytest

    with pytest.raises(TypeError):
        WithinCalibrationPanel(name="unit").build_matplotlib(object())
