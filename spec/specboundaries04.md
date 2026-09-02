# SPEC 0004 - Boundaries

**Phase:** 2
**Budget:** 3-6 h for R4.1-R4.4; R4.5 (first CI run) is budgeted separately and is human-only
**Depends on:** SPEC 0003 complete and committed (`1f58d37`)
**Blocks:** SPEC 0005 (identity), the `jobs/` reorganisation, `make check` ever exiting 0
**Reference:** `spec/quebraplan.md` §2, Phase 2

Rationale lives in `spec/quebraplan.md`. This file contains requirements and acceptance
criteria only.

The governing constraint: dependency direction becomes a build failure rather than a diagram.

---

## Preconditions

- P1. SPEC 0003 committed, working tree clean. Verified at `1f58d37`.
- P2. Behaviour baseline: **380 collected, 378 passed, 2 skipped**. The 375 -> 380 delta came
  from `1f58d37`, the review-fix commit (+74 lines in `test_load_dataset_contract.py`, +50 in
  `test_data_manifest.py`). Only R4.2's `_artifact_guard` move may change this number, and
  only if it does not.
- P3. `make check` exits non-zero on `types` and skips `arch`. Both are this phase.

---

## R4.0 - Measured starting position

Measured 2026-08-29 at `1f58d37`. Every number here was produced by running the tool, not by
reading the source.

**`import-linter` 2.13** is installed and `lint-imports` is on PATH (`dev` extra). No
`[tool.importlinter]` section exists, which is why `make arch` prints SKIPPED and exits 0.

**Under R4.1's layer order: 16 illegal imports in 6 rule violations.**

```
analyzers -> panels        10   (5 x _artifact_guard, 4 x _within_calibration_compute,
                                 1 x within_calibration)
analyzers -> plots          1   (fidelity -> plots.theme)
core      -> plots          2   (job -> plots.base, runner -> plots.targets)
core      -> loaders        1   (job -> loaders.registry)
core      -> schemas        1   (job -> schemas.ramsey_series)
schemas   -> transforms     1   (ramsey_series -> transforms.lookup_prior)
```

**`mypy src/quebra/core`: 10 errors in 2 files** — 7 in `runner.py`, 3 in `job.py`. By
category: 4 `arg-type`, 2 `attr-defined`, 2 `union-attr`, 1 `type-var`, 1 `import-untyped`.
**`mypy src/quebra` (whole package): 242 errors in 51 files** at `1f58d37` — the reason R4.3.3
forbids widening. Re-measured after this phase it reads **208 errors in 41 files**: the 10
under `core` are fixed, and the `[tool.mypy]` pandas override suppresses an `import-untyped`
in every module that imports pandas. Both figures are recorded because a reader running the
command today gets the second one.

**Three tool behaviours were measured because the phase depends on them:**

1. `exclude_type_checking_imports` is a **top-level** `[importlinter]` option. Placed inside a
   contract block it does nothing, and **unknown contract options are silently accepted** — a
   deliberately bogus option produced no complaint. Any option written into a contract block
   must be proven to change behaviour, not assumed.
2. Within a layer, `:` permits sibling imports and `|` forbids them. Measured:
   `core.identity -> provenance` is a violation under `|` and legal under `:`.
3. A stale `ignore_imports` entry **does** fail the run by default —
   `No matches for ignored import ...`, exit 1. R4.2.2's shrink-only claim rests on this and
   it holds.

---

## R4.1 - The layer contract — **DONE 2026-08-29**

**R4.1.1** Add `[tool.importlinter]` to `pyproject.toml`, `root_package = "quebra"`,
`exclude_type_checking_imports = True` at top level, and one `layers` contract, highest first:

```
quebra.cli
quebra.recipes
quebra.panels
quebra.plots
quebra.analyzers
quebra.transforms
quebra.schemas
quebra.loaders
quebra.core
quebra.provenance
```

**R4.1.2 This order declares the TARGET architecture, not today's code.** That is deliberate
and it is what `quebraplan.md` item 2.1 asks for: *"`core/job.py` imports `loaders`,
`transforms`, `plots.base` and root `provenance`, so the compute core sits above every layer
it is meant to sit beneath."* The four `core -> {plots, loaders, schemas}` imports are the
defect the phase exists to name. They are frozen as debt in R4.2, not relabelled as legal.

A reviewer proposed the opposite: promote `core.job` and `core.runner` to top layers on the
grounds that an orchestrator legitimately imports downward, which yields 12 violations instead
of 16. **Rejected**, for a measured reason: `core.job -> plots.base` makes
`import quebra.core.job` load matplotlib *and* plotly — 813 modules against 648 without it —
and `BasePlot` is used only in two annotations. Declaring that edge legal would make a real
and removable cost permanently invisible. R4.1.4 removes it instead.

