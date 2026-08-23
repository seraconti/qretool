"""Kaplan-Meier survival of in-spec windows, estimated from the carve's window table.

This is a STEP: pure compute, no I/O, no matplotlib. It consumes the window table
`analyzers/windows.py` produces and nothing else, so the gap policy, the censoring and
the window identity are the same facts here as in every other consumer of that table.

Two decisions separate this from `panels/_within_calibration_compute._window_survival`, the
crude estimator the within-calibration panel still ships:

- **Right-censored windows are kept, not dropped.** A window that died at a read gap or
  at the end of the scan is not a completed lifetime, but it IS evidence that the window
  survived at least that long. The crude estimator discards it, which biases S(t) toward
  short lifetimes exactly where the record is thinnest. Kaplan-Meier is the estimator
  that uses it, and that is the entire reason for this module.

- **Windows whose birth was not observed are excluded.** An "endurance bag"
  (`birth_type != BIRTH_UP_CROSSING`) was already in spec when observation began or
  resumed, so its age at first sight is unknown: its recorded duration is a residual
  lifetime, not a lifetime. Treating it as a lifetime understates survival; treating it
  as censored at that duration is also wrong. The honest handling is left truncation,
  which needs an entry-age this record does not carry, so these windows are excluded and
  the count is carried on the artifact - `n_unobserved_birth_dropped` - for the figure to
  state. FIGURE_STANDARD requires the exclusion be visible in the panel, not just here.

`reliability_band.estimator` is untouched by this module; flipping the within-calibration
panel over to Kaplan-Meier is a separate change to that band.

Durations are MINUTES (`_min`), matching `ReliabilityBand.survival_curve_min`, because
in-spec windows on this record run from seconds to a few hours and hours would put every
interesting feature below 0.1.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from analyzers.windows import BIRTH_UP_CROSSING, DEATH_DOWN_CROSSING

# Two-sided normal quantile for the confidence band. Named so the figure's band label
# and this constant cannot disagree.
Z_95 = 1.959963984540054
CONF_LEVEL = 0.95


@dataclass(slots=True)
class KaplanMeierInputs:
    """Lifetimes and their censoring indicator, already reduced to observed births.

    death_observed[i] is True when window i died of an observed down-crossing, False
    when it was right-censored (gap start or scan end).
    """

    duration_min: np.ndarray
    death_observed: np.ndarray
    label: str = ""
    dataset_id: str = ""
    threshold_label: str = ""
    n_windows_carved: int = 0
    n_unobserved_birth_dropped: int = 0


@dataclass
class KaplanMeierCurve:
    """A complete Kaplan-Meier estimate: the step function, its band, and its support.

    `time_min` / `survival` are the left ends of the step function's segments, starting
    at (0, 1). Draw with `drawstyle="steps-post"`; the arrays are not resampled onto a
    grid, so a renderer never has to guess where a step fell.

    `band_lower` / `band_upper` are the log-log-transformed pointwise interval at
    CONF_LEVEL. The transform is used rather than Greenwood-on-S directly because the
    plain interval leaves [0, 1] in both tails, which on a survival axis draws a band
    the estimator cannot mean. Entries are NaN where the interval is undefined
    (S = 1 before the first death, S = 0 after the last, or a risk set fully consumed).
    """

    time_min: np.ndarray
    survival: np.ndarray
    band_lower: np.ndarray
    band_upper: np.ndarray
    n_at_risk: np.ndarray

    # Censoring marks, at the S(t) the curve holds when each censored window leaves.
    censor_time_min: np.ndarray
    censor_survival: np.ndarray

    label: str = ""
    dataset_id: str = ""
    threshold_label: str = ""
    conf_level: float = CONF_LEVEL

    n_windows: int = 0
    n_deaths: int = 0
    n_censored: int = 0
    n_windows_carved: int = 0
    n_unobserved_birth_dropped: int = 0
    n_zero_duration: int = 0

    median_survival_min: float | None = None
    # Largest duration in the risk set. S(t) is undefined beyond it; a figure that
    # extends the curve past this is drawing an extrapolation.
    max_observed_min: float = 0.0


@dataclass
class KaplanMeierComparison:
    """Several curves at ONE threshold, plus which two are furthest apart.

    `ranking` is every unordered pair, sorted by `separation` descending, so the pair the
    figure draws is a value in the artifact rather than an eyeball judgement made at draw
    time.

    ONE statistic gates the choice: `separation` = `log_time_separation`, the area between
    the two step curves integrated against d(log10 t) - the vertical gap the eye reads off
    the figure's own log-time axis, summed over the decades it spans. Units are
    survival-fraction x decades.

    The obvious alternative, the vertical supremum sup|S_a - S_b|, is NOT used and must
    not be reintroduced: it is capped at 1 and saturates whenever one curve reaches zero
    before the other starts falling, which is exactly the regime this comparison lives in.
    On the shipped five-dataset carve it returned 0.976 for three different pairs and
    could not rank them at all.

    `separation` is a DISTANCE, not a test: no p-value is attached and none is implied,
    because the curves being ranked were selected on the T2* mean of the same records.
    """

    curves: list[KaplanMeierCurve]
    threshold_label: str
    ranking: list[tuple[str, str, float]] = field(default_factory=list)
    pair: tuple[str, str] | None = None

    def curve(self, label: str) -> KaplanMeierCurve:
        for c in self.curves:
            if c.label == label:
                return c
        raise KeyError(
            f"no Kaplan-Meier curve labelled {label!r}. Have: "
            f"{[c.label for c in self.curves]}"
        )

    def pair_curves(self) -> tuple[KaplanMeierCurve, KaplanMeierCurve]:
        if self.pair is None:
            raise ValueError(
                "KaplanMeierComparison has no selected pair - it was built from fewer "
                "than two curves. Nothing to draw."
            )
        return self.curve(self.pair[0]), self.curve(self.pair[1])


def make_inputs_from_windows(
    windows: pd.DataFrame,
    *,
    threshold_label: str,
    label: str,
    dataset_id: str = "",
) -> KaplanMeierInputs:
    """Select one threshold's windows, drop unobserved births, carry the dropped count.

    Raises on an unknown threshold label rather than returning an empty estimate: a
    silently empty survival curve is the wrong-but-plausible result this repo raises to
    avoid.
    """
    for col in ("threshold_label", "birth_type", "death_type", "duration_s"):
        if col not in windows.columns:
            raise KeyError(
                f"Kaplan-Meier requires column {col!r} in the window table. "
                f"Columns: {list(windows.columns)}"
            )
    known = set(windows["threshold_label"].unique())
    if threshold_label not in known:
        raise KeyError(
            f"threshold {threshold_label!r} is not in the window table. "
            f"Carved thresholds: {sorted(known)}"
        )
    at_threshold = windows[windows["threshold_label"] == threshold_label]
    observed_birth = at_threshold[at_threshold["birth_type"] == BIRTH_UP_CROSSING]
    return KaplanMeierInputs(
        duration_min=observed_birth["duration_s"].to_numpy(dtype=float) / 60.0,
        death_observed=(observed_birth["death_type"].to_numpy() == DEATH_DOWN_CROSSING),
        label=label,
        dataset_id=dataset_id,
        threshold_label=threshold_label,
        n_windows_carved=int(len(at_threshold)),
        n_unobserved_birth_dropped=int(len(at_threshold) - len(observed_birth)),
    )


def run(inputs: KaplanMeierInputs) -> KaplanMeierCurve:
    """Kaplan-Meier product-limit estimate with a log-log pointwise band."""
    t = np.asarray(inputs.duration_min, dtype=float)
    observed = np.asarray(inputs.death_observed, dtype=bool)
    if len(t) != len(observed):
        raise ValueError(
            f"duration_min ({len(t)}) and death_observed ({len(observed)}) must have "
            "the same length"
        )
    if len(t) == 0:
        raise ValueError(
            f"Kaplan-Meier has no windows to estimate from ({inputs.label!r}, "
            f"{inputs.threshold_label!r}). The carve produced "
            f"{inputs.n_windows_carved} window(s), all with unobserved births."
        )
    if not np.all(np.isfinite(t)):
        raise ValueError("duration_min contains non-finite values")
    if np.any(t < 0.0):
        raise ValueError("duration_min contains negative durations")

    # Ties: a death and a censoring at the same recorded time are conventionally ordered
    # death-first, so the censored window is still counted in that time's risk set. The
    # sort key encodes that directly rather than relying on a stable sort of the input.
    order = np.lexsort((observed.astype(int) == 0, t))
    t, observed = t[order], observed[order]

    n_total = len(t)
    times = [0.0]
    surv = [1.0]
    at_risk_out = [n_total]
    greenwood = [0.0]

    s = 1.0
    g = 0.0
    idx = 0
    while idx < n_total:
        t_j = t[idx]
        end = idx
        while end < n_total and t[end] == t_j:
            end += 1
        deaths = int(np.count_nonzero(observed[idx:end]))
        n_j = n_total - idx
        if deaths > 0:
            s *= 1.0 - deaths / n_j
            denom = n_j * (n_j - deaths)
            # A risk set fully consumed at one time makes the Greenwood term infinite;
            # NaN propagates into the band and the renderer draws no band there, which
            # is the honest rendering of "the variance is not defined here".
            g += np.inf if denom == 0 else deaths / denom
            times.append(float(t_j))
            surv.append(float(s))
            at_risk_out.append(int(n_j))
            greenwood.append(float(g))
        idx = end

    time_min = np.asarray(times, dtype=float)
    survival = np.asarray(surv, dtype=float)
    n_at_risk = np.asarray(at_risk_out, dtype=int)
    lower, upper = _loglog_band(survival, np.asarray(greenwood, dtype=float))

    censored_t = t[~observed]
    censor_survival = _step_eval(time_min, survival, censored_t)

    below_half = np.flatnonzero(survival <= 0.5)
    median_min = float(time_min[below_half[0]]) if len(below_half) else None

    n_deaths = int(np.count_nonzero(observed))
    curve = KaplanMeierCurve(
        time_min=time_min,
        survival=survival,
        band_lower=lower,
        band_upper=upper,
        n_at_risk=n_at_risk,
        censor_time_min=censored_t,
        censor_survival=censor_survival,
        label=inputs.label,
        dataset_id=inputs.dataset_id,
        threshold_label=inputs.threshold_label,
        n_windows=n_total,
        n_deaths=n_deaths,
        n_censored=n_total - n_deaths,
        n_windows_carved=inputs.n_windows_carved,
        n_unobserved_birth_dropped=inputs.n_unobserved_birth_dropped,
        n_zero_duration=int(np.count_nonzero(t == 0.0)),
        median_survival_min=median_min,
        max_observed_min=float(np.max(t)),
    )
    print(
        f"[kaplan_meier] {inputs.label} thr={inputs.threshold_label} "
        f"n={n_total} deaths={n_deaths} censored={n_total - n_deaths} "
        f"dropped_unobserved_birth={inputs.n_unobserved_birth_dropped} "
        f"median={median_min if median_min is not None else float('nan'):.3f}min",
        flush=True,
    )
    return curve


def _loglog_band(
    survival: np.ndarray, greenwood: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Pointwise log-log interval: S^exp(+/- z * sqrt(V) / |log S|).

    Undefined where log S is 0 (S = 1) or S is 0; NaN there, so a renderer cannot draw a
    band across a region the estimator says nothing about.
    """
    lower = np.full_like(survival, np.nan, dtype=float)
    upper = np.full_like(survival, np.nan, dtype=float)
    ok = (survival > 0.0) & (survival < 1.0) & np.isfinite(greenwood)
    if not np.any(ok):
        return lower, upper
    s_ok = survival[ok]
    se = np.sqrt(greenwood[ok]) / np.abs(np.log(s_ok))
    lower[ok] = np.clip(s_ok ** np.exp(Z_95 * se), 0.0, 1.0)
    upper[ok] = np.clip(s_ok ** np.exp(-Z_95 * se), 0.0, 1.0)
    return lower, upper


