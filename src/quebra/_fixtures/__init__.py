"""Tiny synthetic records that ship inside the wheel.

They exist so that someone who has installed QUEBRA and has none of our data can still run
a real job: `pip install quebra`, point a `Dataset` at `fixture_path("ramsey_synthetic.csv")`,
and the whole pipeline runs. Nothing here is measured - every number comes from
`scripts/make_fixtures.py` with a fixed seed, which is what makes them redistributable.

These are NOT the datasets. Datasets live outside the package and are found through a data
root (`quebra.core.paths.resolve_data_root`). The two mechanisms are separate on purpose:
`importlib.resources` reaches inside the installed package and cannot reach outside it, and a
data root reaches outside and has no business inside.
"""

from __future__ import annotations

from contextlib import ExitStack
from importlib import resources
from pathlib import Path

__all__ = ["FIXTURES", "fixture_path"]

FIXTURES: tuple[str, ...] = ("ramsey_synthetic.csv",)

# Materialised fixtures are kept alive for the life of the process. `as_file` yields a real
# path, extracting to a temporary file when the package is zipped; closing the context would
# delete it while a Dataset still points at it. A normal wheel install is a directory, so in
# practice nothing is extracted and this holds a no-op.
_STACK = ExitStack()
_RESOLVED: dict[str, Path] = {}


def fixture_path(name: str) -> Path:
    """Filesystem path to a packaged fixture, valid for the life of the process.

    Reached through `importlib.resources`, never through `__file__` arithmetic: an installed
    package may not sit where the source tree did, and computing a path from `__file__` is
    the bug this project already fixed once in `repo_root()`.
    """
    if name not in FIXTURES:
        raise KeyError(f"unknown fixture {name!r}. Available: {', '.join(FIXTURES)}")
    if name not in _RESOLVED:
        resource = resources.files(__name__).joinpath(name)
        _RESOLVED[name] = Path(_STACK.enter_context(resources.as_file(resource)))
    return _RESOLVED[name]
