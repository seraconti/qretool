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

from panels.non_repairable import NonRepairablePanelData

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
    current += float(dt[-1]) if len(dt) > 0 else 0.0
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


def _collect_windows(
    t_h: np.ndarray,
    series: np.ndarray,
    threshold_value: float,
    big_values_good: bool,
) -> list[float]:
    """Window lengths (minutes) for in-spec state.

    big_values_good=True: out-of-spec = below threshold → in-spec = above (e.g. T2*)
    big_values_good=False: out-of-spec = above threshold → in-spec = below (e.g. infidelity)
    """
    t = np.asarray(t_h, dtype=float)
    s = np.asarray(series, dtype=float)
    mask = np.isfinite(t) & np.isfinite(s)
    t, s = t[mask], s[mask]
    if len(t) < 2:
        return []
    dt = np.diff(t) * 60.0
    good = s >= threshold_value if big_values_good else s < threshold_value
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

    `damage_fn` is the descoped damage seam — see _cumulative_damage.
    """
    t_arr = np.asarray(t_h, dtype=float)
    s_arr = np.asarray(primary_series, dtype=float)
    resolved_traces = traces if traces is not None else [(primary_label, s_arr)]

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
        threshold_window_stats={
            label: _analyze_threshold_windows(t_arr, s_arr, thr_val)
            for label, thr_val, _ in thresholds
        },
        window_survival_per_threshold={
            label: _window_survival(_collect_windows(t_arr, s_arr, thr_val, bvg))
            for label, thr_val, bvg in thresholds
        },
        binned_stats_per_trace={
            label: _binned_stats(t_arr, series, bin_h=bin_h)
            for label, series in resolved_traces
        },
        cv=_compute_cv(s_arr),
        threshold_in_spec_frac=_threshold_in_spec_frac(t_arr, s_arr, thresholds),
        threshold_summary=_threshold_summary(t_arr, s_arr, thresholds),
    )
