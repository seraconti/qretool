from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objects as go

from analyzers.fidelity import FidelityResult
from plots.base import BasePlot
from plots.theme import mix_with_white, qubit_color
from plots.fidelity_helpers import make_fidelity_figure, apply_common_style


def _draw_decade_guides(ax, values):
    clipped = np.clip(np.asarray(values, dtype=float), 1e-16, None)
    lo = float(np.min(clipped))
    hi = float(np.max(clipped))
    if not np.isfinite(lo) or not np.isfinite(hi) or lo <= 0.0 or hi <= 0.0:
        return
    p_lo = int(np.floor(np.log10(lo)))
    p_hi = int(np.ceil(np.log10(hi)))
    for power in range(p_lo, p_hi + 1):
        ax.axhline(10.0**power, color="gray", linestyle="--", linewidth=0.7, alpha=0.3, zorder=0)


def _fidelity_percent_from_infidelity(infidelity: np.ndarray) -> np.ndarray:
    return 100.0 * (1.0 - np.asarray(infidelity, dtype=float))


def _adaptive_fidelity_ylim_from_traces(traces):
    values = []
    for _, infidelity in traces:
        values.append(_fidelity_percent_from_infidelity(infidelity))
    all_values = np.concatenate(values) if len(values) > 0 else np.array([], dtype=float)
    all_values = all_values[np.isfinite(all_values)]
    if len(all_values) == 0:
        return 99.0, 100.0

    q_lo = float(np.quantile(all_values, 0.10))
    q_hi = float(np.quantile(all_values, 0.90))
    if q_hi <= q_lo:
        q_lo = float(np.min(all_values))
        q_hi = float(np.max(all_values))

    span = max(0.05, q_hi - q_lo)
    pad = 0.2 * span
    lo = max(0.0, q_lo - pad)
    hi = min(100.0, q_hi + pad)

    if hi - lo < 0.05:
        mid = 0.5 * (hi + lo)
        lo = max(0.0, mid - 0.025)
        hi = min(100.0, mid + 0.025)

    return lo, hi


def _plot_fidelity_zoom_adaptive(ax, t_h, traces, base_color):
    colors = [base_color, mix_with_white(base_color, amount=0.3)]
    styles = ["-", "--"]
    for index, (label, infidelity) in enumerate(traces):
        fidelity_pct = _fidelity_percent_from_infidelity(infidelity)
        ax.plot(
            t_h,
            fidelity_pct,
            styles[index % len(styles)],
            linewidth=1.0,
            color=colors[index % len(colors)],
            alpha=0.9,
            label=label,
        )
    lo, hi = _adaptive_fidelity_ylim_from_traces(traces)
    ax.set_ylim(lo, hi)
    ax.set_ylabel("Fidelity (%)")
    ax.grid(True, alpha=0.25)


def _binned_stats_quartiles(t_h, values, bin_h=0.5):
    t = np.asarray(t_h, dtype=float)
    v = np.asarray(values, dtype=float)
    mask = np.isfinite(t) & np.isfinite(v)
    t = t[mask]
    v = v[mask]
    if len(t) == 0:
        return np.array([]), np.array([]), np.array([]), np.array([]), np.array([])

    t0 = float(np.min(t))
    t1 = float(np.max(t))
    if t1 <= t0:
        med = float(np.median(v))
        q1 = float(np.percentile(v, 25))
        q3 = float(np.percentile(v, 75))
        p90 = float(np.percentile(v, 90))
        return np.array([t0]), np.array([med]), np.array([q1]), np.array([q3]), np.array([p90])

    edges = np.arange(t0, t1 + bin_h, bin_h)
    if len(edges) < 2:
        edges = np.array([t0, t1 + bin_h])

    idx = np.digitize(t, edges) - 1
    centers, medians, q1s, q3s, p90s = [], [], [], [], []
    for i in range(len(edges) - 1):
        matched = idx == i
        if not np.any(matched):
            continue
        yy = v[matched]
        centers.append(0.5 * (edges[i] + edges[i + 1]))
        medians.append(float(np.median(yy)))
        q1s.append(float(np.percentile(yy, 25)))
        q3s.append(float(np.percentile(yy, 75)))
        p90s.append(float(np.percentile(yy, 90)))

    return (
        np.asarray(centers, dtype=float),
        np.asarray(medians, dtype=float),
        np.asarray(q1s, dtype=float),
        np.asarray(q3s, dtype=float),
        np.asarray(p90s, dtype=float),
    )


