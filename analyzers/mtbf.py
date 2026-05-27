"""MTBF (Mean Time Between Failures / calibration events) analyzer.

Takes a list of CalibrationEvent objects (from a CalibrationLogSchema Norm)
and computes inter-event intervals. No filtering is applied — all events
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
    intervals_s: np.ndarray          # N-1 inter-event intervals (seconds)
    event_times_unix_s: np.ndarray   # unix times at which each interval ENDS (N-1 values)
    stats: dict                      # mean, std, count, min, max (all in seconds)
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
        f"mean={stats['mean_s']/3600:.2f}h min={stats['min_s']:.1f}s max={stats['max_s']/3600:.1f}h"
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