**R4.1.3** `cli`, `recipes` and `provenance` are named explicitly. Without them they sit
outside every layer and are unconstrained in both directions — the gap that would have let
`provenance.py`'s hand-copied `_DECLARED_INPUT_FILL` colour be replaced by a `plots.theme` import with
no complaint, which is exactly the coupling this phase forbids.

**R4.1.4** Move `BasePlot` in `core/job.py` under `if TYPE_CHECKING:`. `from __future__ import
annotations` is already on line 1 and `BasePlot` appears only in `_FigureSink.plot_class` and `Job.figure`'s signature,
both annotation-only sites. **Verified before writing this requirement**: the suite stays at 378 passed
/ 2 skipped, `import quebra.core.job` no longer loads matplotlib or plotly, and the violation
count drops 16 -> 15.

**Acceptance**
- `lint-imports` reports the contract by name and, with R4.2's ignores, exits 0.
- `python -c "import sys, quebra.core.job; assert 'matplotlib' not in sys.modules"` passes.
- 380 collected, 378 passed, 2 skipped.

---

## R4.2 - Adopt with a ratchet, and pay down what is free — **DONE 2026-08-29**

**R4.2.1 Move `panels/_artifact_guard.py` to `core/_artifact_guard.py`.** It imports nothing
from `quebra` — a pure leaf sitting in the render package for no reason — and five analyzers
reach up into it. **Verified before writing this requirement**: `StaleArtifactGuard` is a
mixin, never itself pickled, and of **all 666** archived `.pkl` files under `output/`, **zero** contain the
string `_artifact_guard`, because pickle records the concrete class's module and resolves
bases from the live class definition. The move is a file move plus import-line edits in seven
modules (five analyzers, two panels) and breaks no artifact.

**R4.2.2** Freeze the remainder as `ignore_imports`. **MEASURED: 10 entries** — the projection
held exactly (16, less 1 for R4.1.4, less 5 for R4.2.1). Both mutation checks fired: deleting
`core.runner -> plots.targets` failed naming that exact import, and a fabricated stale entry
failed with `No matches for ignored import`.

**R4.2.3** Write `unmatched_ignore_imports_alerting = "error"` explicitly rather than relying
on the default, and raise the pin from `import-linter>=2.0` to `>=2.13`. The ratchet's central
claim must not depend on an upstream default under a floating lower bound.

**R4.2.4** Each entry carries a comment naming the phase that will remove it. These owners are
real, not decorative:
- `core -> plots/loaders/schemas` (3 remaining after R4.1.4): SPEC 0005, which splits `core`
  into a leaf types package and an orchestration package.
- `analyzers -> panels._within_calibration_compute` and `-> panels.within_calibration`: SPEC
  0005. Unlike `_artifact_guard`, `panels/_within_calibration_data.py` *defines*
  `WithinCalibrationPanelData`, so moving it **would** break archived panel pickles. That is
  the true reason these wait — not the claim in an earlier draft that identity records module
  paths, which is false: `Identity.code` is `hash_string(job_file.read_text())`, the job file
  only, and no library module path appears in any provenance record.
- `analyzers.fidelity -> plots.theme`: SPEC 0005.
- `schemas -> transforms.lookup_prior`: SPEC 0005.

**R4.2.5** The ratchet is shrink-only against *stale* entries only; nothing in the tool
prevents a future session adding an eleventh. That is a review obligation on the
`pyproject.toml` diff, and it is stated here rather than implied.

**Acceptance**
- `lint-imports` exits 0; entry count matches the measured post-move number.
- Deleting one entry produces a failure naming that exact import. Do this **once**, not once
  per entry, and say that you did one.
- 380 collected, 378 passed, 2 skipped — the `_artifact_guard` move must not change them.

> **CHECKPOINT 4.1** - contract enforced, the free debt paid, the rest frozen with real owners.
> Suggested: `turns dependency direction into a build failure and decouples the runtime from matplotlib`

---

## R4.3 - `make check` must mean something — **DONE 2026-08-29**

**R4.3.1** Remove `make arch`'s SKIPPED branch. Once R4.1 lands it is dead code that can only
hide a missing contract.

**R4.3.2** Fix the `mypy` errors under `src/quebra/core`, subject to three constraints.

COUNT CORRECTION: it was 10 before R4.2.1 and **11 after**, because moving `_artifact_guard.py`
into `core/` brought its own `arg-type` error with it — `dataclasses.fields(cls)` on a mixin
mypy cannot see as a dataclass. Adding `[tool.mypy] follow_imports = "silent"` then returned
it to 10 by confining the scan to `core`. All 10 are fixed; `mypy src/quebra/core` reports
`Success: no issues found in 9 source files`.

