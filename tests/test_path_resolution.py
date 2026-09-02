"""Path resolution unification.

One dataset root feeds BOTH the loader and provenance hashing, resolved once per
run in core/runner.run_job; everything anchors CWD-independently. These tests run
a tiny real job through run_job from foreign CWDs and assert real sha256 digests
and byte-identical provenance.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import pytest

from quebra.core.dataset import Dataset
from quebra.core.job import Job
from quebra.core.paths import (
    default_dataset_root,
    repo_root,
    resolve_dataset_path,
    resolve_repo_path,
)
from quebra.core.runner import run_job
from quebra.provenance import hash_file

# --- pure units -------------------------------------------------------------


def test_repo_root_is_the_tool_repo(in_repo) -> None:
    root = repo_root()
    # The CLI lives inside the package; the repo root is the
    # directory holding pyproject.toml, not the one holding main.py.
    assert (root / "pyproject.toml").exists()


def test_default_dataset_root_follows_the_declared_root(in_repo) -> None:
    """Not `== repo_root().parent`: the datasets live inside the
    checkout under `data/` and `quebra.toml` now declares `data_root = "."`.

    Asserting against the declared value rather than a fixed relationship is the point -
    `default_dataset_root` delegates to the resolution chain, and a test that hardcodes one
    link's answer stops testing the chain."""
    import tomllib

    declared = tomllib.loads((repo_root() / "quebra.toml").read_text())["tool"][
        "quebra"
    ]["data_root"]
    assert default_dataset_root() == (repo_root() / declared).resolve()


def test_resolve_dataset_path_relative_joins_root(tmp_path: Path) -> None:
    f = tmp_path / "sub" / "d.csv"
    f.parent.mkdir()
    f.write_text("x\n1\n")
    assert resolve_dataset_path("sub/d.csv", tmp_path) == f.resolve()


def test_resolve_dataset_path_absolute_passthrough(tmp_path: Path) -> None:
    f = tmp_path / "d.csv"
    f.write_text("x\n1\n")
    # dataset_root is irrelevant for absolute paths, but existence still checked
    assert resolve_dataset_path(f, Path("/nonexistent")) == f.resolve()


@pytest.mark.parametrize("raw", ["missing.csv", "/absolute/missing.csv"])
def test_resolve_dataset_path_missing_raises(raw: str, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="--data-root"):
        resolve_dataset_path(raw, tmp_path)


def test_resolve_repo_path_is_cwd_independent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert resolve_repo_path("jobs/active") == repo_root() / "jobs" / "active"


# --- integration through run_job ---------------------------------------------


def _make_job(tmp_path: Path) -> tuple[Job, Path]:
    """A minimal real job: one companion load_df + materialize, tmp datasets."""
    data = tmp_path / "data.csv"
    data.write_text("a,b\n1,2\n3,4\n")
    job_py = tmp_path / "tiny_job.py"
    job_py.write_text("# synthetic job file for path-resolution tests\n")
    job = Job(name="tiny_path_job")
    node = job.load_df(Dataset(path="data.csv", schema=None))
    job.materialize(node, name="raw_df")
    job.job_file = job_py.resolve()
    return job, data


def test_run_job_resolves_loads_and_hashes_one_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job, data = _make_job(tmp_path)
    out = tmp_path / "out"
    foreign = tmp_path / "elsewhere"
    foreign.mkdir()
    monkeypatch.chdir(foreign)  # nothing may depend on the CWD

    run_job(job, out, force=True, data_root=tmp_path)

    run_dir = next(out.glob("tiny_path_job_*"))
    record = json.loads((run_dir / "provenance" / "raw_df.prov.json").read_text())
    # the hash is real and matches the file the loader opened
    assert record["dataset_hashes"] == [f"sha256:{hash_file(data)}"]
    # canonical rendering: dataset_root-relative, no absolute leak
    assert record["dataset_paths"] == ["data.csv"]
    # the artifact was really loaded/written
    with (run_dir / "raw_df.pkl").open("rb") as fh:
        df = pickle.load(fh)
    assert list(df.columns) == ["a", "b"]


