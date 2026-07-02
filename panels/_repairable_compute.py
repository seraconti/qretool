"""Output-builder for RepairablePanel: computes the COMPLETE typed panel data.

Owns every data-derived quantity the panel plots — elapsed days, intervals in
hours, 14-day binned interval stats, and the log-spaced histogram (counts + edges)
— so the materialized RepairablePanelData artifact is complete and the renderer
(panels/repairable.py) is a pure function of it. Arithmetic is ported verbatim from
the pre-split draw-time methods; parity is asserted array-equal against golden
baselines captured on the known-good commit.
"""

from __future__ import annotations

import numpy as np

from panels.repairable import RepairablePanelData


def _binned_interval_stats(
    elapsed_days: np.ndarray,
    intervals_h: np.ndarray,
    bin_days: float = 14.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Bin intervals by elapsed days; return (centers, median, q1, q3, p90)."""
    if len(elapsed_days) == 0:
        return (np.array([]),) * 5
    t0, t1 = float(np.min(elapsed_days)), float(np.max(elapsed_days))
    edges = np.arange(t0, t1 + bin_days, bin_days)
    if len(edges) < 2:
        edges = np.array([t0, t1 + bin_days])
    idx = np.digitize(elapsed_days, edges) - 1
    centers, medians, q1s, q3s, p90s = [], [], [], [], []
    for i in range(len(edges) - 1):
        vals = intervals_h[idx == i]
        if len(vals) == 0:
            continue
        centers.append(0.5 * (edges[i] + edges[i + 1]))
        medians.append(float(np.median(vals)))
        q1s.append(float(np.percentile(vals, 25)))
        q3s.append(float(np.percentile(vals, 75)))
        p90s.append(float(np.percentile(vals, 90)))
    return (
        np.asarray(centers),
        np.asarray(medians),
        np.asarray(q1s),
        np.asarray(q3s),
        np.asarray(p90s),
    )


def _interval_histogram(
    intervals_s: np.ndarray, n_bins: int = 50
) -> tuple[np.ndarray, np.ndarray]:
    """Log-spaced histogram of positive intervals; returns (counts, edges).

    Matches the pre-split ax.hist(valid, bins=logspace(...)) exactly (ax.hist counts
    identically to np.histogram). Empty (counts, edges) when no positive intervals.
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


def build_repairable_panel_data(
    *,
    intervals_s: np.ndarray,
    event_times_unix_s: np.ndarray,
    stats: dict[str, object],
    meta: dict[str, object],
    bin_days: float = 14.0,
    hist_bins: int = 50,
) -> RepairablePanelData:
    """Compute every data-derived quantity and return a COMPLETE RepairablePanelData.

    Sole constructor path: the renderer assumes the derived fields are populated.
    """
    intervals_arr = np.asarray(intervals_s, dtype=float)
    times_arr = np.asarray(event_times_unix_s, dtype=float)

    if len(times_arr) > 0:
        t0 = float(times_arr[0])
        elapsed_days = (times_arr - t0) / 86400.0
    else:
        elapsed_days = np.array([])
    intervals_h = intervals_arr / 3600.0

    counts, edges = _interval_histogram(intervals_arr, n_bins=hist_bins)

    return RepairablePanelData(
        intervals_s=intervals_arr,
        event_times_unix_s=times_arr,
        stats=stats,
        meta=meta,
        elapsed_days=elapsed_days,
        intervals_h=intervals_h,
        binned_interval_stats=_binned_interval_stats(
            elapsed_days, intervals_h, bin_days=bin_days
        ),
        histogram_counts=counts,
        histogram_edges=edges,
    )
