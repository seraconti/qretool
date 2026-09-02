from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import scipy.interpolate

Norm = dict[str, object]


def _real_vs_interpolated_counts(
    t_in_s: np.ndarray, t_out_s: np.ndarray
) -> tuple[int, int]:
    """Count exact vs interpolated timestamps.

    Both inputs are in seconds.
    """
    t_in = np.asarray(t_in_s, dtype=float)
    t_out = np.asarray(t_out_s, dtype=float)
    if len(t_out) == 0:
        return 0, 0
    if len(t_in) == 0:
        return 0, int(len(t_out))

    idx = np.searchsorted(t_in, t_out)
    left = np.clip(idx - 1, 0, len(t_in) - 1)
    right = np.clip(idx, 0, len(t_in) - 1)
    nearest_dist = np.minimum(np.abs(t_out - t_in[left]), np.abs(t_out - t_in[right]))

    dt_in = np.diff(t_in)
    dt_in = dt_in[dt_in > 0]
    tol = 1e-9 if len(dt_in) == 0 else max(1e-9, 1e-3 * float(np.median(dt_in)))

    n_real = int(np.sum(nearest_dist <= tol))
    n_interp = int(len(t_out) - n_real)
    return n_real, n_interp


def _interpolate_finite(
    t_rel_s: np.ndarray,
    values: np.ndarray,
    x_uniform: np.ndarray,
    *,
    label: str,
) -> tuple[np.ndarray, int]:
    """pchip through the finite (t, value) pairs only, plus the count dropped.

    Zero-filling instead would put a real, wrong measurement on the grid - for a detuning,
    exactly 0 Hz - and pchip passes through its data, so it would drag the neighbours too.

    Grid points outside the finite support are NaN, not extrapolated: dropping a leading or
    trailing read shortens the support while the grid still spans the original interval.
    """
    finite = np.isfinite(values)
    n_finite = int(np.count_nonzero(finite))
    if n_finite < 2:
        raise ValueError(
            f"cannot interpolate '{label}': {n_finite} finite value(s) of {finite.size}. "
            f"pchip needs at least two."
        )
    t_support = t_rel_s[finite]
    resampled = scipy.interpolate.pchip_interpolate(
        t_support, values[finite], x_uniform
    )
    outside = (x_uniform < t_support[0]) | (x_uniform > t_support[-1])
    if np.any(outside):
        resampled = np.asarray(resampled, dtype=float).copy()
        resampled[outside] = np.nan
    return resampled, int(finite.size - n_finite)


