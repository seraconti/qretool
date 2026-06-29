"""Panel for repairable-system MTBF analysis.

Renders a 4-subplot figure from RepairablePanelData:
  - Top:           inter-event interval vs. elapsed days (scatter, log y)
  - Middle:        14-day binned moving average (median, IQR, p90)
  - Bottom-left:   histogram on log x-axis (multimodal distribution)
  - Bottom-right:  summary text in human-readable time units
"""
from __future__ import annotations

from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objects as go

from analyzers.mtbf import MtbfResult
from plots.base import BasePlot
from plots.fidelity_helpers import apply_common_style
from plots.theme import qubit_color


@dataclass
class RepairablePanelData:
    intervals_s: np.ndarray
    event_times_unix_s: np.ndarray
    stats: dict
    meta: dict


def make_mtbf_panel_data(result: MtbfResult) -> RepairablePanelData:
    return RepairablePanelData(
        intervals_s=result.intervals_s,
        event_times_unix_s=result.event_times_unix_s,
        stats=result.stats,
        meta=result.meta,
    )


def _human_time(seconds: float) -> str:
    if seconds < 120:
        return f"{seconds:.1f} s"
    if seconds < 7200:
        return f"{seconds/60:.1f} min"
    if seconds < 172800:
        return f"{seconds/3600:.2f} h"
    return f"{seconds/86400:.2f} days"


def _binned_interval_stats(
    elapsed_days: np.ndarray,
    intervals_h: np.ndarray,
    bin_days: float = 14.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Bin intervals by elapsed days; return (centers, median, q1, q3, p90)."""
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
        np.asarray(centers), np.asarray(medians),
        np.asarray(q1s), np.asarray(q3s), np.asarray(p90s),
    )


class RepairablePanel(BasePlot):
    """MTBF analysis panel for calibration-event logs."""

    def build_matplotlib(self, result: RepairablePanelData, style: str = "default") -> plt.Figure:
        if not isinstance(result, RepairablePanelData):
            raise TypeError("RepairablePanel expects RepairablePanelData")
        pd_ = result
        color = qubit_color(meta=pd_.meta)

        plt_style = "default" if style == "default" else "classic"
        with plt.style.context(plt_style):
            fig = plt.figure(figsize=(14, 13), constrained_layout=True, facecolor="white")
            gs = fig.add_gridspec(3, 2, height_ratios=[1.6, 1.2, 1.0])
            ax_scatter = fig.add_subplot(gs[0, :])
            ax_roll = fig.add_subplot(gs[1, :])
            ax_hist = fig.add_subplot(gs[2, 0])
            ax_text = fig.add_subplot(gs[2, 1])

            for ax in (ax_scatter, ax_roll, ax_hist):
                apply_common_style(ax)

            self._draw_scatter(ax_scatter, pd_, color)
            self._draw_rolling(ax_roll, pd_, color)
            self._draw_histogram(ax_hist, pd_, color)
            self._draw_summary(ax_text, pd_)

        return fig

    def build_plotly(self, result: object) -> go.Figure:
        raise NotImplementedError(f"{self.__class__.__name__} has no plotly backend")

    @staticmethod
    def _draw_scatter(ax: plt.Axes, pd_: RepairablePanelData, color: str) -> None:
        t0 = float(pd_.event_times_unix_s[0])
        elapsed_days = (pd_.event_times_unix_s - t0) / 86400.0
        intervals_h = pd_.intervals_s / 3600.0
        ax.scatter(elapsed_days, intervals_h, s=4, alpha=0.8, color=color, linewidths=0)
        mean_h = pd_.stats["mean_s"] / 3600.0
        ax.axhline(mean_h, color="gray", linestyle="--", linewidth=1.2,
                   label=f"Mean MTBF = {_human_time(pd_.stats['mean_s'])}")
        ax.set_yscale("log")
        ax.set_xlabel("Elapsed time (days)")
        ax.set_ylabel("Inter-event interval (h)")
        ax.set_title(
            f"Calibration intervals over time "
            f"(qubit {pd_.meta.get('qubit', '?')}, {pd_.meta.get('device', '')})"
        )
        ax.legend(frameon=False, fontsize=8)
        ax.grid(True, which="both", color="lightgray", alpha=0.4)

    @staticmethod
    def _draw_rolling(ax: plt.Axes, pd_: RepairablePanelData, color: str) -> None:
        t0 = float(pd_.event_times_unix_s[0])
        elapsed_days = (pd_.event_times_unix_s - t0) / 86400.0
        intervals_h = pd_.intervals_s / 3600.0
        centers, medians, q1s, q3s, p90s = _binned_interval_stats(elapsed_days, intervals_h)
        if len(centers) == 0:
            ax.axis("off")
            return
        ax.plot(centers, medians, "-", linewidth=1.4, color=color, label="Median", zorder=2)
        ax.fill_between(centers, q1s, q3s, color=color, alpha=0.2, zorder=1, label="IQR")
        ax.plot(centers, p90s, "--", linewidth=0.8, color=color, alpha=0.55, label="p90", zorder=1)
        ax.set_xlabel("Elapsed time (days)")
        ax.set_ylabel("Interval (h)")
        ax.set_title("14-day binned statistics (median, IQR, p90)")
        ax.legend(frameon=False, fontsize=8)
        ax.grid(True, alpha=0.25)

    @staticmethod
    def _draw_histogram(ax: plt.Axes, pd_: RepairablePanelData, color: str) -> None:
        ivs = pd_.intervals_s
        valid = ivs[ivs > 0]
        if len(valid) == 0:
            ax.axis("off")
            return
        log_bins = np.logspace(np.log10(float(np.min(valid))), np.log10(float(np.max(valid))), 50)
        ax.hist(valid, bins=log_bins, color=color, alpha=0.75, edgecolor="none")
        ax.set_xscale("log")
        ax.set_xlabel("Interval (s)")
        ax.set_ylabel("Count")
        ax.set_title("Distribution of inter-event intervals")
        ax.grid(True, which="both", color="lightgray", alpha=0.8)

    @staticmethod
    def _draw_summary(ax: plt.Axes, pd_: RepairablePanelData) -> None:
        s = pd_.stats
        lines = [
            f"dataset:     {pd_.meta.get('dataset_id', '?')}",
            f"qubit:       {pd_.meta.get('qubit', '?')}",
            f"device:      {pd_.meta.get('device', '?')}",
            f"n events:    {pd_.meta.get('n_events', s['count'] + 1)}",
            f"n intervals: {s['count']}",
            "",
            f"mean MTBF:   {_human_time(s['mean_s'])}",
            f"std:         {_human_time(s['std_s'])}",
            f"min:         {_human_time(s['min_s'])}",
            f"max:         {_human_time(s['max_s'])}",
        ]
        ax.axis("off")
        ax.text(
            0.05, 0.95, "\n".join(lines),
            transform=ax.transAxes, ha="left", va="top", fontsize=8.5,
            family="monospace",
            bbox={"facecolor": "lightyellow", "edgecolor": "gray", "boxstyle": "round,pad=0.5"},
        )