The `fn.__name__` landmine did NOT arise: mypy never flagged `job.py:249`, so no fix was
tempted toward `fn_name`. The constraint stays recorded because the next person to widen the
type gate will meet it.

Two helpers were added rather than suppressions: `runner._require` turns an unset
`ResolutionContext` run-directory field into a named error instead of a latent
`NoneType has no attribute glob`, and `runner._dataset_of` narrows a load node's `dataset`
kwarg and raises on a non-Dataset. `job.py:254` narrows by `isinstance` for the same reason.

- **`fn.__name__` classification is load-bearing and must not be replaced by `fn_name`.**
  Several errors are `Callable[..., object]` having no `__name__` (in `build_identity`, `Job.step`
  and the runner's node classification), and `_DAGNode` carries a `fn_name` field that looks like
  the clean fix. **Measured: it is not.** For a load node `fn.__name__` is `'_load_dataset'`
  and `fn_name` is `'load'`; `_LOAD_NODE_FN_NAMES` contains the former. Substituting would
  make `build_identity`'s dataset loop match nothing, leaving `Identity.data` empty — a
  reproducibility tool silently ceasing to hash its inputs. Use
  `getattr(node.fn, "__name__", "")` or a cast.
- Fixes are casts, `getattr`, and narrow annotations. **`_DAGNode.kwargs` and `_DAGNode.fn`
  stay untyped this phase** — typing the node value model is a design change belonging to
  SPEC 0005.
- No `# type: ignore` without a comment naming what it suppresses and why it cannot be fixed
  here.

**R4.3.3** Add a `[tool.mypy]` section so the gate is configured rather than inherited.

CORRECTED after review: this originally set `follow_imports = "silent"` and claimed that was
what scoped errors to `core`. It is not. Measured, `--follow-imports=normal` gives the same
`Success: no issues found in 9 source files`, so the option was a **no-op**. What actually
scopes the gate is mypy's default silencing of site-packages — `quebra` is an editable
install carrying no `py.typed`, so followed `quebra.*` modules are silenced regardless. The
option was **dropped** rather than kept with a corrected comment: it is global, it does
nothing today, and it would begin suppressing real errors the moment a `py.typed` is added or
`PKG` widens. What remains is `python_version` and a pandas `ignore_missing_imports` override,
which is preferred over adding `pandas-stubs` as a dependency this phase is not authorised to
add.

Do not widen `PKG` beyond `src/quebra/core`; the whole-package figure in R4.0 is why.

**R4.3.4** `runner.py` is the provenance emission path (`pipeline_steps` is derived from the
same `fn.__name__` classification). Acceptance must include: re-running one job produces a
`.prov.json` identical to the pre-change run modulo `git_commit` and timestamp. This is the
only thing protecting the phase's behaviour-neutrality claim.

PERFORMED 2026-08-29. `jobs/active/t2star_q1_070423.py` re-run against the changed `runner.py`
and diffed field-by-field against the pre-change run. Both records IDENTICAL once the seven
-character commit is normalised: `identity` stayed `43e8d45ff21b` and `dataset_hash` stayed
`99be492d5395`. The only raw difference was the commit embedded inside `figure_node_label`,
which is the excluded quantity.

**R4.3.5** After R4.3.1-R4.3.4, `make check` exits 0 — the first time in the project's history.

**Acceptance**
- `make check` exits 0; `mypy src/quebra/core` reports zero errors.
- The `.prov.json` comparison in R4.3.4 holds.
- 380 collected, 378 passed, 2 skipped.

---

## R4.4 - Converge CI and `make check` — **DONE 2026-08-29**

**R4.4.1** CI and the local gate currently disagree in three ways: `make lint` runs
`ruff format --check` and CI does not; `make check` omits `deps`; CI has no `mypy` step, so
R4.3.2's work would be a one-time cleanup with nothing stopping error 11. Replace CI's ad-hoc
steps with `make check` followed by `make deps`, so the two can never drift again and `mypy`
and `lint-imports` are enrolled for free.

**R4.4.2** SETTLED: `deptry .`, which is what SPEC 0003's acceptance used. `make deps` was
`deptry $(PKGROOT)` = `deptry src/quebra`; the two differ and the repo-wide form is the one
that catches `jobs/` importing an undeclared package, which is how R3.1's joblib defect was
found. `PKGROOT` is now unused and was removed.

**R4.4.3** Add `mypy` to `make check`'s CI path by virtue of R4.4.1; no separate step needed.

**Acceptance**
- `.github/workflows/ci.yml` invokes `make check` and `make deps` and nothing else that
  duplicates them.
- Both commands pass locally before the workflow is touched.

---

## R4.5 - Prove CI actually works (separate budget, human-only)

**R4.5.1** The workflow has **never executed once**. SPEC 0002 R1.4.2's acceptance ("passes on
a push") is still unverified, and the first real run of an untested two-interpreter matrix is
discovery work, not a TOML edit.

**R4.5.2** Confirm a green run whose log shows `make check` and `make deps` executing.

**R4.5.3** Prove the gate fails: push a deliberate layer violation on a scratch branch, watch
CI go red, revert.

**R4.5.4** This requires `git push`, which the agent cannot do (AGENTS.md §1 denies it at user
scope). Budget **1-3 h of human time**, separate from the 3-6 h above.

> **CHECKPOINT 4.2** - `make check` green locally, committable on its own.
> Suggested: `makes make check exit 0 and converges CI onto it`
>
> **CHECKPOINT 4.3** - CI proven green and proven to fail on a violation. Human-driven.

---

## Review outcome

Reviewed 2026-08-30, in two passes. The first reviewer covered 8 of 9 scoped files before its
session ended. The ninth was this spec — the author spot-checked three of its numbers, which
is not a review, so a SECOND reviewer was run over this file plus the fix layer answering the
first. It re-derived the pre-phase `242 errors in 51 files` without a checkout (via
`git archive`), and decomposed the drift to 208/41 exactly. Two IMPORTANT findings, both fixed:

- `[tool.mypy] follow_imports = "silent"` was a no-op carrying a comment that did not
  reproduce. Dropped; see R4.3.3.
- `job.build_identity` narrowed a load node's `dataset` with `isinstance(...) : continue`,
  which SKIPPED a non-Dataset and silently dropped that dataset's content hash from the
  identity. Before the type fix it raised `AttributeError`. Loud-to-silent, inside the
  identity computation, is the worst direction this project has; it now RAISES and names the
  node, matching `runner._dataset_of`.

Five MINOR findings, all fixed: `_dataset_of` typed to `_DAGNode` instead of an untyped
`getattr` fallback; `job_out_dir` added to the `_require` guards (unset, it would silently
DISABLE the self-read check rather than crash — the only one of the four that fails quietly);
the `[tool.deptry]` comment corrected now that the scan is repo-wide; `quebra._fixtures` added
to the contract, since it was the one top-level module left unconstrained by the very gap
R4.1.3 exists to close; and the CI comment corrected — the `real` marker keeps nothing out
because no test carries it, and the actual guard is the per-test `pytest.skip`.

The second pass found one IMPORTANT and five MINOR, all fixed: `make arch` now runs
`lint-imports --no-cache` and `make clean` removes `.import_linter_cache`, because that cache
can serve a graph built before a module moved and is then NEWER than the sources it
misdescribes — the reviewer saw a cached run report five violations naming the module this
phase deleted. The MINORs were a stale `400` where the figure is 666, a CI comment
attributing `test_artifact_guard.py`'s skip to absent private data when it skips on an absent
`output/` artifact, "ten modules" where seven were edited, R4.3.4's comparison being performed
but unrecorded, an author-asserted check now attributed to the second reviewer, and line
citations anchored to three different revisions, now replaced by symbol names.

Verified and unchanged: the ratchet is load-bearing in both directions, `import
quebra.core.job` loads no rendering stack, `_FigureSink` still builds its slots from string
annotations, the `_require`/`_dataset_of` guards convert no working path (`ResolutionContext`
is constructed at exactly one site, which sets all four fields), the `_artifact_guard` move is
byte-identical apart from the cast, and all 10 concrete subclasses really are dataclasses.

---

## Done when

- `make check` exits 0.
- `lint-imports` exits 0 with the measured number of owned, dated ignore entries.
- `import quebra.core.job` does not load matplotlib or plotly.
- `pytest` reports 380 collected, 378 passed, 2 skipped.
- CI has run green on a real push, with a demonstrated failure on an injected violation.

## Not in this phase

- **`acyclic_siblings` (plan item 2.3).** Explicitly conditioned on `jobs/` splitting into
  `validation/`, `survey/`, `comparison/`, which has not happened. The contract would assert a
  constraint over packages that do not exist.
- **Widening `mypy` past `core/`.** 242 errors in 51 files.
- **The remaining ~10 violations.** Owners are recorded in R4.2.4; all point at SPEC 0005.
- **`tests/test_bench_isolation.py` is NOT subsumed by this contract and must not be deleted
  as redundant.** It AST-walks the pipeline packages to assert nothing outside `jobs/bench/`
  imports the bench. `root_package = "quebra"` cannot see `jobs/` at all, so the contract
  enforces nothing there.
- **The unused marker set.** `slow`, `heavy`, `real` and `r` are declared in `pyproject.toml`
  but **no test carries any of them**, so `make test`'s fast selector equals the full suite by
  accident rather than design. Worth fixing; it is a test-architecture question (SPEC 0006),
  not a boundaries one. Recorded here so the accident is not mistaken for a decision.
