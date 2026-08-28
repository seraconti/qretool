"""Single-axes histogram of the time between calibrations. Nothing else on the figure.

A pure renderer over `analyzers.mtbf.IntervalHistogramResult`: the bin edges arrive in
hours, the mean and median arrive as scalars, and this file does no arithmetic on any of
them beyond placing bars between edges.

The x-axis is logarithmic because a 912-day calibration log runs from seconds to weeks -
four and a half decades - and a linear axis puts every bar in the first pixel column. The
mean and the median are both marked: on a log axis they land far apart, and a figure
titled for the mean that does not show where the median sits invites the reader to take
one for the other.

DEVIATION FROM docs/FIGURE_STANDARD.md, on the author's instruction: no caption and no
in-panel count note. `IntervalHistogramResult` records `n_nonpositive_dropped`, and the
builder raises if nothing is positive, so a dropped interval is still recoverable from the
materialized artifact - but it is no longer visible to someone holding only the image.
Restoring it means putting `_note` back. (On the shipped qubit 6 log that count is zero.)
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter, LogLocator

from quebra.analyzers.mtbf import IntervalHistogramResult
from quebra.plots import theme
from quebra.plots.base import BasePlot

# Vertical room left above the tallest bar for the mean and median labels.
_HEADROOM = 1.16


def _plain_hours(value: float, _pos: int) -> str:
    """Plain-number ticks; the unit lives in the axis label (FIGURE_STANDARD)."""
    if value <= 0:
        return ""
    if value >= 1:
        return f"{value:.0f}"
    return f"{value:g}"


class MTBCHistogramPlot(BasePlot):
    """Distribution of intervals between calibrations, with the mean and median marked."""

    def build_matplotlib(
        self, result: IntervalHistogramResult, style: str = "default"
    ) -> plt.Figure:
        if not isinstance(result, IntervalHistogramResult):
            raise TypeError(
                "MTBCHistogramPlot draws an IntervalHistogramResult, not "
                f"{type(result).__name__}"
            )
        if not len(result.counts):
            raise ValueError(
                "interval histogram is empty - no positive intervals to draw"
            )

        with theme.style_context(style):
            guide_label = theme.scaled_text(theme.GUIDE_LABEL, style)
            color = theme.POSTER_INK_DISTRIBUTION

            edges = result.edges_h
            fig, ax = plt.subplots(figsize=(12.0, 7.5))
            fig.patch.set_facecolor("white")
            ax.set_facecolor("white")

            ax.bar(
                edges[:-1],
                result.counts,
                width=np.diff(edges),
                align="edge",
                color=color,
                edgecolor="none",
                alpha=1.0 - theme.BAND_STYLE["fill_alpha"],
                zorder=2,
            )

            # Two guides, distinguished by style rather than by colour: they are the same
            # KIND of object (a location on the axis), so giving them different hues
            # would suggest they measure different things.
            ax.axvline(result.mean_h, zorder=3, **theme.REFERENCE_LINE)
            median_style = dict(theme.REFERENCE_LINE)
            median_style["linestyle"] = ":"
            ax.axvline(result.median_h, zorder=3, **median_style)

            # Headroom above the tallest bar, so the two guide labels sit in clear space
            # rather than on top of whichever bar the mean happens to land beside.
            top = float(np.max(result.counts))
            ax.set_ylim(0.0, top * _HEADROOM)
            label_y = top * (1.0 + (_HEADROOM - 1.0) * 0.35)
            ax.annotate(
                f"mean {result.mean_h:.2f} h",
                xy=(result.mean_h, label_y),
                xytext=(5, 0),
                textcoords="offset points",
                ha="left",
                va="bottom",
                **guide_label,
            )
            ax.annotate(
                f"median {result.median_h:.2f} h",
                xy=(result.median_h, label_y),
                xytext=(-5, 0),
                textcoords="offset points",
                ha="right",
                va="bottom",
                **guide_label,
            )

            ax.set_xscale("log")
            ax.set_xlim(edges[0], edges[-1])
            ax.xaxis.set_major_locator(LogLocator(base=10.0))
            ax.xaxis.set_major_formatter(FuncFormatter(_plain_hours))
            ax.set_xlabel("Time between calibrations (h)")
            ax.set_ylabel("Number of intervals")
            ax.set_title(_title(result))
            ax.grid(True, which="major", axis="y")
            ax.grid(False, which="both", axis="x")

            fig.tight_layout()
        return fig


def _title(result: IntervalHistogramResult) -> str:
    """Names the object. The user-facing name for this quantity is 'calibrations'."""
    return (
        f"Mean time between calibrations, {result.label}"
        if result.label
        else "Mean time between calibrations"
    )
