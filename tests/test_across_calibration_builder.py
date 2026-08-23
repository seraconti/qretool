"""Regression gate for the AcrossCalibration panel split (builder vs renderer).

The output-builder must produce a COMPLETE typed artifact and the renderer must be a
pure function of it. Array-equality vs the pre-split draw-time values was verified
separately against golden baselines on the known-good commit.
"""

from __future__ import annotations

import matplotlib
import numpy as np

matplotlib.use("Agg")

from panels._across_calibration_compute import build_across_calibration_panel_data
from panels.across_calibration import AcrossCalibrationPanel, AcrossCalibrationPanelData


def _case(
    n: int = 320, span_days: float = 180.0, seed: int = 1
) -> AcrossCalibrationPanelData:
    rng = np.random.default_rng(seed)
    gaps = rng.gamma(2.0, 1.0, n)
    times = np.cumsum(gaps)
    times = times / times[-1] * (span_days * 86400.0)
    ev = 1.6e9 + times
    iv = np.diff(ev)
    ev = ev[1:]
    stats = {
        "count": int(len(iv)),
        "mean_s": float(np.mean(iv)),
        "std_s": float(np.std(iv)),
        "min_s": float(np.min(iv)),
        "max_s": float(np.max(iv)),
    }
    return build_across_calibration_panel_data(
        intervals_s=iv,
        event_times_unix_s=ev,
        stats=stats,
        meta={"qubit": "2", "device": "6D2S", "dataset_id": "unit"},
    )


def test_builder_populates_derived_fields() -> None:
    d = _case()
    assert len(d.elapsed_days) == len(d.event_times_unix_s)
    assert len(d.intervals_h) == len(d.intervals_s)
    assert d.elapsed_days[0] == 0.0
    assert len(d.binned_interval_stats) == 5
    centers = d.binned_interval_stats[0]
    assert len(centers) > 1  # 180-day span → multiple 14-day bins
    assert len(d.histogram_counts) > 0
    assert len(d.histogram_edges) == len(d.histogram_counts) + 1


def test_unit_conversions_are_exact() -> None:
    d = _case()
    np.testing.assert_array_equal(d.intervals_h, d.intervals_s / 3600.0)
    t0 = float(d.event_times_unix_s[0])
    np.testing.assert_array_equal(d.elapsed_days, (d.event_times_unix_s - t0) / 86400.0)


def test_histogram_counts_conserve_positive_intervals() -> None:
    d = _case()
    assert int(d.histogram_counts.sum()) == int(np.sum(d.intervals_s > 0))


def test_short_span_single_bin() -> None:
    d = _case(n=40, span_days=9.0, seed=2)
    centers = d.binned_interval_stats[0]
    assert len(centers) == 1  # span < 14 days → single bin


def test_renderer_produces_figure() -> None:
    d = _case()
    fig = AcrossCalibrationPanel(name="unit").build_matplotlib(d)
    assert len(fig.axes) == 4
    matplotlib.pyplot.close(fig)


def test_renderer_rejects_wrong_type() -> None:
    import pytest

    with pytest.raises(TypeError):
        AcrossCalibrationPanel(name="unit").build_matplotlib(object())