def test_prov_content_is_identical_across_cwds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job, _ = _make_job(tmp_path)
    contents: list[str] = []
    for name in ("cwd_one", "cwd_two"):
        cwd = tmp_path / name
        cwd.mkdir()
        monkeypatch.chdir(cwd)
        out = tmp_path / f"out_{name}"
        run_job(job, out, force=True, data_root=tmp_path)
        run_dir = next(out.glob("tiny_path_job_*"))
        contents.append((run_dir / "provenance" / "raw_df.prov.json").read_text())
    assert contents[0] == contents[1]


def test_pipeline_steps_keep_relative_dataset_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job, _ = _make_job(tmp_path)
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out_steps"
    run_job(job, out, force=True, data_root=tmp_path)
    run_dir = next(out.glob("tiny_path_job_*"))
    record = json.loads((run_dir / "provenance" / "raw_df.prov.json").read_text())
    steps = str(record["pipeline_steps"])
    # the load_df node renders its kwargs verbatim: the RELATIVE path must appear,
    # the machine-specific absolute prefix must not
    assert "data.csv" in steps
    assert str(tmp_path) not in steps


def test_run_job_missing_dataset_raises_before_output_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_py = tmp_path / "tiny_job.py"
    job_py.write_text("# synthetic job file\n")
    job = Job(name="tiny_missing_job")
    node = job.load_df(Dataset(path="nope.csv", schema=None))
    job.materialize(node, name="raw_df")
    job.job_file = job_py.resolve()
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out_missing"
    with pytest.raises(FileNotFoundError, match="nope.csv"):
        run_job(job, out, force=True, data_root=tmp_path)
    assert not list(out.glob("tiny_missing_job_*"))  # no empty output dir left


def test_prov_byte_stable_across_repeated_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two back-to-back runs of the same job, same inputs, same git commit must
    produce prov records that are identical field-for-field - codifies the
    field-by-field diff done manually during the Inc 2.5 review."""
    job, _ = _make_job(tmp_path)
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out_repeat"

    records = []
    for _ in range(2):
        run_job(job, out, force=True, data_root=tmp_path)
        run_dir = sorted(out.glob("tiny_path_job_*"))[-1]
        record = json.loads((run_dir / "provenance" / "raw_df.prov.json").read_text())
        records.append(record)

    assert records[0] == records[1]


def test_run_all_isolates_one_bad_job(tmp_path: Path) -> None:
    """A dataset missing for one job in `run --all` must not abort the batch.

    the CLI's --all loop (quebra/cli.py: the `for job_file in job_files:` block) wraps
    each run_job call in try/except, prints a red ERROR line for the failing job,
    and continues to the next one. jobs/active is glob'd relative to the real
    repo root, so driving the actual CLI here would require the fake bad job to
    live inside the real repo tree; instead this test exercises the identical
    per-job try/except isolation contract directly against run_job, with a real
    good job and a real missing-dataset job side by side.
    """
    from quebra.cli import _module_from_path

    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    (tmp_path / "data.csv").write_text("a,b\n1,2\n")
    (jobs_dir / "ok_job.py").write_text(
        "from quebra.core.job import Job\n"
        "from quebra.core.dataset import Dataset\n"
        'job = Job(name="ok_job")\n'
        'node = job.load_df(Dataset(path="data.csv", schema=None))\n'
        'job.materialize(node, name="raw_df")\n'
    )
    (jobs_dir / "bad_job.py").write_text(
        "from quebra.core.job import Job\n"
        "from quebra.core.dataset import Dataset\n"
        'job = Job(name="bad_job")\n'
        'node = job.load_df(Dataset(path="does_not_exist.csv", schema=None))\n'
        'job.materialize(node, name="raw_df")\n'
    )

    def _load(job_file: Path):
        return _module_from_path(job_file).job

    out = tmp_path / "out"
    failures: list[tuple[Path, Exception]] = []
    for job_file in sorted(jobs_dir.glob("*.py")):
        try:
            run_job(_load(job_file), out, force=True, data_root=tmp_path)
        except Exception as exc:  # mirrors quebra/cli.py's per-job isolation
            failures.append((job_file, exc))

    assert [f.name for f, _ in failures] == ["bad_job.py"]
    assert list(out.glob("ok_job_*"))  # the good job still ran to completion
    assert not list(out.glob("bad_job_*"))  # the bad job left no output dir
