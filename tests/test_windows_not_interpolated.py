"""The carve must never consume a resampled series.

A gap policy is meaningless on a uniform grid, and an interpolated point is not an
observation - a window built from one reports lifetime the instrument never measured.

This is a WHITELIST, not a blacklist. Asserting "no node called interpolate" would pass
for any future decimation or resampling step under a different name, and would be
vacuous on jobs that have no interpolate node at all. Asserting the windows node's
ancestors are a subset of a known-observed set fails on anything new until someone
deliberately adds it here.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from quebra.core.dataset import Dataset
from quebra.core.job import Job
from quebra.core.reference import LocalRef
from quebra.core.runner import _ancestors

REPO_ROOT = Path(__file__).resolve().parents[1]
JOBS_DIR = REPO_ROOT / "jobs" / "active"

# Nodes whose output is observed reads, filtered but never resampled.
OBSERVED_ANCESTORS = {
    "load",
    "load_df",
    "lookup_prior",
    "t2star_filter",
    "t2star_final_filter_stage",
    "t2star",
    "filter",
    "final_filter_stage",
    "fidelity_raw",
    "fidelity_interp",
    "windows",
    "fidelity_windows",
}


def _load_job(path: Path) -> Job:
    spec = importlib.util.spec_from_file_location(f"_jobmod_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    job = getattr(module, "job", None)
    if not isinstance(job, Job):
        raise AssertionError(f"{path} does not define a module-level `job`")
    return job


def _job_files() -> list[Path]:
    return sorted(p for p in JOBS_DIR.glob("*.py") if p.name != "__init__.py")


def _dataset_stems(job: Job) -> set[str]:
    """The file stems this job loads, which is the only suffix a step name may carry.

    A job that carves several datasets needs a distinct node name per dataset - all five
    of km_poster_6d2s's carves would otherwise be called `windows` and the provenance
    graph would not say which record each one came from. Allowing `{whitelisted}_{stem}`
    keeps that readable WITHOUT loosening the whitelist into a prefix match: a step called
    `filter_then_interpolate` still fails, because `then_interpolate` is not a dataset this
    job loads.
    """
    stems = set()
    for node in job.dag.values():
        dataset = node.kwargs.get("dataset")
        if dataset is not None and hasattr(dataset, "path"):
            stems.add(Path(dataset.path).stem)
    return stems


def _unexpected(job: Job, node_id: str) -> set[str]:
    """Ancestor step names that are not known-observed. ONE definition.

    The positive control below asserts against this function rather than re-deriving the
    set expression, so a control cannot keep passing while the real check drifts.
    """
    allowed_suffixes = _dataset_stems(job)
    unexpected = set()
    for ancestor in _ancestors(job, node_id):
        name = job.dag[ancestor].fn_name
        if name in OBSERVED_ANCESTORS:
            continue
        base, _, suffix = name.rpartition("_")
        while suffix and base:
            if base in OBSERVED_ANCESTORS and suffix in allowed_suffixes:
                break
            base, _, tail = base.rpartition("_")
            suffix = f"{tail}_{suffix}"
        else:
            unexpected.add(name)
    return unexpected


def _windows_nodes(job: Job) -> list[str]:
    # Key on node_id / fn_name, never fn.__name__: every closure-factory step in
    # quebra/recipes.py names its inner function `step`, so filter, interpolate, allan
    # and fidelity all report the same fn.__name__.
    # Substring, not equality: the fidelity carve is named `fidelity_windows`, and an
    # exact match silently skipped it - the test passed while that node was in fact
    # carving interpolated data. A matcher that can miss a node makes this whole file
    # vacuous, so it must over-match rather than under-match.
    return [
        node_id
        for node_id, node in job.dag.items()
        if "windows" in node.fn_name or "windows" in node_id
    ]


def test_there_are_jobs_to_check() -> None:
    # Guards against the whole suite passing vacuously if jobs/active empties out.
    assert _job_files(), f"no job files found in {JOBS_DIR}"


@pytest.mark.parametrize("job_file", _job_files(), ids=lambda p: p.stem)
def test_windows_ancestors_are_observed_reads(job_file: Path) -> None:
    job = _load_job(job_file)
    for node_id in _windows_nodes(job):
        unexpected = _unexpected(job, node_id)
        assert not unexpected, (
            f"{job_file.name}: the windows node {node_id!r} consumes {sorted(unexpected)}, "
            f"which is not a known-observed step. If that step does not resample the "
            f"series, add it to OBSERVED_ANCESTORS deliberately."
        )


def test_the_check_catches_a_resampled_input() -> None:
    """Positive control: without it, the whitelist could be vacuously true."""

    def _passthrough(*xs: object) -> object:
        return xs[0]

    job = Job("synthetic_bad_job")
    job.job_file = REPO_ROOT / "jobs" / "active" / "__init__.py"
    raw = job.step(_passthrough, name="filter")
    resampled = job.step(_passthrough, raw, name="interpolate")
    carved = job.step(_passthrough, resampled, name="windows")

    assert isinstance(carved, LocalRef)
    assert _unexpected(job, "windows") == {"interpolate"}


def test_the_check_catches_a_resampled_input_behind_a_dataset_suffix() -> None:
    """Positive control for the suffix rule: the widening must not open a hole.

    A resampling step named after a dataset the job really loads is the exact case the
    suffix rule could have let through, so it is asserted rather than assumed.
    """

    def _passthrough(*xs: object) -> object:
        return xs[0]

    stem = "100423_6D2S_qubit1"
    job = Job("synthetic_suffixed_bad_job")
    job.job_file = REPO_ROOT / "jobs" / "active" / "__init__.py"
    # Loaded, so `stem` really is an allowed suffix for this job - without this the
    # control would pass for the trivial reason that no suffix is allowed at all.
    loaded = job.load(Dataset(path=f"tool/datasets/6D2S/{stem}.pickle", qubit=1))
    filtered = job.step(_passthrough, loaded, name=f"filter_{stem}")
    resampled = job.step(_passthrough, filtered, name=f"interpolate_{stem}")
    job.step(_passthrough, resampled, name=f"windows_{stem}")

    assert _dataset_stems(job) == {stem}
    # `filter_<stem>` is accepted; `interpolate_<stem>` is not. The suffix rule must
    # carry the whitelist through, not replace it.
    assert _unexpected(job, f"windows_{stem}") == {f"interpolate_{stem}"}
