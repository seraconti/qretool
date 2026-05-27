from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping

import numpy as np
import pandas as pd


@dataclass(slots=True)
class FidelityResult:
    frame: pd.DataFrame
    meta: dict[str, object]
    diagnostics: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class FidelityInputs:
    t_rel_s: np.ndarray
    delta_hz: np.ndarray
    rabi_hz: np.ndarray
    profile: str
    raw_frequency_hz: np.ndarray | None = None
    use_angular_frequency: bool = False


def make_inputs_from_norm(norm: Mapping[str, object], config: Mapping[str, object]) -> FidelityInputs:
    """Extract FidelityInputs from a normalized mapping and config dict."""
    if "t_rel_s" not in norm:
        raise KeyError("Fidelity requires 't_rel_s' (relative seconds) in the normalized mapping.")
    if "rabi_hz" not in norm:
        raise KeyError(
            "Fidelity requires 'rabi_hz' in the normalized mapping. "
            "Add it via lookup_prior(..., fields=['Rabi_frequency'], aliases={'Rabi_frequency': 'rabi_hz'}) "
            "or disable fidelity for this job."
        )
    fidelity_cfg = config.get("fidelity", {})
    if not isinstance(fidelity_cfg, Mapping):
        raise TypeError("config['fidelity'] must be a mapping")
    meta = norm.get("meta", {}) if isinstance(norm.get("meta", {}), Mapping) else {}
    profile = str(meta.get("profile", config.get("dataset_profile", "")))
    raw_frequency_hz = np.asarray(norm["raw_frequency_hz"], dtype=float) if "raw_frequency_hz" in norm else None
    return FidelityInputs(
        t_rel_s=np.asarray(norm["t_rel_s"], dtype=float),
        delta_hz=np.asarray(norm["delta_hz"], dtype=float),
        rabi_hz=np.asarray(norm["rabi_hz"], dtype=float),
        profile=profile,
        raw_frequency_hz=raw_frequency_hz,
        use_angular_frequency=bool(fidelity_cfg.get("use_angular_frequency", False)),
    )


def _to_angular_frequency(freq_hz: np.ndarray, use_angular_frequency: bool) -> np.ndarray:
    frequency_hz = np.asarray(freq_hz, dtype=float)
    if use_angular_frequency:
        return 2.0 * np.pi * frequency_hz
    return frequency_hz


def gate_fidelity(delta: np.ndarray, rabi_drive: np.ndarray) -> np.ndarray:
    delta = np.asarray(delta, dtype=float)
    rabi_drive = np.asarray(rabi_drive, dtype=float)
    lam = np.sqrt(delta**2 + rabi_drive**2)
    term_1 = 1.0
    term_2 = (rabi_drive**2) / (lam**2)
    term_3 = (delta**2) / (lam**2) * np.cos((lam * np.pi) / (4.0 * rabi_drive)) ** 2
    term_4 = (rabi_drive / lam) * np.sin((lam * np.pi) / (2.0 * rabi_drive))
    return (1.0 / 3.0) * (term_1 + term_2 + term_3 + term_4)


def run(inputs: FidelityInputs) -> FidelityResult:
    """Compute gate fidelity from typed FidelityInputs.

    Frequencies are in hertz unless inputs.use_angular_frequency is True.
    """
    t_rel_s = inputs.t_rel_s
    delta_hz = inputs.delta_hz
    rabi_hz = inputs.rabi_hz

    if len(t_rel_s) == 0:
        raise ValueError("Cannot run fidelity on empty dataset.")

    rabi_drive = _to_angular_frequency(rabi_hz, inputs.use_angular_frequency)
    rabi_base_hz = float(np.median(rabi_hz))

    if inputs.profile == "longrun":
        if inputs.raw_frequency_hz is None:
            raise KeyError("Longrun fidelity requires 'raw_frequency_hz' in FidelityInputs.")
        raw_frequency_hz = inputs.raw_frequency_hz
        if len(raw_frequency_hz) != len(t_rel_s):
            raise ValueError("raw_frequency_hz length must match t_rel_s for longrun fidelity.")

        delta_f0_hz = raw_frequency_hz - float(raw_frequency_hz[0])
        delta_fmean_hz = raw_frequency_hz - float(np.mean(raw_frequency_hz))
        delta_f0 = _to_angular_frequency(delta_f0_hz, inputs.use_angular_frequency)
        delta_fmean = _to_angular_frequency(delta_fmean_hz, inputs.use_angular_frequency)

        fidelity_f0 = gate_fidelity(delta_f0, rabi_drive)
        fidelity_fmean = gate_fidelity(delta_fmean, rabi_drive)
        infidelity_f0 = np.clip(1.0 - fidelity_f0, 0.0, None)
        infidelity_fmean = np.clip(1.0 - fidelity_fmean, 0.0, None)

        frame = pd.DataFrame(
            {
                "t_rel_s": t_rel_s,
                "delta_hz": delta_fmean_hz,
                "delta_hz_f_minus_f0": delta_f0_hz,
                "delta_hz_f_minus_fmean": delta_fmean_hz,
                "delta_hz_f0": delta_f0_hz,
                "delta_hz_fmean": delta_fmean_hz,
                "rabi_frequency_hz": rabi_hz,
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
                "rabi_base_hz": np.full_like(t_rel_s, rabi_base_hz, dtype=float),
            }
        )
        diag = {
            "mean_infidelity_fmean": float(np.mean(infidelity_fmean)),
            "mean_infidelity_f0": float(np.mean(infidelity_f0)),
            "rabi_base_hz": rabi_base_hz,
        }
        print(
            f"[fidelity] points={len(frame)} mean_infidelity_fmean={diag['mean_infidelity_fmean']:.6e} mean_infidelity_f0={diag['mean_infidelity_f0']:.6e} rabi_base_hz={rabi_base_hz:.6g}",
            flush=True,
        )
        return FidelityResult(
            frame=frame,
            meta={"profile": inputs.profile, "rabi_base_hz": rabi_base_hz},
            diagnostics=diag,
        )

    delta = _to_angular_frequency(delta_hz, inputs.use_angular_frequency)
    fidelity = gate_fidelity(delta, rabi_drive)
    infidelity = np.clip(1.0 - fidelity, 0.0, None)

    frame = pd.DataFrame(
        {
            "t_rel_s": t_rel_s,
            "delta_hz": delta_hz,
            "rabi_frequency_hz": rabi_hz,
            "fidelity": fidelity,
            "infidelity": infidelity,
            "rabi_base_hz": np.full_like(t_rel_s, rabi_base_hz, dtype=float),
        }
    )
    diag = {
        "mean_infidelity": float(np.mean(infidelity)),
        "max_infidelity": float(np.max(infidelity)),
        "rabi_base_hz": rabi_base_hz,
    }
    print(
        f"[fidelity] points={len(frame)} mean_infidelity={diag['mean_infidelity']:.6e} max_infidelity={diag['max_infidelity']:.6e} rabi_base_hz={rabi_base_hz:.6g}",
        flush=True,
    )
    return FidelityResult(
        frame=frame,
        meta={"profile": inputs.profile, "rabi_base_hz": rabi_base_hz},
        diagnostics=diag,
    )
