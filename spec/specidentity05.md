# SPEC 0005 - Identity before parameterisation

**Phase:** 3
**Budget:** 12-24 h in `quebraplan.md`; see R5.0's correction — the evidence moves it
**Depends on:** SPEC 0004 complete and committed
**Blocks:** SPEC 0006 (test architecture), Phase 3C (opening issues, tagging v0.2.0)
**Reference:** `spec/quebraplan.md` §2, Phase 3

Rationale lives in `spec/quebraplan.md`. This file contains requirements and acceptance
criteria only.

The governing constraint, from the plan and still correct: **parameterise nothing until
identity is right.** Collapsing job files while identity is broken multiplies the breakage.

---

## Preconditions

- P1. SPEC 0004 committed, working tree clean.
- P2. Behaviour baseline: `pytest --collect-only -q | tail -1` = **380 tests**.
- P3. `make check` and `make deps` both exit 0.
- P4. ~~CI has run green at least once.~~ **WITHDRAWN.** CI runs exactly `make check` and
  `make deps`, which P3 already requires locally; it adds a 3.11/3.12 matrix and a
  non-editable install, neither a plausible source of divergence for a hash of file bytes.
  Gating the phase on a human `git push` for no technical reason is an invented blocker. The
  real risk it was groping at — that identity might not be install-independent — is a testable
  property and is now an acceptance criterion on R5.1 instead.

---

## R5.0 - Two premises in the plan do not survive contact with the code

Measured 2026-08-30 at the tip of SPEC 0004. Both corrections change what this phase should
do, so they are stated before the requirements rather than in a footnote.

### R5.0.1 The hash is too NARROW, not too broad. Item 3.1 is inverted.

`quebraplan.md` 3.1 says *"editing `analyzers/km.py` already invalidates all 63 jobs"* and
concludes the hash must be narrowed. **Measured, the opposite is true.** `Job.job_code_hash` is
`hash_string(job_file.read_text())` — the job file and nothing else. Appending a line to
`src/quebra/analyzers/t2star.py` and rebuilding the identity of
`jobs/active/t2star_q1_070423.py`:

```
before analyzer edit: 43e8d45ff21badc2
after  analyzer edit: 43e8d45ff21badc2      identity moved: False
```

(First 16 hex of a 64-hex sha256. Run directories use 6, `specboundaries04.md` quotes 12; the
width is stated so the probe is reproducible.)

So the analyzer that produced the numbers can change completely while the identity asserts
nothing did. That is an over-claim in the artifact this whole project exists to make
trustworthy, and it is worse than the blast radius the plan feared.

**What currently saves cache CORRECTNESS is not identity.** `runner._reusable_run` requires
`rec_identity == identity` **and** `rec_commit == git_commit` **and** `rec_tree_clean`. An
analyzer edit dirties the tree, so reuse is refused; once committed, the commit differs, so
reuse is refused. Caching is therefore sound today. What is not sound is the *claim*: two runs
over different analyzer code share an identity digest, share a run-directory prefix
`output/<job>_<identity6>_...`, and a promoted `PROMOTED.toml` cannot distinguish them.

**The plan's destination is still right; only its diagnosis was wrong.** Hashing all of
`src/quebra/` would fix the over-claim and recreate exactly the blast radius 3.1 feared.
Hashing *the sources of the steps a job actually calls* fixes the over-claim and keeps the
radius narrow. R5.1 does that.

### R5.0.2 There are 20 job files, not 63.

Item 3.3 says *"collapse 63 near-identical jobs"*. Measured: **20** non-`__init__` files —
9 in `jobs/active/`, 3 in `jobs/composite/`, 8 in `jobs/bench/`. Only 4 declare a threshold
ladder and 3 declare carve parameters.

Where does 63 come from? Almost certainly a dataset count read as a job count: SPEC 0003
records **63 records copied** into `data/real_private/` (`specdatalayout03.md:123`), and
`quebraplan.md:332` uses "63 qubit-nights" in the same document. The figure then propagated
into four cells of §2.

