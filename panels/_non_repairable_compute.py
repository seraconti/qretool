"""Output-builder for NonRepairablePanel: computes the COMPLETE typed panel data.

This is the compute half of the panel. It owns every data-derived quantity —
cumulative time out of spec, cumulative damage, MTTF, per-threshold window stats,
in-spec window survival, 30-min binned stats, CV, and in-spec fractions — so that
the materialized NonRepairablePanelData artifact is complete and the renderer
(panels/non_repairable.py) is a pure function of it (no data arithmetic at draw
time; only axis/theme concerns stay there).

Arithmetic here is ported verbatim from the pre-split draw-time methods; parity is
asserted array-equal against golden baselines captured on the known-good commit.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from analyzers.windows import BIRTH_UP_CROSSING, DEATH_GAP_START
from panels._non_repairable_data import NonRepairablePanelData

# ---------------------------------------------------------------------------
# Direction-agnostic threshold primitives
# ---------------------------------------------------------------------------


def _out_of_spec_mask(
    series: np.ndarray, threshold_value: float, big_values_good: bool
) -> np.ndarray:
    if not big_values_good:
        return series > threshold_value
    return series < threshold_value


def _excess(
    series: np.ndarray, threshold_value: float, big_values_good: bool
) -> np.ndarray:
    if not big_values_good:
        return np.maximum(series - threshold_value, 0.0)
    return np.maximum(threshold_value - series, 0.0)


# ---------------------------------------------------------------------------
# Scalar / distribution helpers (no domain assumptions)
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
    """Factual above/below window statistics; direction-agnostic."""
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
    # NO tail accumulation here. The loop above already consumes ALL of dt
    # (len(dt) == len(above) - 1), so adding dt[-1] again inflated every trace's
    # final window by one read interval — an all-in-spec 2-hour span reported 180
    # minutes instead of 120.
    (windows_above if in_above else windows_below).append(current)

    def _stats(windows: list[float]) -> dict[str, object]:
        if not windows:
            return {
                "longest": np.nan,
                "mean": np.nan,
                "median": np.nan,
                "p90": np.nan,
                "count": 0,
            }
        w = np.asarray(windows, dtype=float)
        return {
            "longest": float(np.max(w)),
            "mean": float(np.mean(w)),
            "median": float(np.median(w)),
            "p90": float(np.percentile(w, 90)),
            "count": len(windows),
        }

    return {"above": _stats(windows_above), "below": _stats(windows_below)}


def _finite_stat(values: np.ndarray | None, fn: Callable[[np.ndarray], float]) -> float:
    """`fn` over the finite entries; NaN when there are none (never silently zero)."""
    if values is None:
        return float("nan")
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    return float(fn(v)) if len(v) else float("nan")


def _hist_view_limit(
    counts: np.ndarray, edges: np.ndarray, quantile: float = 0.99
) -> tuple[float, int]:
    """Upper x-limit holding `quantile` of the mass, and the count left outside it.

    A handful of failed fits carry errors orders of magnitude above the bulk and would
    flatten the histogram against the left edge. The count is data - it is rendered as
    text and a reader treats it as a fact - so it is computed here, not at draw time.
    """
    if len(counts) == 0:
        return float("nan"), 0
    cumulative = np.cumsum(counts)
    total = int(cumulative[-1])
    if total <= 0:
        return float("nan"), 0
    inside = int(np.searchsorted(cumulative, quantile * total, side="left")) + 1
    x_max = float(edges[min(inside, len(edges) - 1)])
    if x_max <= float(edges[0]):
        return float("nan"), 0
    n_outside = total - int(cumulative[min(inside - 1, len(cumulative) - 1)])
    return x_max, int(n_outside)


def _value_histogram(
    values: np.ndarray | None, n_bins: int = 40
) -> tuple[np.ndarray, np.ndarray]:
    """Histogram of the finite entries of `values`; returns (counts, edges).

    Empty (counts, edges) when there is nothing finite to bin — the renderer treats
    that as "no distribution to draw" rather than crashing on an empty axis.
    """
    if values is None:
        return np.array([], dtype=int), np.array([], dtype=float)
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if len(v) == 0 or float(np.max(v)) == float(np.min(v)):
        return np.array([], dtype=int), np.array([], dtype=float)
    counts, edges = np.histogram(v, bins=n_bins)
    return counts, edges


def _window_survival(windows_min: list[float]) -> list[tuple[float, float]]:
    w = np.asarray(windows_min, dtype=float)
    w = w[np.isfinite(w)]
    if len(w) == 0:
        return []
    unique_w = np.unique(np.sort(w))
    return [
        (
            float(length),
            float(np.clip(np.round(np.sum(w >= length) / len(w), 10), 0.0, 1.0)),
        )
        for length in unique_w
    ]


# ---------------------------------------------------------------------------
# Window-table consumers
#
# Carving lives in analyzers/windows.py and reaches the builder as two DataFrames.
# The panel never carves: it reads what the step produced, so the gap policy,
# censoring and window identity are the same facts everywhere they are used.
# ---------------------------------------------------------------------------


def _uncensored_durations_min(windows: pd.DataFrame, label: str) -> list[float]:
    """In-spec window lengths in minutes, censored windows dropped.

    A censored window's observed length is a lower bound on its lifetime, so feeding it
    to the empirical survival estimator as if it were complete biases the curve down.
    Dropping it is the crude fix; Kaplan-Meier is the real one and is a later pass.
    """
    sub = windows[(windows["threshold_label"] == label) & (~windows["censored"])]
    return (sub["duration_s"].to_numpy(dtype=float) / 60.0).tolist()


def _carve_counts(windows: pd.DataFrame, label: str) -> dict[str, object]:
    """Per-threshold carve facts, reported alongside the above/below stats.

    n_censored and n_endurance_bags OVERLAP — a window born at scan_start and dying at
    scan_end is both — so they must never be summed.
    """
    sub = windows[windows["threshold_label"] == label]
    return {
        "n_windows": int(len(sub)),
        "n_censored": int(sub["censored"].sum()),
        "n_endurance_bags": int((sub["birth_type"] != BIRTH_UP_CROSSING).sum()),
        # windows terminated BY a gap, not the record's total gap count
        "n_gaps": int((sub["death_type"] == DEATH_GAP_START).sum()),
        "n_dropped_censored": int(sub["censored"].sum()),
    }


def _timeline_segments(
    reads: pd.DataFrame, label: str
) -> list[tuple[float, float, str]]:
    """Contiguous (t_start_h, t_end_h, state) runs for one threshold's timeline.

    Replaces the renderer's draw-time walk over primary_series: state is a fact of the
    read table, so a 4-state timeline is a lookup rather than a recomputation. A run
    ends at the timestamp of the first read of the NEXT run, so the bars are contiguous.
    """
    sub = reads[reads["threshold_label"] == label]
    if len(sub) == 0:
        return []
    t_h = sub["t_read_s"].to_numpy(dtype=float) / 3600.0
    states = sub["state"].to_numpy(dtype=object)
    segments: list[tuple[float, float, str]] = []
    start = float(t_h[0])
    state = str(states[0])
    for idx in range(1, len(t_h)):
        if str(states[idx]) != state:
            end = float(t_h[idx])
            segments.append((start, end, state))
            start, state = end, str(states[idx])
    segments.append((start, float(t_h[-1]), state))
    return segments


# ---------------------------------------------------------------------------
# Per-threshold derived series/scalars
# ---------------------------------------------------------------------------


def _cumulative_time_out_of_spec(
    t_h: np.ndarray,
    primary_series: np.ndarray,
    thresholds: list[tuple[str, float, bool]],
) -> dict[str, np.ndarray]:
    """Left-Riemann cumulative time out of spec per threshold (hours)."""
    t = np.asarray(t_h, dtype=float)
    s = np.asarray(primary_series, dtype=float)
    mask = np.isfinite(t) & np.isfinite(s)
    t_f, s_f = t[mask], s[mask]

    result: dict[str, np.ndarray] = {}
    for label, thr_val, big_values_good in thresholds:
        if len(t_f) < 2:
            result[label] = np.zeros(len(t_f))
            continue
        oos = _out_of_spec_mask(s_f, thr_val, big_values_good)
        dt_h = np.diff(t_f)
        increments = oos[:-1].astype(float) * dt_h
        cum = np.zeros(len(t_f))
        cum[1:] = np.cumsum(increments)
        result[label] = cum
    return result


def _cumulative_damage(
    t_h: np.ndarray,
    primary_series: np.ndarray,
    thresholds: list[tuple[str, float, bool]],
    damage_fn: Callable[[np.ndarray], np.ndarray] | None,
) -> dict[str, np.ndarray]:
    """Trapezoidal cumulative damage per threshold (primary_unit · h).

    With the default (damage_fn=None → identity) this is the cumulative integral of
    the excess-over-threshold — a real derived curve, NOT a no-op, distinct from the
    cumulative time out of spec (which integrates a 0/1 mask).

    # EXTENSION: future DamageModel. `damage_fn` is the seam for a user-defined,
    # job-declared damage meaning. It is a plain builder parameter ONLY — never routed
    # through node kwargs / identity / provenance labels, because a callable cannot be
    # hashed deterministically or labeled stably. A future modular DamageModel would
    # carry a stable versioned id (e.g. "linear_v1") that folds into identity instead.
    """
    t = np.asarray(t_h, dtype=float)
    s = np.asarray(primary_series, dtype=float)
    mask = np.isfinite(t) & np.isfinite(s)
    t_f, s_f = t[mask], s[mask]

    apply_damage: Callable[[np.ndarray], np.ndarray] = (
        damage_fn if damage_fn is not None else (lambda x: x)
    )

    result: dict[str, np.ndarray] = {}
    for label, thr_val, big_values_good in thresholds:
        if len(t_f) < 2:
            result[label] = np.zeros(len(t_f))
            continue
        excess = _excess(s_f, thr_val, big_values_good)
        damage_rate = apply_damage(excess)
        dt_h = np.diff(t_f)
        trap_steps = 0.5 * (damage_rate[:-1] + damage_rate[1:]) * dt_h
        cum = np.zeros(len(t_f))
        cum[1:] = np.cumsum(trap_steps)
        result[label] = cum
    return result


def _mttf(
    t_h: np.ndarray,
    primary_series: np.ndarray,
    thresholds: list[tuple[str, float, bool]],
) -> dict[str, float | None]:
    """First threshold-crossing time (elapsed hours from t[0]) per threshold."""
    t = np.asarray(t_h, dtype=float)
    s = np.asarray(primary_series, dtype=float)
    mask = np.isfinite(t) & np.isfinite(s)
    t_f, s_f = t[mask], s[mask]

    result: dict[str, float | None] = {}
    for label, thr_val, big_values_good in thresholds:
        oos = _out_of_spec_mask(s_f, thr_val, big_values_good)
        indices = np.where(oos)[0]
        if len(indices) == 0 or len(t_f) == 0:
            result[label] = None
        else:
            result[label] = float(t_f[indices[0]]) - float(t_f[0])
    return result


def _threshold_in_spec_frac(
    t_h: np.ndarray,
    primary_series: np.ndarray,
    thresholds: list[tuple[str, float, bool]],
) -> dict[str, float]:
    """In-spec time fraction per threshold (timeline definition).

    The renderer applies the ≥5% cull to decide which thresholds appear in the
    compliance timeline (decision documented: keep the cull, preserving figures).
    """
    t = np.asarray(t_h, dtype=float)
    s = np.asarray(primary_series, dtype=float)
    mask = np.isfinite(t) & np.isfinite(s)
    t_f, s_f = t[mask], s[mask]
    total_h = float(t_f[-1] - t_f[0]) if len(t_f) > 1 else 0.0

    result: dict[str, float] = {}
    for label, thr_val, big_values_good in thresholds:
        if len(t_f) < 2 or total_h == 0.0:
            result[label] = 0.0
            continue
        oos = _out_of_spec_mask(s_f, thr_val, big_values_good)
        dt = np.diff(t_f)
        oos_h = float(np.sum(dt[oos[:-1]]))
        result[label] = 1.0 - oos_h / total_h
    return result


def _threshold_summary(
    t_h: np.ndarray,
    primary_series: np.ndarray,
    thresholds: list[tuple[str, float, bool]],
) -> dict[str, dict[str, float] | None]:
    """Per-threshold out-of-spec summary (time_oos_h, frac_oos_pct).

    Value is None where the summary skips the threshold (fewer than 2 finite points),
    matching the pre-split summary's `continue`.
    """
    t = np.asarray(t_h, dtype=float)
    s = np.asarray(primary_series, dtype=float)
    mask = np.isfinite(t) & np.isfinite(s)
    t_f, s_f = t[mask], s[mask]

    result: dict[str, dict[str, float] | None] = {}
    for label, thr_val, big_values_good in thresholds:
        if len(t_f) < 2:
            result[label] = None
            continue
        oos = _out_of_spec_mask(s_f, thr_val, big_values_good)
        dt = np.diff(t_f)
        total_h = float(t_f[-1] - t_f[0])
        time_oos_h = float(np.sum(dt[oos[:-1]])) if len(dt) > 0 else 0.0
        frac_oos = 100.0 * time_oos_h / total_h if total_h > 0 else 0.0
        result[label] = {"time_oos_h": time_oos_h, "frac_oos_pct": frac_oos}
    return result


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_non_repairable_panel_data(
    *,
    t_h: np.ndarray,
    primary_series: np.ndarray,
    primary_label: str,
    thresholds: list[tuple[str, float, bool]],
    meta: dict[str, object],
    windows: pd.DataFrame,
    reads: pd.DataFrame,
    gap_spans_s: list[tuple[float, float]] | None = None,
    primary_sigma: np.ndarray | None = None,
    traces: list[tuple[str, np.ndarray]] | None = None,
    use_log_scale: bool = False,
    color: object = None,
    damage_fn: Callable[[np.ndarray], np.ndarray] | None = None,
    include_cumulative_time: bool = True,
    include_cumulative_damage: bool = True,
    include_mttf: bool = True,
    bin_h: float = 0.5,
) -> NonRepairablePanelData:
    """Compute every data-derived quantity and return a COMPLETE NonRepairablePanelData.

    This is the sole constructor path: the renderer assumes the derived fields are
    populated. All derived quantities are computed regardless of the include_* flags
    (completeness); those flags only gate what the renderer draws.

    `windows` and `reads` are the tables from `analyzers/windows.py::run`, carved on the
    SAME series in the same units as `thresholds`. They are required: the panel does not
    carve, so there is exactly one carve in the repo and the gap policy, censoring and
    per-read state cannot diverge between the artifact and the figure.

    `primary_sigma` is the per-read 1-sigma on `primary_series` (same units), used for
    error bars. None when the dataset carries no uncertainty.

    `damage_fn` is the descoped damage seam — see _cumulative_damage.
    """
    t_arr = np.asarray(t_h, dtype=float)
    s_arr = np.asarray(primary_series, dtype=float)
    resolved_traces = traces if traces is not None else [(primary_label, s_arr)]
    sigma_arr = (
        np.asarray(primary_sigma, dtype=float) if primary_sigma is not None else None
    )
    if sigma_arr is not None and len(sigma_arr) != len(s_arr):
        raise ValueError(
            f"primary_sigma must match primary_series in length; got "
            f"{len(sigma_arr)} and {len(s_arr)}"
        )
    # The tables are joined to the panel by threshold_label. A carve run on a
    # different ladder than the panel renders would otherwise pass silently, showing
    # n_windows=0, an empty survival curve and a blank timeline instead of failing.
    if len(reads):
        carved_labels = set(reads["threshold_label"].unique())
        missing = [label for label, _, _ in thresholds if label not in carved_labels]
        if missing:
            raise ValueError(
                f"the window tables were carved on a different ladder than this panel "
                f"renders: no carved reads for threshold(s) {missing}. Carve and render "
                f"must use the same threshold labels."
            )

    primary_hist = _value_histogram(s_arr)
    sigma_hist = _value_histogram(sigma_arr)
    sigma_view = _hist_view_limit(*sigma_hist)

    return NonRepairablePanelData(
        t_h=t_arr,
        primary_series=s_arr,
        primary_label=primary_label,
        thresholds=list(thresholds),
        meta=meta,
        traces=traces,
        use_log_scale=use_log_scale,
        color=color,
        include_cumulative_time=include_cumulative_time,
        include_cumulative_damage=include_cumulative_damage,
        include_mttf=include_mttf,
        cumulative_time_per_threshold=_cumulative_time_out_of_spec(
            t_arr, s_arr, thresholds
        ),
        cumulative_damage_per_threshold=_cumulative_damage(
            t_arr, s_arr, thresholds, damage_fn
        ),
        mttf_per_threshold=_mttf(t_arr, s_arr, thresholds),
        # Carve counts sit BESIDE "above"/"below", never inside them: the renderer
        # bare-indexes w["above"]/w["below"] and hard-indexes their mean/p90/count.
        threshold_window_stats={
            label: {
                **_analyze_threshold_windows(t_arr, s_arr, thr_val),
                **_carve_counts(windows, label),
            }
            for label, thr_val, _ in thresholds
        },
        window_survival_per_threshold={
            label: _window_survival(_uncensored_durations_min(windows, label))
            for label, _thr_val, _bvg in thresholds
        },
        timeline_segments_per_threshold={
            label: _timeline_segments(reads, label) for label, _, _ in thresholds
        },
        primary_sigma=sigma_arr,
        primary_hist_counts=primary_hist[0],
        primary_hist_edges=primary_hist[1],
        sigma_hist_counts=sigma_hist[0],
        sigma_hist_edges=sigma_hist[1],
        sigma_hist_view_x_max=sigma_view[0],
        sigma_hist_n_above_view=sigma_view[1],
        sigma_mean=_finite_stat(sigma_arr, np.mean),
        sigma_median=_finite_stat(sigma_arr, np.median),
        gap_spans_h=[(lo / 3600.0, hi / 3600.0) for lo, hi in (gap_spans_s or [])],
        binned_stats_per_trace={
            label: _binned_stats(t_arr, series, bin_h=bin_h)
            for label, series in resolved_traces
        },
        cv=_compute_cv(s_arr),
        threshold_in_spec_frac=_threshold_in_spec_frac(t_arr, s_arr, thresholds),
        threshold_summary=_threshold_summary(t_arr, s_arr, thresholds),
    )
