from __future__ import annotations

from typing import Dict, Tuple

import matplotlib.pyplot as plt


def make_fidelity_figure(figsize: Tuple[float, float] = (14, 16)) -> Tuple[plt.Figure, Dict[str, plt.Axes]]:
    """Create a fidelity figure with named axes and friendlier sizing.

    Returns (fig, axes) where axes is a dict with keys:
      'inf', 'thresholds', 'zoom', 'roll', 'survival', 'summary'
    """
    fig = plt.figure(figsize=figsize, constrained_layout=True, facecolor="white")
    # Give more vertical room to the zoom/roll row (index 2)
    height_ratios = [1.8, 0.9, 3.2, 2.0, 1.2]
    gs = fig.add_gridspec(5, 2, height_ratios=height_ratios)

    ax_inf = fig.add_subplot(gs[0, :])
    ax_thresholds = fig.add_subplot(gs[1, :])
    ax_zoom = fig.add_subplot(gs[2, 0])
    ax_roll = fig.add_subplot(gs[2, 1])
    ax_survival = fig.add_subplot(gs[3, :])
    ax_summary = fig.add_subplot(gs[4, :])

    axes = {
        "inf": ax_inf,
        "thresholds": ax_thresholds,
        "zoom": ax_zoom,
        "roll": ax_roll,
        "survival": ax_survival,
        "summary": ax_summary,
    }

    # Ensure white background on axes
    for ax in axes.values():
        ax.set_facecolor("white")

    return fig, axes


def apply_common_style(ax: plt.Axes) -> None:
    """Apply common axis styling (no grey background, light grid)."""
    ax.set_facecolor("white")
    ax.grid(True, which="both", color="lightgray", alpha=0.35)
