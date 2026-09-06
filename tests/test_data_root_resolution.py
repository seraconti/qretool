"""The data-root chain: two demands, two candidates, no `__file__` anywhere.

Oracle: the documented resolution order, and the requirement that a failure name every
location tried rather than guessing.

A DEMAND is a root somebody named for this run - `--data-root` or `QUEBRA_DATA_ROOT`. If it
does not exist, that is an error. A CANDIDATE is a place to look when nobody named one -
`quebra.toml`, then a user data directory - and the first existing hit wins.

Why the split matters more than it looks. `repo_root().parent` is correct only inside a git
checkout, and an installed package has no repository to be the parent of. And a named root
treated as a candidate is worse than either: it falls through to whatever comes next, so the
run analyses a different tree than the one requested and records THAT tree's hashes. The
first symptom is a dataset hash disagreeing with a published provenance record.
"""

from __future__ import annotations

import os

import pytest

from quebra.core.paths import (
    QUEBRA_DATA_ROOT_ENV,
    QUEBRA_TOML,
    DataRootNotFound,
    resolve_data_root,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """A cwd with no quebra.toml above it and no env var set."""
    monkeypatch.delenv(QUEBRA_DATA_ROOT_ENV, raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_an_explicit_argument_wins_over_everything(isolated, tmp_path, monkeypatch):
    """Mechanism 1. This is where `--data-root` arrives, so it must beat the environment."""
    wanted = tmp_path / "wanted"
    wanted.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setenv(QUEBRA_DATA_ROOT_ENV, str(other))
    assert resolve_data_root(wanted) == wanted.resolve()


def test_the_environment_wins_over_a_config_file(isolated, tmp_path, monkeypatch):
    """Mechanism 2 beats mechanism 3, which is what lets CI override a checked-in file."""
    env_root = tmp_path / "from_env"
    env_root.mkdir()
    toml_root = tmp_path / "from_toml"
    toml_root.mkdir()
    (isolated / QUEBRA_TOML).write_text(f'[tool.quebra]\ndata_root = "{toml_root}"\n')
    monkeypatch.setenv(QUEBRA_DATA_ROOT_ENV, str(env_root))
    assert resolve_data_root() == env_root.resolve()


def test_a_config_file_is_found_by_walking_UP_from_the_cwd(isolated, tmp_path):
    """Mechanism 3. Running from a subdirectory must still find the project's config."""
    root = tmp_path / "data"
    root.mkdir()
    (isolated / QUEBRA_TOML).write_text(f'[tool.quebra]\ndata_root = "{root}"\n')
    deep = isolated / "a" / "b" / "c"
    deep.mkdir(parents=True)
    os.chdir(deep)
    assert resolve_data_root() == root.resolve()


def test_a_relative_data_root_anchors_on_the_file_that_declares_it(isolated, tmp_path):
    """Not on the process cwd.

    This repository's own `quebra.toml` says `data_root`. If that resolved against
    the cwd, running a job from a subdirectory would silently point at a different tree.
    """
    root = tmp_path / "sibling"
    root.mkdir()
    (isolated / QUEBRA_TOML).write_text('[tool.quebra]\ndata_root = "sibling"\n')
    deep = isolated / "x" / "y"
    deep.mkdir(parents=True)
    os.chdir(deep)
    assert resolve_data_root() == root.resolve()


def test_when_nothing_resolves_it_raises_and_names_every_location(isolated):
    """The failure has to be actionable, not just a stack trace."""
    with pytest.raises(DataRootNotFound) as excinfo:
        resolve_data_root()
    message = str(excinfo.value)
    for expected in (
        "explicit argument",
        QUEBRA_DATA_ROOT_ENV,
        QUEBRA_TOML,
        "platformdirs",
    ):
        assert expected in message, f"failure message does not mention {expected}"


def test_a_nonexistent_explicit_root_raises_rather_than_falling_through(
    isolated, tmp_path, monkeypatch
):
    """A typo in --data-root must not become a DIFFERENT root.

    This test is the inversion of one that asserted the fall-through, and the reason is that
    "must not become the answer" has two readings. Falling through satisfies the weak one -
    the typo itself is never returned - while producing exactly the dangerous outcome: the run
    silently analyses whatever the next mechanism names. Here that is `real`, a tree the
    caller never asked for, whose dataset hashes would be recorded as if they were the
    requested ones.

    So a named root that does not exist is an error, even when a perfectly good root is
    available further down the chain. Especially then.
    """
    real = tmp_path / "real"
    real.mkdir()
    monkeypatch.setenv(QUEBRA_DATA_ROOT_ENV, str(real))
    with pytest.raises(DataRootNotFound, match="demand, not a candidate"):
        resolve_data_root(tmp_path / "typo")


def test_a_set_but_missing_env_root_raises_rather_than_falling_through(
    isolated, tmp_path
):
    """Same rule for the environment variable, which is also something somebody set.

    An inherited-and-stale `QUEBRA_DATA_ROOT` is the likelier version of this mistake: it is
    invisible at the call site, so the fall-through would be silent twice over.
    """
    (tmp_path / QUEBRA_TOML).write_text(f'[tool.quebra]\ndata_root = "{tmp_path}"\n')
    os.environ[QUEBRA_DATA_ROOT_ENV] = str(tmp_path / "gone")
    try:
        with pytest.raises(DataRootNotFound, match="not a directory"):
            resolve_data_root()
    finally:
        del os.environ[QUEBRA_DATA_ROOT_ENV]


def test_the_repository_resolves_through_its_own_quebra_toml(monkeypatch, in_repo):
    """The checkout keeps working, and through mechanism 3 rather than `__file__`.

    Asserts the checkout resolves to what its own `quebra.toml` SAYS, read from the file,
    rather than to a hardcoded relationship. That is the property mechanism 3 is supposed to
    have, and it is why the declared value can move without this test moving: pinning the
    literal would need rewriting every time it does.
    """
    import tomllib

    monkeypatch.delenv(QUEBRA_DATA_ROOT_ENV, raising=False)
    declared = tomllib.loads((in_repo / "quebra.toml").read_text())["tool"]["quebra"][
        "data_root"
    ]
    # `in_repo` has already chdir'd here; repo_root() is only meaningful once it has.
    assert resolve_data_root() == (in_repo / declared).resolve()
