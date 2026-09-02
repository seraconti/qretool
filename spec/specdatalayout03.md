# SPEC 0003 - Data and outputs layout

**Phase:** 1B
**Budget:** 6-10 h
**Depends on:** SPEC 0002 complete and committed (`db61799`)
**Blocks:** SPEC 0004 (boundaries), documentation, any reviewer-runnable claim
**Reference:** `spec/quebraplan.md` §2, Phase 1B

Rationale lives in `spec/quebraplan.md`. This file contains requirements and acceptance
criteria only.

The governing constraint: a reviewer who has none of the private pickles must be able to
install the tool, run something real, and see exactly what they are missing and why.

---

## Preconditions

- P1. SPEC 0002 committed, working tree clean. Verified at `db61799`.
- P2. Behaviour baseline: `pytest --collect-only -q | tail -1` = **350 tests**. Any change to
  this number outside R3.6 must be explained, not absorbed.
- P3. `deptry .` currently exits **1**. R3.1 is what makes it exit 0; do it first so the rest
  of the phase has a green gate to work against.

---

## R3.0 - What SPEC 0002 already satisfied

Plan item **1B.3** (data root resolution order) is **done**. `resolve_data_root()` in
`src/quebra/core/paths.py` implements explicit argument, then `QUEBRA_DATA_ROOT`, then
`[tool.quebra] data_root` in a `quebra.toml` found by walking up from the cwd, then
`platformdirs`; `DataRootNotFound` lists every location tried. Do not re-open it. R3.4 below
is the separate, still-missing case: the root resolves but the *file* is absent.

**One amendment has since been made to the ORDER's semantics, not to the order.** Mechanisms 1
and 2 — the explicit argument and `QUEBRA_DATA_ROOT` — are demands rather than candidates: a
path they name that does not exist raises instead of falling through. See
`specinstallabity02.md` R1.3.3a for the reasoning. "Do not re-open it" above still stands for
the order itself and for the four mechanisms.

---

## R3.1 - Undeclared `joblib` (carried over from Phase 1) — **DONE 2026-08-29**

**R3.1.1** `jobs/bench/runner.py:33` does `from joblib import Parallel, delayed`. `joblib`
appears in no dependency list. It imports today only because the declared `scikit-learn>=1.5`
requires `joblib>=1.3.0`, so the bench's parallel backend rests on a transitive edge of an
unrelated package.

**R3.1.2** Declare it as an optional extra, not a runtime dependency:

```toml
[project.optional-dependencies]
bench = ["joblib>=1.3"]
```

The comment at `pyproject.toml:25` explaining joblib's absence from `dependencies` stays
correct and must be amended, not deleted: a study's parallel execution backend is still not a
mandatory dependency of the toolkit. What was wrong was leaving it undeclared *anywhere*.

**R3.1.3** Do not silence this with a `DEP003` entry in `[tool.deptry.per_rule_ignores]`. An
ignore records that we looked; an extra records where the dependency lives.

**Acceptance**
- `deptry .` exits 0. (Measured: adding the extra above and nothing else takes deptry from
  `Found 1 dependency issue` to `Success! No dependency issues found.`)
- `pip install -e ".[bench]"` resolves.
- `grep -n joblib pyproject.toml` shows it under `bench`, never under `dependencies`.

> **CHECKPOINT 3.1** - deptry green, packaged fixtures shipping. REACHED 2026-08-29.
> Suggested: `declares joblib as a bench extra and ships synthetic fixtures in the wheel`

---

## R3.2 - The three-way `data/` split — **DONE 2026-08-29**

**R3.2.1** Create the layout, outside `src/`, never packaged:

```
data/
  real_public/       committed if small; a fetch registry if not
  simulated/         generated; only seeds and manifests committed
  real_private/      gitignored entirely, except MANIFEST.toml
```

**R3.2.2** Seven job files reference `tool/datasets/6D2S/...`, a prefix that **does not
resolve under the current data root**: `jobs/active/t2star_q1_070423.py`,
`jobs/active/t2star_q1_100423.py`, `jobs/active/ramsey_q1_100423.py`,
`jobs/active/ramsey_2x2_q1_030723.py`, `jobs/active/km_poster_6d2s.py`,
`jobs/composite/independence_survey.py`, `jobs/bench/probe_unresolved.py`. These jobs cannot
run as committed. The 34 files they want are present at `backups/tool/datasets/6D2S/`, and
that copy is byte-identical to the three `FOR ZENODO/Supplementary/Sup fig {2,5,7}/`
copies (sha256 checked on `070423_6D2S_qubit1.pickle`: all four `99be492d…`).

