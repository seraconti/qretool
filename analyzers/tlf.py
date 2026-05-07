from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from sklearn.mixture import GaussianMixture
from typing import Any


@dataclass(slots=True)
class TLFResult:
    # Group 1 - histogram-based
    is_bimodal: bool
    bic_delta: float
    normalized_bic_delta: float | None
    lobe_separation_ppm: float | None
    # weighted sqrt of per-lobe variances — reflects within-state spread, NOT a clean noise floor; confounded by drift and unresolved sub-fluctuators.
    within_lobe_spread_ppm: float | None
    lobe_snr: float | None
    gmm1: Any
    gmm2: Any

    # Group 2 - dynamics (time-series based, requires timestamps)
    n_transitions: int | None
    switching_rate_per_hour: float | None
    mean_dwell_s0: float | None
    mean_dwell_s1: float | None
    dwell_cv_s0: float | None
    dwell_cv_s1: float | None


def run(values: np.ndarray, timestamps: np.ndarray) -> TLFResult:
    """Fit 1- and 2-component GMMs and return TLF diagnostics.

    Always attempt both fits. If the 2-component fit fails (singular covariance
    or other numerical error), fall back by copying gmm1 into both slots and
    set bic_delta=0.0 and is_bimodal=False.

    Timestamps are required (timestamps in seconds, typically `t_s` from the
    normalized mapping) and are used to compute dwell/run-length dynamics.
    """
    if timestamps is None:
        raise ValueError("timestamps must be provided to TLF.run for dynamics computation")

    vals = np.asarray(values).reshape(-1, 1).astype(float)
    if vals.size == 0:
        raise ValueError("No values provided to TLF analysis")

    gmm1 = GaussianMixture(n_components=1, covariance_type="full")
    gmm1.fit(vals)

    # Attempt a 2-component fit; if it fails, return a fallback copy of gmm1.
    try:
        gmm2 = GaussianMixture(n_components=2, covariance_type="full")
        gmm2.fit(vals)
    except Exception:
        # numerical fallback: copy gmm1 into both slots and set histogram-based extras to None
        return TLFResult(
            is_bimodal=False,
            bic_delta=0.0,
            normalized_bic_delta=None,
            lobe_separation_ppm=None,
            within_lobe_spread_ppm=None,
            lobe_snr=None,
            gmm1=gmm1,
            gmm2=gmm1,
            n_transitions=None,
            switching_rate_per_hour=None,
            mean_dwell_s0=None,
            mean_dwell_s1=None,
            dwell_cv_s0=None,
            dwell_cv_s1=None,
        )

    # compute BICs and histogram-based diagnostics
    bic1 = gmm1.bic(vals)
    bic2 = gmm2.bic(vals)
    bic_delta = float(bic1 - bic2)
    normalized_bic_delta = float(bic_delta / len(vals)) if len(vals) > 0 else None
    is_bimodal = bic_delta > 6.0

    means = np.sort(gmm2.means_.ravel())
    weights = gmm2.weights_.ravel()
    covs = gmm2.covariances_.ravel()

    mean_overall = float(np.mean(vals))
    if mean_overall == 0.0:
        lobe_sep_ppm = None
        within_spread_ppm = None
    else:
        lobe_sep_ppm = float(abs(means[-1] - means[0]) / mean_overall * 1e6)
        # approximate within-lobe spread as sqrt(weighted average of variances)
        sigma_val = float(np.sqrt(np.sum(weights * covs)))
        within_spread_ppm = float(sigma_val / mean_overall * 1e6)

    # lobe SNR: separation divided by within-lobe spread
    if within_spread_ppm is None or within_spread_ppm == 0.0:
        lobe_snr = None
    else:
        lobe_snr = float(lobe_sep_ppm / within_spread_ppm) if lobe_sep_ppm is not None else None

    # Prepare default Group 2 (dynamics) outputs; will be filled if timestamps provided.
    n_transitions = None
    switching_rate_per_hour = None
    mean_dwell_s0 = None
    mean_dwell_s1 = None
    dwell_cv_s0 = None
    dwell_cv_s1 = None

    # Group 2: if timestamps provided, compute run-length dwell metrics. Let any exceptions here
    # propagate so callers can diagnose issues (per requirement).
    if timestamps is not None:
        ts = np.asarray(timestamps)
        if ts.shape[0] != vals.shape[0]:
            raise ValueError("timestamps must have the same length as values")

        # median sampling interval (seconds)
        median_dt = float(np.median(np.diff(ts)))
        if median_dt <= 0.0:
            raise ValueError("Non-positive median sampling interval in timestamps")

        # Assign states using GMM(2) posterior means ordering: state 0 = component with lower mean
        raw_preds = gmm2.predict(vals).ravel()
        comp_means = gmm2.means_.ravel()
        order = np.argsort(comp_means)
        lower_idx = int(order[0])
        # Map original labels to 0/1 where 0 = lower mean
        mapped = np.where(raw_preds == lower_idx, 0, 1).astype(int)

        # Run-length encoding
        if mapped.size == 0:
            runs_vals = []
            runs_lengths = []
        else:
            change_idx = np.flatnonzero(np.diff(mapped)) + 1
            splits = np.split(mapped, change_idx)
            runs_vals = [int(s[0]) for s in splits]
            runs_lengths = [int(len(s)) for s in splits]

        # durations in seconds per run
        durations = np.array(runs_lengths, dtype=float) * median_dt

        # number of transitions is number of changes between runs
        n_transitions = max(0, len(runs_lengths) - 1)

        # total duration in hours
        total_duration_hours = float((ts[-1] - ts[0]) / 3600.0)
        switching_rate_per_hour = float(n_transitions / total_duration_hours) if total_duration_hours > 0 else None

        # exclude first and last run from dwell statistics
        if len(runs_lengths) <= 2:
            # after trimming no runs remain
            mean_dwell_s0 = None
            mean_dwell_s1 = None
            dwell_cv_s0 = None
            dwell_cv_s1 = None
        else:
            trimmed_vals = runs_vals[1:-1]
            trimmed_durations = durations[1:-1]

            # collect per-state durations
            dur_s0 = [d for v, d in zip(trimmed_vals, trimmed_durations) if v == 0]
            dur_s1 = [d for v, d in zip(trimmed_vals, trimmed_durations) if v == 1]

            mean_dwell_s0 = float(np.mean(dur_s0)) if len(dur_s0) > 0 else None
            mean_dwell_s1 = float(np.mean(dur_s1)) if len(dur_s1) > 0 else None

            # CV only defined if >=3 runs for that state
            if len(dur_s0) >= 3:
                dwell_cv_s0 = float(np.std(dur_s0, ddof=1) / np.mean(dur_s0))
            else:
                dwell_cv_s0 = None

            if len(dur_s1) >= 3:
                dwell_cv_s1 = float(np.std(dur_s1, ddof=1) / np.mean(dur_s1))
            else:
                dwell_cv_s1 = None

    return TLFResult(
        is_bimodal=is_bimodal,
        bic_delta=bic_delta,
        normalized_bic_delta=normalized_bic_delta,
        lobe_separation_ppm=lobe_sep_ppm,
        within_lobe_spread_ppm=within_spread_ppm,
        lobe_snr=lobe_snr,
        gmm1=gmm1,
        gmm2=gmm2,
        n_transitions=n_transitions,
        switching_rate_per_hour=switching_rate_per_hour,
        mean_dwell_s0=mean_dwell_s0,
        mean_dwell_s1=mean_dwell_s1,
        dwell_cv_s0=dwell_cv_s0,
        dwell_cv_s1=dwell_cv_s1,
    )