def _plot_fidelity_binned_30m(ax, t_h, traces, base_color):
    colors = [base_color, mix_with_white(base_color, amount=0.3)]
    for index, (label, infidelity) in enumerate(traces):
        fidelity_pct = _fidelity_percent_from_infidelity(infidelity)
        xb, med, q1, q3, p90 = _binned_stats_quartiles(t_h, fidelity_pct, bin_h=0.5)
        if len(xb) == 0:
            continue
        color = colors[index % len(colors)]
        ax.plot(xb, med, "-", linewidth=1.2, color=color, alpha=0.95, label=label, zorder=2)
        ax.fill_between(xb, q1, q3, color=color, alpha=0.2, zorder=1)
        ax.plot(xb, p90, "--", linewidth=0.7, color=color, alpha=0.5, zorder=1)

    ax.set_xlabel("Elapsed time (h)")
    ax.set_ylabel("Fidelity (%)")
    ax.set_title("30 min statistics (median, IQR, p90)")
    ax.grid(True, alpha=0.25)
    lo, hi = _adaptive_fidelity_ylim_from_traces(traces)
    ax.set_ylim(lo, hi)
    if len(traces) > 1:
        ax.legend(frameon=False)


def _fidelity_traces(fidelity_df):
    primary = np.clip(fidelity_df["infidelity"].to_numpy(dtype=float), 1e-16, None)
    traces = [("drift", primary)]
    if "infidelity_f0" in fidelity_df.columns:
        traces = [("f-fmean", primary)]
        traces.append(("f-f(0)", np.clip(fidelity_df["infidelity_f0"].to_numpy(dtype=float), 1e-16, None)))
    return traces


def _compute_infidelity_cv(infidelity):
    inf = np.asarray(infidelity, dtype=float)
    inf = inf[np.isfinite(inf)]
    if len(inf) == 0 or float(np.mean(inf)) <= 0.0:
        return np.nan
    return float(np.std(inf) / np.mean(inf))


def _fidelity_threshold_label(n_nines):
    if n_nines <= 0:
        return "99%"
    return "99." + ("9" * int(n_nines)) + "%"


def _compute_fidelity_thresholds_analysis(t_h, fidelity_pct):
    t = np.asarray(t_h, dtype=float)
    f = np.asarray(fidelity_pct, dtype=float)
    mask = np.isfinite(t) & np.isfinite(f)
    t = t[mask]
    f = f[mask]
    if len(t) < 2:
        return []

    f_min, f_max = float(np.min(f)), float(np.max(f))
    initial_fid = float(f[0])
    thresholds = []
    for n_nines in range(0, 13):
        thr = 100.0 - 10.0 ** (-n_nines)
        if f_min < thr < f_max:
            thresholds.append({"threshold_pct": float(thr), "threshold_label": _fidelity_threshold_label(n_nines)})

    results = []
    dt = np.diff(t) if len(t) > 1 else np.array([], dtype=float)
    for threshold in thresholds:
        thr = float(threshold["threshold_pct"])
        above = f >= thr
        total_time_above_h = float(np.sum(dt[above[:-1]])) if len(dt) > 0 else 0.0
        total_duration_h = float(t[-1] - t[0]) if len(t) > 1 else 0.0
        fraction_time_above_pct = 100.0 * total_time_above_h / total_duration_h if total_duration_h > 0.0 else 0.0

        first_violation_idx = None
        first_violation_time_h = np.nan
        if not np.all(above):
            idx_violation = np.where(~above)[0]
            if len(idx_violation) > 0:
                first_violation_idx = int(idx_violation[0])
                first_violation_time_h = float(t[idx_violation[0]] - t[0])

        results.append({
            "threshold_pct": thr,
            "threshold_label": threshold["threshold_label"],
            "initial_fidelity_pct": initial_fid,
            "first_violation_idx": first_violation_idx,
            "first_violation_time_h": first_violation_time_h,
            "total_time_above_h": total_time_above_h,
            "fraction_time_above_pct": fraction_time_above_pct,
        })
    return results


