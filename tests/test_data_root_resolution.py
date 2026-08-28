"""The data-root chain: four mechanisms, fixed order, no `__file__` anywhere.

Oracle: SPEC 0002 R1.3.3, which fixes the order, and R1.3.4, which requires the failure to
name every location tried rather than guessing.

Why this matters more than it looks. The previous answer was `repo_root().parent`, computed
from where a `.py` file happened to sit. That is correct only inside a git checkout, and an
installed package has no repository to be the parent of. A silent relative fallback would
point an installed QUEBRA at whatever directory it was launched from, and the first symptom
would be a dataset hash that disagrees with a published provenance record.
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

    This repository's own `quebra.toml` says `data_root = ".."`. If that resolved against
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
    """R1.3.4. The failure has to be actionable, not just a stack trace."""
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


def test_a_nonexistent_explicit_root_falls_through_rather_than_being_returned(
    isolated, tmp_path, monkeypatch
):
    """A typo in --data-root must not become the answer.

    Each mechanism is checked for existence before it wins, so a bad explicit path falls
    through to the next mechanism instead of producing a root nothing lives under.
    """
    real = tmp_path / "real"
    real.mkdir()
    monkeypatch.setenv(QUEBRA_DATA_ROOT_ENV, str(real))
    assert resolve_data_root(tmp_path / "typo") == real.resolve()


def test_the_repository_resolves_through_its_own_quebra_toml(monkeypatch, in_repo):
    """The checkout keeps working, and through mechanism 3 rather than `__file__`."""
    monkeypatch.delenv(QUEBRA_DATA_ROOT_ENV, raising=False)
    # `in_repo` has already chdir'd here; repo_root() is only meaningful once it has.
    assert resolve_data_root() == in_repo.parent