def _step_eval(
    step_times: np.ndarray, step_values: np.ndarray, at: np.ndarray
) -> np.ndarray:
    """Right-continuous step function S evaluated at `at`: the value AFTER the last step <= t."""
    if len(at) == 0:
        return np.asarray([], dtype=float)
    idx = np.searchsorted(step_times, np.asarray(at, dtype=float), side="right") - 1
    return step_values[np.clip(idx, 0, len(step_values) - 1)]


def _support_max_min(curve: KaplanMeierCurve) -> float:
    """Largest t at which S is defined.

    A curve whose last recorded window died of an observed crossing has S = 0 there, and
    S = 0 for every later t is a statement the estimator makes, not an extrapolation - so
    its support is unbounded. A curve still above zero at its longest window ended in a
    censored observation: S beyond that point is genuinely unknown, and its support stops.
    """
    return np.inf if curve.survival[-1] == 0.0 else curve.max_observed_min


def log_time_separation(a: KaplanMeierCurve, b: KaplanMeierCurve) -> float:
    """Area between the two step curves against d(log10 t), in fraction x decades.

    Integrated over [t_lo, t_hi]: t_lo is the earlier of the two first step times (below
    it both curves are 1 and contribute nothing), t_hi the end of the shorter support,
    capped at the longer of the two records - past that both curves are flat and the
    integral would run forever.

    Both curves are step functions, so this is an EXACT rectangle sum on the union of
    their step times, not a quadrature approximation.
    """
    t_hi = min(_support_max_min(a), _support_max_min(b))
    t_hi = min(t_hi, max(a.max_observed_min, b.max_observed_min))
    positive_steps = np.concatenate([a.time_min, b.time_min])
    positive_steps = positive_steps[positive_steps > 0.0]
    if len(positive_steps) == 0 or t_hi <= 0.0:
        return 0.0
    t_lo = float(np.min(positive_steps))
    if t_hi <= t_lo:
        return 0.0

    edges = np.unique(np.concatenate([positive_steps, [t_lo, t_hi]]))
    edges = edges[(edges >= t_lo) & (edges <= t_hi)]
    # The curves hold their value on [edges[i], edges[i+1]); evaluate at the left edge.
    left = edges[:-1]
    gap = np.abs(
        _step_eval(a.time_min, a.survival, left)
        - _step_eval(b.time_min, b.survival, left)
    )
    return float(np.sum(gap * np.diff(np.log10(edges))))


