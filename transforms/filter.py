from __future__ import annotations

from collections.abc import Mapping

import numpy as np

Norm = dict[str, object]


def _copy_norm(norm: Mapping[str, object]) -> Norm:
    copied = dict(norm)
    meta = copied.get("meta")
    if isinstance(meta, dict):
        copied["meta"] = dict(meta)
    return copied


def _subset_norm(norm: Mapping[str, object], mask: np.ndarray) -> Norm:
    out = _copy_norm(norm)
    mask = np.asarray(mask, dtype=bool)
    for key, value in list(out.items()):
        if key == "meta":
            continue
        try:
            arr = np.asarray(value)
            if arr.ndim == 0:
                continue
            if len(arr) == len(mask):
                out[key] = arr[mask]
            else:
                out[key] = arr
        except Exception:
            continue

    t_s = np.asarray(out.get("t_s", []), dtype=float)
    if len(t_s) > 0:
        t_s = t_s - float(t_s[0])
    out["t_s"] = t_s
    if "meta" not in out or not isinstance(out["meta"], dict):
        out["meta"] = {}
    out["meta"]["n_points"] = int(len(t_s))
    out["meta"]["duration_h"] = float((np.max(t_s) - np.min(t_s)) / 3600.0) if len(t_s) > 1 else 0.0
    return out


def run(norm: Mapping[str, object], config: Mapping[str, object], output_dir: object) -> Norm:
    """Filter a normalized Ramsey dataset.

    The filter may apply chi-square, frequency-window, and sigma clipping steps.
    Time values are in seconds and frequency values are in hertz.
    """
    del output_dir

    if not isinstance(norm, Mapping):
        raise TypeError("filter.run expects normalized dataset mapping input.")

    dataset_id = norm["meta"]["dataset_id"]
    t_s = np.asarray(norm["t_s"], dtype=float)
    if len(t_s) == 0:
        raise ValueError("Cannot run filter on empty dataset.")

    print(f"[filter] dataset={dataset_id} start_points={len(t_s)}", flush=True)

    current = _copy_norm(norm)
    stages: dict[str, Norm] = {"raw": _copy_norm(norm)}
    stage_order = ["raw"]
    rows: list[dict[str, int | str]] = [{"stage": "raw", "n_points": int(len(t_s))}]

    filter_cfg = config.get("filter", {}) if isinstance(config.get("filter", {}), Mapping) else {}
    apply_chi = bool(filter_cfg.get("apply_chi_squared", True))
    apply_sigma = bool(filter_cfg.get("apply_sigma", True))
    apply_window = bool(filter_cfg.get("apply_frequency_window", False))

    if apply_chi:
        if "chi_squared" not in current:
            raise KeyError("chi_squared filtering requested but normalized mapping has no 'chi_squared' key.")
        if "chi_squared_threshold" not in filter_cfg:
            raise KeyError("Missing config.filter.chi_squared_threshold required for chi-squared filtering.")
        chi_threshold = float(filter_cfg["chi_squared_threshold"])
        print(
            f"[filter] chi_squared profile={config.get('dataset_profile')} threshold={chi_threshold}",
            flush=True,
        )
        mask = np.asarray(current["chi_squared"], dtype=float) < chi_threshold
        current = _subset_norm(current, mask)
        rows.append({"stage": "chi_squared", "n_points": int(len(current["t_s"]))})
        stages["chi_squared"] = _copy_norm(current)
        stage_order.append("chi_squared")
        print(f"[filter] after_chi_squared<{chi_threshold}: {len(current['t_s'])}", flush=True)

    if apply_window:
        if "raw_frequency_hz" not in current:
            raise KeyError("frequency window filtering requested but normalized mapping has no 'raw_frequency_hz'.")
        window_cfg = filter_cfg.get("frequency_window_hz")
        if not isinstance(window_cfg, Mapping) or "min" not in window_cfg or "max" not in window_cfg:
            raise ValueError("filter.frequency_window_hz must be a mapping with numeric min/max.")
        min_hz = float(window_cfg["min"])
        max_hz = float(window_cfg["max"])
        frequency_hz = np.asarray(current["raw_frequency_hz"], dtype=float)
        mask = (frequency_hz > min_hz) & (frequency_hz < max_hz)
        current = _subset_norm(current, mask)
        rows.append({"stage": "frequency_window", "n_points": int(len(current["t_s"]))})
        stages["frequency_window"] = _copy_norm(current)
        stage_order.append("frequency_window")
        print(f"[filter] after_frequency_window({min_hz},{max_hz}): {len(current['t_s'])}", flush=True)

    if apply_sigma:
        sigma_factor = float(filter_cfg.get("sigma_factor", 3.5))
        delta_hz = np.asarray(current["delta_hz"], dtype=float)
        mu = float(np.mean(delta_hz))
        sigma = float(np.std(delta_hz))
        if sigma == 0.0:
            mask = np.ones(len(delta_hz), dtype=bool)
        else:
            mask = (delta_hz - mu < sigma_factor * sigma) & (delta_hz - mu > -sigma_factor * sigma)
        current = _subset_norm(current, mask)
        rows.append({"stage": "sigma", "n_points": int(len(current["t_s"]))})
        stages["sigma"] = _copy_norm(current)
        stage_order.append("sigma")
        print(f"[filter] after_sigma({sigma_factor}): {len(current['t_s'])}", flush=True)

    return {
        "stages": stages,
        "stage_order": stage_order,
        "final_stage": stage_order[-1],
        "counts": rows,
        "meta": dict(current["meta"]),
    }
