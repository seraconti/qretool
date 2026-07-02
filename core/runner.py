from __future__ import annotations

import dataclasses
import pickle
import sys
from datetime import datetime
from pathlib import Path

from core.job import Job, _FigureSink, _DAGNode, _subjob_artifact
from core.paths import default_dataset_root, repo_root, resolve_dataset_path
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


def _format_step(node: _DAGNode) -> str:
    if node.kwargs:
        kwargs = ", ".join(f"{key}={value!r}" for key, value in node.kwargs.items())
        return f"{node.fn_name}({kwargs})"
    return node.fn_name


def _fmt_dataset_path(p: Path, dataset_root: Path) -> str:
    """Stringify a dataset path dataset_root-relative when possible, else absolute."""
    try:
        return str(p.relative_to(dataset_root))
    except Exception:
        return str(p)


def _dataset_load_nodes(job: Job) -> dict[str, _DAGNode]:
    """Load nodes (main + companions) that carry a Dataset kwarg, by node id."""
    return {
        node_id: node
        for node_id, node in job.dag.items()
        if node.fn.__name__ in {"_load_dataset", "_load_dataframe_raw"}
        and node.kwargs.get("dataset") is not None
    }


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


def _emit_prov(
    *,
    job: Job,
    root_node_id: str,
    ordered_ids: list[str],
    job_file: Path,
    repo: Path,
    dataset_root: Path,
    resolved_datasets: dict[str, Path],
    job_hash_full: str,
    git_commit: str,
    includes_prov: list[dict[str, object]],
    hash_cache: dict[Path, str],
    job_out_dir: Path,
    prov_name: str,
    targets: list[str],
    figure_node_label: str | None = None,
) -> None:
    """Build and save one sink's provenance record.

    Datasets reachable from `root_node_id` are looked up in `resolved_datasets`
    (the run's single resolution point — the same paths the loader opened, so the
    recorded hash describes the file actually loaded) and hashed at most once per
    run_job via `hash_cache`. Shared by the figure and materialize sinks so their
    two prov passes cannot drift apart. Only `prov_name`, `targets`, and
    `figure_node_label` differ between them. Hash failures propagate — a
    placeholder hash is never recorded.
    """
    ancestors = _ancestors(job, root_node_id)
    dataset_paths: list[Path] = []
    dataset_hashes: list[str] = []
    for node_id in job.dag:
        if node_id not in ancestors or node_id not in resolved_datasets:
            continue
        p = resolved_datasets[node_id]
        dataset_paths.append(p)
        if p not in hash_cache:
            hash_cache[p] = f"sha256:{hash_file(p)}"
        dataset_hashes.append(hash_cache[p])

    try:
        job_file_rendered: Path | str = job_file.relative_to(repo)
    except ValueError:
        job_file_rendered = job_file

    record = build_prov_record(
        job_file=job_file_rendered,
        job_file_hash=f"sha256:{job_hash_full}",
        dataset_paths=[_fmt_dataset_path(p, dataset_root) for p in dataset_paths],
        dataset_hashes=dataset_hashes,
        git_commit=git_commit,
        pipeline_steps=[
            _format_step(job.dag[node_id])
            for node_id in ordered_ids
            if node_id in ancestors
            and job.dag[node_id].fn.__name__ != "_load_dataset"
            and job.dag[node_id].fn is not _subjob_artifact
        ],
        targets=targets,
        node_name=prov_name,
        figure_node_label=figure_node_label,
        includes=includes_prov,
    )
    save_prov(record, job_out_dir, prov_name)


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
    repo = repo_root()
    dataset_root = Path(data_root).resolve() if data_root else default_dataset_root()
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

    # Single resolution point for every dataset path: this mapping feeds BOTH the
    # execution loop (loader) and _emit_prov (hashing), so the recorded hash always
    # describes the file actually loaded. Runs after the dedup-skip (skipped jobs
    # never touch datasets) and before mkdir (a missing dataset raises before any
    # output dir exists).
    resolved_datasets: dict[str, Path] = {
        node_id: resolve_dataset_path(node.kwargs["dataset"].path, dataset_root)
        for node_id, node in _dataset_load_nodes(job).items()
    }

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
        kwargs = node.kwargs
        if node_id in resolved_datasets:
            # Hand the loader a COPY of the Dataset carrying the resolved absolute
            # path; node.kwargs stays pristine so relative paths (not machine-
            # specific absolutes) render into pipeline_steps/Mermaid labels.
            kwargs = {
                **kwargs,
                "dataset": dataclasses.replace(
                    kwargs["dataset"], path=resolved_datasets[node_id]
                ),
            }
        results[node_id] = node.fn(*inputs, **kwargs)

    # One hash per distinct dataset file per run: sinks share this cache, so a
    # dataset reachable by several sinks is no longer re-hashed once per sink.
    dataset_hash_cache: dict[Path, str] = {}
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
            _emit_prov(
                job=job,
                root_node_id=sink.input.node_id,
                ordered_ids=ordered_ids,
                job_file=job_file,
                repo=repo,
                dataset_root=dataset_root,
                resolved_datasets=resolved_datasets,
                job_hash_full=job_hash_full,
                git_commit=git_commit,
                includes_prov=includes_prov,
                hash_cache=dataset_hash_cache,
                job_out_dir=job_out_dir,
                prov_name=prov_name,
                targets=rendered_targets,
                figure_node_label=fig_label,
            )
            continue

        result = results[sink.node.node_id]
        with (job_out_dir / f"{sink.name}.pkl").open("wb") as handle:
            pickle.dump(result, handle)
        _emit_prov(
            job=job,
            root_node_id=sink.node.node_id,
            ordered_ids=ordered_ids,
            job_file=job_file,
            repo=repo,
            dataset_root=dataset_root,
            resolved_datasets=resolved_datasets,
            job_hash_full=job_hash_full,
            git_commit=git_commit,
            includes_prov=includes_prov,
            hash_cache=dataset_hash_cache,
            job_out_dir=job_out_dir,
            prov_name=sink.name,
            targets=[],
        )
