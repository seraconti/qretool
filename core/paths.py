"""CWD-independent path anchors and resolvers.

Two distinct roots exist and must never be conflated:
  - repo root (qre_tool/): code, jobs, output/ - anchored off this file's location,
    the same pattern as provenance.get_git_commit.
  - dataset root (912days/ by default, --data-root overrides): the published
    read-only datasets live OUTSIDE the git repo, one level above it.

Every dataset path is resolved exactly once per run (core/runner.run_job) through
resolve_dataset_path, and that single resolved path feeds BOTH the loader and the
provenance hash - so the recorded hash always describes the file actually loaded.
Resolution failures raise immediately (errors are raised, not swallowed); nothing
downstream may ever record a placeholder hash.
"""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    """The tool's repository root (the directory containing main.py)."""
    return Path(__file__).resolve().parents[1]


def default_dataset_root() -> Path:
    """Where relative dataset paths anchor: the repo's parent directory."""
    return repo_root().parent


def resolve_dataset_path(path: str | Path, dataset_root: Path) -> Path:
    """Resolve a Dataset.path against dataset_root, then the repo root; must exist.

    Absolute paths pass through (but are existence-checked too - a typo must fail
    up front, before any output dir is created, not later at hash time).

    The repo-root fallback exists for tracked in-repo tables that are genuine data inputs
    rather than code - `jobs/bench/results/size_table.csv` is the case that forced it. Anchoring
    those on the dataset root would look for them one directory ABOVE the repo, and writing
    'qre_tool/jobs/bench/results/…' instead would break the moment --data-root moved. The dataset
    root is still tried first, so an external dataset can never be shadowed by a same-named
    file inside the repo.
    """
    raw = Path(path)
    if raw.is_absolute():
        candidates = [raw.resolve()]
    else:
        candidates = [(dataset_root / raw).resolve(), (repo_root() / raw).resolve()]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    tried = " or ".join(f"'{c}'" for c in candidates)
    raise FileNotFoundError(
        f"dataset not found: '{raw}' resolved to {tried} "
        f"(dataset root: '{dataset_root}', repo root: '{repo_root()}'). Relative dataset "
        "paths anchor on the dataset root, falling back to the repo root for tracked "
        "in-repo tables - pass --data-root to override the former."
    )


def resolve_repo_path(path: str | Path) -> Path:
    """Resolve a repo-root-relative path (e.g. an include's 'jobs/active/…')."""
    raw = Path(path)
    return (raw if raw.is_absolute() else repo_root() / raw).resolve()
