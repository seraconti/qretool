# SPEC 0002 - Installability

**Phase:** 1
**Budget:** 8-16 h
**Depends on:** SPEC 0001 complete and committed
**Blocks:** SPEC 0003 (data layout), boundaries, documentation
**Reference:** `spec/PLAN.md` §2, Phase 1

Rationale lives in `spec/PLAN.md`. This file contains requirements and acceptance criteria only.

The governing constraint: a reviewer runs the documented install steps on a machine that has
never seen this repository. Everything here exists to make that succeed.

---

## Preconditions

- P1. SPEC 0001 fully committed, working tree clean.
- P2. Record `pytest --collect-only -q | tail -1` before starting. This number is the behaviour
  baseline for the whole phase.

---

## R1.1 - Source layout

**R1.1.1** Move the package into `src/quebra/`. Current top-level packages
(`core`, `loaders`, `transforms`, `analyzers`, `plots`, `panels`, `schemas`, `jobs`) become
subpackages of `quebra`.

**R1.1.2** Use `git mv` for every move. No file may appear as add plus delete.

**R1.1.3** Every package directory must have an `__init__.py`, including
`core`, `loaders`, `plots`, `schemas`, `transforms`, and `jobs/composite`. Implicit namespace
packages must not be relied on anywhere.

**R1.1.4** Update imports to the `quebra.` prefix. Absolute imports only. Do not introduce
relative imports beyond a single level, and do not add `sys.path` manipulation anywhere. Any
existing `sys.path.insert` must be removed, not preserved.

**R1.1.5** `tests/` stays at the repository root, outside `src/`.

**R1.1.6** This checkpoint changes **no behaviour**. If a test outcome changes, stop and report
rather than fixing the test.

**Acceptance**
- `git status` shows only renames and import-line edits.
- `grep -rn "sys.path" src/ tests/ | wc -l` returns 0.
- `find src/quebra -type d -not -name "__pycache__" -exec test -f {}/__init__.py \; -print | wc -l`
  equals the directory count.
- `pytest --collect-only -q | tail -1` matches the P2 baseline exactly.

> **CHECKPOINT 1.1** - src layout, behaviour unchanged. Stop here.
> Suggested: `refactor: move package under src/quebra`

---

## R1.2 - Package metadata

**R1.2.1** Add `pyproject.toml` with PEP 621 metadata and the `hatchling` build backend.
Required fields: `name = "quebra"`, `version`, `description`, `readme`, `requires-python`,
`license`, `authors`, `dependencies`, `[project.urls]`.

**R1.2.2** `dependencies` must list every third-party import that appears in `src/quebra/`, with
lower bounds only. Derive the list from the imports; do not copy an existing requirements file
without verifying it.

**R1.2.3** `[project.optional-dependencies]` must define `dev` (ruff, mypy, pytest, pytest-cov,
hypothesis, import-linter, deptry) and `r` (empty for now, a placeholder for SPEC 0007).

**R1.2.4** Configure in the same file: `[tool.ruff]`, `[tool.pytest.ini_options]` with
`addopts = "--strict-markers"` and the four markers `slow`, `heavy`, `real`, `r`, and
`[tool.hatch.build.targets.wheel]` with `packages = ["src/quebra"]`.

**R1.2.5** Exclude from the wheel: `spec/`, `docs/adr/`, `tests/`, `data/`, `outputs/`.

**R1.2.6** Do not add an `[tool.importlinter]` section. That is SPEC 0004.

**Acceptance**
- `python -m build` succeeds and produces both an sdist and a wheel.
- `python -c "import zipfile,glob; z=zipfile.ZipFile(glob.glob('dist/*.whl')[0]); assert not [n for n in z.namelist() if n.startswith(('spec/','data/','outputs/','tests/'))]"`
  exits 0.
- `pytest --strict-markers -m "not slow"` runs without an unknown-marker error.

> **CHECKPOINT 1.2** - package builds. Stop here.
> Suggested: `build: add pyproject.toml with hatchling backend`

---

## R1.3 - Path resolution

**R1.3.1** Remove every assumption that the package runs from a git checkout. `core/paths.py`
currently resolves data relative to the repository root; this fails for an installed package.

**R1.3.2** Two mechanisms, kept separate and never conflated:

- **Packaged resources** - small files that ship inside the wheel. Reached only via
  `importlib.resources`. Create `src/quebra/_fixtures/` for these. Nothing large goes here.
- **Datasets** - live outside the package. Reached via a resolved data root.

**R1.3.3** Data root resolution order, first hit wins:
1. explicit argument passed by the caller
2. `QUEBRA_DATA_ROOT` environment variable
3. `[tool.quebra] data_root` in a `quebra.toml` at the current working directory or above
4. a `platformdirs` user data directory

**R1.3.4** If no root resolves, raise a named exception stating what was looked for and every
location tried. Never fall back to a relative guess.

**R1.3.5** The `--data-root ..` CLI flag must keep working, mapping to mechanism 1.

**R1.3.6** The three-way `data/` split and `MANIFEST.toml` are **not** in this phase. This phase
delivers root resolution only.

**Acceptance**
- `grep -rn "\.\./\|parent.parent\|__file__" src/quebra/core/paths.py` shows no repository-root
  arithmetic.
- From a directory outside the repository, in a venv with the wheel installed:
  `QUEBRA_DATA_ROOT=/tmp/qd python -c "import quebra; print(quebra.__version__)"` succeeds.
- With no root configured, the named exception is raised and its message lists all four
  locations tried.

> **CHECKPOINT 1.3** - path resolution. Stop here.
> Suggested: `fix(core): resolve data root without assuming a git checkout`

---

## R1.4 - Clean-environment acceptance

**R1.4.1** Write `scripts/acceptance.sh` performing, in a throwaway virtualenv outside the
repository: build the wheel, install it, import `quebra`, run
`pytest -m "not slow and not heavy and not real and not r"` against `tests/`, and print each
exit code.

**R1.4.2** Add `.github/workflows/ci.yml` running the fast selector on push and pull request,
on Python 3.11 and 3.12. One job only. No R job, no nightly job, no coverage gate.

**R1.4.3** CI must not have access to `data/real_private/`. Do not add a step that fetches it.

**R1.4.4** Update the README install section to the commands the acceptance script actually runs.
The README must not describe a step the script does not perform.

**Acceptance**
- `bash scripts/acceptance.sh` exits 0 from a clean checkout.
- The CI workflow passes on a push.
- The README install commands and `scripts/acceptance.sh` agree line for line.

> **CHECKPOINT 1.4** - installable and verified. Stop here.
> Suggested: `ci: add clean-environment acceptance and GitHub Actions workflow`

---

## Done when

`pip install .` succeeds in a fresh virtualenv outside the repository, `import quebra` works
from an unrelated working directory, the fast test suite passes there, and CI is green.

**Explicitly not in this phase:** the three-way `data/` split, `MANIFEST.toml`,
`import-linter`, `mypy` in CI, logical job IDs, job parameterisation, documentation, coverage
reporting. Each has its own spec. Do not start them.
