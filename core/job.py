from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from loaders.registry import load as load_dataframe
from core.dataset import Dataset
from core.paths import resolve_repo_path
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


def _subjob_artifact(*args: object, **kwargs: object) -> object:
    """Sentinel for a composite node that yields an included sub-job's result.

    Never executed directly: the runner special-cases nodes whose fn is this
    sentinel (mirroring its `fn.__name__ == "_load_dataset"` dispatch), resolving
    them by running the sub-job in figures-as-materialize mode (or reading its
    cached artifact under --reuse-deps).
    """
    raise RuntimeError(
        "_subjob_artifact is resolved by the runner, not called directly"
    )


def _import_job(path: Path) -> Job:
    """Import a job module by file path and return its top-level `job` (with
    `job_file` attached), mirroring main._module_from_path. Used by Job.include."""
    resolved = path.resolve()
    module_name = (
        f"subjob_{re.sub(r'[^A-Za-z0-9_]', '_', resolved.stem)}_"
        f"{hashlib.sha256(str(resolved).encode('utf-8')).hexdigest()[:8]}"
    )
    spec = importlib.util.spec_from_file_location(module_name, resolved)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot import job module from {resolved}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    job = getattr(module, "job", None)
    if job is None:
        raise ValueError(f"Job module {resolved} has no top-level 'job'")
    job.job_file = resolved
    return job


