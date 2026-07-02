from __future__ import annotations

import hashlib
import json
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


def build_prov_record(
    job_file: str | Path,
    job_file_hash: str,
    dataset_paths: list[str],
    dataset_hashes: list[str],
    git_commit: str,
    pipeline_steps: list[str],
    targets: list[str],
    node_name: str,
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
        "git_commit": git_commit,
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

    includes = record.get("includes") or []
    if includes:
        md_text = _mermaid_with_includes(record, node_name, list(includes))
    else:
        md_text = _mermaid_with_datasets(record, node_name)
    md_path.write_text(md_text, encoding="utf-8")


def _mermaid_with_datasets(record: dict[str, object], node_name: str) -> str:
    # Support multiple dataset paths (primary + companions)
    dataset_paths = record.get("dataset_paths") or (
        [record.get("dataset_path")] if record.get("dataset_path") else []
    )
    dataset_hashes = record.get("dataset_hashes") or (
        [record.get("dataset_hash")] if record.get("dataset_hash") else []
    )
    # Build mermaid nodes for each dataset
    dataset_nodes = []
    for p, h in zip(dataset_paths, dataset_hashes):
        name = Path(str(p)).name
        short = _short_hash(str(h))
        dataset_nodes.append((name, short))
    if not dataset_nodes:
        dataset_nodes = [("unknown", "xxxxxx")]

    steps = [str(step) for step in record.get("pipeline_steps", [])]
    git_commit = str(record["git_commit"])
    figure_node_label = record.get("figure_node_label")

    lines = ["graph LR"]
    # create dataset nodes A, B, C... then connect each to the first pipeline step
    node_letters = []
    for idx, (name, short) in enumerate(dataset_nodes):
        node_id = chr(ord("A") + idx)
        node_letters.append(node_id)
        lines.append(f"  {node_id}[{_mermaid_label(f'{name}\\n{short}')}]")

    previous_node = node_letters[0]
    for index, step in enumerate(steps, start=1):
        node_id = chr(ord("A") + len(dataset_nodes) - 1 + index)
        lines.append(f"  {previous_node} --> {node_id}[{_mermaid_label(step)}]")
        previous_node = node_id

    figure_node = chr(ord("A") + len(dataset_nodes) + len(steps))
    if isinstance(figure_node_label, str) and figure_node_label.strip():
        final_label = figure_node_label
    else:
        final_label = f"{node_name}\\ngit:{git_commit}"
    lines.append(f"  {previous_node} --> {figure_node}[{_mermaid_label(final_label)}]")

    return "\n".join(lines) + "\n"


def _mermaid_with_includes(
    record: dict[str, object], node_name: str, includes: list[dict[str, object]]
) -> str:
    """Composite graph: one opaque node per included sub-job feeding the first
    composite step. Sub-job internals are NOT expanded here — each include node
    carries a `click` link to that sub-job's own provenance graph."""
    steps = [str(step) for step in record.get("pipeline_steps", [])]
    git_commit = str(record["git_commit"])
    figure_node_label = record.get("figure_node_label")

    lines = ["graph LR"]
    click_lines: list[str] = []
    root_letters: list[str] = []
    for idx, inc in enumerate(includes):
        root_id = chr(ord("A") + idx)
        root_letters.append(root_id)
        alias = str(inc.get("alias", "sub"))
        ref_node = str(inc.get("node_name", ""))
        short = _short_hash(str(inc.get("artifact_hash", "")))
        lines.append(
            f"  {root_id}[{_mermaid_label(f'{alias}\\n{ref_node}\\n{short}')}]"
        )
        prov_ref = inc.get("subjob_prov_dir")
        if prov_ref:
            click_lines.append(f'  click {root_id} "{prov_ref}"')

    n_roots = len(root_letters)
    # Downstream chain: composite steps, then the figure node.
    chain: list[tuple[str, str]] = [
        (chr(ord("A") + n_roots + i), _mermaid_label(step))
        for i, step in enumerate(steps)
    ]
    figure_node = chr(ord("A") + n_roots + len(steps))
    if isinstance(figure_node_label, str) and figure_node_label.strip():
        final_label = figure_node_label
    else:
        final_label = f"{node_name}\\ngit:{git_commit}"
    chain.append((figure_node, _mermaid_label(final_label)))

    # Every root feeds the first downstream node; the first edge declares its label.
    first_id, first_label = chain[0]
    for i, root_id in enumerate(root_letters):
        if i == 0:
            lines.append(f"  {root_id} --> {first_id}[{first_label}]")
        else:
            lines.append(f"  {root_id} --> {first_id}")
    prev = first_id
    for nid, lbl in chain[1:]:
        lines.append(f"  {prev} --> {nid}[{lbl}]")
        prev = nid

    lines.extend(click_lines)
    return "\n".join(lines) + "\n"
