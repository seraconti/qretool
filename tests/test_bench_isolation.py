"""`jobs/bench/` is a study of the pipeline, never a dependency of it.

The rule changed shape in P4b and it is worth being precise about what it now protects,
because the old docstring claimed something that is no longer true.

**What moved.** `checks/` became `analyzers/checks/` and both packages became tracked. A
check is now a pipeline step, so the pipeline importing it is correct and the old
"jobs must not import checks" half of this file is gone.

**What still holds.** Nothing outside `jobs/bench/` may import it. It generates synthetic
data and calls the checks hundreds of thousands of times; a pipeline module reaching into
it would make a figure depend on a Monte Carlo study, and `jobs/bench/report.py` in particular
carries decision rules that must not silently become pipeline behaviour.

**What is NOT prevented, stated plainly.** The calibration figures DO depend on the bench -
they plot its tables. That dependency was moved onto the data plane rather than removed:
`jobs/active/check_calibration.py` declares `jobs/bench/results/*.csv` as datasets and loads
them with `job.load_df`, so their sha256 lands in the figure's provenance and in the run
identity. This test cannot and does not stop that. It stops the IMPORT edge, which is the
one that would bypass provenance entirely.

Every rule below carries a positive control, because an import-graph test that passes
because it found nothing to look at is worse than no test.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

# Every package that is part of the pipeline proper. `analyzers` includes `analyzers/checks`
# via rglob, which is deliberate: a check may use `analyzers.windows`, never the bench.
PIPELINE_PACKAGES = (
    "analyzers",
    "core",
    "jobs",
    "loaders",
    "panels",
    "plots",
    "schemas",
    "transforms",
)


def _called_name(func: ast.expr) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _imported_roots(path: Path) -> set[str]:
    """FULL DOTTED module names imported by one module, from its AST.

    Dotted, not top-level, and that is the whole point since the bench moved to
    `jobs/bench/`. Truncating at the first dot made `from jobs.bench.carve import ...`
    read as the root `jobs`, which is a legitimate import everywhere - so the isolation
    check matched nothing and passed vacuously on every package. A guard that cannot fail
    when the thing it guards is broken is not a guard.

    Parsed rather than executed: importing a job module would run its DAG wiring, and
    grepping for "import bench" would miss `importlib.import_module("jobs.bench.runner")` while
    matching it inside a docstring. Covers plain imports, `from` imports at any relative
    level, and the two dynamic forms.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                roots.add(node.module)
            # A RELATIVE import carries its package in `node.level`, not in `node.module`:
            # `from ..bench import runner` inside jobs/active/ has module="bench", level=2,
            # and resolves at runtime to jobs.bench.runner. Recording only `node.module`
            # yielded the bare "bench", which no longer matches "jobs.bench" now that the
            # package moved - so the guard admitted a real, working bench import. Measured:
            # planting that line in jobs/active/ left all 19 tests passing.
            if node.level:
                for alias in node.names:
                    roots.add(f"{'.' * node.level}{node.module or ''}.{alias.name}")
                roots.add(f"{'.' * node.level}{node.module or ''}")
        elif isinstance(node, ast.Call):
            if _called_name(node.func) in {"import_module", "__import__"} and node.args:
                target = node.args[0]
                if isinstance(target, ast.Constant) and isinstance(target.value, str):
                    roots.add(target.value)
    return roots


BENCH_PACKAGE = "jobs.bench"


def _imports_bench(path: Path) -> bool:
    """True when this module imports the bench package by any route.

    Matches `jobs.bench` exactly and any submodule of it, so `from jobs.bench.carve
    import carve_windows` is caught while a module merely importing `jobs.common` is not.
    """
    for name in _imported_roots(path):
        if name == BENCH_PACKAGE or name.startswith(BENCH_PACKAGE + "."):
            return True
        # Relative forms, recorded with their leading dots. Any relative import whose
        # first real segment is `bench` reaches the bench package from inside jobs/.
        bare = name.lstrip(".")
        if name.startswith(".") and (bare == "bench" or bare.startswith("bench.")):
            return True
    return False


def _python_files(*relative: str) -> list[Path]:
    found: list[Path] = []
    for part in relative:
        target = REPO / part
        if target.is_file():
            found.append(target)
        else:
            found.extend(sorted(target.rglob("*.py")))
    # The bench's own modules import each other; scanning them would flag the package
    # against itself. `jobs/` is scanned as a pipeline package and now CONTAINS the bench.
    return [
        p
        for p in found
        if "__pycache__" not in p.parts and "bench" not in p.relative_to(REPO).parts
    ]


@pytest.mark.parametrize("package", PIPELINE_PACKAGES)
def test_pipeline_packages_do_not_import_the_bench(package):
    files = _python_files(package)
    assert files, f"found no modules in {package}/ - the test would pass vacuously"
    offenders = [str(path.relative_to(REPO)) for path in files if _imports_bench(path)]
    assert not offenders, f"{package}/ must not import {BENCH_PACKAGE}:\n" + "\n".join(
        offenders
    )


def test_main_does_not_import_the_bench():
    assert not _imports_bench(REPO / "main.py")


def test_the_checks_package_is_where_the_pipeline_can_reach_it():
    """The move is the point of this increment; pin it so a revert is loud."""
    package = REPO / "analyzers" / "checks"
    assert package.is_dir(), "analyzers/checks/ is missing"
    assert (package / "battery.py").exists()
    assert not (REPO / "checks").exists(), (
        "the old top-level checks/ is back; imports now expect analyzers.checks"
    )


def test_checks_import_analyzers_but_never_the_bench():
    """Direction of the dependency: checks may use the carve, never the study of it."""
    files = _python_files("analyzers/checks")
    assert files, "found no check modules - the test would pass vacuously"
    for path in files:
        assert not _imports_bench(path), f"{path.name} imports the bench"


def test_the_bench_is_allowed_to_import_the_checks():
    """The permitted edge, asserted so nobody 'fixes' it in the wrong direction."""
    roots = _imported_roots(REPO / "jobs" / "bench" / "runner.py")
    assert any(name.startswith("analyzers") for name in roots), (
        "jobs/bench/runner.py should import analyzers.checks; if this fails the move is "
        "half-done"
    )


@pytest.mark.parametrize(
    "source, expected",
    [
        ("from jobs.bench.runner import main\n", "jobs.bench.runner"),
        ("import jobs.bench.runner\n", "jobs.bench.runner"),
        (
            "import importlib\nx = importlib.import_module('jobs.bench.runner')\n",
            "jobs.bench.runner",
        ),
        ("x = __import__('jobs.bench')\n", "jobs.bench"),
        ("from ..bench import runner\n", "bench"),
        (
            "def f():\n    from jobs.bench import runner\n    return runner\n",
            "jobs.bench",
        ),
        (
            "from analyzers.checks.battery import run_battery\n",
            "analyzers.checks.battery",
        ),
    ],
)
def test_import_detector_catches_every_form_it_claims_to(tmp_path, source, expected):
    """Positive control, one case per import form.

    The walk previously handled only `Import` and absolute `ImportFrom`, so it missed the
    `importlib.import_module` form its own docstring offered as the reason for parsing
    rather than grepping, and skipped relative imports entirely.
    """
    planted = tmp_path / "planted_job.py"
    planted.write_text(source)
    assert expected in _imported_roots(planted), f"missed: {source!r}"
