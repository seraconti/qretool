from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_string(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def get_git_commit() -> str:
    repo_root = Path(__file__).resolve().parent
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "nogit"
    commit = completed.stdout.strip()
    return commit or "nogit"


def is_tree_clean() -> bool:
    """True iff there are no uncommitted *tracked* changes.

    Uses `--untracked-files=no` so a stray untracked scratch file does not disable
    artifact reuse; the safety claim is only "no uncommitted tracked changes". Any
    error (no git, etc.) is conservatively reported as dirty so reuse never fires
    on an uncertain tree.
    """
    repo_root = Path(__file__).resolve().parent
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return completed.stdout.strip() == ""


def build_prov_record(
    job_file: str | Path,
    job_file_hash: str,
    dataset_paths: list[str],
    dataset_hashes: list[str],
    git_commit: str,
    pipeline_steps: list[str],
    targets: list[str],
    node_name: str,
    identity: str | None = None,
    tree_clean: bool = True,
    figure_node_label: str | None = None,
    includes: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    # keep backwards-compatible top-level fields for the primary dataset
    primary_path = dataset_paths[0] if dataset_paths else ""
    primary_hash = dataset_hashes[0] if dataset_hashes else ""
    return {
        "node_name": node_name,
        "job_file": str(job_file),
        "job_file_hash": job_file_hash,
        "dataset_path": str(primary_path),
        "dataset_hash": primary_hash,
        "dataset_paths": list(dataset_paths),
        "dataset_hashes": list(dataset_hashes),
        # content identity of the run (code + data + sub-job identities); folds
        # nothing time- or machine-specific. git_commit below is separate lineage.
        "identity": identity,
        "git_commit": git_commit,
        # whether the working tree was clean when this artifact was produced. An
        # artifact built on a dirty tree is never reuse-eligible: it does not
        # correspond to any commit's code (see _reuse_eligible_dir).
        "tree_clean": tree_clean,
        "pipeline_steps": list(pipeline_steps),
        "targets_rendered": list(targets),
        "figure_node_label": figure_node_label,
        # composite jobs: opaque upstream sub-jobs (see save_prov mermaid).
        "includes": list(includes) if includes else [],
    }


def _short_hash(value: str, length: int = 6) -> str:
    stripped = value.removeprefix("sha256:")
    return stripped[:length]


def _mermaid_label(text: str) -> str:
    escaped = text.replace("\n", "\\n").replace('"', '\\"')
    return f'"{escaped}"'


def save_prov(record: dict[str, object], out_dir: Path, node_name: str) -> None:
    # All provenance lives under a provenance/ subdir to keep the job output
    # dir uncluttered (figures and .pkl artifacts stay at the top level).
    prov_dir = out_dir / "provenance"
    prov_dir.mkdir(parents=True, exist_ok=True)

    json_path = prov_dir / f"{node_name}.prov.json"
    md_path = prov_dir / f"{node_name}.prov.md"

    json_path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    md_path.write_text(_mermaid_graph(record, node_name), encoding="utf-8")


def _mermaid_id_factory():
    """Allocate canonical, collision-safe mermaid node ids from human names
    (replacing the old throwaway A/B/C positional letters)."""
    used: dict[str, int] = {}

    def make(base: str) -> str:
        slug = re.sub(r"[^0-9A-Za-z]+", "_", base).strip("_").lower() or "n"
        used[slug] = used.get(slug, 0) + 1
        return slug if used[slug] == 1 else f"{slug}_{used[slug]}"

    return make


def _mermaid_graph(record: dict[str, object], node_name: str) -> str:
    """One DAG renderer for every job (standalone or composite).

    Source nodes — loaded datasets and/or references to included sub-jobs — feed
    the pipeline steps, which feed the sink node. Node ids are canonical slugs of
    the real names (not positional A/B/C letters); labels are human, with machine
    hashes shown only as short tags. An included reference is a first-class node
    that click-throughs to the sub-job's own provenance graph.
    """
    dataset_paths = record.get("dataset_paths") or (
        [record.get("dataset_path")] if record.get("dataset_path") else []
    )
    dataset_hashes = record.get("dataset_hashes") or (
        [record.get("dataset_hash")] if record.get("dataset_hash") else []
    )
    includes = record.get("includes") or []
    steps = [str(step) for step in record.get("pipeline_steps", [])]
    git_commit = str(record["git_commit"])  # always set by build_prov_record
    figure_node_label = record.get("figure_node_label")

    nid = _mermaid_id_factory()
    lines = ["graph LR"]
    click_lines: list[str] = []
    source_ids: list[str] = []

    for p, h in zip(dataset_paths, dataset_hashes, strict=True):
        name = Path(str(p)).name
        node_id = nid(f"ds_{name}")
        lines.append(
            f"  {node_id}[{_mermaid_label(f'{name}\\n{_short_hash(str(h))}')}]"
        )
        source_ids.append(node_id)

    for inc in includes:
        alias = str(inc.get("alias", "sub"))
        job_name = str(inc.get("job_name", ""))
        ref_node = str(inc.get("node_name", ""))
        short = _short_hash(str(inc.get("artifact_hash", "")))
        node_id = nid(f"ref_{alias}_{ref_node}")
        label = f"{alias}: {job_name}:{ref_node}\\n{short}"
        lines.append(f"  {node_id}[{_mermaid_label(label)}]")
        source_ids.append(node_id)
        prov_ref = inc.get("subjob_prov_dir")
        if prov_ref:
            # runner-generated relative path; strip any quote defensively so the
            # click line can't be broken by the URL
            safe_ref = str(prov_ref).replace('"', "")
            click_lines.append(f'  click {node_id} "{safe_ref}"')

    if not source_ids:
        node_id = nid("source")
        lines.append(f'  {node_id}["(no inputs)"]')
        source_ids.append(node_id)

    previous_ids = source_ids
    for step in steps:
        fn_name = step.split("(", 1)[0]
        node_id = nid(f"step_{fn_name}")
        lines.append(f"  {node_id}[{_mermaid_label(step)}]")
        for src in previous_ids:
            lines.append(f"  {src} --> {node_id}")
        previous_ids = [node_id]

    if isinstance(figure_node_label, str) and figure_node_label.strip():
        final_label = figure_node_label
    else:
        final_label = f"{node_name}\\ngit:{git_commit}"
    sink_id = nid(f"sink_{node_name}")
    lines.append(f"  {sink_id}[{_mermaid_label(final_label)}]")
    for src in previous_ids:
        lines.append(f"  {src} --> {sink_id}")

    lines.extend(click_lines)
    return "\n".join(lines) + "\n"
