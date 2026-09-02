"""Make the repository's own trees importable to the test suite.

`quebra` itself is NOT provided here. It comes from the installed distribution, which is
the entire point of dropping `pythonpath` when `pyproject.toml` landed: if the suite could
import the package from `src/`, `pip install` would never actually be exercised and the
claim this phase exists to make would go unverified.

What this file does provide is the two trees that are deliberately NOT in the wheel:

  jobs/   the researcher's analysis configuration. It stays at the repository root so that
          `output/` is never written inside site-packages and so a study's dependencies
          (joblib) never become dependencies of the toolkit.
  tests/  the suite itself, which imports its own fixtures package.

pytest's default `prepend` import mode puts the directory containing the rootdir conftest
on `sys.path`, so simply existing here is enough. It is spelled out rather than left
implicit because a reader coming from the deleted `pytest.ini` will look for the setting
that replaced `pythonpath` and should find this explanation instead of a bare file.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent


@pytest.fixture
def in_repo(monkeypatch):
    """Run the test with the repository as the working directory.

    Needed because `repo_root()` and `resolve_data_root()` are now defined BY the working
    directory: `repo_root()` walks up looking for a project marker, and `resolve_data_root()`
    walks up looking for `quebra.toml`. That was the fix for an installed wheel reporting
    its repo root as `<venv>/lib/python3.13`, and it is correct - but it means a test that
    asserts something about THIS repository has to say which directory it means.

    Without it the suite passed only when pytest happened to be invoked from the repository.
    Measured: six tests failed under `cd /tmp && pytest <repo>/tests`, which is precisely
    the "unrelated working directory" the installability phase claims to support. The
    acceptance script pinned the cwd itself, so the gate hid the gap instead of catching it.

    `Path(__file__).parent` and not `Path.cwd()`: this file's location is stable, which is
    the whole point.

    FUTURE: worth revisiting whether `repo_root()` and `resolve_data_root()` should take the
    starting directory as an argument, defaulted to the cwd, instead of reading it from
    global state. Call sites that need a specific root could then say so, and this fixture
    would not be necessary. That is a signature change across ~17 call sites, so it is not
    a small edit.
    """
    monkeypatch.chdir(REPO_ROOT)
    return REPO_ROOT
