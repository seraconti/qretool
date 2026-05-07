from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Callable

from analyzers.allan import run as run_allan
from analyzers.fidelity import run as run_fidelity
from analyzers.tlf import run as run_tlf
from core.dataset import Dataset
from core.job import Job
from plots.allan_plot import AllanPlot
from plots.fidelity_plot import FidelityPlot
from plots.tlf_plot import TLFPlot
from transforms.filter import run as run_filter
from transforms.interpolate import run as run_interpolate


RAMSEY_CONFIG: dict[str, object] = {
    "filter": {
        "apply_chi_squared": True,
        "chi_squared_threshold": 0.8,
        "apply_sigma": True,
        "sigma_factor": 3.5,
        "apply_frequency_window": False,
        "frequency_window_hz": {"min": 1.0e6, "max": 3.0e6},
    },
    "allan": {"modes": ["raw"], "taus_mode": "all", "min_points_for_allan": 8},
    "fidelity": {"use_angular_frequency": False},
    "dataset_profile": "overnight",
}


def _copy_config(profile: str) -> dict[str, object]:
    config = dict(RAMSEY_CONFIG)
    config["dataset_profile"] = profile
    config["filter"] = dict(RAMSEY_CONFIG["filter"])
    config["filter"]["frequency_window_hz"] = dict(RAMSEY_CONFIG["filter"]["frequency_window_hz"])
    config["allan"] = dict(RAMSEY_CONFIG["allan"])
    config["fidelity"] = dict(RAMSEY_CONFIG["fidelity"])
    return config


def _filter_step(config: Mapping[str, object]) -> Callable[[dict[str, object]], dict[str, object]]:
    def step(norm: dict[str, object]) -> dict[str, object]:
        return run_filter(norm, config, None)

    return step


def _interpolate_step(config: Mapping[str, object]) -> Callable[[dict[str, object]], dict[str, object]]:
    def step(norm: dict[str, object]) -> dict[str, object]:
        return run_interpolate(norm, config)

    return step


def _allan_step(config: Mapping[str, object]) -> Callable[[dict[str, object]], object]:
    def step(norm: dict[str, object], fractional: bool = False, carrier_col: str = "frequency") -> object:
        return run_allan(norm, config, fractional=fractional, carrier_col=carrier_col)

    return step


def _fidelity_step(config: Mapping[str, object]) -> Callable[[dict[str, object]], object]:
    def step(norm: dict[str, object]) -> object:
        return run_fidelity(norm, config)

    return step


def _tlf_step() -> Callable[[dict[str, object]], dict[str, object]]:
    def step(norm: dict[str, object]) -> dict[str, object]:
        # TLF analysis on filtered (but NOT interpolated) data to preserve noise metrics.
        # Input norm is the final filtered stage from filter step, with uninterpolated timestamps.
        if "raw_frequency_hz" in norm:
            values_hz = norm["raw_frequency_hz"]
        elif "delta_hz" in norm:
            values_hz = norm["delta_hz"]
        else:
            raise KeyError("TLF analysis requires 'raw_frequency_hz' or 'delta_hz' in normalized mapping")

        # timestamps (seconds, relative to start) required for dynamics computation
        if "t_s" not in norm:
            raise KeyError("TLF analysis requires 't_s' (relative timestamps in seconds) in normalized mapping for dynamics")
        timestamps = norm["t_s"]

        result = run_tlf(values_hz, timestamps)
        return {
            "result": result,
            "values_hz": values_hz,
            "meta": dict(norm.get("meta", {})),
        }

    return step


def _final_stage(bundle: dict[str, object]) -> dict[str, object]:
    return dict(bundle["stages"][bundle["final_stage"]])


def configure_ramsey_job(
    job: Job,
    dataset: object,
    *,
    profile: str,
    plot_mode: str,
    include_fidelity: bool,
    include_tlf: bool = False,
    allan_fractional: bool = False,
    allan_carrier_col: str = "frequency",
    figure_prefix: str | None = None,
) -> None:
    del plot_mode

    config = _copy_config(profile)
    # dataset may be a Dataset (to load) or a pre-registered NodeHandle (already loaded/enriched)
    if hasattr(dataset, "node_id"):
        raw = dataset
    else:
        raw = job.load(dataset)

    # Decide fidelity inclusion based on device family when caller didn't explicitly
    # disable it. Device-aware branching keeps the job semantics clear per dataset.
    dev = None
    # if raw was created from a Dataset node, that original Dataset lives in kwargs
    if hasattr(raw, "kwargs") and isinstance(raw.kwargs.get("dataset"), Dataset):
        dev = raw.kwargs.get("dataset").device
    elif hasattr(dataset, "device"):
        dev = dataset.device
    if dev is not None and isinstance(dev, str) and dev.lower().startswith("2x2"):
        include_fidelity = False
        include_tlf = False
        allan_fractional = False
    filtered = job.step(_filter_step(config), raw, name="filter")
    final_filtered = job.step(_final_stage, filtered, name="final_filter_stage")
    interpolated = job.step(_interpolate_step(config), final_filtered, name="interpolate")
    allan = job.step(
        _allan_step(config),
        interpolated,
        name="allan",
        fractional=allan_fractional,
        carrier_col=allan_carrier_col,
    )

    prefix = figure_prefix or job.name
    job.figure(AllanPlot, allan, targets=["static", "academic"], title=f"{prefix} Allan")

    if include_fidelity:
        fidelity_raw = job.step(_fidelity_step(config), final_filtered, name="fidelity_raw")
        fidelity_interp = job.step(_fidelity_step(config), interpolated, name="fidelity_interp")
        job.figure(FidelityPlot, fidelity_interp, targets=["static", "academic"], title=f"{prefix} Fidelity")
        job.materialize(fidelity_raw, name=f"{prefix}_fidelity_raw")

    if include_tlf:
        tlf = job.step(_tlf_step(), final_filtered, name="tlf")
        job.figure(TLFPlot, tlf, targets=["static", "academic"], title=f"{prefix} TLF")
        job.materialize(tlf, name=f"{prefix}_tlf")