Repoint the seven files at the new `data/real_private/` location as part of this requirement.
Do not leave a path that only works on one machine.

**R3.2.3** Moving datasets changes the identity of every job that loads them, because the
dataset hash is folded into the run identity. Expect a full re-run. Do not attempt to
preserve old identities.

**Acceptance**
- `grep -rn "tool/datasets" jobs/ src/ | wc -l` returns 0.
- Each of the seven jobs reaches at least `quebra inspect <job>` exit 0, and one T2* job and
  the survey run to completion.
- `git check-ignore data/real_private/<any-pickle>` succeeds; `data/real_private/MANIFEST.toml`
  is **not** ignored.

---

## R3.3 - `data/real_private/MANIFEST.toml` — **DONE 2026-08-29**

**R3.3.1** Committed. One entry per private file: filename, sha256, provenance (instrument,
device, date), embargo status.

**R3.3.2** Generated by a script, not hand-written, and the script is committed. The 34
6D2S pickles plus the calibration logs are too many to maintain by hand.

**R3.3.3** A test asserts the manifest is complete and current against whatever is present:
every file in `data/real_private/` has an entry, and every entry's sha256 matches. The test
**skips**, not fails, when `data/real_private/` is absent — a reviewer without the data must
still get a green suite.

**Acceptance**
- `MANIFEST.toml` committed and parseable.
- Corrupting one byte of one pickle makes the R3.3.3 test fail.
- Deleting `data/real_private/` makes it skip.

**Outcome.** 63 records copied (not moved) from `backups/tool/datasets/` and two `FOR ZENODO`
locations into `data/real_private/{6D2S,2x2,calibration_logs,companion}`, every one sha256-
verified after the copy, zero mismatches, sources left intact. `quebra.toml` `data_root`
moved `".."` -> `"."`. Ten files repointed; `grep -rn "tool/datasets\|FOR ZENODO"` returns 0.
Eight of nine jobs `inspect` clean - `jobs/bench/probe_unresolved.py` has no top-level `job`
and is a script, which is the pre-existing misplacement the Phase 0 review already logged.
`t2star_q1_070423` ran end to end under a new identity `43e8d4`, as R3.2.3 predicted. Of
64 files under `data/`, git can see exactly one: `MANIFEST.toml`.

**Still owed:** R3.2's acceptance asks that the survey run to completion. It was not run -
`INCLUDE_C3=True` over 415 cells is ~6.5 h. Verified instead that all 34 of its datasets and
the bench size table resolve under the new root. The full run is outstanding.

**Five tests changed**, each pinning behaviour this requirement deliberately moved, and each
rewritten to assert a property rather than a constant:
- `test_default_dataset_root_is_repo_parent` -> `..._follows_the_declared_root`, reading
  `quebra.toml` instead of hardcoding `repo_root().parent`.
- `test_the_repository_resolves_through_its_own_quebra_toml` likewise.
- `test_without_the_fallback_that_path_would_not_exist` now drives an explicit empty root
  via `tmp_path`. Its old form asserted that THIS checkout's dataset root lacked the bench
  table, which stopped being true when the root became the repo; the rewrite tests the
  fallback under every configuration instead of one.
- The two `test_resolve_dataset_path_missing_raises` cases were NOT changed - they matched
  `--data-root` in the message, and the fix was to restore that hint to `DataUnavailable`'s
  wrong-path branch, which had dropped it.

> **CHECKPOINT 3.2** - data split, paths repointed, manifest, DataUnavailable. REACHED
> 2026-08-29. Stop here.
> Suggested: `splits data/ by redistribution status and manifests the private records`

---

## R3.4 - `DataUnavailable`, not a stack trace — **DONE 2026-08-29** (pulled forward into CHECKPOINT 3.2 by your call)

**R3.4.1** A named exception raised when the data root resolves but the requested file is
absent. It must carry: the `Dataset.path` as written, every absolute location tried, and
whether the file appears in `MANIFEST.toml` — the distinction between "you are missing an
embargoed file" and "this path is wrong" is the whole value of the message.

**R3.4.2** It must name the simulated path as the way forward, so the message ends in an
action rather than an apology.

**R3.4.3** Raised from `resolve_dataset_path` in `src/quebra/core/paths.py`, which is the one
place that currently raises a bare `FileNotFoundError`.

**Acceptance**
- Requesting a manifested-but-absent file raises `DataUnavailable` naming the embargo.
- Requesting a genuinely wrong path raises `DataUnavailable` **not** claiming embargo.
- A test covers both branches without needing the private data.

