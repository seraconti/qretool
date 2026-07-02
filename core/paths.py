"""CWD-independent path anchors and resolvers.

Two distinct roots exist and must never be conflated:
  - repo root (qre_tool/): code, jobs, output/ — anchored off this file's location,
    the same pattern as provenance.get_git_commit.
  - dataset root (912days/ by default, --data-root overrides): the published
    read-only datasets live OUTSIDE the git repo, one level above it.

Every dataset path is resolved exactly once per run (core/runner.run_job) through
resolve_dataset_path, and that single resolved path feeds BOTH the loader and the
provenance hash — so the recorded hash always describes the file actually loaded.
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
    """Resolve a Dataset.path against dataset_root; the file must exist.

    Absolute paths pass through (but are existence-checked too — a typo must fail
    up front, before any output dir is created, not later at hash time).
    """
    raw = Path(path)
    resolved = (raw if raw.is_absolute() else dataset_root / raw).resolve()
    if not resolved.exists():
        raise FileNotFoundError(
            f"dataset not found: '{raw}' resolved to '{resolved}' "
            f"(dataset root: '{dataset_root}'). Relative dataset paths anchor on "
            "the dataset root — pass --data-root to override it."
        )
    return resolved


def resolve_repo_path(path: str | Path) -> Path:
    """Resolve a repo-root-relative path (e.g. an include's 'jobs/active/…')."""
    raw = Path(path)
    return (raw if raw.is_absolute() else repo_root() / raw).resolve()
