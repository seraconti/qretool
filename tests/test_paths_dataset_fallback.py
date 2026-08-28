"""`resolve_dataset_path` resolves against two roots, in a fixed order.

The dataset root (912days/, one level above the repo) is where the published read-only
pickles live. The repo-root fallback was added for tracked in-repo tables that are genuine
data inputs - `jobs/bench/results/size_table.csv`, which a figure job declares as a Dataset so
its sha256 enters provenance and the run identity.

Order is the load-bearing part: dataset root FIRST, so an external dataset can never be
shadowed by a same-named file that happens to exist inside the repo.
"""

from __future__ import annotations

import pytest

from quebra.core.paths import default_dataset_root, repo_root, resolve_dataset_path


def test_a_tracked_in_repo_table_resolves(in_repo):
    """The case that forced the fallback: bench tables live inside the repo."""
    resolved = resolve_dataset_path(
        "jobs/bench/results/size_table.csv", default_dataset_root()
    )
    assert resolved == (repo_root() / "jobs/bench/results/size_table.csv").resolve()
    assert resolved.exists()


def test_without_the_fallback_that_path_would_not_exist(in_repo):
    """Positive control: the dataset root really is the wrong place to look for it.

    Without this, the test above could pass because the dataset root happens to contain a
    copy, and the fallback would be untested.
    """
    assert not (
        default_dataset_root() / "jobs/bench/results/size_table.csv"
    ).exists(), (
        "the dataset root now contains a bench table; the fallback test is no longer "
        "exercising the fallback"
    )


def test_the_dataset_root_wins_when_both_exist(tmp_path):
    """Shadowing must be impossible: an external dataset takes precedence."""
    external = tmp_path / "jobs" / "bench" / "results"
    external.mkdir(parents=True)
    decoy = external / "size_table.csv"
    decoy.write_text("this is the external one\n")
    resolved = resolve_dataset_path("jobs/bench/results/size_table.csv", tmp_path)
    assert resolved == decoy.resolve(), (
        "the dataset root must be tried first, or --data-root stops meaning anything"
    )


def test_an_absolute_path_is_still_existence_checked(tmp_path, in_repo):
    missing = tmp_path / "nope.csv"
    with pytest.raises(FileNotFoundError, match="dataset not found"):
        resolve_dataset_path(missing, default_dataset_root())


def test_a_missing_relative_path_names_both_roots_it_tried(tmp_path):
    """The error has to be actionable: a reader must see where it looked."""
    with pytest.raises(FileNotFoundError) as excinfo:
        resolve_dataset_path("no/such/table.csv", tmp_path)
    message = str(excinfo.value)
    assert str(tmp_path) in message
    assert str(repo_root()) in message
