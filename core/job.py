from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from loaders.registry import load as load_dataframe
from core.dataset import Dataset
from core.types import Norm
from plots.base import BasePlot
from transforms.lookup_prior import check_unix_s


@dataclass(slots=True)
class NodeHandle:
    node_id: str
    job_ref: Job
    fn_name: str
    kwargs: dict[str, object]


@dataclass(slots=True)
class _DAGNode:
    node_id: str
    fn: Callable[..., object]
    fn_name: str
    inputs: list[NodeHandle]
    kwargs: dict[str, object]


@dataclass(slots=True)
class _FigureSink:
    plot_class: type[BasePlot]
    input: NodeHandle
    targets: list[str]
    name: str


@dataclass(slots=True)
class _MaterializeSink:
    node: NodeHandle
    name: str


def _load_dataset(dataset: Dataset) -> Norm:
    frame = load_dataframe(dataset.path, meta=dict(dataset.extra))
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Dataset loader must return a pandas.DataFrame")

    frame = frame.copy()
    if "qubit_id" not in frame.columns:
        frame["qubit_id"] = int(dataset.qubit)
    # expose device metadata to the schema so device-specific validation/cleanup
    # can be performed inside the schema class (not in job runtime).
    if "device" not in frame.columns:
        frame["device"] = dataset.device

    if dataset.schema is not None:
        schema = dataset.schema
        if hasattr(schema, "validate"):
            frame = schema.validate(frame, dataset=dataset)

    if "timestamp" not in frame.columns or "frequency" not in frame.columns:
        raise KeyError("Loaded dataset must contain 'timestamp' and 'frequency' columns")

    timestamp = pd.to_numeric(frame["timestamp"], errors="coerce")
    frequency = pd.to_numeric(frame["frequency"], errors="coerce")
    valid = np.isfinite(timestamp.to_numpy(dtype=float)) & np.isfinite(frequency.to_numpy(dtype=float))
    if not np.any(valid):
        raise ValueError(f"Dataset {dataset.path} has no valid numeric timestamp/frequency rows")

    t_raw = timestamp.to_numpy(dtype=float)[valid]
    f_hz = frequency.to_numpy(dtype=float)[valid]
    order = np.argsort(t_raw)
    t_raw = t_raw[order]
    f_hz = f_hz[order]
    t_rel_s = t_raw - float(t_raw[0])

    meta = dict(dataset.extra)
    meta.update(
        {
            "dataset_id": str(meta.get("run_name", Path(dataset.path).stem)),
            "run_name": str(meta.get("run_name", Path(dataset.path).stem)),
            "qubit": dataset.qubit,
            "device": dataset.device,
            "duration_h": dataset.duration_h,
            "n_points": int(len(t_rel_s)),
        }
    )
    # Determine run_start_unix_s via three resolution levels (see TIME_SEMANTICS.md):
    #   1. Explicit: Dataset.extra['run_start_unix_s'] already in meta — validate and use.
    #   2. date_only_midnight: DDMMYY_ filename prefix — midnight of that date (local naive).
    #   3. No valid source → raise; do NOT fall back to t_raw[0] (yields ~1970 epoch).
    if meta.get("run_start_unix_s") is not None:
        meta["run_start_unix_s"] = check_unix_s(meta["run_start_unix_s"], label="Dataset.extra['run_start_unix_s']")
        meta["run_start_resolution"] = "explicit"
    else:
        date_match = re.match(r"^(\d{2})(\d{2})(\d{2})_", Path(dataset.path).stem)
        if date_match is not None:
            try:
                day = int(date_match.group(1))
                month = int(date_match.group(2))
                year = 2000 + int(date_match.group(3))
                run_day = pd.Timestamp(year=year, month=month, day=day)
                meta["run_start_unix_s"] = float(run_day.value / 1e9)
                meta["run_start_resolution"] = "date_only_midnight"
                warnings.warn(
                    f"[{meta['dataset_id']}] run_start_unix_s derived from DDMMYY filename prefix "
                    f"as midnight local time (resolution: date_only_midnight). Intra-day "
                    f"precision is lost; a calibration from earlier the same day or late "
                    f"the previous day may be selected incorrectly. "
                    f"Provide Dataset.extra['run_start_unix_s'] for precision.",
                    UserWarning,
                    stacklevel=2,
                )
            except Exception as exc:
                raise ValueError(
                    f"Cannot determine run start time for '{meta['dataset_id']}': DDMMYY prefix "
                    f"found but parsing failed ({exc}). "
                    f"Provide Dataset.extra['run_start_unix_s'] explicitly."
                ) from exc
        else:
            raise ValueError(
                f"Cannot determine run start time for '{meta['dataset_id']}'. "
                f"Provide Dataset.extra['run_start_unix_s'] explicitly, "
                f"or use a filename with a DDMMYY_ prefix encoding the run date."
            )

    # default delta (relative to mean); rabi drive is not synthesized here
    delta_hz = f_hz - float(np.mean(f_hz))
    meta.setdefault("rabi_source", "missing")

    norm = Norm({
        "t_rel_s": t_rel_s,
        "delta_hz": delta_hz,
        "raw_frequency_hz": f_hz,
        "meta": meta,
    })
    if "normalised chi-square" in frame.columns:
        chi = pd.to_numeric(frame["normalised chi-square"], errors="coerce").to_numpy(dtype=float)[valid][order]
        norm["chi_squared"] = chi
    if "T2star" in frame.columns:
        norm["T2star_s"] = pd.to_numeric(frame["T2star"], errors="coerce").to_numpy(dtype=float)[valid][order]
    if "T2star error" in frame.columns:
        norm["T2star_error_s"] = pd.to_numeric(frame["T2star error"], errors="coerce").to_numpy(dtype=float)[valid][order]
    return norm