def run(norm: Mapping[str, object], config: Mapping[str, object]) -> Norm:
    """Interpolate a normalized Ramsey dataset onto a uniform time grid.

    Time values are in seconds and frequency values are in hertz.

    Row-aligned columns come out at the grid length. Reads whose value did not fit are
    dropped before the pchip, never zero-filled.
    """
    del config

    if not isinstance(norm, Mapping):
        raise TypeError("interpolate.run expects normalized dataset mapping input.")

    if "t_rel_s" not in norm:
        raise KeyError(
            "interpolate.run requires 't_rel_s' (relative seconds) in normalized mapping"
        )
    t_rel_s = np.asarray(norm["t_rel_s"], dtype=float)
    delta_hz = np.asarray(norm["delta_hz"], dtype=float)
    if "omega_hz" in norm:
        raise KeyError(
            "interpolate.run no longer accepts 'omega_hz'; use 'rabi_hz' if provided"
        )
    rabi_hz = np.asarray(norm["rabi_hz"], dtype=float) if "rabi_hz" in norm else None
    raw_frequency_hz = (
        np.asarray(norm["raw_frequency_hz"], dtype=float)
        if "raw_frequency_hz" in norm
        else None
    )

    if len(t_rel_s) < 2:
        raise ValueError("Interpolation requires at least two points.")

    # A NaN timestamp sorts last and becomes `t_rel_s[-1]`; an infinite one survives the
    # shift below. Either way the grid is unusable, and unlike a value there is nothing to
    # interpolate a timestamp from.
    if not np.all(np.isfinite(t_rel_s)):
        n_bad = int(t_rel_s.size - np.count_nonzero(np.isfinite(t_rel_s)))
        raise ValueError(
            f"'t_rel_s' carries {n_bad} non-finite timestamp(s) of {t_rel_s.size}. The time "
            f"axis has to be real before anything can be resampled onto it."
        )

    order = np.argsort(t_rel_s)
    t_rel_s = t_rel_s[order]
    delta_hz = delta_hz[order]
    if rabi_hz is not None:
        if len(rabi_hz) != len(order):
            raise ValueError("rabi_hz length must match t_rel_s when provided")
        rabi_hz = rabi_hz[order]
    if raw_frequency_hz is not None:
        # Dropping it instead would hand downstream a Norm missing a key it declared,
        # which reads as "no raw frequency" rather than "its length was wrong".
        if len(raw_frequency_hz) != len(order):
            raise ValueError("raw_frequency_hz length must match t_rel_s when provided")
        raw_frequency_hz = raw_frequency_hz[order]

    t_rel_s = t_rel_s - float(t_rel_s[0])
    x_uniform = np.linspace(0.0, float(t_rel_s[-1]), num=len(t_rel_s))

    # Per column, because each has its own pattern of failed fits.
    nonfinite_dropped: dict[str, int] = {}

    def _resample(values: np.ndarray, label: str) -> np.ndarray:
        resampled, dropped = _interpolate_finite(
            t_rel_s, values, x_uniform, label=label
        )
        if dropped:
            nonfinite_dropped[label] = dropped
        return resampled

    delta_uniform = _resample(delta_hz, "delta_hz")
    rabi_uniform = None if rabi_hz is None else _resample(rabi_hz, "rabi_hz")
    raw_uniform = (
        None
        if raw_frequency_hz is None
        else _resample(raw_frequency_hz, "raw_frequency_hz")
    )

    idx = np.searchsorted(t_rel_s, x_uniform)
    left = np.clip(idx - 1, 0, len(t_rel_s) - 1)
    right = np.clip(idx, 0, len(t_rel_s) - 1)
    nearest = np.where(
        np.abs(x_uniform - t_rel_s[left]) <= np.abs(t_rel_s[right] - x_uniform),
        left,
        right,
    )

    out: Norm = {
        "t_rel_s": np.asarray(x_uniform, dtype=float),
        "delta_hz": np.asarray(delta_uniform, dtype=float),
        "meta": dict(norm["meta"]),
    }
    if rabi_uniform is not None:
        out["rabi_hz"] = np.asarray(rabi_uniform, dtype=float)
    if raw_uniform is not None:
        out["raw_frequency_hz"] = np.asarray(raw_uniform, dtype=float)

    handled_keys = {"t_rel_s", "delta_hz", "rabi_hz", "raw_frequency_hz", "meta"}
    for key, value in norm.items():
        if key in handled_keys:
            continue
        try:
            arr = np.asarray(value)
        except (TypeError, ValueError) as exc:
            # Named rather than left to numpy, and raised rather than passed through, so this
            # matches `filter._subset_norm` on the same input class. A user job can wire this
            # step without a filter upstream, so it cannot lean on that ordering.
            raise ValueError(
                f"interpolate cannot resample '{key}': it is neither a scalar nor an array "
                f"({type(value).__name__}). A Norm value has to be one or the other."
            ) from exc

        # Scalars carry no time axis, so there is nothing to resample in them.
        if arr.ndim == 0:
            out[key] = value
            continue

        # Every array a Norm carries is one value per read, so a length disagreeing with the
        # time axis is a defect rather than a column with nothing to resample. Passing it
        # through would leave it at its input sampling against the new grid - the same silent
        # misalignment `filter._subset_norm` raises on, which is the parity that matters.
        if len(arr) != len(order):
            raise ValueError(
                f"interpolate cannot resample '{key}': length {len(arr)} against a time axis "
                f"of {len(order)}. Leaving it unresampled would misalign it against the grid."
            )

        # Row-aligned from here. Passing the array through unresampled would keep the input
        # sampling at the grid length - misaligned against its own time axis, at a length
        # nothing downstream can use to detect it.
        arr_sorted = arr[order]
        if np.issubdtype(arr_sorted.dtype, np.number):
            out[key] = _resample(arr_sorted.astype(float), key)
        else:
            out[key] = arr_sorted[nearest]

    out["meta"]["n_points"] = int(len(out["t_rel_s"]))
    out["meta"]["duration_h"] = float(
        (np.max(out["t_rel_s"]) - np.min(out["t_rel_s"])) / 3600.0
    )
    # Against the input CLOCK, which is what these keys are about: how much of the grid
    # coincides with a real timestamp. Reads whose VALUE was dropped are a separate fact and
    # are reported under `n_nonfinite_dropped` below.
    n_real, n_interp = _real_vs_interpolated_counts(t_rel_s, out["t_rel_s"])
    total = max(1, n_real + n_interp)
    out["meta"]["n_real_points"] = int(n_real)
    out["meta"]["n_interpolated_points"] = int(n_interp)
    out["meta"]["pct_real_points"] = float(100.0 * n_real / total)
    out["meta"]["pct_interpolated_points"] = float(100.0 * n_interp / total)
    # Which columns lost reads to failed fits, and how many. Absent, nothing was dropped.
    if nonfinite_dropped:
        out["meta"]["n_nonfinite_dropped"] = dict(nonfinite_dropped)

    return out
