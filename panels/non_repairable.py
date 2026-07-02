"""Generic non-repairable panel: degradation view with optional cumulative metrics.

Two halves:
  - NonRepairablePanelData is the COMPLETE typed artifact — raw inputs plus every
    data-derived quantity (cumulative time/damage, MTTF, window stats, survival,
    binned stats, CV, in-spec fractions). It is built solely by
    panels._non_repairable_compute.build_non_repairable_panel_data.
  - NonRepairablePanel is a PURE renderer: it reads fields and draws. It performs no
    data arithmetic; only axis/theme concerns (adaptive y-limits, decade-guide ticks,
    colors) live here.

Accepts any monotonic or time-varying metric. No fidelity-specific logic lives here —
fidelity adaptation is in plots/fidelity_plot.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objects as go

from panels._artifact_guard import StaleArtifactGuard
from plots.base import BasePlot
from plots.fidelity_helpers import apply_common_style


# Per-threshold color palette: used on primary-axis dashed lines, cumulative
# subplots, and survival curves so all three can be visually correlated.
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
class NonRepairablePanelData(StaleArtifactGuard):
    """Complete typed contract for NonRepairablePanel.

    Built by build_non_repairable_panel_data (panels/_non_repairable_compute.py),
    which is the sole constructor path: the renderer assumes the derived fields are
    populated. Directly constructing this dataclass leaves the derived fields empty
    (their defaults) and the renderer will show empty derived views — go through the
    builder. Unpickling a stale pre-split artifact (one missing any field) raises
    ValueError via StaleArtifactGuard. A full completeness validator at construction
    time is deferred (see the restructure plan).

    Raw input fields
    ----------------
    t_h              : time array in hours (x-axis for all subplots)
    primary_series   : metric values (same units as threshold values)
    primary_label    : y-axis label, e.g. "Infidelity" or "T2* (µs)"
    thresholds       : list of (label, value, big_values_good) triples.
                       big_values_good=False: above threshold = out-of-spec
                         (lower is better, e.g. infidelity)
                       big_values_good=True: below threshold = out-of-spec
                         (higher is better, e.g. T2*)
    meta             : arbitrary dict shown in summary text (≤4 items displayed)
    traces           : optional extra labeled series for zoom/binned subplots;
                       None → panel uses primary_series as the sole trace
    use_log_scale    : semilogy on the primary panel (default False)
    color            : matplotlib color for primary trace; "C0" if None
    include_cumulative_time   : render cumulative time-out-of-spec subplot
    include_cumulative_damage : render cumulative damage subplot
    include_mttf     : include first-crossing times in summary/timeline text

    Note: damage is no longer a field here. The damage function is a builder
    parameter only (# EXTENSION: future DamageModel) — a callable cannot be hashed
    deterministically for identity nor labeled stably, so it never enters the
    materialized artifact; only the resulting damage curve does.

    Derived fields (populated by the builder)
    -----------------------------------------
    Keyed by threshold label unless noted. See _non_repairable_compute for the math.
    """

    # raw inputs
    t_h: np.ndarray
    primary_series: np.ndarray
    primary_label: str
    thresholds: list[tuple[str, float, bool]]
    meta: dict[str, object]
    traces: list[tuple[str, np.ndarray]] | None = None
    use_log_scale: bool = False
    color: object = None
    include_cumulative_time: bool = True
    include_cumulative_damage: bool = True
    include_mttf: bool = True

    # derived (populated by build_non_repairable_panel_data)
    cumulative_time_per_threshold: dict[str, np.ndarray] = field(default_factory=dict)
    cumulative_damage_per_threshold: dict[str, np.ndarray] = field(default_factory=dict)
    mttf_per_threshold: dict[str, float | None] = field(default_factory=dict)
    threshold_window_stats: dict[str, dict[str, object]] = field(default_factory=dict)
    window_survival_per_threshold: dict[str, list[tuple[float, float]]] = field(
        default_factory=dict
    )
    binned_stats_per_trace: dict[str, tuple[np.ndarray, ...]] = field(
        default_factory=dict
    )
    # default_factory (not a plain class default) so the value lives in instance
    # __dict__ like every other derived field: absence is then detectable rather
    # than silently falling back to a class attribute.
    cv: float = field(default_factory=lambda: float("nan"))
    threshold_in_spec_frac: dict[str, float] = field(default_factory=dict)
    threshold_summary: dict[str, dict[str, float] | None] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Panel class (pure renderer)
# ---------------------------------------------------------------------------


class NonRepairablePanel(BasePlot):
    """Degradation analysis panel for non-repairable systems.

    Pure renderer over a complete NonRepairablePanelData. Renders up to 8 axes
    depending on the data's flags:
      - Primary time series with per-threshold dashed lines
      - Threshold compliance timeline (Gantt-style, per-threshold direction)
      - Detail view (zoom) and 30-min binned statistics
      - In-spec window survival curves (per-threshold direction)
      - Cumulative time out of spec per threshold  [opt-in, default on]
      - Cumulative damage per threshold            [opt-in, default on]
      - Summary text (CV, initial value, per-threshold stats, MTTF)
    """

    def build_matplotlib(
        self, result: NonRepairablePanelData, style: str = "default"
    ) -> plt.Figure:
        if not isinstance(result, NonRepairablePanelData):
            raise TypeError("NonRepairablePanel expects NonRepairablePanelData")
        pd_ = result
        has_cum_time = pd_.include_cumulative_time
        has_cum_dmg = pd_.include_cumulative_damage
        has_extra_row = has_cum_time or has_cum_dmg

        plt_style = "default" if style == "default" else "classic"
        with plt.style.context(plt_style):
            n_thr = len(pd_.thresholds)
            # Scale the compliance-timeline row so labels don't overlap for wide ladders.
            thr_row_h = max(0.9, 0.22 * n_thr)
            figheight = 16.0 + (2.5 if has_extra_row else 0.0) + (thr_row_h - 0.9)
            fig = plt.figure(
                figsize=(14, figheight), constrained_layout=True, facecolor="white"
            )

            if has_extra_row:
                gs = fig.add_gridspec(
                    6, 2, height_ratios=[1.8, thr_row_h, 3.2, 2.0, 2.0, 1.2]
                )
            else:
                gs = fig.add_gridspec(
                    5, 2, height_ratios=[1.8, thr_row_h, 3.2, 2.0, 1.2]
                )

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
            traces = (
                pd_.traces
                if pd_.traces is not None
                else [(pd_.primary_label, pd_.primary_series)]
            )

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

    # --- axis/theme helpers (render-local; functions of axes/theme, not of data) ---

    @staticmethod
    def _draw_decade_guides(ax: plt.Axes, values: np.ndarray) -> None:
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

    @staticmethod
    def _adaptive_ylim(series_list: list[np.ndarray]) -> tuple[float, float]:
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

    # --- private drawing methods (read precomputed fields; no data arithmetic) ---

    def _draw_primary(
        self, ax: plt.Axes, pd_: NonRepairablePanelData, color: object
    ) -> None:
        plot_fn = ax.semilogy if pd_.use_log_scale else ax.plot
        plot_fn(pd_.t_h, pd_.primary_series, color=color, linewidth=1.2, zorder=2)
        if pd_.use_log_scale:
            self._draw_decade_guides(ax, pd_.primary_series)
        for i, (label, thr_val, _) in enumerate(pd_.thresholds):
            thr_color = _THRESHOLD_COLORS[i % len(_THRESHOLD_COLORS)]
            ax.axhline(
                thr_val,
                color=thr_color,
                linestyle="--",
                linewidth=1.0,
                alpha=0.75,
                label=label,
                zorder=1,
            )
        if pd_.thresholds:
            # Outside the right spine: full-width axis, so this lands in the
            # figure margin and is captured by bbox_inches="tight" without
            # overflowing onto the data or x-axis ticks (constrained_layout
            # won't shrink the short primary axis to fit a tall legend).
            ax.legend(
                frameon=False,
                fontsize=7,
                loc="upper left",
                bbox_to_anchor=(1.01, 1.0),
                borderaxespad=0.0,
            )
        ax.set_ylabel(pd_.primary_label)
        ax.set_xlabel("Elapsed time (h)")
        ax.set_title(pd_.primary_label)
        ax.grid(True, which="both", color="lightgray", alpha=0.4)

    def _draw_threshold_timeline(
        self, ax: plt.Axes, pd_: NonRepairablePanelData
    ) -> None:
        if not pd_.thresholds:
            ax.text(
                0.5,
                0.5,
                "No thresholds defined",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.axis("off")
            return

        # Only plot thresholds with ≥5% in-spec time; keep all in textual summary.
        # (Decision: keep the cull, preserving current figures.)
        plotted = [
            (label, thr_val, bvg)
            for label, thr_val, bvg in pd_.thresholds
            if pd_.threshold_in_spec_frac.get(label, 0.0) >= 0.05
        ]

        if not plotted:
            ax.text(
                0.5,
                0.5,
                "No thresholds with ≥5% in-spec time",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.axis("off")
            return

        mttf_map = pd_.mttf_per_threshold if pd_.include_mttf else {}
        n_plot = len(plotted)
        y_positions = np.arange(n_plot)[::-1]

        for y_pos, (label, thr_val, big_values_good) in zip(y_positions, plotted):
            # big_values_good=True: above threshold = green (good), below = red (out-of-spec)
            # big_values_good=False: above threshold = red (out-of-spec), below = green (good)
            color_if_above = "green" if big_values_good else "red"
            color_if_below = "red" if big_values_good else "green"
            above = pd_.primary_series >= thr_val
            state = bool(above[0]) if len(above) > 0 else False
            start = float(pd_.t_h[0])
            for idx in range(1, len(pd_.t_h)):
                if bool(above[idx]) != state:
                    end = float(pd_.t_h[idx])
                    ax.barh(
                        y_pos,
                        end - start,
                        left=start,
                        height=0.75,
                        color=color_if_above if state else color_if_below,
                        alpha=0.7,
                        edgecolor="none",
                    )
                    start, state = end, bool(above[idx])
            ax.barh(
                y_pos,
                float(pd_.t_h[-1]) - start,
                left=start,
                height=0.75,
                color=color_if_above if state else color_if_below,
                alpha=0.7,
                edgecolor="none",
            )

            if pd_.include_mttf:
                mttf = mttf_map.get(label)
                mttf_str = f"MTTF={mttf:.1f}h" if mttf is not None else "—"
                # y fraction: assumes ylim = [-0.5, n_plot - 0.5] (set below)
                y_frac = (y_pos + 0.5) / n_plot
                ax.text(
                    1.01,
                    y_frac,
                    mttf_str,
                    transform=ax.transAxes,
                    ha="left",
                    va="center",
                    fontsize=7,
                    clip_on=False,
                )

        ax.set_ylim(-0.5, n_plot - 0.5)
        ax.set_yticks(np.arange(n_plot))
        ax.set_yticklabels([label for label, _, _ in plotted][::-1], fontsize=8)
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
            ax.plot(
                pd_.t_h,
                series,
                styles[i % 2],
                linewidth=1.0,
                color=colors[i % 2],
                alpha=0.9,
                label=label,
            )
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
        for i, (label, _series) in enumerate(traces):
            stats = pd_.binned_stats_per_trace.get(label)
            if stats is None:
                continue
            xb, med, q1, q3, p90 = stats
            if len(xb) == 0:
                continue
            color = colors[i % 2]
            ax.plot(
                xb,
                med,
                "-",
                linewidth=1.2,
                color=color,
                alpha=0.95,
                label=label,
                zorder=2,
            )
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
            ax.text(
                0.5,
                0.5,
                "No thresholds defined",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.axis("off")
            return

        plotted = 0
        for i, (label, _thr_val, _bvg) in enumerate(pd_.thresholds):
            survival = pd_.window_survival_per_threshold.get(label, [])
            if not survival:
                continue
            surv_x, surv_y = zip(*survival)
            color = _THRESHOLD_COLORS[i % len(_THRESHOLD_COLORS)]
            ax.semilogy(
                surv_x,
                surv_y,
                linewidth=1.2,
                markersize=4,
                markevery=max(1, len(surv_x) // 10),
                color=color,
                label=label,
                linestyle="-",
            )
            plotted += 1

        if plotted == 0:
            ax.text(
                0.5,
                0.5,
                "No in-spec windows for defined thresholds",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.axis("off")
            return

        ax.set_xlabel("Window length (minutes)")
        ax.set_ylabel("Fraction of windows lasting ≥ length")
        ax.set_title("In-spec window survival per threshold")
        ax.grid(True, which="both", color="lightgray", alpha=0.4)
        ax.legend(
            frameon=False,
            fontsize=7,
            loc="upper left",
            bbox_to_anchor=(1.01, 1.0),
            borderaxespad=0.0,
        )

    def _draw_cumulative_time(self, ax: plt.Axes, pd_: NonRepairablePanelData) -> None:
        """Cumulative time out of spec per threshold (hours)."""
        if not pd_.thresholds:
            ax.text(
                0.5,
                0.5,
                "No thresholds defined",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.axis("off")
            return

        cum_time = pd_.cumulative_time_per_threshold
        t = np.asarray(pd_.t_h, dtype=float)
        plotted = 0
        for i, (label, _, _) in enumerate(pd_.thresholds):
            arr = cum_time.get(label)
            if arr is None or len(arr) == 0:
                continue
            ax.plot(
                t,
                arr,
                color=_THRESHOLD_COLORS[i % len(_THRESHOLD_COLORS)],
                linewidth=1.2,
                label=label,
            )
            plotted += 1

        if plotted == 0:
            ax.text(
                0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes
            )
            return

        ax.set_xlabel("Elapsed time (h)")
        ax.set_ylabel("Cumulative time out of spec (h)")
        ax.set_title("Cumulative time out of spec")
        ax.grid(True, alpha=0.25)
        # Half-width axis: keep the legend inside, in the empty top-left corner
        # (cumulative curves rise toward top-right). Columns cap it at ≤5 rows.
        ax.legend(
            frameon=False,
            fontsize=7,
            loc="upper left",
            ncol=max(1, (len(pd_.thresholds) + 4) // 5),
        )

    def _draw_cumulative_damage(
        self, ax: plt.Axes, pd_: NonRepairablePanelData
    ) -> None:
        """Cumulative damage per threshold (primary_unit · h)."""
        if not pd_.thresholds:
            ax.text(
                0.5,
                0.5,
                "No thresholds defined",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.axis("off")
            return

        cum_dmg = pd_.cumulative_damage_per_threshold
        t = np.asarray(pd_.t_h, dtype=float)
        ylabel = f"Cumulative damage ({pd_.primary_label} · h)"
        plotted = 0
        for i, (label, _, _) in enumerate(pd_.thresholds):
            arr = cum_dmg.get(label)
            if arr is None or len(arr) == 0:
                continue
            ax.plot(
                t,
                arr,
                color=_THRESHOLD_COLORS[i % len(_THRESHOLD_COLORS)],
                linewidth=1.2,
                label=label,
            )
            plotted += 1

        if plotted == 0:
            ax.text(
                0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes
            )
            return

        ax.set_xlabel("Elapsed time (h)")
        ax.set_ylabel(ylabel)
        ax.set_title("Cumulative damage")
        ax.grid(True, alpha=0.25)
        # Half-width axis: legend in the empty top-left corner, columnized.
        ax.legend(
            frameon=False,
            fontsize=7,
            loc="upper left",
            ncol=max(1, (len(pd_.thresholds) + 4) // 5),
        )

    def _draw_summary(self, ax: plt.Axes, pd_: NonRepairablePanelData) -> None:
        series = pd_.primary_series
        cv = pd_.cv
        finite = series[np.isfinite(series)]

        lines: list[str] = [
            f"Metric: {pd_.primary_label}",
            f"Points: {len(finite)}",
            f"Initial value: {float(finite[0]):.6g}"
            if len(finite) > 0
            else "Initial value: N/A",
            f"Range: {float(np.min(finite)):.6g} to {float(np.max(finite)):.6g}"
            if len(finite) > 0
            else "Range: N/A",
            f"CV: {cv:.4f}" if np.isfinite(cv) else "CV: N/A",
        ]
        if pd_.meta:
            lines.append("")
            for k, v in list(pd_.meta.items())[:4]:
                lines.append(f"{k}: {v}")

        mttf_map = pd_.mttf_per_threshold if pd_.include_mttf else {}

        for label, thr_val, big_values_good in pd_.thresholds:
            summ = pd_.threshold_summary.get(label)
            if summ is None:
                continue
            time_oos_h = summ["time_oos_h"]
            frac_oos = summ["frac_oos_pct"]
            lines.append("")
            lines.append(f"{label} (thr={thr_val:.6g}):")
            lines.append(f"  Out of spec: {time_oos_h:.2f} h ({frac_oos:.1f}%)")
            w = pd_.threshold_window_stats.get(label, {"above": {}, "below": {}})
            # big_values_good=False (infidelity): above threshold = oos, below = in-spec
            # big_values_good=True  (T2*):        below threshold = oos, above = in-spec
            oos_key = "above" if not big_values_good else "below"
            in_spec_key = "below" if not big_values_good else "above"
            ws_oos = w[oos_key]
            ws_in_spec = w[in_spec_key]
            if ws_oos.get("count", 0) > 0:
                lines.append(
                    f"  oos: count={ws_oos['count']}, mean={ws_oos['mean']:.1f} min, p90={ws_oos['p90']:.1f} min"
                )
            if ws_in_spec.get("count", 0) > 0:
                lines.append(
                    f"  in-spec: count={ws_in_spec['count']}, mean={ws_in_spec['mean']:.1f} min, p90={ws_in_spec['p90']:.1f} min"
                )
            if pd_.include_mttf and label in mttf_map:
                first_cross = mttf_map[label]
                if first_cross is None:
                    lines.append("  First crossing: none in dataset")
                else:
                    lines.append(f"  First crossing: {first_cross:.3f} h")

        ax.axis("off")
        ax.text(
            0.02,
            0.98,
            "\n".join(lines).strip(),
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=7.5,
            family="monospace",
            bbox={
                "facecolor": "lightyellow",
                "edgecolor": "gray",
                "boxstyle": "round,pad=0.5",
            },
        )