def _analyze_threshold_windows(t_h, fidelity_pct, threshold_pct):
    t = np.asarray(t_h, dtype=float)
    f = np.asarray(fidelity_pct, dtype=float)
    mask = np.isfinite(t) & np.isfinite(f)
    t = t[mask]
    f = f[mask]
    if len(t) < 2:
        return {"above": {}, "below": {}}

    dt = np.diff(t) * 60.0
    above = f >= threshold_pct
    windows_above, windows_below = [], []
    current_window = 0.0
    in_above_state = bool(above[0]) if len(above) > 0 else False

    for i in range(len(above) - 1):
        current_window += float(dt[i])
        if above[i] != above[i + 1]:
            if in_above_state:
                windows_above.append(current_window)
            else:
                windows_below.append(current_window)
            current_window = 0.0
            in_above_state = above[i + 1]
    current_window += float(dt[-1]) if len(dt) > 0 else 0.0
    if in_above_state:
        windows_above.append(current_window)
    else:
        windows_below.append(current_window)

    def window_stats(windows):
        if len(windows) == 0:
            return {"longest": np.nan, "mean": np.nan, "median": np.nan, "p90": np.nan, "count": 0}
        w = np.asarray(windows, dtype=float)
        return {
            "longest": float(np.max(w)),
            "mean": float(np.mean(w)),
            "median": float(np.median(w)),
            "p90": float(np.percentile(w, 90)),
            "count": len(windows),
        }

    return {"above": window_stats(windows_above), "below": window_stats(windows_below)}


def _fidelity_window_survival(windows_min):
    w = np.asarray(windows_min, dtype=float)
    if len(w) == 0:
        return []
    w = w[np.isfinite(w)]
    if len(w) == 0:
        return []

    sorted_w = np.sort(w)
    unique_w = np.unique(sorted_w)
    survival = []
    for length in unique_w:
        frac = float(np.round(np.sum(w >= length) / len(w), 10))
        frac = np.clip(frac, 0.0, 1.0)
        survival.append((float(length), frac))
    return survival


