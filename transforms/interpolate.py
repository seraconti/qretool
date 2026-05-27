from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import scipy.interpolate

Norm = dict[str, object]


def _real_vs_interpolated_counts(t_in_s: np.ndarray, t_out_s: np.ndarray) -> tuple[int, int]:
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


def run(norm: Mapping[str, object], config: Mapping[str, object]) -> Norm:
    """Interpolate a normalized Ramsey dataset onto a uniform time grid.

    Time values are in seconds and frequency values are in hertz.
    """
    del config

    if not isinstance(norm, Mapping):
        raise TypeError("interpolate.run expects normalized dataset mapping input.")

    if "t_rel_s" not in norm:
        raise KeyError("interpolate.run requires 't_rel_s' (relative seconds) in normalized mapping")
    t_rel_s = np.asarray(norm["t_rel_s"], dtype=float)
    delta_hz = np.asarray(norm["delta_hz"], dtype=float)
    if "omega_hz" in norm:
        raise KeyError("interpolate.run no longer accepts 'omega_hz'; use 'rabi_hz' if provided")
    rabi_hz = np.asarray(norm["rabi_hz"], dtype=float) if "rabi_hz" in norm else None
    raw_frequency_hz = np.asarray(norm["raw_frequency_hz"], dtype=float) if "raw_frequency_hz" in norm else None

    if len(t_rel_s) < 2:
        raise ValueError("Interpolation requires at least two points.")

    order = np.argsort(t_rel_s)
    t_rel_s = t_rel_s[order]
    delta_hz = delta_hz[order]
    if rabi_hz is not None:
        rabi_hz = rabi_hz[order]
    if raw_frequency_hz is not None and len(raw_frequency_hz) == len(order):
        raw_frequency_hz = raw_frequency_hz[order]

    t_rel_s = t_rel_s - float(t_rel_s[0])
    x_uniform = np.linspace(0.0, float(t_rel_s[-1]), num=len(t_rel_s))
    delta_uniform = scipy.interpolate.pchip_interpolate(t_rel_s, np.nan_to_num(delta_hz), x_uniform)

    rabi_uniform = None
    if rabi_hz is not None:
        if len(rabi_hz) == len(t_rel_s):
            rabi_uniform = scipy.interpolate.pchip_interpolate(t_rel_s, np.nan_to_num(rabi_hz), x_uniform)
        else:
            raise ValueError("rabi_hz length must match t_rel_s when provided")

    raw_uniform = None
    if raw_frequency_hz is not None and len(raw_frequency_hz) == len(t_rel_s):
        raw_uniform = scipy.interpolate.pchip_interpolate(t_rel_s, np.nan_to_num(raw_frequency_hz), x_uniform)

    idx = np.searchsorted(t_rel_s, x_uniform)
    left = np.clip(idx - 1, 0, len(t_rel_s) - 1)
    right = np.clip(idx, 0, len(t_rel_s) - 1)
    nearest = np.where(np.abs(x_uniform - t_rel_s[left]) <= np.abs(t_rel_s[right] - x_uniform), left, right)

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
            if arr.ndim == 0 or len(arr) != len(order):
                out[key] = value
                continue

            arr_sorted = arr[order]
            if np.issubdtype(arr_sorted.dtype, np.number):
                out[key] = scipy.interpolate.pchip_interpolate(t_rel_s, np.nan_to_num(arr_sorted.astype(float)), x_uniform)
            else:
                out[key] = arr_sorted[nearest]
        except Exception:
            out[key] = value

    out["meta"]["n_points"] = int(len(out["t_rel_s"]))
    out["meta"]["duration_h"] = float((np.max(out["t_rel_s"]) - np.min(out["t_rel_s"])) / 3600.0)
    n_real, n_interp = _real_vs_interpolated_counts(t_rel_s, out["t_rel_s"])
    total = max(1, n_real + n_interp)
    out["meta"]["n_real_points"] = int(n_real)
    out["meta"]["n_interpolated_points"] = int(n_interp)
    out["meta"]["pct_real_points"] = float(100.0 * n_real / total)
    out["meta"]["pct_interpolated_points"] = float(100.0 * n_interp / total)

    print(
        f"[interpolate] dataset={out['meta']['dataset_id']} input_points={len(t_rel_s)} output_points={len(out['t_rel_s'])} real={out['meta']['pct_real_points']:.1f}% interp={out['meta']['pct_interpolated_points']:.1f}%",
        flush=True,
    )
    return out
