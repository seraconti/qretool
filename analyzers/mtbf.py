"""MTBF (Mean Time Between Failures / calibration events) analyzer.

Takes a list of CalibrationEvent objects (from a CalibrationLogSchema Norm)
and computes inter-event intervals. No filtering is applied - all events
in the log are used regardless of chi_squared or other quality metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from core.types import CalibrationEvent, Norm


@dataclass
class MtbfInputs:
    events: list[CalibrationEvent]
    meta: dict = field(default_factory=dict)


@dataclass
class MtbfResult:
    intervals_s: np.ndarray  # N-1 inter-event intervals (seconds)
    event_times_unix_s: (
        np.ndarray
    )  # unix times at which each interval ENDS (N-1 values)
    stats: dict  # mean, std, count, min, max (all in seconds)
    diagnostics: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)


def run(inputs: MtbfInputs) -> MtbfResult:
    if len(inputs.events) < 2:
        raise ValueError(f"MTBF requires at least 2 events; got {len(inputs.events)}")
    times = np.array([e.t_event_unix_s for e in inputs.events], dtype=float)
    times.sort()
    intervals = np.diff(times)
    stats = {
        "mean_s": float(np.mean(intervals)),
        "std_s": float(np.std(intervals)),
        "count": int(len(intervals)),
        "min_s": float(np.min(intervals)),
        "max_s": float(np.max(intervals)),
    }
    print(
        f"[mtbf] events={len(inputs.events)} intervals={len(intervals)} "
        f"mean={stats['mean_s'] / 3600:.2f}h min={stats['min_s']:.1f}s max={stats['max_s'] / 3600:.1f}h"
    )
    return MtbfResult(
        intervals_s=intervals,
        event_times_unix_s=times[1:],
        stats=stats,
        meta=inputs.meta,
    )


def make_inputs_from_norm(norm: Norm) -> MtbfInputs:
    return MtbfInputs(
        events=norm.events["calibration"],
        meta=dict(norm["meta"]),
    )


# ---------------------------------------------------------------------------
# Interval histogram
#
# One definition of the binning, used by BOTH the across-calibration panel's histogram
# subplot (via panels/_across_calibration_compute._interval_histogram) and the standalone
# mean-time-between-calibrations figure. Two copies would be two chances for the
# same bar to mean different things in two figures of the same log.
# ---------------------------------------------------------------------------


def log_interval_histogram(
    intervals_s: np.ndarray, n_bins: int = 50
) -> tuple[np.ndarray, np.ndarray]:
    """Log-spaced histogram of POSITIVE intervals; returns (counts, edges_s).

    Non-positive intervals cannot be placed on a log axis and are dropped here. Callers
    that render the result must state how many - `IntervalHistogramResult` carries the
    count for exactly that reason. Empty (counts, edges) when nothing is positive.
    """
    ivs = np.asarray(intervals_s, dtype=float)
    valid = ivs[ivs > 0]
    if len(valid) == 0:
        return np.array([]), np.array([])
    log_bins = np.logspace(
        np.log10(float(np.min(valid))), np.log10(float(np.max(valid))), n_bins
    )
    counts, edges = np.histogram(valid, bins=log_bins)
    return counts, edges


@dataclass
class IntervalHistogramResult:
    """Complete typed artifact for the single-axes interval histogram.

    Hours throughout (`_h`), because a calibration log spans seconds to weeks and hours
    is the only unit that keeps both ends of that range readable as plain numbers. The
    conversion happens HERE, in the step, not at draw time.

    `mean_h` is the arithmetic mean of every positive interval - the "mean time between
    calibrations" the figure is named for. It is reported beside `median_h` because on a
    log axis the two land in visibly different places, and a reader given only the mean
    cannot tell that.
    """

    counts: np.ndarray
    edges_h: np.ndarray
    mean_h: float
    median_h: float
    n_intervals: int
    n_nonpositive_dropped: int
    label: str = ""
    dataset_id: str = ""
    meta: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.counts) and len(self.edges_h) != len(self.counts) + 1:
            raise ValueError(
                "incomplete IntervalHistogramResult: edges_h must have one more entry "
                f"than counts ({len(self.edges_h)} vs {len(self.counts)})"
            )


def make_interval_histogram(
    result: MtbfResult, *, label: str = "", n_bins: int = 50
) -> IntervalHistogramResult:
    """Adapter: MtbfResult -> the typed artifact the histogram figure draws.

    The mean and median are taken over the SAME positive intervals the bars count, so the
    marked mean cannot sit at a value no bar contributed to.
    """
    intervals_s = np.asarray(result.intervals_s, dtype=float)
    positive = intervals_s[intervals_s > 0]
    if len(positive) == 0:
        raise ValueError(
            "interval histogram needs at least one positive inter-event interval; "
            f"got {len(intervals_s)} intervals, none positive"
        )
    counts, edges_s = log_interval_histogram(intervals_s, n_bins=n_bins)
    meta = dict(result.meta)
    return IntervalHistogramResult(
        counts=counts,
        edges_h=edges_s / 3600.0,
        mean_h=float(np.mean(positive)) / 3600.0,
        median_h=float(np.median(positive)) / 3600.0,
        n_intervals=int(len(positive)),
        n_nonpositive_dropped=int(len(intervals_s) - len(positive)),
        label=label,
        dataset_id=str(meta.get("dataset_id", "")),
        meta=meta,
    )
