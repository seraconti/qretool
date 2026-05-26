"""Generic non-repairable panel: degradation view with optional cumulative metrics.

Accepts any monotonic or time-varying metric via NonRepairablePanelData.
No fidelity-specific logic lives here — fidelity adaptation is in
plots/fidelity_plot.py.

NOTE: This file is ~650 lines, exceeding the 200-line guideline.  A split
(e.g. separating compute helpers into panels/_non_repairable_compute.py) is
the natural next step but has been deferred per the R1 spec, which requires
these views to be panel-internal.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objects as go

from plots.base import BasePlot
from plots.fidelity_helpers import apply_common_style, make_fidelity_figure


# Per-threshold color palette used on the primary plot and cumulative subplots
# so curves can be visually matched across axes.
_THRESHOLD_COLORS = [
    "#1f77b4",  # blue
    "#ff7f0e",  # orange
    "#2ca02c",  # green
    "#d62728",  # red
    "#9467bd",  # purple
    "#8c564b",  # brown
    "#e377c2",  # pink
    "#7f7f7f",  # grey
]


@dataclass
class NonRepairablePanelData:
    """Input contract for NonRepairablePanel.

    All compliance analysis (CV, threshold stats, window survival, cumulative
    metrics) is computed internally by the panel. Callers provide only raw
    data and labeling.

    Fields
    ------
    t_h              : time array in hours (x-axis for all panels)
    primary_series   : metric values in their natural units (y-axis)
    primary_label    : y-axis label (e.g. "Infidelity", "Cumulative damage (a.u.)")
    thresholds       : caller-defined (label, value) pairs in the same units as
                       primary_series. All thresholds are shown — no filtering.
    meta             : arbitrary dict shown in summary text (e.g. dataset_id, qubit)
    traces           : optional extra labeled series for zoom/binned panels;
                       if None the panel uses primary_series as the sole trace
    use_log_scale    : semilogy on the primary panel (default False)
    higher_is_better : if True, above threshold = green; if False, above = red.
                       Also controls survival "good window" direction.
    color            : matplotlib color for primary trace; auto if None
    damage_fn        : damage function applied to per-threshold excess before
                       integration. Signature: (excess: np.ndarray) -> np.ndarray.
                       None = linear default (identity on excess).
    include_cumulative_time   : render cumulative time-out-of-spec subplot
    include_cumulative_damage : render cumulative damage subplot
    include_mttr     : include first-crossing times in summary text
    direction        : "above" → above threshold = out-of-spec (use when lower
                       is better, e.g. infidelity); "below" → below threshold =
                       out-of-spec (use when higher is better). Default "below"
                       matches higher_is_better=True. Must be consistent with
                       higher_is_better to avoid contradictory rendering.
    """

    t_h: np.ndarray
    primary_series: np.ndarray
    primary_label: str
    thresholds: list[tuple[str, float]]
    meta: dict[str, object]
    traces: list[tuple[str, np.ndarray]] | None = None
    use_log_scale: bool = False
    higher_is_better: bool = True
    color: object = None
    damage_fn: Callable[[np.ndarray], np.ndarray] | None = None
    include_cumulative_time: bool = True
    include_cumulative_damage: bool = True
    include_mttr: bool = True
    direction: Literal["above", "below"] = "below"


# ---------------------------------------------------------------------------
# Generic compute helpers (no fidelity/domain assumptions)
# ---------------------------------------------------------------------------

def _compute_cv(series: np.ndarray) -> float:
    s = np.asarray(series, dtype=float)
    s = s[np.isfinite(s)]
    if len(s) == 0:
        return np.nan
    mean = float(np.mean(s))
    if mean == 0.0:
        return np.nan
    return float(np.std(s) / abs(mean))


def _binned_stats(
    t_h: np.ndarray, values: np.ndarray, bin_h: float = 0.5
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    t = np.asarray(t_h, dtype=float)
    v = np.asarray(values, dtype=float)
    mask = np.isfinite(t) & np.isfinite(v)
    t, v = t[mask], v[mask]
    if len(t) == 0:
        return (np.array([]),) * 5
    t0, t1 = float(np.min(t)), float(np.max(t))
    if t1 <= t0:
        return (
            np.array([t0]),
            np.array([float(np.median(v))]),
            np.array([float(np.percentile(v, 25))]),
            np.array([float(np.percentile(v, 75))]),
            np.array([float(np.percentile(v, 90))]),
        )
    edges = np.arange(t0, t1 + bin_h, bin_h)
    if len(edges) < 2:
        edges = np.array([t0, t1 + bin_h])
    idx = np.digitize(t, edges) - 1
    centers, medians, q1s, q3s, p90s = [], [], [], [], []
    for i in range(len(edges) - 1):
        yy = v[idx == i]
        if len(yy) == 0:
            continue
        centers.append(0.5 * (edges[i] + edges[i + 1]))
        medians.append(float(np.median(yy)))
        q1s.append(float(np.percentile(yy, 25)))
        q3s.append(float(np.percentile(yy, 75)))
        p90s.append(float(np.percentile(yy, 90)))
    return (
        np.asarray(centers),
        np.asarray(medians),
        np.asarray(q1s),
        np.asarray(q3s),
        np.asarray(p90s),
    )


def _analyze_threshold_windows(
    t_h: np.ndarray, series: np.ndarray, threshold_value: float
) -> dict[str, object]:
    """Compute above/below window statistics for a single threshold."""
    t = np.asarray(t_h, dtype=float)
    s = np.asarray(series, dtype=float)
    mask = np.isfinite(t) & np.isfinite(s)
    t, s = t[mask], s[mask]
    if len(t) < 2:
        return {"above": {}, "below": {}}

    dt = np.diff(t) * 60.0  # minutes
    above = s >= threshold_value
    windows_above: list[float] = []
    windows_below: list[float] = []
    current = 0.0
    in_above = bool(above[0]) if len(above) > 0 else False

    for i in range(len(above) - 1):
        current += float(dt[i])
        if above[i] != above[i + 1]:
            (windows_above if in_above else windows_below).append(current)
            current = 0.0
            in_above = above[i + 1]
    current += float(dt[-1]) if len(dt) > 0 else 0.0
    (windows_above if in_above else windows_below).append(current)

    def _stats(windows: list[float]) -> dict[str, object]:
        if not windows:
            return {"longest": np.nan, "mean": np.nan, "median": np.nan, "p90": np.nan, "count": 0}
        w = np.asarray(windows, dtype=float)
        return {
            "longest": float(np.max(w)),
            "mean": float(np.mean(w)),
            "median": float(np.median(w)),
            "p90": float(np.percentile(w, 90)),
            "count": len(windows),
        }

    return {"above": _stats(windows_above), "below": _stats(windows_below)}


def _window_survival(windows_min: list[float]) -> list[tuple[float, float]]:
    w = np.asarray(windows_min, dtype=float)
    w = w[np.isfinite(w)]
    if len(w) == 0:
        return []
    unique_w = np.unique(np.sort(w))
    return [
        (float(length), float(np.clip(np.round(np.sum(w >= length) / len(w), 10), 0.0, 1.0)))
        for length in unique_w
    ]


# ---------------------------------------------------------------------------
# Panel class
# ---------------------------------------------------------------------------

class NonRepairablePanel(BasePlot):
    """Degradation analysis panel for non-repairable systems.

    Renders up to 8 axes depending on NonRepairablePanelData flags:
      - Primary time series with threshold lines
      - Threshold compliance timeline (Gantt-style)
      - Detail view (zoom) and 30-min binned statistics
      - Threshold window survival curves
      - Cumulative time out of spec per threshold  [opt-in, default on]
      - Cumulative damage per threshold            [opt-in, default on]
      - Summary text (CV, initial value, per-threshold stats, MTTR)
    """

    def build_matplotlib(self, result: NonRepairablePanelData, style: str = "default") -> plt.Figure:
        if not isinstance(result, NonRepairablePanelData):
            raise TypeError("NonRepairablePanel expects NonRepairablePanelData")
        pd_ = result
        has_cum_time = pd_.include_cumulative_time
        has_cum_dmg = pd_.include_cumulative_damage
        has_extra_row = has_cum_time or has_cum_dmg

        plt_style = "default" if style == "default" else "classic"
        with plt.style.context(plt_style):
            figheight = 16.0 + (2.5 if has_extra_row else 0.0)
            fig = plt.figure(figsize=(14, figheight), constrained_layout=True, facecolor="white")

            if has_extra_row:
                height_ratios = [1.8, 0.9, 3.2, 2.0, 2.0, 1.2]
                gs = fig.add_gridspec(6, 2, height_ratios=height_ratios)
            else:
                height_ratios = [1.8, 0.9, 3.2, 2.0, 1.2]
                gs = fig.add_gridspec(5, 2, height_ratios=height_ratios)

            ax_primary = fig.add_subplot(gs[0, :])
            ax_thr = fig.add_subplot(gs[1, :])
            ax_zoom = fig.add_subplot(gs[2, 0])
            ax_roll = fig.add_subplot(gs[2, 1])
            ax_surv = fig.add_subplot(gs[3, :])

            for ax in (ax_primary, ax_thr, ax_zoom, ax_roll, ax_surv):
                apply_common_style(ax)

            if has_extra_row:
                if has_cum_time and has_cum_dmg:
                    ax_cum_time = fig.add_subplot(gs[4, 0])
                    ax_cum_dmg = fig.add_subplot(gs[4, 1])
                elif has_cum_time:
                    ax_cum_time = fig.add_subplot(gs[4, :])
                    ax_cum_dmg = None
                else:
                    ax_cum_time = None
                    ax_cum_dmg = fig.add_subplot(gs[4, :])
                ax_sum = fig.add_subplot(gs[5, :])
            else:
                ax_cum_time = None
                ax_cum_dmg = None
                ax_sum = fig.add_subplot(gs[4, :])

            color = pd_.color if pd_.color is not None else "C0"
            traces = pd_.traces if pd_.traces is not None else [(pd_.primary_label, pd_.primary_series)]

            self._draw_primary(ax_primary, pd_, color)
            self._draw_threshold_timeline(ax_thr, pd_)
            self._draw_traces(ax_zoom, pd_, traces, color, title="Detail view")
            self._draw_binned_30m(ax_roll, pd_, traces, color)
            self._draw_survival(ax_surv, pd_)

            if ax_cum_time is not None:
                apply_common_style(ax_cum_time)
                self._draw_cumulative_time(ax_cum_time, pd_)
            if ax_cum_dmg is not None:
                apply_common_style(ax_cum_dmg)
                self._draw_cumulative_damage(ax_cum_dmg, pd_)

            self._draw_summary(ax_sum, pd_)
        return fig

    def build_plotly(self, result: object) -> go.Figure:
        raise NotImplementedError(f"{self.__class__.__name__} has no plotly backend")

    # --- private compute methods ---

    @staticmethod
    def _out_of_spec_mask(
        series: np.ndarray, threshold_value: float, direction: Literal["above", "below"]
    ) -> np.ndarray:
        if direction == "above":
            return series > threshold_value
        return series < threshold_value

    @staticmethod
    def _excess(
        series: np.ndarray, threshold_value: float, direction: Literal["above", "below"]
    ) -> np.ndarray:
        if direction == "above":
            return np.maximum(series - threshold_value, 0.0)
        return np.maximum(threshold_value - series, 0.0)

    def _cumulative_time_out_of_spec(
        self, data: NonRepairablePanelData
    ) -> dict[str, np.ndarray]:
        """Left-Riemann cumulative time out of spec per threshold (result in hours)."""
        t = np.asarray(data.t_h, dtype=float)
        s = np.asarray(data.primary_series, dtype=float)
        mask = np.isfinite(t) & np.isfinite(s)
        t_f, s_f = t[mask], s[mask]

        result: dict[str, np.ndarray] = {}
        for label, thr_val in data.thresholds:
            if len(t_f) < 2:
                result[label] = np.zeros(len(t_f))
                continue
            oos = self._out_of_spec_mask(s_f, thr_val, data.direction)
            dt_h = np.diff(t_f)  # hours
            # left-Riemann: indicator is a step function
            increments = oos[:-1].astype(float) * dt_h
            cum = np.zeros(len(t_f))
            cum[1:] = np.cumsum(increments)
            result[label] = cum
        return result

    def _cumulative_damage(
        self, data: NonRepairablePanelData
    ) -> dict[str, np.ndarray]:
        """Trapezoidal cumulative damage per threshold (result in primary_unit · h)."""
        t = np.asarray(data.t_h, dtype=float)
        s = np.asarray(data.primary_series, dtype=float)
        mask = np.isfinite(t) & np.isfinite(s)
        t_f, s_f = t[mask], s[mask]

        damage_fn: Callable[[np.ndarray], np.ndarray] = (
            data.damage_fn if data.damage_fn is not None else lambda x: x
        )

        result: dict[str, np.ndarray] = {}
        for label, thr_val in data.thresholds:
            if len(t_f) < 2:
                result[label] = np.zeros(len(t_f))
                continue
            excess = self._excess(s_f, thr_val, data.direction)
            damage_rate = damage_fn(excess)
            dt_h = np.diff(t_f)  # hours
            # trapezoidal: damage_rate is continuous
            trap_steps = 0.5 * (damage_rate[:-1] + damage_rate[1:]) * dt_h
            cum = np.zeros(len(t_f))
            cum[1:] = np.cumsum(trap_steps)
            result[label] = cum
        return result

    def _mttr(
        self, data: NonRepairablePanelData
    ) -> dict[str, float | None]:
        """First threshold-crossing time (hours elapsed from t[0]) per threshold."""
        t = np.asarray(data.t_h, dtype=float)
        s = np.asarray(data.primary_series, dtype=float)
        mask = np.isfinite(t) & np.isfinite(s)
        t_f, s_f = t[mask], s[mask]

        result: dict[str, float | None] = {}
        for label, thr_val in data.thresholds:
            oos = self._out_of_spec_mask(s_f, thr_val, data.direction)
            indices = np.where(oos)[0]
            if len(indices) == 0 or len(t_f) == 0:
                result[label] = None
            else:
                result[label] = float(t_f[indices[0]]) - float(t_f[0])
        return result

    # --- private drawing methods ---

    @staticmethod
    def _draw_decade_guides(ax: plt.Axes, values: np.ndarray) -> None:
        clipped = np.clip(np.asarray(values, dtype=float), 1e-16, None)
        lo, hi = float(np.min(clipped)), float(np.max(clipped))
        if not (np.isfinite(lo) and np.isfinite(hi) and lo > 0.0 and hi > 0.0):
            return
        for power in range(int(np.floor(np.log10(lo))), int(np.ceil(np.log10(hi))) + 1):
            ax.axhline(10.0**power, color="gray", linestyle="--", linewidth=0.7, alpha=0.3, zorder=0)

    @staticmethod
    def _adaptive_ylim(series_list: list[np.ndarray]) -> tuple[float, float]:
        all_values = np.concatenate([np.asarray(s, dtype=float) for s in series_list if len(s) > 0])
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

    def _draw_primary(self, ax: plt.Axes, pd_: NonRepairablePanelData, color: object) -> None:
        plot_fn = ax.semilogy if pd_.use_log_scale else ax.plot
        plot_fn(pd_.t_h, pd_.primary_series, color=color, linewidth=1.2, zorder=2)
        if pd_.use_log_scale:
            self._draw_decade_guides(ax, pd_.primary_series)
        # Threshold lines in _THRESHOLD_COLORS so viewers can match cumulative curves
        for i, (label, thr_val) in enumerate(pd_.thresholds):
            thr_color = _THRESHOLD_COLORS[i % len(_THRESHOLD_COLORS)]
            ax.axhline(
                thr_val, color=thr_color, linestyle="--", linewidth=1.0,
                alpha=0.75, label=label, zorder=1,
            )
        if pd_.thresholds:
            ax.legend(frameon=False, fontsize=7, loc="upper right")
        ax.set_ylabel(pd_.primary_label)
        ax.set_xlabel("Elapsed time (h)")
        ax.set_title(pd_.primary_label)
        ax.grid(True, which="both", color="lightgray", alpha=0.4)

    def _draw_threshold_timeline(self, ax: plt.Axes, pd_: NonRepairablePanelData) -> None:
        if not pd_.thresholds:
            ax.text(0.5, 0.5, "No thresholds defined", ha="center", va="center", transform=ax.transAxes)
            ax.axis("off")
            return

        color_above = "green" if pd_.higher_is_better else "red"
        color_below = "red" if pd_.higher_is_better else "green"

        y_positions = np.arange(len(pd_.thresholds))[::-1]
        for y_pos, (label, thr_val) in zip(y_positions, pd_.thresholds):
            above = pd_.primary_series >= thr_val
            state = bool(above[0]) if len(above) > 0 else False
            start = float(pd_.t_h[0])
            for idx in range(1, len(pd_.t_h)):
                if bool(above[idx]) != state:
                    end = float(pd_.t_h[idx])
                    ax.barh(y_pos, end - start, left=start, height=0.75,
                            color=color_above if state else color_below, alpha=0.7, edgecolor="none")
                    start, state = end, bool(above[idx])
            ax.barh(y_pos, float(pd_.t_h[-1]) - start, left=start, height=0.75,
                    color=color_above if state else color_below, alpha=0.7, edgecolor="none")

        ax.set_yticks(np.arange(len(pd_.thresholds)))
        ax.set_yticklabels([label for label, _ in pd_.thresholds][::-1], fontsize=7)
        ax.set_xlabel("Elapsed time (h)")
        ax.set_ylabel("Threshold")
        ax.set_title("Threshold compliance timeline")
        ax.set_xlim(float(np.min(pd_.t_h)), float(np.max(pd_.t_h)))
        ax.grid(True, axis="x", color="lightgray", alpha=0.4)

    def _draw_traces(
        self,
        ax: plt.Axes,
        pd_: NonRepairablePanelData,
        traces: list[tuple[str, np.ndarray]],
        base_color: object,
        title: str = "",
    ) -> None:
        from plots.theme import mix_with_white
        colors = [base_color, mix_with_white(base_color, amount=0.3)]
        styles = ["-", "--"]
        for i, (label, series) in enumerate(traces):
            ax.plot(pd_.t_h, series, styles[i % 2], linewidth=1.0,
                    color=colors[i % 2], alpha=0.9, label=label)
        if not pd_.use_log_scale:
            lo, hi = self._adaptive_ylim([s for _, s in traces])
            ax.set_ylim(lo, hi)
        ax.set_ylabel(pd_.primary_label)
        ax.set_xlabel("Elapsed time (h)")
        ax.set_title(title)
        ax.grid(True, alpha=0.25)
        if len(traces) > 1:
            ax.legend(frameon=False)

    def _draw_binned_30m(
        self,
        ax: plt.Axes,
        pd_: NonRepairablePanelData,
        traces: list[tuple[str, np.ndarray]],
        base_color: object,
    ) -> None:
        from plots.theme import mix_with_white
        colors = [base_color, mix_with_white(base_color, amount=0.3)]
        for i, (label, series) in enumerate(traces):
            xb, med, q1, q3, p90 = _binned_stats(pd_.t_h, series)
            if len(xb) == 0:
                continue
            color = colors[i % 2]
            ax.plot(xb, med, "-", linewidth=1.2, color=color, alpha=0.95, label=label, zorder=2)
            ax.fill_between(xb, q1, q3, color=color, alpha=0.2, zorder=1)
            ax.plot(xb, p90, "--", linewidth=0.7, color=color, alpha=0.5, zorder=1)
        if not pd_.use_log_scale:
            lo, hi = self._adaptive_ylim([s for _, s in traces])
            ax.set_ylim(lo, hi)
        ax.set_xlabel("Elapsed time (h)")
        ax.set_ylabel(pd_.primary_label)
        ax.set_title("30 min statistics (median, IQR, p90)")
        ax.grid(True, alpha=0.25)
        if len(traces) > 1:
            ax.legend(frameon=False)

    def _draw_survival(self, ax: plt.Axes, pd_: NonRepairablePanelData) -> None:
        if not pd_.thresholds:
            ax.text(0.5, 0.5, "No thresholds defined", ha="center", va="center", transform=ax.transAxes)
            ax.axis("off")
            return

        styles = [
            {"color": "#000000", "linestyle": "-", "marker": "o"},
            {"color": "#444444", "linestyle": "--", "marker": "s"},
            {"color": "#222222", "linestyle": "-.", "marker": "^"},
            {"color": "#111111", "linestyle": ":", "marker": "D"},
        ]
        plotted = 0
        for i, (label, thr_val) in enumerate(pd_.thresholds):
            if i >= len(styles):
                break
            good_windows = self._collect_windows(pd_.t_h, pd_.primary_series, thr_val, pd_.higher_is_better)
            survival = _window_survival(good_windows)
            if not survival:
                continue
            surv_x, surv_y = zip(*survival)
            sty = styles[i]
            ax.semilogy(surv_x, surv_y, linestyle=sty["linestyle"], marker=sty["marker"],
                        linewidth=1.2, markersize=5, markevery=4, color=sty["color"], label=label)
            plotted += 1

        if plotted == 0:
            ax.text(0.5, 0.5, "No survival data for defined thresholds",
                    ha="center", va="center", transform=ax.transAxes)
            ax.axis("off")
            return

        ax.set_xlabel("Window length (minutes)")
        ax.set_ylabel("Fraction of windows lasting ≥ length")
        good_label = "above" if pd_.higher_is_better else "below"
        ax.set_title(f"Threshold window survival ({good_label}-threshold windows)")
        ax.grid(True, which="both", color="lightgray", alpha=0.4)
        ax.legend(frameon=False, loc="upper right")

    @staticmethod
    def _collect_windows(
        t_h: np.ndarray, series: np.ndarray, threshold_value: float, higher_is_better: bool
    ) -> list[float]:
        """Return list of window lengths (minutes) for 'good' state."""
        t = np.asarray(t_h, dtype=float)
        s = np.asarray(series, dtype=float)
        mask = np.isfinite(t) & np.isfinite(s)
        t, s = t[mask], s[mask]
        if len(t) < 2:
            return []
        dt = np.diff(t) * 60.0
        good = s >= threshold_value if higher_is_better else s < threshold_value
        windows: list[float] = []
        current = 0.0
        in_good = bool(good[0]) if len(good) > 0 else False
        for i in range(len(good) - 1):
            current += float(dt[i])
            if good[i] != good[i + 1]:
                if in_good:
                    windows.append(current)
                current = 0.0
                in_good = good[i + 1]
        current += float(dt[-1]) if len(dt) > 0 else 0.0
        if in_good:
            windows.append(current)
        return windows

    def _draw_cumulative_time(self, ax: plt.Axes, pd_: NonRepairablePanelData) -> None:
        """Cumulative time out of spec per threshold (hours on y-axis)."""
        if not pd_.thresholds:
            ax.text(0.5, 0.5, "No thresholds defined", ha="center", va="center", transform=ax.transAxes)
            ax.axis("off")
            return

        cum_time = self._cumulative_time_out_of_spec(pd_)
        t = np.asarray(pd_.t_h, dtype=float)
        plotted = 0
        for i, (label, _) in enumerate(pd_.thresholds):
            arr = cum_time.get(label)
            if arr is None or len(arr) == 0:
                continue
            color = _THRESHOLD_COLORS[i % len(_THRESHOLD_COLORS)]
            ax.plot(t, arr, color=color, linewidth=1.2, label=label)
            plotted += 1

        if plotted == 0:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            return

        ax.set_xlabel("Elapsed time (h)")
        ax.set_ylabel("Cumulative time out of spec (h)")
        ax.set_title("Cumulative time out of spec")
        ax.grid(True, alpha=0.25)
        ax.legend(frameon=False, fontsize=7)

    def _draw_cumulative_damage(self, ax: plt.Axes, pd_: NonRepairablePanelData) -> None:
        """Cumulative damage per threshold (primary_unit · h on y-axis)."""
        if not pd_.thresholds:
            ax.text(0.5, 0.5, "No thresholds defined", ha="center", va="center", transform=ax.transAxes)
            ax.axis("off")
            return

        cum_dmg = self._cumulative_damage(pd_)
        t = np.asarray(pd_.t_h, dtype=float)

        unit_str = pd_.primary_label
        ylabel = f"Cumulative damage ({unit_str} · h)"

        plotted = 0
        for i, (label, _) in enumerate(pd_.thresholds):
            arr = cum_dmg.get(label)
            if arr is None or len(arr) == 0:
                continue
            color = _THRESHOLD_COLORS[i % len(_THRESHOLD_COLORS)]
            ax.plot(t, arr, color=color, linewidth=1.2, label=label)
            plotted += 1

        if plotted == 0:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            return

        ax.set_xlabel("Elapsed time (h)")
        ax.set_ylabel(ylabel)
        ax.set_title("Cumulative damage")
        ax.grid(True, alpha=0.25)
        ax.legend(frameon=False, fontsize=7)

    def _draw_summary(self, ax: plt.Axes, pd_: NonRepairablePanelData) -> None:
        series = pd_.primary_series
        cv = _compute_cv(series)
        finite = series[np.isfinite(series)]

        lines: list[str] = [
            f"Metric: {pd_.primary_label}",
            f"Points: {len(finite)}",
            f"Initial value: {float(finite[0]):.6g}" if len(finite) > 0 else "Initial value: N/A",
            f"Range: {float(np.min(finite)):.6g} to {float(np.max(finite)):.6g}" if len(finite) > 0 else "Range: N/A",
            f"CV: {cv:.4f}" if np.isfinite(cv) else "CV: N/A",
        ]
        # metadata
        if pd_.meta:
            lines.append("")
            for k, v in list(pd_.meta.items())[:4]:
                lines.append(f"{k}: {v}")

        # per-threshold stats + MTTR
        mttr: dict[str, float | None] = self._mttr(pd_) if pd_.include_mttr else {}

        for label, thr_val in pd_.thresholds:
            t = np.asarray(pd_.t_h, dtype=float)
            s = np.asarray(series, dtype=float)
            mask_finite = np.isfinite(t) & np.isfinite(s)
            t_f, s_f = t[mask_finite], s[mask_finite]
            if len(t_f) < 2:
                continue
            above = s_f >= thr_val
            dt = np.diff(t_f)
            total_h = float(t_f[-1] - t_f[0])
            time_above_h = float(np.sum(dt[above[:-1]])) if len(dt) > 0 else 0.0
            frac_above = 100.0 * time_above_h / total_h if total_h > 0 else 0.0
            lines.append("")
            lines.append(f"{label} (thr={thr_val:.6g}):")
            lines.append(f"  Time above: {time_above_h:.2f} h ({frac_above:.1f}%)")
            w = _analyze_threshold_windows(pd_.t_h, series, thr_val)
            for state in ("above", "below"):
                ws = w[state]
                if ws.get("count", 0) > 0:
                    lines.append(
                        f"  {state}: count={ws['count']}, mean={ws['mean']:.1f} min, p90={ws['p90']:.1f} min"
                    )
            if pd_.include_mttr and label in mttr:
                first_cross = mttr[label]
                if first_cross is None:
                    lines.append("  First crossing: none in dataset")
                else:
                    lines.append(f"  First crossing: {first_cross:.3f} h")

        ax.axis("off")
        ax.text(
            0.02, 0.98, "\n".join(lines).strip(),
            transform=ax.transAxes, ha="left", va="top", fontsize=7.5,
            family="monospace",
            bbox={"facecolor": "lightyellow", "edgecolor": "gray", "boxstyle": "round,pad=0.5"},
        )