@dataclass(slots=True)
class _IncludedJob:
    """A sub-job pulled into a composite via Job.include.

    `figures=False` (default) → the composite runs it with figures-as-materialize
    (each figure() persists its input node as a .pkl, ref-able by node id);
    `figures=True` → the sub-job's figures are rendered too.
    """

    alias: str
    path: Path
    job: Job
    figures: bool
    composite: Job

    def _referenceable(self) -> set[str]:
        """Node names whose results the composite can `ref` (persisted artifacts)."""
        names: set[str] = set()
        for sink in self.job.sinks:
            if isinstance(sink, _MaterializeSink):
                names.add(sink.name)
            elif isinstance(sink, _FigureSink) and not self.figures:
                names.add(sink.input.node_id)
        return names

    def ref(self, composite_job: Job, node_name: str) -> NodeHandle:
        if composite_job is not self.composite:
            raise ValueError(
                "ref() must be called with the composite Job that created this include"
            )
        available = self._referenceable()
        if node_name not in available:
            raise ValueError(
                f"Sub-job '{self.job.name}' (alias '{self.alias}') does not persist a node "
                f"'{node_name}'. Referenceable outputs: {sorted(available) or '<none>'}. "
                f"(Figure inputs are persisted only when figures=False; or add an explicit "
                f"job.materialize(node, '{node_name}') in the sub-job.)"
            )
        return composite_job._register_node(
            fn=_subjob_artifact,
            inputs=[],
            kwargs={"included": self, "node_name": node_name},
            base_name=f"{self.alias}__{node_name}",
        )


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
        if hasattr(schema, "to_norm"):
            # Event-log schemas bypass standard time-series normalization entirely.
            return schema.to_norm(frame, dataset)
        if hasattr(schema, "validate"):
            frame = schema.validate(frame, dataset=dataset)

    if "timestamp" not in frame.columns or "frequency" not in frame.columns:
        raise KeyError(
            "Loaded dataset must contain 'timestamp' and 'frequency' columns"
        )

    timestamp = pd.to_numeric(frame["timestamp"], errors="coerce")
    frequency = pd.to_numeric(frame["frequency"], errors="coerce")
    valid = np.isfinite(timestamp.to_numpy(dtype=float)) & np.isfinite(
        frequency.to_numpy(dtype=float)
    )
    if not np.any(valid):
        raise ValueError(
            f"Dataset {dataset.path} has no valid numeric timestamp/frequency rows"
        )

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
        meta["run_start_unix_s"] = check_unix_s(
            meta["run_start_unix_s"], label="Dataset.extra['run_start_unix_s']"
        )
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

    norm = Norm(
        {
            "t_rel_s": t_rel_s,
            "delta_hz": delta_hz,
            "raw_frequency_hz": f_hz,
            "meta": meta,
        }
    )
    if "normalised chi-square" in frame.columns:
        chi = pd.to_numeric(frame["normalised chi-square"], errors="coerce").to_numpy(
            dtype=float
        )[valid][order]
        norm["chi_squared"] = chi
    if "T2star" in frame.columns:
        norm["T2star_s"] = pd.to_numeric(frame["T2star"], errors="coerce").to_numpy(
            dtype=float
        )[valid][order]
    if "T2star error" in frame.columns:
        norm["T2star_error_s"] = pd.to_numeric(
            frame["T2star error"], errors="coerce"
        ).to_numpy(dtype=float)[valid][order]
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
        # Composite jobs: sub-jobs pulled in via include(); empty for normal jobs.
        self.includes: list[_IncludedJob] = []

    def include(
        self, path: str | Path, alias: str | None = None, figures: bool = False
    ) -> _IncludedJob:
        """Pull another job in as a dependency, to `ref` one of its outputs.

        The composite runs the included job through the normal run_job (so its
        datasets/provenance resolve exactly as a standalone run); `figures=False`
        (default) turns each of its figure() sinks into a materialization.
        """
        # Resolve BEFORE _import_job so the import works from any CWD; the
        # absolute path is also what _resolve_one_include re-reads for the
        # reuse-glob source hash.
        sub_path = resolve_repo_path(path)
        if not sub_path.exists():
            raise FileNotFoundError(
                f"include not found: '{path}' resolved to '{sub_path}'. "
                "Include paths are repo-root-relative (e.g. 'jobs/active/<job>.py')."
            )
        sub_job = _import_job(sub_path)
        if sub_job.includes:
            raise ValueError(
                f"Cannot include '{sub_job.name}' ({sub_path}): it is itself a composite job. "
                f"Nested composites are not supported."
            )
        included = _IncludedJob(
            alias=alias or sub_job.name,
            path=sub_path,
            job=sub_job,
            figures=figures,
            composite=self,
        )
        self.includes.append(included)
        return included

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
                raise ValueError(
                    "All inputs to a job step must belong to the same Job instance"
                )
        node_id = self._allocate_node_id(base_name)
        self.dag[node_id] = _DAGNode(
            node_id=node_id, fn=fn, fn_name=base_name, inputs=inputs, kwargs=kwargs
        )
        return NodeHandle(
            node_id=node_id, job_ref=self, fn_name=base_name, kwargs=kwargs
        )

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
        return self._register_node(
            fn=_load_dataframe_raw,
            inputs=[],
            kwargs={"dataset": dataset},
            base_name="load_df",
        )

    def step(
        self,
        fn: Callable[..., object],
        *inputs: NodeHandle,
        name: str | None = None,
        **kwargs: object,
    ) -> NodeHandle:
        step_name = name or getattr(fn, "__name__", fn.__class__.__name__)
        return self._register_node(
            fn=fn, inputs=list(inputs), kwargs=dict(kwargs), base_name=step_name
        )

    def figure(
        self,
        PlotClass: type[BasePlot],
        input: NodeHandle,
        targets: list[str],
        title: str = "",
    ) -> None:
        if input.job_ref is not self:
            raise ValueError("Figure input must belong to the same Job instance")
        sink_name = _safe_name(title) if title else f"fig_{input.node_id}"
        self.sinks.append(
            _FigureSink(
                plot_class=PlotClass, input=input, targets=list(targets), name=sink_name
            )
        )

    def materialize(self, node: NodeHandle, name: str) -> None:
        if node.job_ref is not self:
            raise ValueError("Materialized node must belong to the same Job instance")
        self.sinks.append(_MaterializeSink(node=node, name=_safe_name(name)))
