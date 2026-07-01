from __future__ import annotations

import pickle
import sys
from datetime import datetime
from pathlib import Path

from core.job import Job, _FigureSink, _DAGNode, _subjob_artifact
from provenance import (
    build_prov_record,
    get_git_commit,
    hash_file,
    hash_string,
    save_prov,
)
from plots.targets import RENDER_TARGETS


def _job_file(job: Job) -> Path:
    # Prefer explicit job_file attached at import time (main._module_from_path sets this).
    explicit = getattr(job, "job_file", None)
    if explicit is not None:
        return Path(explicit).resolve()

    # Fallback: attempt to locate via job.__module__ (legacy behavior)
    module = sys.modules.get(getattr(job, "__module__", ""))
    module_file = getattr(module, "__file__", None) if module is not None else None
    if module_file is None:
        raise ValueError(
            "Cannot resolve job file: attach 'job.job_file' when importing job modules"
        )
    return Path(module_file).resolve()


def _project_root(job_file: Path) -> Path:
    return job_file.parents[2]


def _resolve_dataset_path(
    job_file: Path, dataset_path: Path, data_root: Path | None = None
) -> Path:
    if dataset_path.is_absolute():
        return dataset_path
    # If caller provided a data_root, resolve relative to it (explicit override)
    if data_root is not None:
        return (Path(data_root) / dataset_path).resolve()
    # Default: resolve relative to the project root inferred from the job file
    return (_project_root(job_file) / dataset_path).resolve()


def _format_step(node: _DAGNode) -> str:
    if node.kwargs:
        kwargs = ", ".join(f"{key}={value!r}" for key, value in node.kwargs.items())
        return f"{node.fn_name}({kwargs})"
    return node.fn_name


def _toposort(job: Job, root_ids: list[str]) -> list[str]:
    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visited:
            return
        if node_id in visiting:
            raise ValueError(f"Cycle detected in job DAG at node '{node_id}'")
        node = job.dag[node_id]
        visiting.add(node_id)
        for input_handle in node.inputs:
            visit(input_handle.node_id)
        visiting.remove(node_id)
        visited.add(node_id)
        ordered.append(node_id)

    for node_id in root_ids:
        visit(node_id)
    return ordered


def _ancestors(job: Job, root_id: str) -> set[str]:
    reachable: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in reachable:
            return
        reachable.add(node_id)
        for input_handle in job.dag[node_id].inputs:
            visit(input_handle.node_id)

    visit(root_id)
    return reachable


def _load_node(job: Job, ordered_ids: list[str]) -> _DAGNode:
    for node_id in ordered_ids:
        node = job.dag[node_id]
        if node.fn.__name__ == "_load_dataset":
            return node
    raise ValueError("Job does not contain a load node")


