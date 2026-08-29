"""`resolve_dataset_path` resolves against two roots, in a fixed order.

The dataset root is wherever `--data-root` / `QUEBRA_DATA_ROOT` / `quebra.toml` point; the
repo-root fallback was added for tracked in-repo tables that are genuine data inputs -
`jobs/bench/results/size_table.csv`, which a figure job declares as a Dataset so its sha256
enters provenance and the run identity.

SPEC 0003 moved this checkout's data under `data/`, so its declared root is now the repo
itself and the two candidates coincide HERE. That is a property of one configuration, not of
the resolver, which is why the control below drives an explicit root rather than reading this
checkout's.

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


def test_without_the_fallback_that_path_would_not_exist(tmp_path, in_repo):
    """Positive control: with a dataset root that lacks the file, only the fallback finds it.

    Driven from an explicit empty root rather than `default_dataset_root()`. The earlier
    version asserted that THIS checkout's dataset root lacked the table, which held only
    while the root was the repo's parent; SPEC 0003 made it the repo itself, and the control
    started failing for a configuration reason rather than a resolver one. Using `tmp_path`
    tests the fallback itself, under every configuration.
    """
    assert not (tmp_path / "jobs/bench/results/size_table.csv").exists()
    resolved = resolve_dataset_path("jobs/bench/results/size_table.csv", tmp_path)
    assert resolved == (repo_root() / "jobs/bench/results/size_table.csv").resolve(), (
        "the repo-root fallback did not fire for a table absent from the dataset root"
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