class FidelityPlot(BasePlot):
    def build_matplotlib(self, result: FidelityResult, style: str = "default") -> plt.Figure:
        if style not in {"default", "paper"}:
            raise ValueError(f"Unknown Fidelity style '{style}'")

        plt_style = "default" if style == "default" else "classic"
        with plt.style.context(plt_style):
            frame = result.frame
            if len(frame) == 0:
                raise ValueError("FidelityResult contains no rows to plot")

            meta = dict(result.meta)
            dataset_id = str(meta.get("dataset_id", self.name))
            base_color = qubit_color(dataset_id=dataset_id, meta=meta)
            alt_color = mix_with_white(base_color, amount=0.3)

            t_h = frame["t_s"].to_numpy(dtype=float) / 3600.0
            infidelity = np.clip(frame["infidelity"].to_numpy(dtype=float), 1e-16, None)
            fidelity_pct = _fidelity_percent_from_infidelity(infidelity)
            omega_base_hz = float(np.median(frame["omega_base_hz"].to_numpy(dtype=float))) if "omega_base_hz" in frame.columns else np.nan
            traces = _fidelity_traces(frame)

            fig, axes = make_fidelity_figure(figsize=(14, 16))
            ax_inf = axes["inf"]
            ax_thresholds = axes["thresholds"]
            ax_zoom = axes["zoom"]
            ax_roll = axes["roll"]
            ax_survival = axes["survival"]
            ax_summary = axes["summary"]

            # apply consistent white background + light grid styling
            apply_common_style(ax_inf)
            apply_common_style(ax_thresholds)
            apply_common_style(ax_zoom)
            apply_common_style(ax_roll)
            apply_common_style(ax_survival)

            ax_inf.semilogy(t_h, infidelity, color=base_color, linewidth=1.2, label="infidelity")
            _draw_decade_guides(ax_inf, infidelity)
            if np.isfinite(omega_base_hz):
                ax_inf.set_title(f"Infidelity with decade guides (Rabi used={omega_base_hz:.5e} Hz)")
            else:
                ax_inf.set_title("Infidelity with decade guides")
            ax_inf.set_ylabel("Infidelity")
            ax_inf.set_xlabel("Elapsed time (h)")
            ax_inf.grid(True, which="both", color="lightgray", alpha=0.4)
            ax_inf.legend(frameon=False, loc="upper left")

            threshold_results = _compute_fidelity_thresholds_analysis(t_h, fidelity_pct)
            filtered_thresholds = [item for item in threshold_results if item["fraction_time_above_pct"] >= 5.0]
            filtered_thresholds.sort(key=lambda item: item["threshold_pct"])
            if len(filtered_thresholds) == 0:
                ax_thresholds.text(0.5, 0.5, "No thresholds with >= 5.0% time shown", ha="center", va="center", transform=ax_thresholds.transAxes)
                ax_thresholds.axis("off")
            else:
                y_positions = np.arange(len(filtered_thresholds))[::-1]
                for y_pos, threshold in zip(y_positions, filtered_thresholds):
                    thr = float(threshold["threshold_pct"])
                    above = fidelity_pct >= thr
                    state = bool(above[0]) if len(above) > 0 else False
                    start = float(t_h[0])
                    for index in range(1, len(t_h)):
                        if bool(above[index]) != state:
                            end = float(t_h[index])
                            ax_thresholds.barh(y_pos, end - start, left=start, height=0.75, color="green" if state else "red", alpha=0.7, edgecolor="none")
                            start = end
                            state = bool(above[index])
                    ax_thresholds.barh(y_pos, float(t_h[-1]) - start, left=start, height=0.75, color="green" if state else "red", alpha=0.7, edgecolor="none")

                ax_thresholds.set_yticks(np.arange(len(filtered_thresholds)))
                ax_thresholds.set_yticklabels([thr["threshold_label"] for thr in filtered_thresholds][::-1], fontsize=7)
                ax_thresholds.set_xlabel("Elapsed time (h)")
                ax_thresholds.set_ylabel("Fidelity threshold")
                ax_thresholds.set_title("Threshold compliance timeline (green=fidelity >= threshold, red=below; >= 5.0% time shown)")
                ax_thresholds.set_xlim(float(np.min(t_h)), float(np.max(t_h)))
                ax_thresholds.grid(True, axis="x", color="lightgray", alpha=0.4)

            _plot_fidelity_zoom_adaptive(ax_zoom, t_h, traces, base_color)
            ax_zoom.set_title("Fidelity zoom (adaptive)")
            ax_zoom.set_xlabel("Elapsed time (h)")

            _plot_fidelity_binned_30m(ax_roll, t_h, traces, base_color)
            ax_roll.set_title("30 min statistics (median, IQR, p90)")

            if len(filtered_thresholds) == 0:
                ax_survival.text(0.5, 0.5, "No thresholds computed", ha="center", va="center", transform=ax_survival.transAxes)
                ax_survival.axis("off")
            else:
                survival_styles = [
                    {"color": "#000000", "linestyle": "-", "marker": "o"},
                    {"color": "#444444", "linestyle": "--", "marker": "s"},
                    {"color": "#222222", "linestyle": "-.", "marker": "^"},
                    {"color": "#111111", "linestyle": ":", "marker": "D"},
                ]
                for index, threshold in enumerate(filtered_thresholds):
                    if index >= len(survival_styles):
                        break
                    style = survival_styles[index]
                    thr = float(threshold["threshold_pct"])
                    above = fidelity_pct >= thr
                    windows = _analyze_threshold_windows(t_h, fidelity_pct, thr)
                    above_windows = []
                    current_window = 0.0
                    for sample in range(len(above) - 1):
                        dt_minutes = float((t_h[sample + 1] - t_h[sample]) * 60.0)
                        if above[sample]:
                            current_window += dt_minutes
                        elif current_window > 0.0:
                            above_windows.append(current_window)
                            current_window = 0.0
                    if len(above) > 0 and above[-1] and current_window > 0.0:
                        above_windows.append(current_window)

                    survival = _fidelity_window_survival(above_windows)
                    if len(survival) > 0:
                        surv_x, surv_y = zip(*survival)
                        threshold_label = f"{thr:.12f}".rstrip("0").rstrip(".") + "%"
                        ax_survival.semilogy(
                            surv_x,
                            surv_y,
                            linestyle=style["linestyle"],
                            marker=style["marker"],
                            linewidth=1.2,
                            markersize=5,
                            markevery=4,
                            color=style["color"],
                            label=threshold_label,
                        )

                ax_survival.set_xlabel("Window length (minutes)")
                ax_survival.set_ylabel("Fraction of windows lasting >= length")
                ax_survival.set_title("Fidelity threshold window survival curves")
                ax_survival.grid(True, which="both", color="lightgray", alpha=0.4)
                ax_survival.legend(frameon=False, loc="upper right")

            infidelity_cv = _compute_infidelity_cv(infidelity)
            summary_lines = [
                f"Coefficient of variation (infidelity): {infidelity_cv:.4f}",
                f"Initial fidelity: {fidelity_pct[0]:.4f}%",
                f"Fidelity range: {float(np.min(fidelity_pct)):.4f}% to {float(np.max(fidelity_pct)):.4f}%",
                "",
            ]
            for threshold in threshold_results:
                windows = _analyze_threshold_windows(t_h, fidelity_pct, float(threshold["threshold_pct"]))
                summary_lines.append(f"{threshold['threshold_label']}:")
                summary_lines.append(
                    f"  Time above: {threshold['total_time_above_h']:.2f} h ({threshold['fraction_time_above_pct']:.1f}%)"
                )
                if np.isfinite(threshold["first_violation_time_h"]):
                    summary_lines.append(f"  First violation time: {threshold['first_violation_time_h']:.2f} h")
                if windows["above"]["count"] > 0:
                    summary_lines.append(
                        f"  Above windows: count={windows['above']['count']}, mean={windows['above']['mean']:.2f} min, median={windows['above']['median']:.2f} min, p90={windows['above']['p90']:.2f} min"
                    )
                if windows["below"]["count"] > 0:
                    summary_lines.append(
                        f"  Below windows: count={windows['below']['count']}, mean={windows['below']['mean']:.2f} min, median={windows['below']['median']:.2f} min, p90={windows['below']['p90']:.2f} min"
                    )
                summary_lines.append("")

            ax_summary.axis("off")
            ax_summary.text(
                0.02,
                0.98,
                "\n".join(summary_lines).strip(),
                transform=ax_summary.transAxes,
                ha="left",
                va="top",
                fontsize=8,
                family="monospace",
                bbox={"facecolor": "lightyellow", "edgecolor": "gray", "boxstyle": "round,pad=0.5"},
            )

            return fig

    def build_plotly(self, result: FidelityResult) -> go.Figure:
        raise NotImplementedError(f"{self.__class__.__name__} has no plotly backend")
