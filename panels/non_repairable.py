"""Generic non-repairable panel: degradation view with optional cumulative metrics.

NonRepairablePanelData (the contract) lives in _non_repairable_data and is re-exported
here, which stays the public import surface. Pure view arithmetic lives in
_non_repairable_render.

That re-export is load-bearing and must not be removed: artifacts materialized before
the split name `panels.non_repairable.NonRepairablePanelData` in their pickle stream,
and output/ is append-only, so dropping it would silently break reloading them.

Two halves:
  - NonRepairablePanelData is the COMPLETE typed artifact — raw inputs plus every
    data-derived quantity (cumulative time/damage, MTTF, window stats, survival,
    binned stats, CV, in-spec fractions). It is built solely by
    panels._non_repairable_compute.build_non_repairable_panel_data.
  - NonRepairablePanel is a PURE renderer: it reads fields and draws. It performs no
    data arithmetic; only axis/theme concerns (adaptive y-limits, decade-guide ticks,
    colors) live here.

Accepts any monotonic or time-varying metric. No fidelity-specific logic lives here —
fidelity adaptation is in analyzers/fidelity.py::make_panel_data.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objects as go

from panels import _non_repairable_render as render
from panels._non_repairable_data import NonRepairablePanelData
from plots import theme
from plots.base import BasePlot
from plots.fidelity_helpers import apply_common_style


# Per-threshold colours come from plots.theme.threshold_color: used on primary-axis
# dashed lines, cumulative subplots, and survival curves so all three can be visually
# correlated. Sampling a colormap across len(thresholds) replaces a fixed 8-entry list
# that wrapped modulo its length - a 10-entry ladder drew 1 us and 9 us in one blue.


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

        with theme.style_context(style):
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

            # Top row: the long series, its own distribution rotated to share the y
            # axis, and a squarer histogram of the per-read fit error.
            gs_top = gs[0, :].subgridspec(
                1, 3, width_ratios=[7.0, 1.2, 1.8], wspace=0.06
            )
            ax_primary = fig.add_subplot(gs_top[0, 0])
            ax_primary_hist = fig.add_subplot(gs_top[0, 1], sharey=ax_primary)
            ax_sigma_hist = fig.add_subplot(gs_top[0, 2])
            ax_thr = fig.add_subplot(gs[1, :])
            ax_zoom = fig.add_subplot(gs[2, 0])
            ax_roll = fig.add_subplot(gs[2, 1])
            ax_surv = fig.add_subplot(gs[3, :])

            for ax in (
                ax_primary,
                ax_primary_hist,
                ax_sigma_hist,
                ax_thr,
                ax_zoom,
                ax_roll,
                ax_surv,
            ):
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

            self._draw_primary(ax_primary, pd_, color, legend_ax=ax_sigma_hist)
            self._draw_primary_hist(ax_primary_hist, pd_, color)
            self._draw_sigma_hist(ax_sigma_hist, pd_, color)
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

    # --- private drawing methods (read precomputed fields; no data arithmetic) ---

    def _draw_primary(
        self,
        ax: plt.Axes,
        pd_: NonRepairablePanelData,
        color: object,
        legend_ax: plt.Axes | None = None,
    ) -> None:
        plot_fn = ax.semilogy if pd_.use_log_scale else ax.plot
        # One call per observed stretch, split at the gaps the carve found, so no
        # segment is drawn across unobserved time.
        for lo, hi in render.observed_slices(pd_):
            plot_fn(
                pd_.t_h[lo:hi],
                pd_.primary_series[lo:hi],
                color=color,
                linewidth=1.2,
                zorder=2,
            )
        if pd_.primary_sigma is not None:
            # Error bars are drawn UNDER the trace and the threshold lines — the point
            # of showing them is to see which reads they overlap a threshold with.
            # The y-limits are snapshotted from the series and restored afterwards:
            # per-read sigma can be many times the signal range, and letting it drive
            # autoscale would squash the whole ladder into a few pixels.
            y_limits = ax.get_ylim()
            ax.errorbar(
                pd_.t_h,
                pd_.primary_series,
                yerr=pd_.primary_sigma,
                fmt="none",
                ecolor=color,
                elinewidth=0.5,
                alpha=0.25,
                zorder=0,
            )
            ax.set_ylim(y_limits)
        if pd_.use_log_scale:
            render.draw_decade_guides(ax, pd_.primary_series)
        for i, (label, thr_val, _) in enumerate(pd_.thresholds):
            thr_color = theme.threshold_color(i, len(pd_.thresholds))
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
            # Anchored outside the RIGHT-MOST axis of the row, not this one: the
            # primary axis no longer spans the full width, so its own right spine is
            # now interior. This keeps the legend in the figure margin (captured by
            # bbox_inches="tight") instead of on top of the data.
            (legend_ax or ax).legend(
                *ax.get_legend_handles_labels(),
                frameon=False,
                loc="upper left",
                bbox_to_anchor=(1.01, 1.0),
                borderaxespad=0.0,
            )
        ax.set_ylabel(pd_.primary_label)
        ax.set_xlabel("Elapsed time (h)")
        ax.set_title(pd_.primary_label)
        ax.grid(True, which="both", color="lightgray", alpha=0.4)

    def _draw_primary_hist(
        self, ax: plt.Axes, pd_: NonRepairablePanelData, color: object
    ) -> None:
        """The series' own distribution, rotated to share the primary y axis."""
        if len(pd_.primary_hist_counts) == 0:
            ax.text(
                0.5,
                0.5,
                "no spread",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.axis("off")
            return
        centers, widths = render.bin_centers_and_widths(pd_.primary_hist_edges)
        ax.barh(
            centers,
            pd_.primary_hist_counts,
            height=widths,
            color=color,
            alpha=0.6,
            edgecolor="none",
        )
        ax.set_xlabel("Count")
        ax.tick_params(axis="y", labelleft=False)
        ax.set_title("Distribution")
        ax.grid(True, axis="x", color="lightgray", alpha=0.4)

    def _draw_sigma_hist(
        self, ax: plt.Axes, pd_: NonRepairablePanelData, color: object
    ) -> None:
        """Spread of the per-read fit error itself, with its mean and median marked."""
        if len(pd_.sigma_hist_counts) == 0:
            ax.text(
                0.5,
                0.5,
                "no per-read error",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.axis("off")
            return
        centers, widths = render.bin_centers_and_widths(pd_.sigma_hist_edges)
        ax.bar(
            centers,
            pd_.sigma_hist_counts,
            width=widths,
            color=color,
            alpha=0.6,
            edgecolor="none",
        )
        # Annotated in-axis rather than via ax.legend(): this axis already carries the
        # primary axis's threshold legend in its right margin, and a second ax.legend()
        # call would replace it.
        notes: list[str] = []
        for value, style, name in (
            (pd_.sigma_mean, "-", "mean"),
            (pd_.sigma_median, "--", "median"),
        ):
            if np.isfinite(value):
                ax.axvline(value, color="gray", linestyle=style, linewidth=1.0)
                notes.append(f"{name} {value:.3g}")
        if notes:
            ax.text(
                0.97,
                0.97,
                "\n".join(notes),
                ha="right",
                va="top",
                transform=ax.transAxes,
                color="gray",
            )
        # A handful of failed fits carry errors orders of magnitude above the bulk and
        # would flatten the distribution against the left edge. Clip the VIEW, never
        # the data, and say how many reads fall outside it.
        if np.isfinite(pd_.sigma_hist_view_x_max):
            ax.set_xlim(float(pd_.sigma_hist_edges[0]), pd_.sigma_hist_view_x_max)
        n_outside = pd_.sigma_hist_n_above_view
        ax.set_xlabel(f"Fit error ({pd_.primary_label})")
        ax.set_ylabel("Count")
        # The clipped count goes in the title: this axis is too short to carry a second
        # annotation, and a panel that narrows its view has to say by how much.
        ax.set_title(
            "Per-read fit error"
            if not n_outside
            else f"Per-read fit error ({n_outside} above view)"
        )
        ax.grid(True, axis="y", color="lightgray", alpha=0.4)

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

        for y_pos, (label, _thr_val, _big_values_good) in zip(y_positions, plotted):
            # Segments and their states are computed by the builder from the read table
            # (direction and uncertainty already applied). Draw only.
            for t_start_h, t_end_h, state in pd_.timeline_segments_per_threshold.get(
                label, []
            ):
                ax.barh(
                    y_pos,
                    t_end_h - t_start_h,
                    left=t_start_h,
                    height=0.75,
                    color=theme.state_color(state),
                    alpha=0.85,
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
        colors = [base_color, theme.mix_with_white(base_color, amount=0.3)]
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
            lo, hi = render.adaptive_ylim([s for _, s in traces])
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
        colors = [base_color, theme.mix_with_white(base_color, amount=0.3)]
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
            lo, hi = render.adaptive_ylim([s for _, s in traces])
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
            color = theme.threshold_color(i, len(pd_.thresholds))
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
                color=theme.threshold_color(i, len(pd_.thresholds)),
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
                color=theme.threshold_color(i, len(pd_.thresholds)),
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


__all__ = ["NonRepairablePanel", "NonRepairablePanelData"]