---

## R3.5 - Outputs — **DONE 2026-08-29**

**R3.5.1** SETTLED 2026-08-29: the directory is `output/`, singular, which is what the code
already writes (`src/quebra/cli.py:32`). The plural was a spec-side invention; nine references
across `spec/quebraplan.md`, `spec/spec01hygiene.md` and `spec/specinstallabity02.md` were
corrected to match the code, and the redundant `outputs/` line was dropped from `.gitignore`.
No code change is owed here.

**R3.5.2** Run directories stay gitignored. For figures that appear in a paper, commit the
run's provenance record only — node ids, input hashes, artifact ids, software version,
timings, cache status. Kilobytes, and enough to audit a published figure without the
artifacts.

**R3.5.3** A documented command that promotes one run's provenance into the committed tree.
Manual copying will drift.

**Acceptance**
- A promoted record is committed; the artifacts beside it are not.
- The promote command is in the Makefile and in `docs/`.

MET. `scripts/promote_run.py` copies `provenance/` and nothing else into
`published/<job>_<identity>/` with a `PROMOTED.toml` naming where the figure appears.
Measured on a real run: 20 KB promoted against 4.5 MB of artifacts, zero `.pkl`/`.pdf`/`.png`
carried. `make promote RUN=… NOTE=…` in the Makefile, and a "Publishing a figure" section in
`docs/WRITING_A_JOB.md`.

A run made against a dirty tree is REFUSED unless `--allow-dirty` is passed, and the flag is
recorded as `tree_clean = false`: a record no commit reproduces is exactly the unauditable
claim this directory exists to prevent. Eight tests, all against synthetic runs under
`tmp_path`.

No promoted record is committed yet. One was created twice while testing and removed both
times, because its `note` would have asserted a publication that does not exist.

---

## R3.6 - Packaged fixtures — **DONE 2026-08-29** (out of checkpoint order: it is independent of the `data/` layout, which is blocked on a decision)

**R3.6.1** `src/quebra/_fixtures/` holding tiny synthetic records, shipped inside the wheel,
reached via `importlib.resources` — never via a path computed from `__file__`.

**R3.6.2** They must be small enough to commit without thought and synthetic enough to carry
no embargo.

**R3.6.3** This is the only requirement in the phase expected to change the P2 collect count.
Say by how much and why.

DECLARED: **350 -> 356, +6**, all in `tests/test_packaged_fixtures.py`. Every fixture is
reachable; an unknown name is refused; the path comes from the imported package rather than
the source tree; the fixture loads through the default normaliser; it runs the real T2*
analyzer; and it carries the step it claims to. No existing test changed.

**Acceptance**
- `pip install <wheel> && python -c "import quebra; ..."` reaches a fixture from a directory
  with no checkout, verified inside `scripts/acceptance.sh`.
- The sdist and wheel both contain `_fixtures/`.

> **CHECKPOINT 3.3** - outputs and the promotion path. REACHED 2026-08-29. Unavailability
> (R3.4) landed at CHECKPOINT 3.2 and fixtures (R3.6) at CHECKPOINT 3.1.
> Suggested: `adds a provenance promotion path so a published figure stays auditable`
> Suggested: `adds DataUnavailable, packaged fixtures, and a provenance promotion path`

---

## Done when

- `deptry .`, `ruff check`, `ruff format --check` and `pytest` all exit 0. **MET** - 373
  passed, 2 skipped, 375 collected (baseline was 350).
- `scripts/acceptance.sh` exits 0 and exercises a packaged fixture. **MET.**
- A machine with no `data/real_private/` runs the full suite green and gets `DataUnavailable`
  with an embargo note when it asks for a private record. **MET** - the manifest tests skip
  rather than fail, verified by pointing them at an absent tree.
- No path in `jobs/` or `src/` resolves only on one machine. **MET** - no `tool/datasets` or
  `FOR ZENODO` reference remains.

## Outstanding after this phase

**The survey has not been re-run.** R3.2's acceptance asks for it and it was not done:
`INCLUDE_C3=True` over 415 cells is roughly 6.5 hours. Its 34 datasets and the bench size
table were verified to resolve under the new root, and one T2* job ran end to end, but every
existing survey artifact was computed against the old dataset paths and therefore carries a
stale identity. Re-run before any survey figure is promoted.

## Not in this phase

- `mypy` and `lint-imports` (SPEC 0004). `make check` continues to exit non-zero until then.
- A public fetch registry for `real_public/`. Only the directory and the split are in scope.
- Re-opening data root resolution (R3.0).