def compare(
    curves: list[KaplanMeierCurve], threshold_label: str
) -> KaplanMeierComparison:
    """Rank every pair by `log_time_separation` and record the widest-apart pair.

    All curves must share `threshold_label`: survival at different thresholds measures
    different events, and ranking distances across them compares nothing.
    """
    mismatched = [c.label for c in curves if c.threshold_label != threshold_label]
    if mismatched:
        raise ValueError(
            f"compare() was given curves carved at a different threshold than "
            f"{threshold_label!r}: {mismatched}. Survival at two thresholds is survival "
            "of two different events."
        )
    ranking = [
        (curves[i].label, curves[j].label, log_time_separation(curves[i], curves[j]))
        for i in range(len(curves))
        for j in range(i + 1, len(curves))
    ]
    ranking.sort(key=lambda row: row[2], reverse=True)
    pair = (ranking[0][0], ranking[0][1]) if ranking else None
    if pair is not None:
        print(
            f"[kaplan_meier] widest pair at {threshold_label}: "
            f"{pair[0]} vs {pair[1]} separation={ranking[0][2]:.3f} fraction*decades",
            flush=True,
        )
    return KaplanMeierComparison(
        curves=list(curves),
        threshold_label=threshold_label,
        ranking=ranking,
        pair=pair,
    )