The duplication is nonetheless real at the level that matters: `t2star_q1_070423.py` and
`t2star_q1_100423.py` are 128 lines each and, after normalising the date, differ by **2 removed
and 2 added lines carrying ONE logical difference** — the run duration, which appears twice
(`PREFIX`'s `27h`/`13h` and `duration_h` 27/13). So 3.3's instinct holds and its scale does
not. A family abstraction that pays for itself over 63 files
may not over 9, and R5.3 is scoped accordingly.

### R5.0.3 The closure is contaminated until the layering debt is paid. This reorders the phase.

MEASURED, and it is the finding that most changes this spec. `quebra.analyzers.t2star`
transitively reaches **14** `quebra` modules, and **4 of them are render modules**:

```
quebra.panels._within_calibration_render
quebra.plots.base
quebra.plots.fidelity_helpers
quebra.plots.theme
```

reached through `analyzers/t2star.py -> panels.within_calibration -> plots.*`, all runtime
imports, none under `TYPE_CHECKING`. Those are two of the ten violations SPEC 0004 R4.2 froze.

So if R5.1 lands first, **editing a module that draws and computes no number invalidates every
cached T2\* compute artifact** — exactly the blast radius R5.1.4 forbids. The phase would ship
a digest whose sensitivity is wrong in the direction the plan explicitly warned about, and
paying the violations down afterwards would move every identity a second time.

It also makes R5.1's second acceptance criterion a trap: "editing a module the job does not
reach" is satisfied by `plots/km_survival_plot.py` and refuted by `plots/theme.py`. A reviewer
picking the wrong example gets a green test on a broken property.

**Therefore the `analyzers -> panels` violations are paid down BEFORE CHECKPOINT 5.1**, as
R5.0.4 below — not deferred as an earlier draft of this spec had it.

### R5.0.4 The reason those violations were deferred is wrong, and the repo says so — **DONE 2026-08-30**

An earlier draft deferred them because moving `panels/_within_calibration_data.py` would break
archived pickles naming it (2 of 666). That argument is dead three times over:

1. `tests/test_artifact_guard.py` already records that **every artifact written before SPEC
   0002 is out of reach** — the vocabulary rename and the src-layout move each severed them.
   The 664 others are already dead; there is no compatibility population being protected.
2. The only path that unpickles an archived artifact is gated on `rec_commit == git_commit`.
   Moving the module IS a commit, so those 2 become unreachable at the moment of the move
   whatever identity does.
3. `output/` is gitignored, generated and regenerable by design.

**R5.0.4 requirement:** pay down the five `analyzers -> panels.*` entries in
`[tool.importlinter] ignore_imports` by moving `_within_calibration_compute` (and whatever it
needs) out of the render package into a compute location. The `core -> {plots, loaders,
schemas}` entries may stay frozen — they do not contaminate a compute closure — but their
`pyproject.toml` comments name SPEC 0005 as owner, so either fix them here or correct the
comment to name the spec that will.

**Acceptance**
- `analyzers.t2star`'s transitive `quebra` closure contains **zero** `plots.*` or `*_render`
  modules. Re-run the grimp measurement above; it is four today.
- `lint-imports` exits 0 with five fewer `ignore_imports` entries, and no entry names a phase
  that will not remove it.
- 380 collected, 378 passed, 2 skipped.

**Outcome.** `panels/_within_calibration_{data,compute}.py` moved to
`analyzers/within_calibration_{data,compute}.py`; 12 files repointed. `analyzers.t2star`'s
transitive closure went from **14 quebra modules with 4 render** to **9 with 0**. The
`ignore_imports` ratchet dropped from 10 entries to **5**, none of which touches a compute
path. `test_artifact_guard.py`'s docstring now records THREE renames, not two — this move
strands 2 further pickles, both already unreachable behind the commit gate.

> **CHECKPOINT 5.0** - the compute closure is clean. REACHED 2026-08-30.
> Suggested: `moves the within-calibration compute out of the render package`

---

## R5.1 - Identity must cover the code that produced the numbers — **DONE 2026-08-30**

**R5.1.1** Fold the source of every step function a job invokes into the `code` contribution,
alongside the job file. Resolve each `_DAGNode.fn` to its defining module and hash that
module's source. The job file alone is not the code that produced the result.

**R5.1.2** Transitive, not just direct. A step calling `t2star.run` must move when `t2star`
moves.

**Seed from every step's defining module INCLUDING the job module; traverse imports; hash only
the `quebra.*` nodes reached.** That sentence is load-bearing and its absence would have made
this requirement a no-op. Measured: of the six steps in `t2star_q1_070423`, the three that
actually call `t2star.run` belong to module `subjob_t2star_q1_070423_45edbf17` — the job
module, not a `quebra.*` one. Filtering the SEED set to `quebra.*` therefore drops exactly the
steps that reach the analyzers, and `analyzers.t2star` never enters the closure. The filter
applies to what is HASHED, not to where the walk STARTS.

**R5.1.3** Deterministic, order-independent and install-independent: sort by dotted module
name and hash file BYTES. Four measured hazards, each of which silently breaks the closure:

1. **`sys.modules` is not a valid source.** `quebra run --all` imports every job into one
   process in a loop, so a closure read from `sys.modules` gives job N the union of jobs 1..N
   and `run --all` disagrees with `run <one job>`. The walk must be a static traversal from
   the seed modules.
2. **Function-local imports must be walked.** At least ten exist under `src/quebra/`, and
   `quebra.analyzers.permutation` is reachable ONLY through a function body — it is what
   computes the xi permutation null that `xi_seed` feeds. A module-body-only AST walk drops
   it silently. AGENTS.md already records this exact defect class.
3. **`from <package> import <submodule>` must resolve to the submodule.** `panels/
   _within_calibration_compute.py` does `from quebra.analyzers import distinguish_band,
   reliability_band, signal_band`; a naive resolver maps all three to the package.
4. **Never key on `module.__name__` or a file path.** Job modules are named
   `subjob_<stem>_<sha256(abspath)[:8]>` — measured `subjob_t2star_q1_070423_45edbf17` — so
   the name embeds an absolute path and is machine-dependent.

An unresolvable callable RAISES and names the node. `build_identity` already sets that
precedent, and its comment says why: an identity that quietly stops covering an input is the
one failure this scheme exists to prevent.

**R5.1.4** Do NOT hash all of `src/quebra/`. That would restore the blast radius 3.1 warned
about — editing a plot module would invalidate every cached compute artifact. The closure is
the point.

**R5.1.7 Fold the RESOLVED parameter row, not just module sources.** `quebraplan.md` 3.1 reads
"per-step sources rather than the module file, *resolved parameter row rather than the table*",
and an earlier draft of this spec implemented only the first clause.

It matters twice. Today every job parameter sits in the job file text, so `code` covers it for
free; the moment R5.3 moves rows into a manifest, identity stops covering them. And
`Identity` is `code + data + children` with no `job.name`, so two family members sharing a
definition file and differing only by a parameter would **collide on one digest**. The two
T2\* jobs survive only because they load different datasets; the next family member would not.

Closure captures are the live case: `_filter_step(config)` captures `config`, and
`jobs/active/t2star_q1_070423.py`'s own docstring records that closure captures are invisible
to the provenance label. Module-source hashing does not see them either. Fold the step kwargs
and any captured config, keyed and sorted deterministically.

**R5.1.5 Record the third-party surface separately**, not in `code`. Package versions belong
in provenance as their own field so a numpy upgrade is visible without pretending it is a
source change.

**R5.1.6** This changes every identity in the repository: every cached artifact becomes
unreusable and every run directory gets a new name. That is correct and unavoidable — the old
digests assert something that was never true.

The migration story is one sentence, because the affected population is **zero**: `published/`
does not exist and `specdatalayout03.md` records that no promoted record is committed. So
nothing already published needs reconciling; the rule is simply *re-run before the first
promotion*. Also sweep `docs/` — `WRITING_A_JOB.md` cites a run directory by its identity
prefix and that example goes stale.

**R5.1.8 This buys truth, not caching, and the spec must not imply otherwise.** `_reuse_eligible_dir`
keys on `git_commit`, which is repo-wide, so *any* commit to *any* file already invalidates
every cached artifact — a README typo included. The blast radius the plan feared is already at
maximum, enforced by the commit gate rather than by identity. R5.1 leaves that gate untouched
and improves cache reuse by exactly zero. Its whole value is that the digest stops
over-claiming: a run directory name, a provenance record and a future `PROMOTED.toml` begin
describing the computation that actually ran. Relaxing the commit gate to key on the closure
is the change that would buy reuse across commits; it is a separate risk surface and is NOT in
this phase.

**Acceptance**
- The mutation probe in R5.0.1 inverts: appending a line to `analyzers/t2star.py` MOVES
  `t2star_q1_070423`'s identity. Restore the file and it returns to the previous value.
- Editing a module the job does NOT reach leaves it unchanged. **Use `plots/km_survival_plot.py`,
  not `plots/theme.py`** — after R5.0.4 the T2* closure excludes the former and would still,
  correctly, include the latter if anything it reaches imports it. Naming the example is what
  stops this criterion passing vacuously.
- Two consecutive builds of the same job agree.
- **Install-independence** (replacing the withdrawn P4): the same job's identity is equal under
  the editable install and under the wheel that `scripts/acceptance.sh` builds and installs
  outside the repository. This is the property a promoted record depends on, and it is the
  reason R5.1.3 keys on dotted `quebra.*` names and file BYTES, never on paths.
- A test pins both directions; this is the phase's central claim and must not rest on a probe
  run once by hand.

**Outcome.** `core/closure.py` uses `grimp` (promoted to a runtime dependency, approved) to
walk the static import graph. The probe INVERTS as required:

```
baseline                                  5c35194470316077
edit analyzers/t2star.py    (reached)     54091a9befb88895   moved=True
edit plots/km_survival_plot (unreached)   5c35194470316077   moved=False
restore                                   5c35194470316077   == baseline
```

Determinism holds across processes, and hazard 1 is confirmed avoided: importing three other
jobs first leaves the digest identical, so `run --all` agrees with `run <one job>`.
Install-independence holds — the wheel-installed package in site-packages computes the same
`5c35194470316077`, which is the property that replaced the withdrawn P4.

R5.1.7's collision was real and is closed. Before: two jobs differing only by `x=1` vs
`x=999` both produced `93f7286634eef03b`. After: `59506bbe93c717ec` vs `4b6683503eb8eaab`.

13 tests in `tests/test_identity_closure.py`. Collect 380 -> 393.

> **CHECKPOINT 5.1** - identity covers the computation. REACHED 2026-08-30.
> Suggested: `folds the reachable step sources into the identity, so editing an analyzer moves it`

---

## R5.2 - Logical job IDs, not filesystem paths — **DONE 2026-08-30**

**R5.2.1** `job.include` takes a repo-relative path string at 4 call sites, all in
`jobs/composite/`: `compare_t2star_0704_vs_1004.py` and `check_ledger_q1.py` each include
`jobs/active/t2star_q1_070423.py` and `..._100423.py`. Moving a job file is therefore a
breaking change to every composite that includes it.

**R5.2.2** SCOPE CORRECTION. Half of the motivation is already satisfied: moving a job file
today does NOT change its identity, because `job_code_hash` is file *content* and `job.name` is a
string inside the file, not a path. Only `include` breaks. So this requirement is not "build
an ID scheme and a registry" — it is **make `include` take the logical name that R5.4's
discovery already produces.**

**R5.2.3** A module-level `JOB_ID` constant, resolved through R5.4's discovery. A duplicate
`JOB_ID` is an error at discovery time, not a silent last-one-wins.

**R5.2.4** No deprecation window. An earlier draft kept the path form "for jobs outside this
repository", of which there are none — that is deferred design documented as normative. Four
in-repo call sites in two files convert in one edit. If an external caller ever appears, add
the compatibility path then, against a real case.

**Acceptance**
- All 4 in-repo `include` sites use `JOB_ID`.
- Moving a job file between `jobs/active/` and a sibling directory changes no composite and no
  identity.
- A duplicate `JOB_ID` fails discovery, naming both files.

---

## R5.3 - Collapse the duplication that exists — **DONE 2026-08-30**

**R5.3.1** Scope: the two T2* jobs, which differ by 2 logical values. `ramsey_q1_100423.py` and
`ramsey_2x2_q1_030723.py` already share `configure_ramsey_job` from `quebra.recipes`, so the
recipe mechanism exists and is proven; this is a further application of it, not a new framework.

**R5.3.2** A job family is a definition plus a manifest of parameter rows. The manifest is
committed and reviewed — it is the object a reader diffs to see what changed between runs.

**R5.3.3 One named family, one binary decision.** An earlier draft said "if a family has one
member, leave the file alone and record why", with acceptance "any family left uncollapsed has
a recorded reason". That is an escape hatch: satisfiable by writing a sentence and doing
nothing, and a reviewer could not tell a careful judgement from an evasion.

The repo has exactly one family of size greater than one: the two T2\* jobs. Decide on THAT,
and state the reason as a measurement — lines removed, parameters exposed in the manifest —
not as "a legitimate outcome". The honest question is not "does a family abstraction pay at
9 jobs" (a scale argument against a scale-independent 2-file case) but "is a manifest row
clearer than a second 128-line file". That has a yes or no answer.

**R5.3.4** No behaviour change — stated as the RESULT, not the identity. An earlier draft
required "the same identity as its pre-collapse form", which is unsatisfiable: `code` includes
the job file's text, collapsing rewrites or deletes that file, so the identity MUST move. Worse,
an implementer trying to satisfy it would be pushed toward dropping the job file from `code`,
which silently removes every job-level parameter from identity — the "weaken the check to make
it pass" failure mode, with a spec standing in for a test.

The requirement is: the collapsed job produces a **byte-identical artifact**, with identity
expected to move. Record both digests in the commit.

**Acceptance**
- The two T2* jobs produce byte-identical artifacts; both digests recorded, movement expected.
- The manifest is human-readable and diffable.
- Any family left uncollapsed has a recorded reason.

**Outcome.** `core/discovery.py` reads `JOB_ID` and `JOB_FAMILY` statically with `ast`;
12 jobs declare both. `include` resolves an ID first and a path second — the 4 in-repo sites
now name IDs, and the acceptance holds: moving `t2star_q1_070423.py` into a different
directory left `check_ledger_q1` inspecting at exit 0.

R5.3's binary decision came out COLLAPSE, and the measurement is why: once the date AND the
run duration were normalised the two files were **byte-identical**.

The line counts, stated precisely because an earlier draft of this paragraph got them wrong.
At HEAD each file is **128** lines; they reached 133 mid-phase when R5.2's three declarations
were added; they are **34** now. `git diff --numstat` over the pair: **226 removed, 38 added**,
against **+113** in `recipes.py` — repo-wide net **-75**. The draft's "133-line" contradicted
R5.0.2's own 128, and its "198 lines removed" matched no measurement.

R5.3.4 verified as reworded, and the rewording earned itself. `q1_27h_0704_dataset_windows.pkl`
is byte-identical across the collapse. `t2star_panel_data.pkl` differs by exactly **2 bytes**,
traced to the module-path string `panels._within_calibration_data` ->
`analyzers.within_calibration_data` (+2 chars) and the pickle FRAME header that counts it.
Zero data bytes differ, and both differences come from R5.0.4, not from the collapse.
Identities: `43e8d4` -> `ffba1a`, moving as expected.

> **CHECKPOINT 5.2** - logical IDs and the collapse that earns its place. REACHED 2026-08-30.

---

## R5.4 - Declarative categorisation and discovery — **DONE 2026-08-30**

**R5.4.1** Today `run --all` globs `jobs/active/*.py` and `jobs/archived/*.py`. Category is a
directory, so recategorising a job moves a file — which under R5.2 must stop being meaningful.
Note `jobs/archived/` **does not exist**; the glob is dead and should go with this change.

**R5.4.2** A module-level `JOB_FAMILY = "survey"` constant. No class hierarchy, no entry
points, no `pluggy`. Recategorising costs one string edit.

**NOT `pkgutil`**, which `quebraplan.md` 3.5 names and an earlier draft repeated uncritically.
It contradicts R5.4.3 — `pkgutil` enumerates *importable* packages and R5.4.3 forbids
importing — and `jobs/` is deliberately outside the wheel, with SPEC 0002 R1.1.4 forbidding
`sys.path` manipulation to reach it. The mechanism is a `Path.cwd()/"jobs"` glob plus `ast`,
which is what `cli.py` already does for `--all` and what `tests/test_bench_isolation.py`
already does for source walking.

**R5.4.3** Discovery must not import a job to read its category — importing a job file builds
its graph. Read the constant statically (`ast`), the way `tests/test_bench_isolation.py`
already walks module sources without importing them.

**R5.4.4** `run --all` selects by family, and the directory layout becomes presentation only.

**Acceptance**
- `quebra run --all --family survey` selects by constant, not directory.
- Discovery imports nothing: prove it by pointing discovery at a job whose import would raise.
- A job with no `JOB_FAMILY` is reported, not silently skipped.

---

## R5.5 - The generated job manifest — **DONE 2026-08-30**

**R5.5.1** A generated, committed, human-readable table: one row per job, with `JOB_ID`,
family, datasets, and the parameters that distinguish it from its family's defaults.

**R5.5.2** Generated by a committed script and regenerable; a test asserts it is current, in
the shape `scripts/make_data_manifest.py` and `tests/test_data_manifest.py` already establish.

**R5.5.3** This is what makes R5.3's abstraction reviewable. It is not optional decoration:
the plan is explicit that 63 explicit files were greppable and one parameterised definition is
not, and the same argument holds at 20.

**Acceptance**
- Manifest committed, regenerable, and its test fails when a job changes without regeneration.

**Outcome.** `run --all --family <name>` selects by the constant and lists the declared
families on a miss; the dead `jobs/archived/` glob and its `--include-archived` flag are gone.
`docs/JOBS.md` is generated by `scripts/make_job_manifest.py` and its staleness gate fires —
editing one line of the manifest fails `test_the_manifest_is_current`.

**Two existing tests changed, both because this phase moved their source of truth, neither
weakened.** `test_the_survey_carves_windows_the_same_way_the_t2star_job_does` read the carve
from the T2* job's step kwargs, which the collapse moved into the recipe's signature; it now
reads the EFFECTIVE value (job override if present, else recipe default), which is strictly
stronger — verified by mutation from both sides, the survey constant and the recipe default,
each of which fails the control. `test_a_step_defined_in_a_job_file_still_seeds_the_analyzers`
lost its subject for the same reason and was repointed at `mtbf_q1`, which still defines local
steps; it caught its own stale premise because the premise was asserted rather than assumed.

> **CHECKPOINT 5.3** - discovery, categorisation, and the readable view. REACHED 2026-08-30.

---

## Done when

- Editing a reachable analyzer moves the dependent job's identity; editing an unreachable
  module does not. Both pinned by tests.
- No `include` site names a filesystem path.
- `run --all` selects by family constant.
- The job manifest is committed, generated and tested current.
- `make check`, `make deps` exit 0; `scripts/acceptance.sh` exits 0.
- The collect count is recorded with its delta explained.

## Critique outcome

Critiqued 2026-08-30 before any implementation. The critic had no shell, so its central claim
was re-measured here rather than accepted: `grimp.build_graph("quebra")` confirms
`analyzers.t2star` transitively reaches 14 `quebra` modules, **4 of them render**
(`panels._within_calibration_render`, `plots.base`, `plots.fidelity_helpers`, `plots.theme`).
That settled the reordering — R5.0.4 now precedes CHECKPOINT 5.1 — and it was the single
change that decides whether this phase's central claim is true when it ships.

Also corrected from that pass: the seed/filter ambiguity in R5.1.2 that would have made the
requirement a no-op (measured: the three steps calling `t2star.run` belong to the job module,
not a `quebra.*` one); the missing half of plan item 3.1, the resolved parameter row, now
R5.1.7; R5.3.4's unsatisfiable identity criterion; R5.3.3's escape hatch; the withdrawn P4;
`pkgutil` contradicting the no-import rule; R5.2's registry and deprecation window as premature
abstraction for four in-repo call sites; and R5.1.6 describing a migration for a population
that is zero.

Rejected nothing from the critique. Its one factual slip was assuming `|` and `:` semantics
from documentation in the prior Phase 2 pass; this pass it flagged its own unmeasured claims
explicitly, which is why they were checkable.

## Review outcome — discovery slice

Reviewed cold 2026-08-30. One CRITICAL, thirteen IMPORTANT, all fixed.

**CRITICAL: `run --all` silently widened from 9 jobs to 12.** R5.4 replaced the
`jobs/active/*.py` glob with "every discovered job", which pulled in the three composites
that `AGENTS.md:46,201` and `docs/WRITING_A_JOB.md` both promise are NOT swept — one of them
the ~6.5 h independence survey. Typing `quebra run --all` would have started it unasked and
re-run every sub-job.

The fix keeps R5.4's declarative principle rather than reverting to directories: a third
constant, `JOB_SWEEP` (default `True`), declared `False` on the three composites. `--all` is
back to 9; `--family` overrides, because naming a family is asking for all of it.

The reviewer also caught that `JOB_FAMILY = "composite"` was a MECHANISM, not a subject —
`independence_survey` carried it while having no `job.include` at all, which is the directory
rule surviving in a constant. Families are subjects now (`independence`, `t2star`), and being
swept is its own declaration.

Also fixed: an unparseable job file was swallowed and VANISHED from `--all` at exit 0, quieter
than the glob it replaced — it raises `UnreadableJobFile` now, and the test asserting the old
behaviour was inverted rather than deleted. `--family` without `--all` was silently ignored.
The manifest's `INTERESTING` allowlist omitted two seeds and five other run-defining
constants, so editing a seed left the manifest byte-identical and its staleness gate blind —
replaced by a rule (every uppercase scalar that is not a declaration). Two tests were
self-defeating: `test_regenerating_is_idempotent` shelled out to a generator whose `main()`
WRITES the manifest, so the run reporting staleness also erased it; and
`test_the_generator_does_not_import_the_jobs` asserted the truthiness of a function object
without ever calling it.

Documentation the phase should have swept and did not: `WRITING_A_JOB.md` described a
pre-closure identity, taught `job.include("other_job.py")`, cited the stale `43e8d4` run
prefix, and still carried a `tool/datasets/` path SPEC 0003 repointed. It now has a "What a
job file declares" section.

Two of this spec's own numbers were wrong: "133-line files" contradicted R5.0.2's 128 (128 at
HEAD; 133 was a mid-phase state after R5.2 added declarations), and "198 lines removed"
matched no measurement — `git diff --numstat` gives 226 removed / 38 added over the pair,
+113 in `recipes.py`, net -75.

**Not verified by that reviewer:** the identity digests, the byte-identical windows artifact
and the 2-byte panel delta all require running jobs over `data/real_private/`, which it was
forbidden to touch. They are checked in the identity slice.

## Not in this phase

- **Phase 3C** — opening the four MSc issues and tagging `v0.2.0`. The plan is explicit that
  this comes *after* the architecture stabilises, and it is a human action.
- **Five of the ten frozen import-linter violations** — the `core -> {plots, loaders, schemas}`
  group. They do not contaminate a compute closure, so they can wait. The other five
  (`analyzers -> panels.*`) are NOT deferred: they are R5.0.4, before CHECKPOINT 5.1.

  **Ownership orphan to fix while here:** `pyproject.toml`'s ignore comments and
  `specboundaries04.md` R4.2.4 both name SPEC 0005 as owner of all ten, and R4.2.4 says the
  split of `core` into leaf-types and orchestration packages happens here. It does not.
  `unmatched_ignore_imports_alerting = "error"` catches stale ENTRIES, not stale COMMENTS, so
  nothing flags this. Either do the `core` split in this phase or correct both documents to
  name the spec that will.
- **Widening `mypy` beyond `core/`.** SPEC 0004 R4.0 measured 208 errors in 41 files.
- **The unused `slow`/`heavy`/`real`/`r` markers.** No test carries any of them, so the fast
  selector equals the full suite. It is a test-architecture question, SPEC 0006.

## Budget

The plan says 12-24 h. R5.0.2 removes work (20 jobs, not 63); R5.0.3 and R5.0.1 add it.

- **R5.0.4** (move the compute out of `panels/`): 2-3 h. Now the phase's first checkpoint.
- **R5.1** (closure walker, fold extension, tests both directions, mypy under `core/`): 3-5 h
  of hands-on time. It lands inside the `make types` gate, so `inspect.getmodule` returning
  `ModuleType | None` needs narrowing — small but real.
- **R5.2 / R5.4 / R5.5**: 3-5 h combined, once R5.2 is trimmed to "include takes the
  discovered name".
- **R5.3**: 1-2 h, or zero if the binary decision in R5.3.3 goes the other way.

**The survey re-run is NOT in this figure.** `independence_survey` is ~6.5 h wall-clock at
`INCLUDE_C3=True` over 415 cells, it is already owed from SPEC 0003 (its artifacts carry a
stale identity from the dataset move), and R5.1 invalidates it again. Treat it as overnight
wall-clock owed before the first promotion, not as hands-on time inside this phase. Saying
which is the difference between a credible 12-24 h and a phase that silently doubles.