def _resolve_includes(
    job: Job,
    out_dir: Path,
    job_out_dir: Path,
    reuse_deps: bool,
    data_root: Path | None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Resolve every `_subjob_artifact` node of a composite: fresh-run each included
    sub-job (figures-as-materialize, nested under subjobs_output/) or read its
    standalone cache under --reuse-deps. Returns (node_id -> result, prov entries)."""
    subjobs_dir = job_out_dir / "subjobs_output"
    include_results: dict[str, object] = {}
    includes_prov: list[dict[str, object]] = []
    for node_id, node in job.dag.items():
        if node.fn is not _subjob_artifact:
            continue
        inc = node.kwargs["included"]
        node_name = str(node.kwargs["node_name"])
        obj, mode, prov_rel, artifact_hash = _resolve_one_include(
            inc, node_name, out_dir, subjobs_dir, job_out_dir, reuse_deps, data_root
        )
        include_results[node_id] = obj
        includes_prov.append(
            {
                "alias": inc.alias,
                "job_name": inc.job.name,
                "node_name": node_name,
                "artifact_hash": artifact_hash,
                "mode": mode,
                "subjob_prov_dir": prov_rel,
            }
        )
    return include_results, includes_prov


def _resolve_one_include(
    inc: object,
    node_name: str,
    out_dir: Path,
    subjobs_dir: Path,
    job_out_dir: Path,
    reuse_deps: bool,
    data_root: Path | None,
) -> tuple[object, str, str, str]:
    sub_hash = hash_string(inc.path.read_text(encoding="utf-8"))[:6]
    artifact_rel = f"{node_name}.pkl"
    dir_glob = f"{inc.job.name}_{sub_hash}_*"

    def _cached_runs() -> list[Path]:
        # A reusable run is one whose dir holds {node_name}.pkl. That artifact only
        # exists where the node was materialized: a standalone run that materialized
        # it, OR a prior composite's nested subjobs_output/. Search both; the dir
        # basename ends with the run timestamp, so sorting by name => newest last.
        # Exclude this composite's own in-progress dir so a second include of the
        # same sub-job can't self-read the first include's fresh write this run.
        candidates = list(out_dir.glob(dir_glob))
        candidates += list(out_dir.glob(f"*/subjobs_output/{dir_glob}"))
        return sorted(
            (
                d
                for d in candidates
                if (d / artifact_rel).exists() and job_out_dir not in d.parents
            ),
            key=lambda d: d.name,
        )

    cached = _cached_runs()
    if reuse_deps and cached:
        produced_dir = cached[-1]
        mode = "cached"
    else:
        if cached:
            print(
                f"[NOTE] composite is re-running sub-job '{inc.job.name}' which has a "
                f"cached '{node_name}'; pass --reuse-deps to reuse it.",
                flush=True,
            )
        run_job(
            inc.job,
            subjobs_dir,
            force=True,
            data_root=data_root,
            render_figures=inc.figures,
        )
        produced = sorted(
            (d for d in subjobs_dir.glob(dir_glob) if (d / artifact_rel).exists()),
            key=lambda d: d.name,
        )
        if not produced:
            raise FileNotFoundError(
                f"sub-job '{inc.job.name}' did not persist '{artifact_rel}' under {subjobs_dir}. "
                f"Reference a figure-input node (with figures off) or an explicit materialize sink."
            )
        produced_dir = produced[-1]
        mode = "fresh"

    artifact_path = produced_dir / artifact_rel
    with artifact_path.open("rb") as handle:
        obj = pickle.load(handle)
    artifact_hash = f"sha256:{hash_file(artifact_path)}"
    # Record the sub-job's provenance dir relative to the output/ root: stable and
    # copy-pasteable for both fresh (nested) and reuse (prior composite) cases,
    # never a machine-specific absolute path.
    prov_path = produced_dir / "provenance"
    try:
        prov_rel = str(prov_path.relative_to(out_dir))
    except ValueError:
        prov_rel = str(prov_path)
    return obj, mode, prov_rel, artifact_hash


def run_job(
    job: Job,
    out_dir: Path,
    force: bool = False,
    data_root: Path | None = None,
    render_figures: bool = True,
    reuse_deps: bool = False,
) -> None:
    job_file = _job_file(job)
    job_source = job_file.read_text(encoding="utf-8")
    project_root = _project_root(job_file)
    job_hash_full = hash_string(job_source)
    job_hash = job_hash_full[:6]
    git_commit = get_git_commit()
    is_composite = bool(job.includes)

    # Dedup-skip for standalone jobs only. Composites ALWAYS run fresh (that's the
    # point of fresh-by-default), so they never serve a stale sub-job result.
    if not is_composite:
        pattern = f"{job.name}_{job_hash}_*"
        existing = list(out_dir.glob(pattern))
        if existing and not force:
            print(f"Skipping {job.name}: output already exists")
            return

    # Create timestamped folder: always unique when creating or force-rerunning
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_out_dir = out_dir / f"{job.name}_{job_hash}_{timestamp}"
    job_out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running {job.name} -> {job_out_dir.relative_to(out_dir)}")

    # Composites: resolve each included sub-job's referenced artifact (fresh run
    # via run_job in figures-as-materialize mode, nested under subjobs_output/, or
    # read from the standalone cache under --reuse-deps).
    include_results: dict[str, object] = {}
    includes_prov: list[dict[str, object]] = []
    if is_composite:
        include_results, includes_prov = _resolve_includes(
            job, out_dir, job_out_dir, reuse_deps, data_root
        )

    sink_ids = [
        sink.input.node_id if isinstance(sink, _FigureSink) else sink.node.node_id
        for sink in job.sinks
    ]
    ordered_ids = _toposort(job, sink_ids)
    results: dict[str, object] = {}

    for node_id in ordered_ids:
        node = job.dag[node_id]
        if node.fn is _subjob_artifact:
            results[node_id] = include_results[node_id]
            continue
        inputs = [results[input_handle.node_id] for input_handle in node.inputs]
        results[node_id] = node.fn(*inputs, **node.kwargs)

    for sink in job.sinks:
        if isinstance(sink, _FigureSink):
            result = results[sink.input.node_id]
            if render_figures:
                plot = sink.plot_class(name=sink.name)
                for target_name in sink.targets:
                    target = RENDER_TARGETS[target_name]
                    target(plot, result, job_out_dir)
                prov_name = sink.name
                rendered_targets = sink.targets
                fig_label = f"{sink.plot_class.__name__}\\ngit:{git_commit}"
            else:
                # Figures-as-materialize: persist the figure's input under its node
                # id so a composite can ref it by that name; emit no PDF.
                prov_name = sink.input.node_id
                with (job_out_dir / f"{prov_name}.pkl").open("wb") as handle:
                    pickle.dump(result, handle)
                rendered_targets = []
                fig_label = None
            # collect all dataset load nodes reachable by this sink (main + companions)
            ancestors = _ancestors(job, sink.input.node_id)
            dataset_nodes = [
                node
                for node_id, node in job.dag.items()
                if node_id in ancestors
                and node.fn.__name__ in {"_load_dataset", "_load_dataframe_raw"}
            ]
            dataset_paths: list[Path] = []
            dataset_hashes: list[str] = []
            for node in dataset_nodes:
                ds = node.kwargs.get("dataset")
                if ds is None:
                    continue
                p = _resolve_dataset_path(job_file, Path(ds.path), data_root=data_root)
                dataset_paths.append(p)
                try:
                    dataset_hashes.append(f"sha256:{hash_file(p)}")
                except Exception:
                    dataset_hashes.append("sha256:unreadable")

            # Build provenance record including lists of dataset paths/hashes
            # stringify dataset paths: prefer project-relative when possible, else absolute
            def _fmt(p: Path) -> str:
                try:
                    return str(p.relative_to(project_root))
                except Exception:
                    return str(p)

            record = build_prov_record(
                job_file=job_file.relative_to(project_root),
                job_file_hash=f"sha256:{job_hash_full}",
                dataset_paths=[_fmt(p) for p in dataset_paths],
                dataset_hashes=dataset_hashes,
                git_commit=git_commit,
                pipeline_steps=[
                    _format_step(job.dag[node_id])
                    for node_id in ordered_ids
                    if node_id in ancestors
                    and job.dag[node_id].fn.__name__ != "_load_dataset"
                    and job.dag[node_id].fn is not _subjob_artifact
                ],
                targets=rendered_targets,
                node_name=prov_name,
                figure_node_label=fig_label,
                includes=includes_prov,
            )
            save_prov(record, job_out_dir, prov_name)
            continue

        result = results[sink.node.node_id]
        with (job_out_dir / f"{sink.name}.pkl").open("wb") as handle:
            pickle.dump(result, handle)
        ancestors = _ancestors(job, sink.node.node_id)
        dataset_nodes = [
            node
            for node_id, node in job.dag.items()
            if node_id in ancestors
            and node.fn.__name__ in {"_load_dataset", "_load_dataframe_raw"}
        ]
        dataset_paths: list[Path] = []
        dataset_hashes: list[str] = []
        for node in dataset_nodes:
            ds = node.kwargs.get("dataset")
            if ds is None:
                continue
            p = _resolve_dataset_path(job_file, Path(ds.path), data_root=data_root)
            dataset_paths.append(p)
            try:
                dataset_hashes.append(f"sha256:{hash_file(p)}")
            except Exception:
                dataset_hashes.append("sha256:unreadable")

        def _fmt(p: Path) -> str:
            try:
                return str(p.relative_to(project_root))
            except Exception:
                return str(p)

        record = build_prov_record(
            job_file=job_file.relative_to(project_root),
            job_file_hash=f"sha256:{job_hash_full}",
            dataset_paths=[_fmt(p) for p in dataset_paths],
            dataset_hashes=dataset_hashes,
            git_commit=git_commit,
            pipeline_steps=[
                _format_step(job.dag[node_id])
                for node_id in ordered_ids
                if node_id in ancestors
                and job.dag[node_id].fn.__name__ != "_load_dataset"
                and job.dag[node_id].fn is not _subjob_artifact
            ],
            targets=[],
            node_name=sink.name,
            includes=includes_prov,
        )
        save_prov(record, job_out_dir, sink.name)