def _load_dataframe_raw(dataset: Dataset) -> pd.DataFrame:
    df = load_dataframe(dataset.path, meta=dict(dataset.extra))
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Raw loader must return a pandas.DataFrame")
    return df.copy()


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    cleaned = cleaned.strip("_")
    return cleaned or "node"


class Job:
    def __init__(self, name: str) -> None:
        self.name = name
        self.dag: dict[str, _DAGNode] = {}
        self.sinks: list[_FigureSink | _MaterializeSink] = []
        self._node_counts: dict[str, int] = {}

    def _allocate_node_id(self, base_name: str) -> str:
        slug = _safe_name(base_name)
        count = self._node_counts.get(slug, 0) + 1
        self._node_counts[slug] = count
        node_id = slug if count == 1 else f"{slug}_{count}"
        while node_id in self.dag:
            count += 1
            self._node_counts[slug] = count
            node_id = f"{slug}_{count}"
        return node_id

    def _register_node(
        self,
        fn: Callable[..., object],
        inputs: list[NodeHandle],
        kwargs: dict[str, object],
        base_name: str,
    ) -> NodeHandle:
        for input_handle in inputs:
            if input_handle.job_ref is not self:
                raise ValueError("All inputs to a job step must belong to the same Job instance")
        node_id = self._allocate_node_id(base_name)
        self.dag[node_id] = _DAGNode(node_id=node_id, fn=fn, fn_name=base_name, inputs=inputs, kwargs=kwargs)
        return NodeHandle(node_id=node_id, job_ref=self, fn_name=base_name, kwargs=kwargs)

    def load(self, dataset: Dataset) -> NodeHandle:
        return self._register_node(
            fn=_load_dataset,
            inputs=[],
            kwargs={"dataset": dataset},
            base_name="load",
        )

    def load_df(self, dataset: Dataset) -> NodeHandle:
        """Load a dataset as a raw pandas.DataFrame node (for companion/auxiliary files).

        This registers a node that yields a DataFrame (not the normalized mapping).
        """
        return self._register_node(fn=_load_dataframe_raw, inputs=[], kwargs={"dataset": dataset}, base_name="load_df")

    def step(self, fn: Callable[..., object], *inputs: NodeHandle, name: str | None = None, **kwargs: object) -> NodeHandle:
        step_name = name or getattr(fn, "__name__", fn.__class__.__name__)
        return self._register_node(fn=fn, inputs=list(inputs), kwargs=dict(kwargs), base_name=step_name)

    def figure(self, PlotClass: type[BasePlot], input: NodeHandle, targets: list[str], title: str = "") -> None:
        if input.job_ref is not self:
            raise ValueError("Figure input must belong to the same Job instance")
        sink_name = _safe_name(title) if title else f"fig_{input.node_id}"
        self.sinks.append(_FigureSink(plot_class=PlotClass, input=input, targets=list(targets), name=sink_name))

    def materialize(self, node: NodeHandle, name: str) -> None:
        if node.job_ref is not self:
            raise ValueError("Materialized node must belong to the same Job instance")
        self.sinks.append(_MaterializeSink(node=node, name=_safe_name(name)))
