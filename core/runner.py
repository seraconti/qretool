from __future__ import annotations

import dataclasses
import json
import pickle
import sys
from datetime import datetime
from pathlib import Path

from core.job import Job, _FigureSink, _DAGNode
from core.identity import content_hash
from core.paths import default_dataset_root, repo_root, resolve_dataset_path
from core.reference import (
    ArtifactRef,
    LocalRef,
    LocatedArtifact,
    ResolutionContext,
)
from provenance import (
    build_prov_record,
    get_git_commit,
    hash_file,
    is_tree_clean,
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
        for input_ref in node.inputs:
            # Only LocalRefs point at in-job nodes; ArtifactRefs are external roots.
            if isinstance(input_ref, LocalRef):
                visit(input_ref.node_id)
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
        for input_ref in job.dag[node_id].inputs:
            if isinstance(input_ref, LocalRef):
                visit(input_ref.node_id)

    visit(root_id)
    return reachable


def _load_node(job: Job, ordered_ids: list[str]) -> _DAGNode:
    for node_id in ordered_ids:
        node = job.dag[node_id]
        if node.fn.__name__ == "_load_dataset":
            return node
    raise ValueError("Job does not contain a load node")


def _read_prov_reuse_fields(
    run_dir: Path,
) -> tuple[str | None, str | None, bool]:
    """Read (identity, git_commit, tree_clean_at_build) from any prov record in
    `run_dir` (all sinks of a run share them), or (None, None, False) if
    unreadable. Missing tree_clean (older records) reads as False → not reusable."""
    prov_files = sorted((run_dir / "provenance").glob("*.prov.json"))
    if not prov_files:
        return None, None, False
    try:
        record = json.loads(prov_files[0].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None, False
    return (
        record.get("identity"),
        record.get("git_commit"),
        bool(record.get("tree_clean", False)),
    )


def _reuse_eligible_dir(
    candidates: list[Path], identity: str, git_commit: str, tree_clean: bool
) -> Path | None:
    """The newest candidate run reusable under the gate, else None (→ re-run fresh).

    Reuse requires ALL of: matching content identity, matching git commit, the
    consumer's tree clean NOW, and the artifact PRODUCED on a clean tree. Commit +
    clean-tree (both ends) stand in for a dependency hash on imported/shared code
    (which the identity's code component does not capture): they guarantee the
    artifact was built from — and is being reused under — exactly the committed
    code. Any mismatch re-runs — commit-safe, not content-safe against code edits.
    `candidates` is sorted oldest→newest.
    """
    if not tree_clean:
        return None
    for run_dir in reversed(candidates):
        rec_identity, rec_commit, rec_tree_clean = _read_prov_reuse_fields(run_dir)
        if rec_identity == identity and rec_commit == git_commit and rec_tree_clean:
            return run_dir
    return None


def _locate_artifact(ref: ArtifactRef, context: ResolutionContext) -> LocatedArtifact:
    """The identity-keyed dir-glob locator (the strategy injected on the context).

    Finds the included sub-job's `{node_name}.pkl` — under --reuse-deps from a
    prior standalone or nested run whose identity AND commit match and whose tree
    is clean, otherwise by fresh-running the sub-job in figures-as-materialize mode
    nested under this composite's subjobs_output/ — loads it, and returns the value
    plus provenance facts. The strategy is injected on the context, so it can be
    swapped without changing ArtifactRef.
    """
    inc = ref.included
    node_name = ref.node_name
    out_dir = context.out_dir
    subjobs_dir = context.subjobs_dir
    job_out_dir = context.job_out_dir

    # Identity-keyed: the sub-job's content identity (memoized on the job) names its
    # output dir, so reuse keys on what the run IS, not merely its source.
    sub_identity = inc.job.build_identity(context.dataset_root).digest
    identity_short = sub_identity[:6]
    artifact_rel = f"{node_name}.pkl"
    dir_glob = f"{inc.job.name}_{identity_short}_*"

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
    eligible = (
        _reuse_eligible_dir(
            cached, sub_identity, context.git_commit, context.tree_clean
        )
        if context.reuse_deps
        else None
    )
    if eligible is not None:
        produced_dir = eligible
        mode = "cached"
    else:
        if cached and context.reuse_deps:
            print(
                f"[NOTE] '{inc.job.name}' has a cached '{node_name}' but it is not "
                f"reuse-eligible (identity/commit/clean-tree); re-running.",
                flush=True,
            )
        elif cached:
            print(
                f"[NOTE] composite is re-running sub-job '{inc.job.name}' which has a "
                f"cached '{node_name}'; pass --reuse-deps to reuse a cache that "
                f"matches the current identity + commit on a clean tree.",
                flush=True,
            )
        run_job(
            inc.job,
            subjobs_dir,
            force=True,
            data_root=context.data_root,
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
    return LocatedArtifact(
        value=obj, artifact_hash=artifact_hash, mode=mode, prov_dir_rel=prov_rel
    )


def _collect_includes_prov(
    job: Job, ordered_ids: list[str], context: ResolutionContext
) -> list[dict[str, object]]:
    """One prov entry per distinct ArtifactRef consumed, in first-seen toposort
    order (deterministic, independent of resolution timing)."""
    includes_prov: list[dict[str, object]] = []
    seen: set[int] = set()
    for node_id in ordered_ids:
        for input_ref in job.dag[node_id].inputs:
            if not isinstance(input_ref, ArtifactRef) or id(input_ref) in seen:
                continue
            seen.add(id(input_ref))
            located = context.artifacts[id(input_ref)]
            includes_prov.append(
                {
                    "alias": input_ref.included.alias,
                    "job_name": input_ref.included.job.name,
                    "node_name": input_ref.node_name,
                    "artifact_hash": located.artifact_hash,
                    "mode": located.mode,
                    "subjob_prov_dir": located.prov_dir_rel,
                }
            )
    return includes_prov


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
    identity: str,
    tree_clean: bool,
    includes_prov: list[dict[str, object]],
    job_out_dir: Path,
    prov_name: str,
    targets: list[str],
    figure_node_label: str | None = None,
) -> None:
    """Build and save one sink's provenance record.

    Datasets reachable from `root_node_id` are looked up in `resolved_datasets`
    (the run's single resolution point — the same paths the loader opened, so the
    recorded hash describes the file actually loaded) and hashed via `content_hash`
    (memoized per process). Shared by the figure and materialize sinks so their two
    prov passes cannot drift apart. Only `prov_name`, `targets`, and
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
        dataset_hashes.append(f"sha256:{content_hash(p)}")

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
        identity=identity,
        tree_clean=tree_clean,
        pipeline_steps=[
            _format_step(job.dag[node_id])
            for node_id in ordered_ids
            if node_id in ancestors and job.dag[node_id].fn.__name__ != "_load_dataset"
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
    job.job_file = job_file  # ensure set for code_hash()/build_identity()
    repo = repo_root()
    dataset_root = Path(data_root).resolve() if data_root else default_dataset_root()
    job_hash_full = job.code_hash()  # recorded as job_file_hash in prov
    git_commit = get_git_commit()
    tree_clean = is_tree_clean()
    is_composite = bool(job.includes)

    # Resolve every dataset path once (fail-fast on a missing file, before any
    # output dir exists) — this mapping feeds BOTH the execution loop (loader) and
    # _emit_prov (hashing), so the recorded hash describes the file actually loaded.
    resolved_datasets: dict[str, Path] = {
        node_id: resolve_dataset_path(node.kwargs["dataset"].path, dataset_root)
        for node_id, node in _dataset_load_nodes(job).items()
    }

    # Content identity (code + dataset content + sub-job identities): names the
    # output dir and keys reuse. build_identity is a function of static job
    # structure only, so a missing dataset raises here, before mkdir.
    identity = job.build_identity(dataset_root).digest
    identity_short = identity[:6]

    # Reuse gate (standalone jobs; composites always run fresh). Skip only when a
    # prior run has the SAME identity AND the SAME commit AND the tree is clean —
    # any mismatch (edited shared code → commit differs; dirty tree) re-runs fresh.
    if not is_composite and not force:
        candidates = sorted(
            out_dir.glob(f"{job.name}_{identity_short}_*"), key=lambda d: d.name
        )
        if _reuse_eligible_dir(candidates, identity, git_commit, tree_clean):
            print(
                f"Skipping {job.name}: reusable output exists "
                f"(identity + commit match, clean tree)"
            )
            return

    # Create timestamped folder: always unique when creating or force-rerunning
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_out_dir = out_dir / f"{job.name}_{identity_short}_{timestamp}"
    job_out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running {job.name} -> {job_out_dir.relative_to(out_dir)}")

    sink_ids = [
        sink.input.node_id if isinstance(sink, _FigureSink) else sink.node.node_id
        for sink in job.sinks
    ]
    ordered_ids = _toposort(job, sink_ids)
    results: dict[str, object] = {}

    # One context resolves every input the same way: LocalRefs read `results`,
    # ArtifactRefs (composite → included sub-job) run/locate via the injected
    # locator. A referenced sub-job runs lazily, at most once per ref (memoized).
    context = ResolutionContext(
        results=results,
        locate=_locate_artifact,
        out_dir=out_dir,
        subjobs_dir=job_out_dir / "subjobs_output",
        job_out_dir=job_out_dir,
        reuse_deps=reuse_deps,
        data_root=data_root,
        dataset_root=dataset_root,
        git_commit=git_commit,
        tree_clean=tree_clean,
    )

    for node_id in ordered_ids:
        node = job.dag[node_id]
        inputs = [input_ref.resolve(context) for input_ref in node.inputs]
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

    includes_prov = _collect_includes_prov(job, ordered_ids, context)

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
                identity=identity,
                tree_clean=tree_clean,
                includes_prov=includes_prov,
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
            identity=identity,
            tree_clean=tree_clean,
            includes_prov=includes_prov,
            job_out_dir=job_out_dir,
            prov_name=sink.name,
            targets=[],
        )
