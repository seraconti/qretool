from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

import numpy as np
import pandas as pd


@dataclass(slots=True)
class FidelityResult:
    frame: pd.DataFrame
    meta: dict[str, object]


def _to_angular_frequency(freq_hz: np.ndarray, use_angular_frequency: bool) -> np.ndarray:
    frequency_hz = np.asarray(freq_hz, dtype=float)
    if use_angular_frequency:
        return 2.0 * np.pi * frequency_hz
    return frequency_hz


def gate_fidelity(delta: np.ndarray, omega: np.ndarray) -> np.ndarray:
    delta = np.asarray(delta, dtype=float)
    omega = np.asarray(omega, dtype=float)
    lam = np.sqrt(delta**2 + omega**2)
    term_1 = 1.0
    term_2 = (omega**2) / (lam**2)
    term_3 = (delta**2) / (lam**2) * np.cos((lam * np.pi) / (4.0 * omega)) ** 2
    term_4 = (omega / lam) * np.sin((lam * np.pi) / (2.0 * omega))
    return (1.0 / 3.0) * (term_1 + term_2 + term_3 + term_4)


def run(norm: Mapping[str, object], config: Mapping[str, object]) -> FidelityResult:
    """Compute gate fidelity from a normalized Ramsey dataset.

    Frequencies are in hertz unless the config requests angular frequency.
    """
    if not isinstance(norm, Mapping):
        raise TypeError("fidelity.run expects normalized dataset mapping input.")

    t_s = np.asarray(norm["t_s"], dtype=float)
    delta_hz = np.asarray(norm["delta_hz"], dtype=float)
    omega_hz = np.asarray(norm["omega_hz"], dtype=float)
    if len(t_s) == 0:
        raise ValueError("Cannot run fidelity on empty dataset.")

    fidelity_cfg = config.get("fidelity", {})
    if not isinstance(fidelity_cfg, Mapping):
        raise TypeError("config['fidelity'] must be a mapping")
    use_angular_frequency = bool(fidelity_cfg.get("use_angular_frequency", False))
    omega = _to_angular_frequency(omega_hz, use_angular_frequency)
    omega_base_hz = float(np.median(omega_hz))
    profile = str(norm.get("meta", {}).get("profile", config.get("dataset_profile", "")))

    if profile == "longrun":
        if "raw_frequency_hz" not in norm:
            raise KeyError("Longrun fidelity requires 'raw_frequency_hz' in normalized data.")

        raw_frequency_hz = np.asarray(norm["raw_frequency_hz"], dtype=float)
        if len(raw_frequency_hz) != len(t_s):
            raise ValueError("raw_frequency_hz length must match t_s for longrun fidelity.")

        delta_f0_hz = raw_frequency_hz - float(raw_frequency_hz[0])
        delta_fmean_hz = raw_frequency_hz - float(np.mean(raw_frequency_hz))
        delta_f0 = _to_angular_frequency(delta_f0_hz, use_angular_frequency)
        delta_fmean = _to_angular_frequency(delta_fmean_hz, use_angular_frequency)

        fidelity_f0 = gate_fidelity(delta_f0, omega)
        fidelity_fmean = gate_fidelity(delta_fmean, omega)
        infidelity_f0 = np.clip(1.0 - fidelity_f0, 0.0, None)
        infidelity_fmean = np.clip(1.0 - fidelity_fmean, 0.0, None)

        frame = pd.DataFrame(
            {
                "t_s": t_s,
                "delta_hz": delta_fmean_hz,
                "delta_hz_f_minus_f0": delta_f0_hz,
                "delta_hz_f_minus_fmean": delta_fmean_hz,
                "delta_hz_f0": delta_f0_hz,
                "delta_hz_fmean": delta_fmean_hz,
                "omega_hz": omega_hz,
                "fidelity": fidelity_fmean,
                "fidelity_f_minus_f0": fidelity_f0,
                "fidelity_f_minus_fmean": fidelity_fmean,
                "fidelity_f0": fidelity_f0,
                "fidelity_fmean": fidelity_fmean,
                "infidelity": infidelity_fmean,
                "infidelity_f_minus_f0": infidelity_f0,
                "infidelity_f_minus_fmean": infidelity_fmean,
                "infidelity_f0": infidelity_f0,
                "infidelity_fmean": infidelity_fmean,
                "omega_base_hz": np.full_like(t_s, omega_base_hz, dtype=float),
            }
        )
        print(
            f"[fidelity] points={len(frame)} mean_infidelity_fmean={float(np.mean(infidelity_fmean)):.6e} mean_infidelity_f0={float(np.mean(infidelity_f0)):.6e} rabi_base_hz={omega_base_hz:.6g}",
            flush=True,
        )
        return FidelityResult(frame=frame, meta={"profile": profile, "omega_base_hz": omega_base_hz})

    delta = _to_angular_frequency(delta_hz, use_angular_frequency)
    fidelity = gate_fidelity(delta, omega)
    infidelity = np.clip(1.0 - fidelity, 0.0, None)

    frame = pd.DataFrame(
        {
            "t_s": t_s,
            "delta_hz": delta_hz,
            "omega_hz": omega_hz,
            "fidelity": fidelity,
            "infidelity": infidelity,
            "omega_base_hz": np.full_like(t_s, omega_base_hz, dtype=float),
        }
    )
    print(
        f"[fidelity] points={len(frame)} mean_infidelity={float(np.mean(infidelity)):.6e} max_infidelity={float(np.max(infidelity)):.6e} rabi_base_hz={omega_base_hz:.6g}",
        flush=True,
    )
    return FidelityResult(frame=frame, meta={"profile": profile, "omega_base_hz": omega_base_hz})