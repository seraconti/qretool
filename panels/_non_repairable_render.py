"""Render-local helpers for NonRepairablePanel: functions of axes and theme only.

Nothing here derives a SCIENTIFIC quantity or writes into the artifact. These are
view-only functions of already-computed arrays: adaptive limits, decade guides, bin
geometry, and the observed-stretch slicing. They do arithmetic — `adaptive_ylim` takes
quantiles, `observed_slices` searches for cut indices — but only to decide where to put
ink, which CLAUDE.md places on the renderer's side of the line. Every value they read
was computed by _non_repairable_compute and lives in the artifact.

Kept out of non_repairable.py so the renderer file is the drawing sequence and this
file is the arithmetic that drawing needs.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from panels._non_repairable_data import NonRepairablePanelData


def draw_decade_guides(ax: plt.Axes, values: np.ndarray) -> None:
    clipped = np.clip(np.asarray(values, dtype=float), 1e-16, None)
    lo, hi = float(np.min(clipped)), float(np.max(clipped))
    if not (np.isfinite(lo) and np.isfinite(hi) and lo > 0.0 and hi > 0.0):
        return
    for power in range(int(np.floor(np.log10(lo))), int(np.ceil(np.log10(hi))) + 1):
        ax.axhline(
            10.0**power,
            color="gray",
            linestyle="--",
            linewidth=0.7,
            alpha=0.3,
            zorder=0,
        )


def adaptive_ylim(series_list: list[np.ndarray]) -> tuple[float, float]:
    all_values = np.concatenate(
        [np.asarray(s, dtype=float) for s in series_list if len(s) > 0]
    )
    finite = all_values[np.isfinite(all_values)]
    if len(finite) == 0:
        return 0.0, 1.0
    q_lo = float(np.quantile(finite, 0.05))
    q_hi = float(np.quantile(finite, 0.95))
    if q_hi <= q_lo:
        q_lo, q_hi = float(np.min(finite)), float(np.max(finite))
    span = max(1e-9, q_hi - q_lo)
    pad = 0.15 * span
    return q_lo - pad, q_hi + pad


def observed_slices(pd_: NonRepairablePanelData) -> list[tuple[int, int]]:
    """[start, stop) index ranges of contiguously observed reads.

    Pure lookup of the gap boundaries the carve recorded — the renderer decides
    nothing about where a gap is, only that it does not draw through one.
    """
    if not pd_.gap_spans_h:
        return [(0, len(pd_.t_h))]
    cut_points = []
    for _t_before_h, t_after_h in pd_.gap_spans_h:
        idx = int(np.searchsorted(pd_.t_h, t_after_h, side="left"))
        if 0 < idx < len(pd_.t_h):
            cut_points.append(idx)
    bounds = [0, *sorted(set(cut_points)), len(pd_.t_h)]
    return [(lo, hi) for lo, hi in zip(bounds[:-1], bounds[1:]) if hi > lo]


def bin_centers_and_widths(
    edges: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    widths = np.diff(edges)
    return edges[:-1] + widths / 2.0, widths
