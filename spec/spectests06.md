# SPEC 0006 - Test architecture

**Phase:** 5
**Budget:** 24-34 h. Below `quebraplan.md`'s 30-55 h, and the reduction is measured rather than
asserted. R6.0.1 measures the premise 5.1 is built on and finds it false here, so the rewrite it
scoped is not owed. R6.0.7 finds four of 5.5's six invariants already covered. R6.0.4 declines 5.2's
generator subsystem against a measurement the repository already holds. Against those, R6.2 adds
work 5.1 costed as a directory move and this spec spends on a marker axis instead.
**Depends on:** SPEC 0008 complete and committed (`db651e0`).
**Feeds:** `quebraplan.md` 9.1, whose ADR on the bespoke runner consumes R6.7 directly.
**Blocks:** nothing hard. `quebraplan.md` Phase 6 is made easier by the marker axis but is not
gated by it: `r` is already a declared marker and Phase 6 can populate it without this spec. Stated
as a convenience rather than a dependency, because an unmet "blocks" claim is how a phase order
becomes folklore.
**Reference:** `spec/quebraplan.md` §2, Phase 5, items 5.1 through 5.6.

**Numbering.** 0006 is claimed by three references as test architecture (`specidentity05.md:6`,
`specidentity05.md:516`, `specboundaries04.md:342`). All three are verified correct at `72a3aae` and
this spec takes that number so they stay so. `specinstallabity02.md:68` reserves 0007 for the R
boundary and is untouched here.

Rationale lives in `spec/quebraplan.md`. This file contains requirements and acceptance criteria
only, plus the measurements in R6.0 that change what the phase should do. Do not re-derive or
re-argue the decisions below.

The governing constraint: **a test that names an oracle has not thereby been shown to detect
anything, and an estimator with no oracle is unvalidated whatever its coverage says.**

---

## Preconditions

Baseline on `dev` at `72a3aae`, measured 2026-09-04, not assumed. The working tree was dirty at
measurement time (`spec/specvalidity08.md` and `.claude/review-findings-0008.md` untracked), which
affects the reuse gate and nothing measured here.

- `pytest --collect-only -q` gives **535 tests** across **423 test functions** in **40 files**,
  8560 lines. The gap is parametrisation. Every requirement states its collect delta against 535.
- `pytest -q` gives **533 passed, 2 skipped, 9 warnings in 27.46 s**. Under `--cov=quebra`, 53.25 s.
- `make types` exits 0 over `src/quebra/core`, 11 source files. `make arch` exits 0, one contract
  kept, zero broken.
- Coverage, measured with `pytest --cov=quebra --cov-report=term`: **69% overall, 6486 statements,
  2032 missed**. Per module: `kaplan_meier.py` **76%**, `mtbf.py` 66%, `windows.py` 79%,
  `allan.py` 22%, `fidelity.py` 22%, `psd.py` 0%, `loaders/registry.py` 52%; `core/identity.py`
  100%, `core/closure.py` 94%, `provenance.py` 99%, `core/job.py` 91%, `core/runner.py` 85%.
- `tests/` is flat. No tier directories, no per-tier conftest. `tests/conftest.py` does not exist;
  the only conftest is at the repository root and provides `sys.path` plus one `in_repo` fixture.
- **Zero tests carry `slow`, `heavy`, `real` or `r`.** All four are declared in
  `pyproject.toml` `[tool.pytest.ini_options]`, and `Makefile:4`'s `FAST` selector names all four, so
  the fast selector currently excludes nothing. `make test-real` and `make test-r` both exit 5.
- `grep "pytest.mark"` across `tests/` returns 41 hits, **all `parametrize`**. There is no tier axis.
- **The private tree is present on this machine and two modules read it.**
  `tests/test_windows_carve.py:243-259` loads five records and skips per record when absent;
  `tests/test_data_manifest.py` reads it in four of six tests and skips. `specvalidity08.md:33-34`'s
  precondition "no test in `tests/` reads private data" **no longer holds as written**; the property
  it protected does, because both modules skip when the tree is absent and CI has no tree.
- The two skips today are `tests/test_checks_c3_bridge.py` (skips because `Rscript` **is** on PATH
  here) and `tests/test_checks_published_values.py` (raw Aalen-Husebye period lengths not
  obtainable).
- `git for-each-ref refs/tags` is **empty**. `published/`, the destination `scripts/promote_run.py`
  writes to, does not exist. Both bear on R6.0.6.
- `scipy` 1.17.1, `numpy` 2.4.4, `scikit-learn` 1.8.0 installed. `pyproject.toml` declares
  `scipy>=1.14` under a comment reading "Lower bounds only, set to the versions this was developed
  against".
- `hypothesis` and `pytest-cov` are declared dev dependencies with **zero imports** anywhere, and
  both sit in `[tool.deptry.per_rule_ignores]` `DEP002`. `coverage` is **not** separately declared.

---

## R6.0 - Ten premises in `quebraplan.md` Phase 5 that do not survive contact with the code

Phase 5 was written when there were 63 jobs, no assumption records, no instrument report and no
marker set. Each finding below changes what the phase should build, so they precede the
requirements rather than sitting in a footnote.

### R6.0.1 The suite is not a change-detector suite. The audit measured it.

Phase 5 opens with "your current suite was agent-written, and agent-written tests have a
characteristic failure mode: they assert what the code currently does", and derives an entry rule
that every test must name its oracle. **That rule is already `AGENTS.md` section 7's oracle rule ("Oracle rule,
effective now") and it is already kept.**

Classification rule, stated so a second rater can disagree with it. **S**: the assertion is about
the numeric value or the sampling behaviour of an estimator, statistic, p-value, size, power or
distribution function. **A**: an S test naming its source of truth in the test name or first
docstring line. **B**: an S test naming no oracle. **C**: no statistical claim.

Measured over all 423 test functions: **S = 68, A = 67, B = 1, C = 355.** An independent second pass
over 127 of the 423 assertion bodies put S at **73 to 81**, with the difference concentrated inside
`tests/test_shape_stats.py`, a file already classified majority-S. The seven files graded entirely C
held at 79 of 80.

Supporting measurements: only 39 of 423 test functions pin a float literal of three or more
significant digits, and 33 of those name their source; the remaining six assert analytic identities
named in the test name. **22 test functions are declared positive or negative controls** across 12
files, which is the opposite of a change detector.

One legitimate declared exception: `tests/test_style_baseline.py` is a **ratchet**, pinning a count
and permitting downward movement only. A ratchet is a change detector by construction and is
legitimate because it declares itself one and is directional. There is exactly one, carrying 2 of
535 collected tests.

**Consequence.** 5.1's "expect to delete more than you keep, and expect that to feel bad and be
correct" describes a suite that does not exist here. The audit was worth running and its result is
that the rewrite it scoped is not owed. 5.1's 4-8 h becomes roughly 1 h.

### R6.0.2 Naming an oracle is not detecting anything, and three tests prove it

This is the finding that replaces R6.0.1's headline as the phase's actual justification.
"67 of 68 name an oracle" measures **labels, not detection power**. Three tests carry an oracle and
cannot fail when the thing they guard breaks. All three were found by reading, not by running.

1. **`tests/test_check_ledger.py:98-111` is a dead control.**
   `test_the_per_threshold_seed_is_stable_across_processes` never imports or calls `check_ledger`.
   It re-types the seed formula as a string literal at `:104` and asserts `zlib.crc32` is
   deterministic across three subprocesses. Changing the real site at `check_ledger.py:391` from
   `zlib.crc32(...)` to `hash(...)` leaves it green, reintroducing exactly the cross-process
   irreproducibility its own docstring says it exists to prevent. **Established by reading, not
   predicted.**
2. **`tests/test_checks_statistics.py:171` is circular.**
   `test_eq16_reduces_to_eq4_for_a_single_segment` calls `gamma_hat` at `:175` and divides by it at
   `:177`, so a divisor mutation cancels on both sides. It pins the eq (16) to eq (4) reduction and
   pins nothing about `gamma_hat`.
3. **`tests/test_within_calibration_builder.py:88` guards two copies of one convention.**
   `_occupancy` and `_threshold_summary` both call the same threshold helper, so a mutation to the
   shared helper moves both sides of the 1e-9 identity together.

This is the `AGENTS.md` §4 defect class ("a positive control must fail when the thing it guards is
broken") alive in three places, in files the audit graded clean. R6.1 acts on it.

### R6.0.3 The five-layer estimator validation of 5.3 is built, is four tiers, and ships as an artifact

`analyzers/instrument_validation.py:7-10` declares the scheme: tier 1 the routine computes what its
source's equation says; tier 2 it reproduces the numbers the source prints, from the source's own
data; tier 3 its p-value holds its nominal level under a null it is entitled to; tier 4 it agrees
with an independent implementation. It is finer than 5.3's list in the way that matters: it attaches
to **instruments**, not to test files, and states that no tier subsumes another. It emits 19
`TierRow` cells over 7 instruments. `tests/test_instrument_validation.py` exists to stop the report
claiming evidence it does not have, and one of its own rows says a tier-4 cell is "tier-1 evidence
wearing a tier-4 label".

5.3's fifth layer is "figures", which is `quebraplan.md` Phase 7 and out of scope here.

**The gap is the subject list.** The 19 cells cover C1, C2, C3, C5, C6, CvM, Chatterjee xi and
distance correlation. They do not cover `kaplan_meier`, `mtbf` or `windows`.

### R6.0.4 Kaplan-Meier has 76% line coverage and no oracle test at all

`analyzers/kaplan_meier.py` is a hand-rolled product-limit loop with an explicit tie sort
(`:286`), a Greenwood accumulator that deliberately admits `inf` on a consumed risk set, a log-log
band (`_loglog_band`, `:361`), a median by first crossing of 0.5, and exclusion accounting for
unobserved births.

`kaplan_meier` appears in exactly two test files. `tests/test_contract_boundary.py` tests the
`icontract` dtype precondition; `tests/test_check_outcome.py` constructs `KaplanMeierComparison` to
assert field attachment. **No test asserts a survival value, a band bound, a median, a risk-set
count or a tie outcome against anything.** The strongest claim made about the estimator's output is
`assert len(curve.time_min) > 1`.

**76% covered with zero evidence of correctness** is the Inozemtseva and Holmes result
`quebraplan.md` 5.6 already cites, reproduced inside this repository, on the module the whole
within-calibration tier depends on. R6.8 uses it for exactly that and does not chase the number.

`mtbf.py` is 66% with no test file. It is `np.diff` plus five summary statistics and makes no
distributional claim, so it does not need four tiers.

### R6.0.5 5.2's generator: the premise "no estimator sees a read" is false, and two analyzers are the exception

The chain is reads to `windows.carve` to a window table to durations.
`kaplan_meier.make_inputs_from_windows` takes `duration_s` and a boolean from `death_type`;
`checks/_multiprocess.segments_from_windows` takes durations and birth times. **For every
duration-consuming estimator, a read-level noise model is an oracle for the carve and for nothing
downstream of it**, and `jobs/bench/arms.py:397` measures why: read-level AR(1) induces no positive
duration-level dependence at any rho, reaching only -0.086 at rho = 0.99, because level crossings of
a stationary Gaussian process regenerate and successive excursion lengths are very nearly a renewal
process.

**But two shipped analyzers consume reads directly, and they are the two 5.2 names.**

- **`analyzers/tlf.py` is an RTN estimator.** `run(values, timestamps, *, seed)` at `:37` fits a
  two-component mixture to a read series and returns `switching_rate_per_hour`, `mean_dwell_s0`,
  `mean_dwell_s1`, `dwell_cv_s0` and `dwell_cv_s1`. `tests/test_transform_guards.py:6-8` states its
  scope is "deliberately the GUARDS, not the numbers", so those five fields have **no oracle of any
  kind**.
- **`analyzers/allan.py` consumes `norm["delta_hz"]` directly** at `:85` and is wired into every
  Ramsey job. Tempered, because `allantools` does the arithmetic.

**Ornstein-Uhlenbeck is already shipped.** `jobs/bench/arms.py:140` `_stationary_ar1` is a discretely
sampled OU process at the exact Gaussian transition, not an Euler integrator, which is what
`quebraplan.md:266-267` asks for. Arm C thresholds and carves it through the pipeline's own
primitives.

**The correct RTN truths are the SAMPLED ones, not the continuous ones.** `tlf.py:139-144` takes a
hard per-read MAP assignment, `:151-154` run-length encodes the assigned read sequence, and `:157`
sets `durations = runs_lengths * median_dt`. Dwells are `k * dt` for integer `k`. So for a two-state
chain with rates lambda and mu sampled at spacing `dt`, interior run lengths are exactly
Geometric(`p01`) with

```
p01 = (lambda / (lambda + mu)) * (1 - exp(-(lambda + mu) * dt))
```

giving `mean_dwell -> dt / p01` and `dwell_cv -> sqrt(1 - p01)`. These reduce to `1/lambda` and 1
only as `(lambda + mu) * dt -> 0`. Computed: at `lambda = mu` with `p01 = 0.05` the sampled mean is
**5.3605%** above `1/lambda`, and at `p01 = 0.1` it is **11.5718%** above. So a test written against
the continuous limit at a 5% tolerance does not merely sit on the boundary, it **already fails** at
`p01 = 0.05`. A measured mean quoted from either dwell state must name which state it came from,
since the two are equal only at `lambda = mu`.

`switching_rate_per_hour` (`:160-168`) counts transitions over the untrimmed record and has the
sampled limit `p01 / dt` transitions per unit time in each direction. A test must fix `lambda = mu`
for it to have a single rate to compare against - and once it does, **the rate assertion is the
reciprocal of the dwell assertion and is not independent evidence**, which is why R6.4 marks it
optional rather than counting it as a third oracle.

**`tlf.py:134` carries the same defect as `allan.py:20-25`.** Both take a median of read spacings and
treat it as the sample period: `tlf.py:134` `np.median(np.diff(ts))`, multiplied into dwells at
`:157`. On a gapped record the dwell in seconds is not elapsed time. `allan.py:22` at least filters
to positive diffs; `tlf.py:134` does not. Recorded, not fixed here.

**Consequence.** No generator subsystem, and no `src/quebra/synth/`. R6.4 states what is built
instead and what stays an open question.

### R6.0.6 The six tiers of 5.1 do not partition the suite, and the `regression` tier asks an embargo question

Applying the six tier directories to the 40 files:

- **`regression/` requires a decision nobody has made.** 5.1 defines it as golden values from a
  pinned tagged run over `real_private/`, committed into a tracked test file. That means publishing
  derived statistics from embargoed data into public git history. **That is a data-publication
  decision, not a testing one.** The safe form already exists and commits no private-derived number:
  `tests/test_windows_carve.py:243` asserts an **agreement between two code paths** on private
  records. Neither precondition for the tier exists anyway: no tags, no `published/`.
- **The `jobs/` tier was budgeted against 63 jobs.** There are 13 in 6 families, and most declare a
  `data/real_private/` dataset, so a CI-runnable version needs synthetic datasets that do not exist.
- **Directories cross-cut the index `AGENTS.md` section 7's indexing rule already mandates**, which is by oracle and
  subject. `tests/test_checks_statistics.py` is described by its own docstring as "identities,
  oracles, and the guards", which is three tiers in one file; `tests/test_windows_carve.py` holds
  synthetic contract tests at `:202` and real-record tests at `:243`.
- **38 citation sites in R6.10's scope point at test modules**, and three are already stale:
  `jobs/bench/arms.py:48` cites `tests/test_checks_c2.py`, and
  `src/quebra/analyzers/checks/c1_lewis_robinson.py` and `c2_anderson_darling.py` cite
  `test_checks_c1.py` and `test_checks_c2.py` in the bare form. None has ever existed. An
  earlier draft said "31 tracked references from outside `tests/`", which is neither this
  scope's figure nor that one's.

**What 5.1 gets right and this spec keeps:** the integration-versus-validation distinction is real
and correctly stated. Integration should pass even if every estimator is wrong; validation should
fail if the estimator is wrong even when the wiring is perfect.

**Consequence.** The tier is adopted as a **marker axis**, not a directory layout. R6.2 builds it.
A seventh tier, `policy`, is added on measurement: seven files are guards over the source tree whose
oracle is a written rule and whose characteristic failure is silent vacuity, which is why each
already carries a positive control. Filing them under `unit` would make that tier's stated oracle
false for a fifth of its members.

### R6.0.7 The CI and local partition is a data and R availability problem, not a latency one

The full suite is 27.46 s against 5.2's "under 3 min" fast-CI budget, a factor of six of headroom.
`slow` is declared as "> 30 s" and **no test qualifies**, none within an order of magnitude. `heavy`
is "large end-to-end job runs"; none qualifies. `r` has zero members and gains them in
`quebraplan.md` Phase 6, not here.

Applying all four cost markers now is impossible without fabricating members, and marking a
sub-second test `slow` is the same defect class as a docstring quoting a number from a different
run. `real` is the only cost marker with members: 9 of 535 collected items.

### R6.0.8 Two of 5.5's six invariants name a mechanism that does not exist, and one names none

| 5.5 invariant | Measured status |
|---|---|
| deterministic identity | covered: `tests/test_identity.py`, `tests/test_identity_closure.py` |
| no reuse under code mismatch | covered at the pure helper |
| no reuse under content mismatch | covered at the pure helper |
| no reuse under a dirty tree | covered: `tests/test_reuse_gate.py`, `tests/test_reuse_completeness.py` |
| acyclicity | **structural, not a runner property** |
| cycle detection reports the full chain | **already satisfied by the mechanism that has cycles** |
| valid topological order | **zero tests** |

`core/runner.py:101-123` `_toposort` has no direct test. Nothing asserts a valid topological order,
and nothing reaches its cycle branch at `:110`.

**That branch is REACHABLE through the public API, and a validation hole is why.** An earlier draft
of this spec asserted the opposite, that a cycle "requires mutating `job.dag` directly". Measured,
by execution, that is false:

```python
job = Job("probe")
fwd = LocalRef(node_id="g", job_ref=job, fn_name="g", kwargs={})   # public dataclass, public ctor
f = job.step(fn, fwd, name="f")
g = job.step(fn, f, name="g")
# edges {'f': ['g'], 'g': ['f']}  ->  ValueError: Cycle detected in job DAG at node 'f'
```

`_register_node` (`core/job.py:367-372`) validates only that a `LocalRef` input satisfies
`job_ref is self`. **It never checks that the input's `node_id` is already in `self.dag`**, and
`LocalRef` (`core/reference.py:76-90`) is a plain public dataclass. So a forward reference to a
not-yet-allocated node is accepted, registration order is NOT a topological order, and an ordinary
job file can build a cyclic DAG with no private access.

The same hole has a second consequence. A `LocalRef` naming an id that is never allocated at all
produces a raw `KeyError` from inside `_toposort` (`runner.py:111`) rather than a named error at
registration. Measured: `LocalRef(node_id="g_1", ...)` with no `g_1` node gives `KeyError: 'g_1'`.

**R6.7 closes the hole rather than documenting it.** Adding the missing membership check to
`_register_node` makes registration order a topological order in fact, which is what turns R6.7's
constructor property from "one attempted construction happens to raise" into an actual invariant,
and it removes the `KeyError` at the same time. Measured cost of the check: **50 ns per input ref**,
against the 1036 ns `_allocate_node_id` already spends looping the same dict, at graph BUILD time
and not inside `_toposort`'s recursion or the execution loop. All 13 shipped jobs run green today,
so no working job relies on the current behaviour.

**`runner.py:110`'s single-node message is then left alone, for one reason rather than three.**
Once the constructor rejects a dangling reference, the branch becomes genuine defence in depth
against a caller that bypasses the API, and improving the wording of an error that can no longer
fire from a job file buys nothing. The two reasons an earlier draft gave alongside this one are
both withdrawn: the unreachability claim is refuted above, and the `PYTHONHASHSEED` argument was
about a test that this spec no longer proposes to write.

The cycle that was already reachable and already handled is the composite `include` cycle at
`core/job.py:75-77`, which reports the full chain and is tested by `tests/test_nesting.py`. Nothing
here duplicates it.

**A reachable, untested property nobody named.** `_toposort` is seeded only from sink ids, so a node
registered but never reaching a sink is **never executed and never appears in `pipeline_steps`**
(`runner.py:455-459` filters on ancestors). R6.7 pins it.

### R6.0.9 5.4's "cumulative hazard non-decreasing" has no subject

No Nelson-Aalen module ships. `AGENTS.md's not-implemented list` records this and `grep -rli` finds nothing.

**And one shipped field actively manufactures the impression that one does.**
`analyzers/reliability_band.py:70` declares `cumulative_hazard: dict[str, list[tuple[float, float]]]
| None = None`, and the module docstring at `:10` states that when Kaplan-Meier lands
"`cumulative_hazard` and the band bounds populate". Measured: **nothing in `src/`, `jobs/` or
`tests/` ever writes it** - the only two references in the repository are the declaration and the
docstring promising it. A reader who greps for a hazard estimator finds a typed field and a
commitment, and concludes the subject exists. It is recorded here so the dropped property in R6.6
reads as "no subject" rather than as an oversight, and so the field is not mistaken for evidence.
Removing or populating it is a product change and is not in this phase.

The property is dropped rather than written against a stub, and R6.6 says so rather than leaving a
reader to wonder which of the five named properties landed.

### R6.0.10 The declared `scipy` floor is exercised by nothing, and the failure is silent

`pyproject.toml` declares `scipy>=1.14` under a comment reading "Lower bounds only, set to the
versions this was developed against". The installed version is 1.17.1, so the comment is already
inaccurate for this dependency. `.github/workflows/ci.yml` runs `pip install ".[dev]"`, which
resolves the **newest** admissible version on every matrix leg, so no gate ever installs the floor.

The consequence is not a red CI leg. It is that **the declared floor is a claim no gate checks**,
and something already shipped disappears under it. The casualty is not R6.5's `ecdf` oracle, which
an earlier draft named: `ecdf` and `CensoredData` predate `1.14` and work at the floor. It is
`scipy.stats.chatterjeexi`. `tests/test_r_cross_implementation.py:268` carries the reason string
naming the version it needs and guards the call with `hasattr` at `:270` and `:286`, so below that
version a tier-4 cross-implementation oracle **silently skips instead of failing** -
the exact "skip, never pass with mocked values" boundary `AGENTS.md` §7 draws, sitting on the wrong
side of a version bound nothing tests. R6.8 raises the floor rather than testing at it, which needs
no new environment.

### R6.0.11 `scripts/acceptance.sh` does not exit 0, and has not for some time

Measured during implementation, not during planning, which is the point: an earlier draft of
this spec listed `bash scripts/acceptance.sh` under Verification as a gate the phase must keep
green. It is **already red**, and was red before this phase touched anything.

**7 tests fail from an unrelated working directory** and pass from the repository:
3 in `tests/test_nesting.py`, 1 in `tests/test_reuse_completeness.py`, 3 in
`tests/test_windows_not_interpolated.py`. The cause is one mechanism.
`Job.include` (`core/job.py:329`) resolves a logical `JOB_ID` against the **current working
directory**, so from `/tmp` it raises
`FileNotFoundError: include not found: 't2star_q1_070423' resolved to '/tmp/t2star_q1_070423'`.

Verified as pre-existing rather than introduced: the same 7 fail under the ORIGINAL fast
selector from an unrelated cwd, so neither the marker axis nor the `real`-in-`FAST` change is
responsible.

`conftest.py:38-41` already names this class exactly - "six tests failed under
`cd /tmp && pytest <repo>/tests`" - and the `in_repo` fixture was the fix, applied to five
modules. These seven never got it. The same docstring records why that matters: "The
acceptance script pinned the cwd itself, so the gate hid the gap instead of catching it."
Once the script stopped pinning the cwd, the gap became visible and nothing was watching.

**Not fixed in this phase, and the reason is a real fork.** Adding `in_repo` to the seven
makes the script green by pinning the cwd again, which is what the fixture's own docstring
says hid the gap the first time. Making them genuinely cwd-independent is the "signature
change across ~17 call sites" `conftest.py:47-51` already flags as not small. Which of those
is right is a decision about the installability contract, not about test architecture, so it
is recorded here and left to Sera.

---

## R6.1 - Publish the audit, fix what it found, and add no liveness guard

The measurement in R6.0.1 and the three dead controls in R6.0.2 are the deliverable. They live in
this spec, which is dated, rather than in a document that would go stale silently.

**What is fixed.**

1. `tests/test_check_ledger.py:98` is rewritten to call `check_ledger` and assert the seed derived
   by the shipped code is stable across processes, so that changing `check_ledger.py:391` makes it
   fail. The current version cannot.
2. `tests/test_checks_statistics.py:171` keeps its eq (16) to eq (4) reduction and **gains no new
   pin**. An earlier draft added one "so the divisor is asserted somewhere". That reason is false:
   `gamma_hat`'s divisor is already pinned non-circularly and directly against the published values
   at `tests/test_checks_published_values.py:73-84`, in both branches. Verified by mutation -
   changing the `GAMMA_COMPLETE` divisor turns 6 tests red and the `GAMMA_TRUNCATED` divisor turns 4
   red, while `test_eq16_reduces_to_eq4_for_a_single_segment` stays green in both cases. So the
   circularity at `:171` is real but **costs zero detection**, and adding a third transcription of
   the published-values file is what `AGENTS.md` section 7's indexing rule pushes against. The circularity is recorded
   in R6.0.2 as a weak test, not repaired with a redundant one.
3. `tests/test_within_calibration_builder.py:88` gains an assertion against a hand-computed
   occupancy rather than only against the sibling code path.
4. The one **B** row, `tests/test_checks_cvm.py::test_the_reviewers_verdict_flip_case_now_rejects`,
   is **deleted, not documented**. Its stated mechanism would be wrong: `cvm_limiting_cdf` never
   evaluates the series at 794.4, because `cvm_cramer_von_mises.py:137-145` replaces `z` with 1.0
   above `_SERIES_Z_MAX = 5.0` and returns a hardcoded 1.0, so the return is a guard-clause branch,
   not a floating-point limit. It is also redundant to
   `test_the_p_value_is_monotone_across_the_whole_range_including_the_tail` at `:170` under every
   mutation tried. **Replaced by** a test that runs `cvm.run(..., CALIB_ASYMPTOTIC)` on a segment
   giving `observed > 5.0` and asserts both `p_value == 0.0` and that the `p_saturated` note is
   attached, which nothing currently asserts. R6.9's deletion discipline applies and its evidence is
   recorded at the checkpoint.

**No liveness guard is added, and the reason is stated rather than left as an omission.** The
predicate "this test makes a statistical claim" is a judgement, not a decidable property, so no
guard can enforce the oracle rule as written. A guard over a decidable proxy such as "every test in
these modules has a non-empty docstring" would enforce something other than the rule and would be a
test written to satisfy an architecture, which is the failure mode this phase exists to remove. The
rule stays where it is enforceable: `AGENTS.md` section 7's oracle rule, `CONTRIBUTING.md`, and review.

**Acceptance.**

1. The classification rule is in this file (R6.0.1), stated so a second rater can disagree with it,
   together with the four aggregate counts. **No per-test table is published**: the rule plus the
   named exceptions is what a second rater needs, and a 423-row table in a spec is a status table of
   the kind `AGENTS.md` §8 says goes stale. An earlier draft's acceptance criterion claimed a table
   was present when only the aggregates were, and that claim is withdrawn rather than satisfied.
2. Each of the three dead controls fails when the code it names is mutated, demonstrated at the
   checkpoint rather than asserted.
3. The B row is gone and the `p_saturated` note has a test.
4. No new guard over the oracle rule, with the reason recorded.
5. Collect delta: **+0 to +1**. Files: **4**.

*Derivation.* Two rewrites change no collection; the B deletion is -1 and its replacement +1, net
zero; the occupancy pin is +1 at most. Fix 2 adds nothing, per the mutation evidence above.

**Ordering constraint.** R6.9's deletion discipline governs the only deletion in this phase, which
happens here. The discipline therefore lands **at this checkpoint, before the deletion**, not at
CHECKPOINT 6.8 where R6.9 otherwise sits. R6.9's requirement text is unchanged; only its landing
point moves.

**Done when** the audit is published, the three controls can fail, and the single B is resolved by
deletion rather than by a docstring naming a mechanism the code does not use.

---

## R6.2 - The tier axis: seven markers, a selector, and a completeness guard

`tests/` stays flat. `quebraplan.md` 5.1's six directories are declined on R6.0.6's evidence and the
tier is adopted as a marker axis instead.

**The two axes are orthogonal and the spec says so.** `unit`, `properties`, `statistical`,
`integration`, `validation`, `regression` and `policy` classify the **question a test answers**.
`slow`, `heavy`, `real` and `r` classify its **cost or requirement**. A test can be `statistical`
and `slow`. Without that sentence "exactly one tier marker" is not well defined.

The seven, declared in `pyproject.toml` beside the existing four:

```
"unit: does this function do the small thing it claims"
"properties: mathematical invariants under generated inputs"
"statistical: is the estimator correct, against a named oracle"
"integration: does the machinery wire up"
"validation: does an end-to-end job reach the right verdict on known truth"
"regression: did a refactor move a published number"
"policy: does the source tree obey a rule we wrote down"
```

`policy` is the seventh tier `quebraplan.md` 5.1 does not have, added on measurement. Its members
are the seven files whose oracle is a written rule checked by AST or filesystem scan:
`test_bench_isolation.py`, `test_job_manifest.py`, `test_windows_not_interpolated.py`,
`test_contract_boundary.py`, `test_style_baseline.py`, `test_data_manifest.py`,
`test_artifact_guard.py`.

**Applied** as module-level `pytestmark` where a file is single-tier and per test where it is not.
`test_windows_carve.py` and `test_checks_statistics.py` are known to be mixed.
`--strict-markers` is already on, so a typo fails collection.

**A selector, or the axis is a taxonomy built to fill.** `Makefile` gains one target per tier
(`make tier-unit` and so on) and a `make tiers` that reports the count in each. Nothing in `make
check` selects on the tier axis; the cost axis keeps that job.

**The completeness guard.** One test asserting every collected item carries exactly one tier marker,
with a positive control. This is decidable and total, unlike the oracle rule R6.1 declines to guard:
"does this item carry one of these seven markers" enforces the rule itself, whereas any regex over a
docstring enforces the presence of a word.

**`regression` is declared with zero members and the guard permits it.** Its oracle does not exist
(no tags, no `published/`) and populating it asks the embargo question in R6.0.6. `Makefile:54-57`
records that a target reporting "selected nothing" as success is how an unrun tier rots unnoticed,
so the spec states why this one is allowed to be empty: the tier is declared so the marker exists
the day a public record ships, and the emptiness is a recorded decision rather than an accident.

**Acceptance.**

1. Seven tier markers declared, and the orthogonality of the tier and cost axes stated in
   `pyproject.toml` and in `AGENTS.md` §7.
2. `pytest -m "unit or properties or statistical or integration or validation or regression or
   policy"` selects **535** items, that is the whole suite.
3. A test carrying no tier marker, or two, fails the completeness guard, and the guard's positive
   control demonstrates it can fail.
4. `regression` selects zero and that is recorded as intended, not as a failure.
5. `AGENTS.md` section 7 and `CONTRIBUTING.md` record the decision as **declined in favour of a marker
   axis**, not as "planned and not built". `CONTRIBUTING.md`'s "the six-tier layout described in
   `AGENTS.md`" is a wrong locator today, since `AGENTS.md` describes no such layout and points at
   `quebraplan.md`; both halves are corrected.
6. Collect delta: **+1 to +2**. Files: **1 new, roughly 42 edited**.

*Derivation.* The guard is one test plus one control. The file count is the 40 test modules plus
`pyproject.toml`, `Makefile`, `AGENTS.md` and `CONTRIBUTING.md`, less those needing no per-test
decoration.

**Known cost, stated because a collect delta hides it.** Decorating 40 files, some per test, is a
several-hundred-line diff that produces one collected test. It is cheap in the §9 collect column and
expensive in wall clock, which is why CHECKPOINT 6.2b carries it alone.

**Done when** every collected item carries exactly one tier marker, a selector exists per tier, and
the guard fails on a planted violation.

---

## R6.3 - The cost markers, and why there is no private-data guard

**`real` gets its 9 members**: the four tests in `tests/test_data_manifest.py` that read the tree,
and the five parametrised items of
`tests/test_windows_carve.py::test_the_two_job_configurations_agree_on_the_real_records`. The two
`test_data_manifest.py` tests that monkeypatch `PRIVATE_ROOT` to a `tmp_path` are **not** marked;
they are synthetic and must keep running in CI. Markers do not affect direct calls, so those
controls keep working.

**Every marked test keeps its `pytest.skip`.** The marker and the skip are two belts and the
existing one is not removed.

**`slow`, `heavy` and `r` gain no members**, with the reason stated for each rather than leaving
empty markers looking like an oversight. `r` is `quebraplan.md` Phase 6's, and this spec states
explicitly that "no members, reason given" must not be read as "R is covered": the path past
`c3_serial_copula._invoke_rscript` has never executed here.

**`real` stays inside the local `FAST` selector.** `Makefile:4` becomes
`FAST := -m "not slow and not heavy and not r"`. Excluding `real` would cost coverage only on the
one machine where those tests do more than skip, and would move manifest integrity from a gate onto
a discipline promise, which `AGENTS.md` §9 is a whole paragraph about. CI is unaffected because CI
has no tree.

**The selector is spelled literally in THREE places and this requirement edits all of them.**
Measured: `Makefile:4`, `scripts/check_ci.sh:80` and `scripts/acceptance.sh:97` each contain
`-m "not slow and not heavy and not real and not r"` as a literal. Changing only the Makefile makes
both scripts run a **different** selector from `make test`, which silently falsifies
`scripts/check_ci.sh:70`'s claim that "every tool runs from the repository root with the same
arguments the Makefile uses, so a disagreement between this and `make check` is the environment and
nothing else". `check_ci.sh` runs from the repository, where the private tree exists, so the
divergence is live rather than theoretical. **Preferred fix: define the selector once and have all
three read it**, so the next change cannot desynchronise them. Editing three literals in step is
acceptable only if the single-definition route is impractical, and the spec says which was done.

**Five further edits this implies, which are easy to miss.** `Makefile:38`'s "everything a laptop
can run without private data" stops describing `test-all` once neither selector is a subset of the
other; `Makefile:46-47` and `Makefile:54` carry the "both selectors match no test, so both exit 5"
note, which becomes false for `test-real` once `real` has 9 members and for the `regression` half
once the marker is declared; `pyproject.toml`'s `real` marker text "never runs in CI" becomes
"never has data in CI"; and `.github/workflows/ci.yml:40-42`'s "no test carries the markers the fast
selector names, so it excludes nothing" becomes false. That last one is replaced by the statement
actually owed: nine tests carry `real`, `real` is deliberately **not** excluded from the fast
selector, and the per-test `pytest.skip` on an absent path remains the mechanism that keeps CI
green.

**No private-data guard is built.** A guard over the literal `data/real_private/` cannot
discriminate: the string appears in `tests/test_windows_not_interpolated.py`,
`tests/test_promote_run.py`, `tests/test_data_unavailable.py` and `tests/test_data_manifest.py` in
paths that are built and inspected but never read, so once the whitelist covers them the guard
guards nothing. A runtime fixture was considered and declined for consistency with R6.1: the
enforcement is that **CI has no private tree at all**, which `.github/workflows/ci.yml:38` already
states and forbids changing. `tests/test_artifact_guard.py:273-277`, which globs gitignored
`output/` trees and defines no `PRIVATE_ROOT`, is the concrete case a proxy detector would have
missed.

**Acceptance.**

1. `pytest -m real` selects exactly 9 items; `make test-real` exits 0 with the tree present and
   skips without it, rather than exiting 5.
2. `pytest -m "not slow and not heavy and not r"` selects 535 here and 535 in CI, where the 9 skip.
3. `slow`, `heavy` and `r` select nothing, each with its reason in the spec.
4. All four documentation edits above land in the same checkpoint as the marker change.
5. Collect delta: **+0**. Files: **9**.

*Derivation.* Markers and selector changes alter no collection. Files: the three literal
selector sites (`Makefile`, `scripts/check_ci.sh`, `scripts/acceptance.sh`), `pyproject.toml`,
`.github/workflows/ci.yml`, and the two test modules carrying the `real` marker, plus the two
Makefile comment blocks if they land separately.

**Done when** the private tree is declared by a marker, still guarded by skips, still unreachable in
CI, and no document asserts something the change made false.

---

## R6.4 - The generator question, answered before anything is built on it

R6.0.5 carries the measurement. **No new generator subsystem, and no `src/quebra/synth/`.**

Promotion into `src/quebra` is refused: it would put a Monte Carlo study inside the wheel and inside
the identity closure and make it importable by a figure, inverting the reason
`tests/test_bench_isolation.py` exists. A clean-room generator is refused: it is a second
implementation of the science, and validating it means comparing against the bench, a circular
oracle, or against the estimators it is meant to be an oracle for, which is worse.

**What is built instead, in this order.**

1. **The carve-to-duration-law oracle, over a fixed sequence of seeds, with NO committed fixture.**
   `jobs/bench/arms.py:331-347` draws iid `standard_normal` reads and thresholds them, so carved
   run lengths are geometric with `p = 1 - IN_SPEC_P = 0.5` and **no small-`dt` approximation at
   all**. This closes metric record to carve to duration law end to end, which Arms A, D and E
   cannot, because they emit `Segment` directly and never touch a threshold.

   **An earlier draft committed a CSV under `src/quebra/_fixtures/` for this and that was wrong.**
   The geometric law is a statement about a *distribution*; a committed file is *one realisation*
   of it, and its byte-identity - which nothing in the phase's gate list checks - is precisely what
   stops the seed being varied. A single draw cannot separate a correct carve from a subtly wrong
   one.

   Instead the test imports `jobs.bench.arms.arm_b` directly, which `tests/` is permitted to do and
   `tests/test_bench_uses_real_carve.py:21` already does, and draws from **a fixed tuple of seeds
   written out in the test module**, following the idiom at `tests/test_tier3_calibration.py:93`
   ("One fixed seed per cell, written out rather than derived, so a rerun reproduces exactly").
   Zero new files and zero wheel surface.

   **The run lengths from every seed are POOLED into one sample and asserted once.** Asserting
   per seed would create one weak test per seed and a multiplicity problem - at alpha = 0.05 roughly
   one in twenty fails by chance - which is the flakiness `AGENTS.md` §4's "state the aggregation
   and the multiplicity before reading a verdict off it" exists to prevent. Pooling gives one test
   with the full sample behind it and no multiplicity to correct. The assertion message carries the
   per-seed observed mean run length against `1/p`, so a failure names the anomalous seed without a
   re-run.

   **The redistributable-fixture argument is already satisfied elsewhere** and is not a reason to
   commit a second CSV: `src/quebra/_fixtures/ramsey_synthetic.csv` ships in the wheel today and
   `tests/test_packaged_fixtures.py` asserts a reviewer with no private data reaches a real `t2star`
   result through it.
2. **One `tlf` test, demoted below the fixture**, written against the **sampled** truths from
   R6.0.5: `mean_dwell -> dt / p01` and `dwell_cv -> sqrt(1 - p01)`, with `lambda = mu` fixed so
   `switching_rate_per_hour` has a single rate to compare to. It requires a noise-free two-level
   draw, because `predict` is a MAP on value alone and one misassigned read splits a true run into
   three, so the oracle needs misassignment much smaller than `p01`. **The restriction is stated as
   a restriction**: with noise there is no closed form, and the test is then honestly a unit test of
   `tlf.py:139-197`'s run-length bookkeeping, label-ordering map, trim and CV formula rather than
   simulation-truth validation of an RTN estimator.

**The isolation contract is narrowed, by comment rather than by test.** `tests/` is not in
`PIPELINE_PACKAGES` (`tests/test_bench_isolation.py:38-47`), so a test importing the bench is
permitted and `tests/test_bench_uses_real_carve.py:21` already does. That permission is currently an
**omission, not a decision**: someone adding `"tests"` to the tuple would break that file while
believing they were tightening a contract. The reason goes in a comment beside the tuple, where the
person editing it will read it. A test asserting `"tests" not in PIPELINE_PACKAGES` is declined: it
would assert what the code currently is, which `AGENTS.md` section 7's indexing rule bans.

**Left as open questions**, recorded in `spec/quebraplan.md` §7 rather than built:

- Whether read-level long-memory noise (1/f), unlike the short-memory AR(1) of Arm C, produces
  duration-level dependence the battery can detect. It is a bench arm and a finding, not a test
  oracle, and Arm E already supplies duration-level dependence with analytic ground truth.
- The shared median-spacing defect in `tlf.py:134` and `allan.py:20-25`.
- `allan.py:141-142` computes `fractional_adev` by dividing by `carrier_hz`, the mean of
  `qubit_frequency_hz`, while mode `"fractional"` at `:63` divides by `f0_hz`, the mean of
  `delta_hz`. **Two different denominators under one name**, which is the unit-suffix bug class
  `AGENTS.md` §3 names as the costly one here. Recorded, not fixed, because fixing it changes a
  shipped figure.

**Acceptance.**

1. No new generator module anywhere in `src/quebra/` or `jobs/`, and **no new committed fixture**.
2. The carve-law test draws from a written-out seed tuple, carves each draw with
   `analyzers/windows.py`, pools the run lengths, and asserts the geometric law once with the
   aggregation and the sample size stated in the assertion message.
3. The `tlf` test asserts `dt / p01` and `sqrt(1 - p01)`, not `1 / lambda` and 1, and its docstring
   states the noise-free restriction and why.
4. The isolation contract's scope is explained in a comment, and no test is added that pins a
   constant's current value.
5. The three open questions are in `spec/quebraplan.md` §7 with their measured reasons.
6. Collect delta: **+2 to +4**. Files: **1**.

**Landed at +6 across 2 files, and the deviation is recorded rather than absorbed.** The carve
law and the `tlf` dwell law are separate subjects with separate oracles, so `AGENTS.md` §7's
index puts them in separate files: `tests/test_carve_duration_law.py` (+2) and
`tests/test_tlf_dwell_law.py` (+4). The envelope assumed one file because an earlier draft
treated the `tlf` oracle as a single assertion; it is four, because the sampled law has a mean
and a CV per state and the two states are no longer interchangeable. 1.5x the stated ceiling,
inside the §9 2x STOP.

*Derivation.* Carve law: 1 pooled test. `tlf`: 1 to 3, being mean dwell, CV, and optionally
switching rate - noting per R6.0.5 that at `lambda = mu` the rate assertion is the reciprocal of the
dwell assertion and not independent evidence, so it is optional for that reason. Files: one new test
module. `scripts/make_fixtures.py` and `src/quebra/_fixtures/` are untouched.

**Done when** the carve-to-duration-law path has an exact oracle, `tlf`'s dwell statistics have a
correct sampled one, and nothing new is imported by any pipeline package.

---

## R6.5 - Kaplan-Meier: the oracle gap `quebraplan.md` Phase 5 does not name

**This is the phase.** R6.0.4 carries the measurement.

One new file, `tests/test_kaplan_meier.py`, indexed by subject per `AGENTS.md` section 7's indexing rule, with the
oracle named per test because the oracles differ across the file.

**Analytic.**

1. **No censoring reduces to the empirical survival function.** With every `death_observed` true,
   the product-limit estimate equals `1 - ECDF` exactly.
2. **A hand-computed censored case.** Six observations, deaths and censorings interleaved, `S(t)`
   worked out by hand in the docstring with the risk sets shown. This catches a mis-stepped risk
   set, which the ECDF reduction cannot see.
3. **The risk set at a tie includes the censored window.** A death and a censoring at the same
   recorded time leave the censored observation in that time's risk set.
4. **The estimate is invariant to input order.** This is the property `kaplan_meier.py:286`'s sort
   is there to provide, and it stresses the tie block.
5. **The median definition.** Smallest `t` with `S(t) <= 0.5`, asserted where `S` touches 0.5
   exactly, which is where `<=` and `<` differ.
6. **A consumed risk set, asserted as a rendering contract rather than as a correctness oracle.**
   The `inf` Greenwood term and the resulting `NaN` band are what `specvalidity08.md` defends as the
   honest rendering. Stated as "the band is `NaN` there" this is a positive control that cannot
   fail, because `_loglog_band` returns `NaN` for every excluded point regardless. The test
   therefore asserts the **discriminating** pair: that `greenwood[-1]` is `inf` where the risk set
   is consumed and finite at the preceding step, and that the `NaN` set of the band is exactly
   `{S = 1} u {S = 0} u {greenwood = inf}` and not larger. A change that made the band `NaN`
   everywhere fails it.

**Not written: a test that fails when the `lexsort` key is dropped.** Measured: the sort is a no-op
for the output. `kaplan_meier.py:298-316` computes `n_j = n_total - idx` at the tie block's first
index and `deaths` over the whole block, so both are invariant to ordering inside a tie, and
`censored_t = t[~observed]` selects equal values. **The lexsort's redundancy is a finding recorded
here, not a test**, because a test asserting it would be another positive control that cannot fail.
The code comment at `:283-286` overstates what the sort does and is corrected.

**Cross-implementation, no new dependency and no R.**

7. **The product-limit estimate against `scipy.stats.ecdf` with `CensoredData`.** Verified available
   and correct on scipy 1.17.1.
8. **The log-log band against `confidence_interval(method="log-log")`**, which is the exponential
   Greenwood interval `_loglog_band` computes.

**Two implementation facts the tests must respect or be written wrong.**

- **The two grids differ by a prepended row, and an elementwise comparison misaligns every point.**
  Measured on three uncensored deaths at t = 1, 2, 3: `run` returns `time_min = [0, 1, 2, 3]` with
  `survival = [1, 2/3, 1/3, 0]`, while `ecdf(...).sf` returns `quantiles = [1, 2, 3]` with
  `probabilities = [2/3, 1/3, 0]`. `run` prepends a `t = 0`, `S = 1` row that scipy has no
  counterpart for. Separately, `run` appends a point only where `deaths > 0` (`:305-315`), so
  `time_min` omits censoring-only times while `ecdf` steps at every distinct observation time.
  **The comparison drops KM's `t = 0` row, forms the union grid, and evaluates both as step
  functions on it**, never elementwise.
- `_loglog_band` (`:368-377`) returns `NaN` where `S = 1`, where `S = 0` and where Greenwood is
  infinite, and clips to [0, 1]. Verified: on the case above the band is `NaN` at both endpoints and
  finite between. scipy's interval does not use the same exclusion set, so **the requirement states
  the rule as "compare where both are finite" and names the excluded points**, rather than
  discovering the reconciliation at the checkpoint.

**Simulation truth.**

9. **Band coverage at nominal.** Exponential durations with a known `S(t)`, right-censored at a fixed
   time, over enough replicates that the Monte Carlo standard error is stated in the assertion
   message. A wide band with **no direction claim**, following
   `tests/test_tier3_calibration.py`, whose docstring states why a tight band would encode one
   distribution's miss as correct.

**The carve-to-estimator handoff.**

10. **`make_inputs_from_windows` on a carved synthetic trace.** Durations are the window table's
    `duration_s`, only `BIRTH_UP_CROSSING` windows survive, and `n_unobserved_birth_dropped` counts
    the rest. This is the composition 5.1's validation-jobs tier would test, at one test rather than
    a job, a fixture and a sink.
11. **A zero-duration window, asserted as the CENSORED case it actually is.** `specvalidity08.md`
    measured 2 of 418 windows with `duration_s == 0.0` on a real record, and records that both died
    at `gap_start` and `scan_end`. An earlier draft pinned `S(0) < 1` as the consequence. That is
    **unreachable from a carve**: `windows.py:419-422` sets `t_death_s = t[e]` for a down-crossing
    death and `t[e-1]` otherwise, with `e > s` always, so an *observed* death has
    `duration_s > 0` on any strictly increasing read clock. A zero-duration window can only be
    censored, and `kaplan_meier.py:305`'s `if deaths > 0` appends nothing for it, leaving
    `S(0) == 1.0`. The test therefore asserts, on a synthetic carve with one single-read window
    dying at a gap: `n_zero_duration == 1`, `survival[0] == 1.0` with `time_min[0] == 0.0`
    unchanged, and a censor mark at `(0.0, 1.0)` via `censor_time_min` / `censor_survival`.
    If a zero-duration *observed* death is ever wanted it must be hand-constructed around the carve,
    and then `time_min` carries a duplicate `0.0`, which the scipy comparison in oracles 7 and 8
    must handle because `ecdf`'s quantiles are unique.

**The crude estimator versus Kaplan-Meier: three axes, not two.**
`kaplan_meier.py:7-14` names two differences. There is a third.
`within_calibration_compute._window_survival` returns `P(W >= t)` while `run` is right-continuous,
so **the two differ by one step even at zero censoring on identical inputs**, and the crude curve
never reaches 0. Separately, `reliability_band.py` feeds `_window_survival` only `~censored` windows
and does **not** filter on `birth_type`, while `make_inputs_from_windows` keeps censored
observations and drops non-up-crossing births. **All three are reported as measured numbers.**
Changing which estimator the within-calibration panel draws is **not** in this phase: that is a
product change, and `AGENTS.md` §11 puts it outside a test-architecture spec.

**MTBF.** Two tests, not four tiers: the interval arithmetic against `np.diff` on a hand-written
**unsorted** series, since `mtbf.run` sorts before diffing (`mtbf.py:38`) and a sorted input would
not exercise that; and the fewer-than-two-events raise. MTBF is a mean, not an estimator of a
distribution, so a four-tier validation would apply a tier scheme to a subject that does not have
one. Recorded, not fixed: `mtbf.stats["mean_s"]` is a pooled mean over an entire calibration log
with no factor named, which is the class `AGENTS.md` §4's first rule is about, and `stats["std_s"]`
is `np.std` with `ddof=0`, a population SD, undocumented.

**Kaplan-Meier gets its rows in `analyzers/instrument_validation.py`.** R6.0.3 identifies the gap and
this requirement produces exactly the evidence its four tiers describe, so leaving the artifact
silent on KM would leave a known gap open in the table that exists to prevent it. The rows reuse
`TierRow` and the `TIER_*` verdicts and add no second tier vocabulary.

**Acceptance.**

1. Every test names its oracle in its name or first docstring line, and each analytic oracle is
   computed in the test rather than copied from a run of the code under test.
2. A deliberately broken product-limit loop fails the scipy comparison. The positive control is
   mandatory: `AGENTS.md` §4 records the carve control that compared `reference` to `reference` and
   passed with a broken carve.
3. The excluded-point rule for the band comparison is stated in the requirement and in the test
   docstring.
4. The coverage test states its Monte Carlo standard error in the assertion message and makes no
   direction claim.
5. The three crude-versus-KM axes are reported as numbers, and no panel artifact changes.
6. `instrument_validation` carries KM rows, and no row claims evidence that does not exist.
7. Collect delta: **+30 to +38** across **2 new and 4 edited files**, carried **per checkpoint**, not per requirement: 6.5a
   analytic **+11 to +14**, 6.5b cross-implementation **+9 to +12**, 6.5c simulation and handoff
   **+6 to +8**, 6.5d MTBF and the ledger rows **+4**.

   **Revised upward during implementation, with the reason, rather than trimmed to fit.** The
   original envelope (+6..+8, +3..+4, +3..+4, +2) assumed the cross-check would parametrise over
   "two or three cases". It parametrises over five censoring SHAPES - none, interleaved with a
   death/censoring tie, censoring-first, heavily censored, tied deaths - across two tests, which
   is 10 collected where the envelope allowed 4. Each shape exercises a structurally different
   path and dropping any loses a case, so the envelope was wrong rather than the work. 6.5b
   landed at 2.75x the original and halted the phase under `AGENTS.md` section 9; the overrun was
   presented and accepted, and the numbers above are the accepted ones. **The 2x STOP applies at each checkpoint**,
   so the requirement cannot absorb an overrun of +104 while still reporting itself inside a
   requirement-level envelope. Files: **2 new, 2 edited**.

*Derivation.* Eleven named oracles plus two MTBF tests is 13 items, and the broken-estimator
positive control at acceptance 2 is mandatory rather than optional, so the **floor is 14, not 10**.
An earlier draft wrote +10, which was the count with no control and no parametrisation - a floor the
requirement's own acceptance criteria make unreachable. The ceiling of 18 adds parametrisation on
three of them (the ECDF reduction over sizes, the scipy agreement over censoring patterns, order
invariance over permutations).

**Done when** Kaplan-Meier has analytic, cross-implementation and simulation-truth oracles, each
naming its source, and the estimator the within-calibration tier depends on is no longer
unvalidated.

---

## R6.6 - Properties, with `hypothesis`

`hypothesis` is a declared dev dependency with zero imports. Adopting it removes it from
`[tool.deptry.per_rule_ignores]` `DEP002`, which R6.5's sibling requirement in the plan overlooked
and this one lists.

**Three of 5.4's five property classes are declined, with reasons.** Cumulative hazard
non-decreasing has no subject (R6.0.9). Permutation invariance is already covered on the real
permutation machinery by `tests/test_checks_statistics.py`. Shape and type preservation is what the
typed dataclasses and `make types` do, and a property test asserting an array's dtype restates the
annotation.

**Adopted for one subject, `kaplan_meier.run`**, because a hand-rolled product-limit loop with a
tie sort and a while loop over tied times has an input space that hand-picked cases sample thinly,
and that loop is exactly where R6.5's fixed cases stop. Three properties:

1. `survival` is non-increasing and lies in [0, 1].
2. Where both are finite, `band_lower <= survival <= band_upper`.
3. **Reduction to `1 - ECDF` under no censoring, at every death time**, as a property over generated
   inputs rather than the single fixed case in R6.5.

Properties 1 and 2 are close to tautologies of the expression as written and are kept as cheap
regression cover, not as the requirement's justification. Property 3 and R6.5's order invariance are
what exercise the tie block.

**Not written:** "adding a censored observation later than every death does not change `S(t)` below
that time". It is **false**. A subject censored after the last death is at risk at every death, so
`n_j` rises at each: deaths at t = 1 and t = 2 with n = 2 give `S(1) = 0.5`, and adding a censored
observation at t = 3 gives `S(1) = 2/3`. Recorded so it is not reintroduced as an obvious-looking
invariant.

**The reproducibility cost, stated because this repository's culture is reproducibility.**
`hypothesis` introduces nondeterminism into a suite where `checks/_permutation.block_permutations`
raises on a `None` rng because defaulting to OS entropy made p-values irreproducible while the run
identity stayed unchanged. The mitigation is a profile registered in the root `conftest.py` with
**`derandomize=True`** and the example database disabled, so each test's example set is a
deterministic function of its source. That is a requirement, not a suggestion.

**Acceptance.**

1. Three properties on one subject, in `tests/test_kaplan_meier.py` beside the oracle tests, because
   the subject is one and the constructor is shared.
2. A profile in `conftest.py` with `derandomize=True`, loaded unconditionally, its reason stated as
   a contract rather than as history.
3. Two consecutive runs produce identical example counts.
4. `hypothesis` leaves the `DEP002` ignore list and `make deps` exits 0.
5. No property asserts a statistical validity condition; that is R6.5's job.
6. `scripts/acceptance.sh` installs `hypothesis`. Measured: `acceptance.sh:64` installs only
   `pytest` into its clean venv and then runs the suite with the repository's root `conftest.py`
   loaded, so an unconditional `import hypothesis` there makes collection error and the script
   exit 1. `scripts/check_ci.sh` is unaffected because it installs `.[dev]`.
7. Collect delta: **+3 to +4**. Files: **4** (one test module, `conftest.py`, `pyproject.toml`,
   `scripts/acceptance.sh`).

**Done when** three properties hold under generated input, deterministically, and the two declined
classes and the one false invariant are recorded rather than silently absent.

---

## R6.7 - The runner contract, scoped to the gaps

R6.0.8 carries the table. Four of 5.5's six invariants are covered; this requirement delivers what
is not, and does not rewrite over 26 working identity tests.

`tests/test_dag_contract.py`:

1. **The topological order respects every edge.** Build a diamond and a fan-in, resolve, and assert
   every node appears after all of its `LocalRef` inputs. Reversing an edge in `_toposort` turns it
   red.
2. **The order is deterministic** across repeated builds.
3. **A node that reaches no sink is never executed and never appears in `pipeline_steps`.** This is
   the reachable, untested, lazy-DAG property R6.0.8 identifies and neither source plan named.
4. **A dangling `LocalRef` is refused at registration**, and a forward reference can therefore no
   longer build a cycle. This is a property, not one attempted construction, because item 5 makes
   it one.

**The validation hole R6.0.8 measured is closed here, and it is the only source change in this
requirement.** `_register_node`'s `LocalRef` branch (`core/job.py:367-372`) gains a membership
check:

5. `if input_ref.node_id not in self.dag: raise ValueError(...)`, naming the offending id and the
   node being registered. This makes "registration order is a topological order" true in fact,
   converts item 4 from an anecdote into an invariant, and replaces the raw `KeyError` from
   `runner.py:111` with a named error at the point of the mistake. Measured cost 50 ns per input
   ref at build time; all 13 shipped jobs stay green.

**Reuse driven end to end.** `tests/test_reuse_gate.py` exercises the pure helper with
`is_tree_clean` monkeypatched. Three tests drive `run_job` twice for real: an identity moved because
reached code changed, an identity moved because input content changed, and a dirty tree. **A
negative control in which reuse does fire already exists** at `tests/test_reuse_completeness.py:296`
and is cited rather than rebuilt.

**`runner.py:110`'s message is not changed**, for the single surviving reason in R6.0.8: after item
5 the branch cannot be reached from a job file at all. Nothing duplicates `tests/test_nesting.py`'s
include-cycle coverage.

**Acceptance.**

1. `_toposort` has a test asserting a valid, deterministic order. It fails under a named code
   mutation: reversing the `ordered.append` position so the post-order becomes a pre-order.
2. An unreachable node is asserted absent from execution and from `pipeline_steps`, and the
   identity and dataset-resolution records are asserted to exclude it too.
3. A `LocalRef` naming an unregistered node id raises a named `ValueError` at `job.step`, not a
   `KeyError` later, and the forward-reference cycle from R6.0.8 is refused at registration.
4. **NOT MET, and recorded as owed rather than carried as satisfied.** The three tests that
   drive `run_job` twice for real - an identity moved by reached code, an identity moved by
   input content, and a dirty tree - were not written. Measured: no test anywhere drives
   `run_job` twice and asserts a REFUSAL under a mismatch, and every end-to-end path
   monkeypatches `is_tree_clean` to `True`, so the gate's refusal branches are exercised only
   at the pure helper in `tests/test_reuse_gate.py`. The existing negative control at
   `tests/test_reuse_completeness.py:296` shows reuse firing, which is the other half. This
   is why R6.7 landed +5 against a stated +7. It is listed in "Not in this phase".
5. No test asserts a chain from `runner.py:110`.
6. Collect delta: **+7**. Files: **2** (`tests/test_dag_contract.py`, `core/job.py`).

*Derivation.* Four DAG tests (order, determinism, unreachable node, dangling ref refused), the
mutation control on the order test, and two end-to-end reuse tests, reusing the existing negative
control and the existing diamond coverage in `tests/test_nesting.py`.

**Done when** `_toposort` is tested, a dangling reference is refused where it is made rather than
where it is dereferenced, unreachable nodes are pinned as unexecuted, and every reuse invariant has
an end-to-end counterpart to its helper-level unit test.

---

## R6.8 - Coverage reported and not gated, and the `scipy` floor raised

`quebraplan.md` 5.6 is right on its central point and this spec adopts it. Two of its four proposed
numbers happen to be close to the measurement and the closeness is a coincidence worth recording,
because it is what makes the case:

| 5.6's proposal | Measured at CHECKPOINT 6.8 |
|---|---|
| roughly 70% overall | **70%**, 6522 statements, 1961 missed |
| roughly 90% on identity hashing | `identity.py` 100%, `closure.py` 94%, `provenance.py` 99% |
| roughly 90% on estimators | `kaplan_meier.py` 79%, `mtbf.py` 80%, `allan.py` 22%, `fidelity.py` 22% |
| 0% expected on `jobs/active/` | not measurable as written: `--cov=quebra` cannot see `jobs/` |

From `make cov`: selector `not slow and not heavy and not r`, private tree PRESENT, 589 passed and
2 skipped. An earlier draft of this table read 69% overall, 6486 statements, `kaplan_meier.py` 76%
and `mtbf.py` 66%. Those were a planning agent's figures that were never re-run, and R6.5 moved two
of them. Acceptance 3 below exists to stop exactly that number entering a permanent file, so they
are replaced rather than carried.

**And the number that made the argument, in the tense it is now true in: `kaplan_meier.py` was 76%
covered while the only assertion anywhere about its output was `len(curve.time_min) > 1`.** R6.5 is
what closed it, and what happened to the number is the argument for reporting rather than gating.
Thirty-four Kaplan-Meier tests - an analytic hand-derived oracle, a scipy cross-implementation, a
band coverage measurement, four algebraic properties - moved coverage from 76% to **79%**. Three
points. A gate on this number would have registered almost nothing while the evidence went from
none to four independent oracles.

**What lands:** a non-gating `make cov` wrapping `pytest --cov=quebra --cov-report=term`, in no
other target, documented in `CONTRIBUTING.md`. It goes through `pytest --cov` rather than a bare
`coverage` call, because `pytest-cov` is declared and `coverage` is not. `pytest-cov` stays a dev
extra and stays in the `DEP002` ignore list, with a comment saying why.

**Plus one non-gating CI step, adopting 5.6's actual wording.** An earlier draft declined the
reporting half. That was wrong on its own terms: 5.6 says "Report it in CI so regressions are
visible; do not gate on it", and the argument the draft gave - that a signal would read noise as
regression and silence as safety - is an argument against a **gate** or a diff-alert, neither of
which is proposed. The draft was also inconsistent with itself: R6.3 keeps `real` inside `FAST`
precisely to avoid moving a check onto a discipline promise, and a local-only `make cov` is exactly
a discipline promise. R6.0.4 further argues *from* the coverage number, so declining to publish it
is not a position this spec can hold.

The step prints the table to the job summary and **carries a one-line comment stating what it is
for**: to show whether a module or a suite is executing code nothing checks, which is how
`kaplan_meier.py` at 76% with no oracle was found. No threshold, no `fail_under`, no diff against a
previous run, no external coverage service.

Cost, stated as a ratio rather than in seconds: the step is ADDITIVE, a second full run after
`make check` has already run the suite, so it costs **a whole covered run per leg**, and a covered
run measures roughly 1.3x to 1.5x a bare one on this machine. An earlier draft quoted the bare
versus covered *difference* as though it were the added cost, understating it several-fold, and
then quoted absolute seconds that did not reproduce on a second measurement of the same tree.
Absolute figures are omitted deliberately: a GitHub runner is neither machine, and three legs pay
the cost on a workflow that declares no `timeout-minutes`.

**The reported number names the selector and the data state it was measured under**, because the
value moves depending on whether the private tree is present.

**The `scipy` floor is raised to 1.15, and two earlier reasons for it were both wrong.** The first
draft justified a raise by R6.5's `ecdf(...).sf.confidence_interval(method="log-log")` oracle;
`ecdf` and `CensoredData` predate the declared `>=1.14` floor, so they justify nothing. The real
argument is `scipy.stats.chatterjeexi`, which `tests/test_r_cross_implementation.py:270` and `:286`
guard with `hasattr`, so below the version that added it a tier-4 cross-implementation oracle
**silently skips instead of failing**.

The second draft then set the floor at **1.17**, taken from a string inside that same test rather
than measured. That is a fabricated number, the §4 defect this phase exists to remove, committed
inside the requirement that raises the floor. Measured instead: the scipy 1.15.0 release notes list
`chatterjeexi` under new features with the signature the test uses, its versioned API page exists
at 1.15.0 and 404s at 1.14.1, and 1.15.0 ships `cp311` wheels so the 3.11 CI leg is safe. 1.14
genuinely lacks it, so raising is right; 1.17 needlessly excluded 1.15 and 1.16, under which the
oracle runs. The only other post-1.14 scipy API in the tree, `permutation_test(rng=...)` at
`src/quebra/analyzers/permutation.py:136`, also arrived in 1.15.0, so 1.15 is not too low either.
Every "1.17" site is corrected, including the test's own docstring.

Combined with R6.0.10 - CI resolves newest on every leg, so the floor is exercised by nothing - the
declared floor is a claim no gate checks under which a shipped oracle disappears.

**Acceptance.**

1. `make cov` produces a report and exits 0 regardless of the number.
2. One CI step prints coverage, carries its one-line purpose comment, names the selector and data
   state, and cannot fail the build. No `fail_under` anywhere.
3. The measured numbers in this spec come from the run that produced them, quoted rather than
   estimated.
4. `scipy`'s floor is raised to 1.15 justified by `chatterjeexi`, not by `ecdf`, with the version
   taken from that function's release notes rather than from a string in the test, and R6.0.10's
   finding that the floor is exercised by nothing is recorded so a later reader does not assume CI
   checks it. The two `hasattr` guards at `tests/test_r_cross_implementation.py:270` and `:286`
   become dead and are recorded as such rather than removed in this phase.
5. Collect delta: **+0**. Files: **6** (`pyproject.toml`, `Makefile`, `CONTRIBUTING.md`,
   `.github/workflows/ci.yml`, `tests/test_r_cross_implementation.py` for the reason string the
   corrected floor makes false, and this spec, whose stale figures acceptance 3 requires be
   replaced by the run that produced them).

**Done when** the number is visible in CI without anyone remembering a command, nothing gates on it,
and the declared floor is one under which every shipped oracle actually runs.

---

## R6.9 - The deletion discipline

`quebraplan.md` 5.1 says "expect to delete more than you keep". **Volume of deletion is the wrong
metric.** A deleted test that was catching something is an undetectable regression: the suite goes
green, the diff shows a removal, and nothing records what stopped being checked. Deletion is the one
operation in a test suite whose damage is invisible to every gate this repository runs.

Added to `AGENTS.md` §7 as prose. Before a test is removed, all three must hold:

1. **Name the property it asserts, and name the test that still asserts it.** If no other test does,
   it is not redundant; it is the only evidence.
2. **Show the removal is safe by mutation, not by reading.** Break the code the test guards and
   demonstrate the **remaining** suite goes red. If the suite stays green, the deletion is refused
   and the mutation result is reported, because a test whose guarded code can break with the suite
   still green has found a second gap rather than proved itself redundant.
3. **Record it in the checkpoint banner**: the property on `Not done`, the mutation result on
   `Known risk`.

This is the repository's existing positive-control idiom, of which 22 instances already exist,
applied to the removal itself. It applies at exactly one site in this phase, R6.1's B row.

**Not written: a negative-delta rule for the §9 budget line.** This phase's net is positive, and
writing normative governance for a case that does not exist is what `AGENTS.md` §8 forbids. It is
recorded as an open question in `spec/quebraplan.md` §7 for whichever phase first removes tests in
bulk.

**Acceptance.**

1. `AGENTS.md` §7 carries the three-part discipline as prose, presented at the checkpoint for
   approval rather than landed as a detail, because it changes what a reviewer must demand.
2. R6.1's deletion carries items 1 and 2 in its banner.
3. No negative-delta budget rule is written.
4. Collect delta: **+0**. Files: **1**.

---

## R6.10 - The stale test-reference guard

The one guard in this phase that is total, decidable, and enforces exactly the rule it states -
which is the property R6.1 argues it cannot get for the oracle rule and therefore declines to fake.

Roughly fifteen lines: walk the tracked files outside `tests/`, match `tests/test_[a-z_0-9]+\.py`,
and assert every referenced path exists. A positive control plants a reference to a non-existent
module and asserts the guard fires.

**Measured in scope: 38 citation sites naming 18 distinct test modules, of which three were
stale** - `jobs/bench/arms.py:48` citing `tests/test_checks_c2.py`, and
`src/quebra/analyzers/checks/c1_lewis_robinson.py` and `c2_anderson_darling.py` citing
`test_checks_c1.py` and `test_checks_c2.py` without the `tests/` prefix. All three are corrected
in this requirement. Two earlier figures here were wrong and are recorded rather than quietly
replaced: "70 distinct references outside `tests/`", for which no counting rule produces 70; and
"48 distinct across 482 sites over all tracked files", which does not reproduce either and was in
any case not a stable measurement, since most of those sites sit in `.claude/` review ledgers that
change on every review.

**The pattern admits the bare form, and an earlier draft did not.** Requiring the `tests/` prefix
made the guard miss the two `checks/` citations above - the same absent module it was written to
catch in `arms.py`, in `src/`, live at the time the requirement claimed to be total. A guard that
misses a form the tree writes is not total, so the pattern is `(?:tests/)?test_[a-z_0-9]+\.py` and
citations are canonicalised to `tests/<name>` before they are resolved or counted. A docstring citing a test that was renamed or deleted is a claim
about evidence that no longer exists, and `AGENTS.md` §10 forbids inventing a locator; nothing
currently notices when one goes stale.

**Scope is `src/`, `jobs/`, `docs/`, `scripts/`, `AGENTS.md` and `CONTRIBUTING.md`.** `spec/` is
excluded deliberately: a spec is a dated record of what was true when it was written, and a phase
spec citing a test that a later phase renamed is history rather than a defect. There is a second,
mechanical reason: this spec quotes the stale `arms.py` path twice as its own example, so a guard
over `spec/` would flag it for describing the defect correctly.

**The exclusion is not free, and two earlier claims about its cost were both wrong.** The first said
no stale reference exists under `spec/`. The second said five do, and named lines that do not carry
citations - it was counting with the prefix-only pattern this requirement then broadened. Measured
with the pattern the guard actually ships: **nine stale citation sites on seven lines** in the `.md`
specs. Seven sites are this spec's own and are quotations of the defect rather than defects, at
`:241`, `:243`, `:1124`, `:1126` and `:1151`, the `:243` and `:1126` pairs being the bare-form
quotations. The remaining two are a real defect this guard will not catch: `spec/specvalidity08.md:117` and
`:158` both cite `tests/test_calendar_tau_truncation.py` as pinning the calendar-clock tau
truncation, and `git log --all` shows that module never existed under any commit. The property is in
fact covered by `tests/test_checks_statistics.py`. Rewriting a shipped spec is out of scope here, so
this is recorded as a finding rather than fixed, and the guard's docstring carries it so a reader
meets the cost where they meet the exclusion.

**Acceptance.**

1. Every `tests/test_*.py` path referenced from a tracked file in scope names a file that exists.
2. The positive control demonstrates the guard failing on a planted stale reference.
3. `jobs/bench/arms.py:48` is corrected to cite a test that exists, or the sentence is rewritten to
   name the property rather than the file.
4. `spec/` is out of scope and the reason is stated in the test's docstring, not only here.
5. Collect delta: **+1 to +3**. Files: **4** (`tests/test_stale_references.py`,
   `jobs/bench/arms.py`, and `src/quebra/analyzers/checks/c1_lewis_robinson.py` and
   `c2_anderson_darling.py`, whose bare-form citations the guard only catches once its pattern
   admits that form. Fixing the pattern without fixing the two sites it then finds would leave
   the requirement failing its own acceptance 1).

**Done when** a renamed or deleted test module cannot leave a dangling citation behind it.

---

## Phase budget

| Requirement | Collect | Files | Hours |
|---|---|---|---|
| R6.1 audit published, three dead controls fixed, one B deleted | +0 to +2 | 4 | 2-3 |
| R6.2 the tier axis: 7 markers, selector, completeness guard | +1 to +2 | 1 new, ~42 edited | 4-6 |
| R6.3 cost markers, three selector sites, no private-data guard | +0 | 9 | 1-2 |
| R6.4 no generator subsystem, no fixture; pooled carve law; tlf oracle | +2 to +4 | 1 | 2-3 |
| R6.5 Kaplan-Meier oracles | +30 to +38 | 2 new, 2 edited | 8-12 |
| R6.6 three properties on one subject | +3 to +4 | 4 | 2-3 |
| R6.7 runner contract, two gaps, one validation fix | +7 | 2 | 2-3 |
| R6.8 coverage reported in CI, scipy floor raised to 1.15 | +0 | 6 | 1 |
| R6.9 deletion discipline | +0 | 1 | 0.5 |
| R6.10 stale test-reference guard | +1 to +3 | 4 | 0.5 |
| **Total** | **+44 to +60** | | **24-34** |

535 becomes **579 to 595**. **Measured on completion: 592**, inside that range.

Per requirement, measured rather than projected: R6.1 +3, R6.2 +3, R6.3 +1, R6.4 +6, R6.5 +31
(30 in `tests/test_kaplan_meier.py` plus the recomputation guard in
`tests/test_instrument_report_currency.py`), R6.6 +4, R6.7 +6, R6.8 +0, R6.9 +0, R6.10 +3.
These sum to +57, so 535 becomes 592. Two figures read higher than the count recorded at
their own checkpoint, in both cases because that checkpoint's cold review found a test that
could not fail: R6.7 is +6 rather than +5 because the sink guard had no test at all, and
R6.10 is +3 rather than +2 because the citation pattern's lookbehind had none, so deleting
it left the suite green. The figures are the landed counts, not the counts at the banner.

R6.2 and R6.3 both touch `pyproject.toml` and the `Makefile`; those are counted once each in R6.3
and are not double-counted above.

**Two corrections to this spec's own budget arithmetic, recorded rather than quietly fixed.**

First, the planning document behind this spec summed the phase at +28 to +49 by adding a "scipy
layer-2 oracle, +2" on top of an envelope that already contained it: the scipy cross-implementation
tests are oracles 7 and 8 inside R6.5's own count.

Second, an earlier draft of this table gave R6.5 a floor of +10 while its own acceptance criteria
make the broken-estimator positive control mandatory, so the reachable floor was always 14. Both are
the §4 defect class the phase exists to remove, caught in the phase's own budget. The figures above
are derived per requirement rather than by adjusting a prior estimate.

**Why 24-34 and not `quebraplan.md`'s 30-55**, item by item: 5.1's 4-8 h becomes 2-3 because the
audit found nothing to rewrite and the work is fixing three controls it did find; 5.2's 12-20
becomes 3-4 because the generator subsystem is declined against a measurement already in the
repository; 5.3's 8-14 becomes 8-12 and moves from the check battery, which has 19 tier cells, to
Kaplan-Meier, which has none; 5.4's 3-6 becomes 2-3 on one subject; 5.5's 4-6 becomes 2-3 because
four of six invariants are covered; 5.6's 2-3 becomes 1. Against those reductions, R6.2 adds 4-6 h
that 5.1 costed as a directory move and this spec spends on a marker axis instead.

---

## Checkpoints

Checkpoint 6.N delivers R6.N, except 6.2 and 6.5, which split. 6.8 and 6.9 land together: both are
one review pass over documents and neither changes a test.

> **CHECKPOINT 6.0** - this spec lands, recording the ten premises in R6.0. No behaviour change.

> **CHECKPOINT 6.1** - the audit is published, the three dead controls are rewritten so they can
> fail, and the single B is deleted and replaced. **Stop:** the audit's classification is
> single-rater and its rule excludes the carve, the ledger verdict and the tau construction. If
> Sera reads the table and disagrees with the rule, R6.2 onward are re-scoped.

> **CHECKPOINT 6.2a** - the seven tier markers declared, the orthogonality statement, the selector
> and the completeness guard. No test decorated yet, so the guard is red on purpose and that is the
> demonstration it can fail.

> **CHECKPOINT 6.2b** - the 40-file decoration, alone. Mechanical, nothing semantic in the same
> diff, because the checkpoint protocol depends on `git diff` being reviewable.

> **CHECKPOINT 6.3** - the cost markers, the `FAST` change and the four documentation edits.
> **Stop:** `make test-real` must go from exit 5 to exit 0 with 9 selected; if it does not, the
> marker set is wrong.

> **CHECKPOINT 6.4** - the Arm B fixture and its carve-law test, the demoted `tlf` test, the
> isolation comment, and the three open questions filed. **Stop if the carved run lengths do not
> match the geometric law** - that would be a carve defect, not a tolerance to widen.

> **CHECKPOINT 6.5a** - the analytic Kaplan-Meier oracles, including order invariance and the
> lexsort redundancy finding. Envelope +6 to +8.

> **CHECKPOINT 6.5b** - the scipy cross-implementation, with the excluded-point rule stated, and its
> broken-estimator positive control. Envelope +3 to +4. **Stop if KM disagrees with scipy** - that
> is a defect in a shipped estimator, not a tolerance to widen.

> **CHECKPOINT 6.5c** - band coverage, the carve handoff, the zero-duration window, and the three
> crude-versus-KM axes reported as numbers. Envelope +3 to +4. **Stop:** the decomposition is a
> number the within-calibration panel currently reports without, so what to do with it is Sera's
> call and is not decided here.

> **CHECKPOINT 6.5d** - MTBF and the Kaplan-Meier rows in `instrument_validation`. Envelope +2.

> **CHECKPOINT 6.6** - three properties, the `derandomize` profile, and `hypothesis` out of the
> `DEP002` list. **Stop:** `hypothesis` in this suite is a reproducibility change, not a test
> addition.

> **CHECKPOINT 6.7** - the DAG contract, the `_register_node` membership check, and the
> end-to-end reuse tests. **Stop:** the membership check is the phase's only change to `core/`
> behaviour. It is three lines and all 13 jobs stay green, but it is a behaviour change and Sera
> approves it as one.

> **CHECKPOINT 6.8** - `make cov`, the non-gating CI step, the coverage numbers, the `scipy` floor,
> and the deletion discipline in `AGENTS.md` §7. **Stop:** the discipline changes what a reviewer
> must demand.

> **CHECKPOINT 6.10** - the stale test-reference guard and the corrected citation in
> `jobs/bench/arms.py`.

Every checkpoint prints the `AGENTS.md` §9 banner including the mandatory `Not done` and
`Known risk` lines, neither reading "none" unless that is literally true, and the `Budget` line
reporting the running collect delta and file count against the envelope above. **For R6.5 the 2x
STOP applies per checkpoint, not per requirement.**

---

## Verification

Deterministic gates, run and reported by exit code:

- `make check` **and `make deps`** at every checkpoint. `make check` is `lint types arch test` and
  omits deptry, which CI enforces as a separate step, so the two are not interchangeable.
- `make check-ci` before any push. It does not reproduce CI's 3.11, 3.12 and 3.13 matrix legs, and
  it resolves newest rather than the declared floors, so R6.0.10's gap stays invisible to it.
- **`make test-real` from CHECKPOINT 6.3 onward**, on the machine where the private tree exists. It
  exits 5 today and must exit 0 with 9 selected afterwards.
- `make tiers` reports a non-zero count for six tiers and zero for `regression`, which is the
  recorded intent rather than a failure.
- `bash scripts/acceptance.sh` runs the fast selector from a directory that is not the
  repository, so a marker that breaks collection from elsewhere fails there and nowhere else.
  **It does not currently exit 0**, for 7 pre-existing cwd-dependent failures unrelated to this
  phase (R6.0.11). The criterion this phase holds itself to is therefore that the script's failure
  set does not GROW: 7 before, 7 after, the same node ids.
- The collect count moves from **535** by the sum of the per-requirement deltas above, with any
  difference explained rather than absorbed.

Tests, each naming its oracle per `AGENTS.md` §7:

- Kaplan-Meier without censoring equals `1 - ECDF` exactly, and with censoring equals a survival
  function worked out by hand in the docstring (R6.5).
- The product-limit estimate and the log-log band agree with `scipy.stats.ecdf` on `CensoredData`,
  evaluated as step functions on a common grid with the excluded points stated, and a deliberately
  broken estimator fails that comparison (R6.5).
- The band covers a known exponential `S(t)` at nominal, with the Monte Carlo standard error in the
  assertion message and no direction claim (R6.5).
- Carved run lengths from the committed Arm B fixture follow the exact geometric law (R6.4).
- `tlf`'s dwell statistics recover `dt / p01` and `sqrt(1 - p01)` on a noise-free two-level draw at
  `lambda = mu` (R6.4).
- Every node's inputs precede it in `_toposort`'s output, and a node reaching no sink never executes
  (R6.7).
- Reuse is refused end to end under code mismatch, content mismatch and a dirty tree, and fires
  otherwise (R6.7).
- The seed derived by `check_ledger` itself is stable across processes, so mutating
  `check_ledger.py:391` fails it (R6.1).
- Every collected item carries exactly one tier marker (R6.2).

**Known risk to carry at every checkpoint.** R6.5 is a third of the phase's hours and carries the
widest envelope, now split across four checkpoints so a single requirement cannot absorb an overrun
while reporting itself inside a requirement-level budget. If any of the four breaches its 2x, the
phase halts there. That is the designed outcome: R6.1 through R6.4 land independently and each is
useful alone.

**Second known risk.** R6.2's decoration touches every test file. A mis-applied `pytestmark` on a
module that mixes tiers silently mislabels rather than failing, because the completeness guard
checks presence and count, not correctness of the choice. The guard cannot catch a wrong tier, only
a missing or doubled one, and the spec says so rather than implying the axis is verified.

---

## Done when

1. The oracle audit is published with its classification rule, and the three tests that carry an
   oracle and cannot fail are rewritten so they can.
2. `tests/` is flat, the six-tier directory layout is recorded as declined in favour of a marker
   axis, and `AGENTS.md` §7 and `CONTRIBUTING.md` say so rather than saying it is planned.
3. Every collected item carries exactly one tier marker, the two axes are documented as orthogonal,
   a selector exists per tier, and `regression` is empty by recorded decision.
4. `real` has 9 members, keeps its skips, stays inside the local fast selector, and no document
   asserts something the marker change made false.
5. No new generator subsystem exists. The carve-to-duration-law path has an exact oracle from a
   committed fixture, and `tlf`'s dwell statistics have a correct sampled one.
6. `kaplan_meier.run` has analytic, cross-implementation and simulation-truth oracles, each naming
   its source, and `instrument_validation` carries its rows.
7. The three crude-versus-Kaplan-Meier axes are reported as numbers, and no panel artifact changed.
8. Three properties hold under a derandomised `hypothesis` profile; the two declined classes and the
   one false invariant are recorded.
9. `_toposort` has a test, an unreachable node is pinned as never executed, and a dangling
   `LocalRef` is refused where it is written rather than where it is dereferenced.
10. Coverage is reachable through `make cov`, printed by one non-gating CI step that names its
    selector and data state, gated nowhere, and quoted from the run that produced it. The `scipy`
    floor is one under which `chatterjeexi` runs rather than silently skipping.
11. `AGENTS.md` §7 carries the deletion discipline, and no negative-delta budget rule was written.
12. Every `tests/test_*.py` path cited from `src/`, `jobs/`, `docs/`, `scripts/`, `AGENTS.md` or
    `CONTRIBUTING.md` names a file that exists, enforced by a guard with a positive control.
12. `make check`, `make deps`, `make check-ci` and `make test-real` all exit 0.

---

## Not in this phase

Populated deliberately: **23 modules under `src/quebra/` have no test file touching them**, and a
phase named "test architecture" that leaves them untested must say so, or the first reader assumes
otherwise.

- **`loaders/__init__.py` and `loaders/registry.py`.** The whole package, at 52% line coverage from
  incidental execution, with **no test of any kind**. `AGENTS.md` §3's claim that "one decorated
  function adds a format or a target with zero other changes" therefore has no guard. **Re-open
  trigger: the next format or target added.** This is the largest single gap this phase leaves.
- **The eight untested `plots/` modules** (`allan_plot`, `base`, `calibration_plot`,
  `fidelity_helpers`, `instrument_validation_plot`, `interpolation_stage_plot`, `mtbc_hist_plot`,
  `tlf_plot`) and `panels/comparison.py`, `panels/check_ledger.py`,
  `panels/_check_ledger_render.py`. Render code, and `quebraplan.md` Phase 7 owns the plot contract.
  **Re-open trigger: Phase 7.**
- **`analyzers/fidelity.py`** (22%) and **`analyzers/allan.py`** (22%). R6.4 records why an analytic
  case on `allan` would test `allantools`, and names the live `fractional_adev` denominator
  discrepancy as the thing actually worth fixing. **Re-open trigger: the denominator decision.**
- **`analyzers/psd.py`.** A stub raising `NotImplementedError`. Nothing to validate.
- **`within_calibration_compute._window_survival` itself.** R6.5 measures its three differences
  from Kaplan-Meier and reports them; it does not give the crude estimator an oracle of its own, so
  the estimator the within-calibration panel currently draws remains unvalidated after this phase.
  Said plainly because R6.5's "no longer unvalidated" applies to `kaplan_meier.run`, which is what
  two jobs and `plots/km_survival_plot.py` draw, and not to the panel's own curve.
- **`reliability_band.cumulative_hazard`.** Declared, never written, and promised by its own module
  docstring (R6.0.9). Removing or populating it is a product change.
- **`schemas/base.py`, `schemas/calibration_log.py`, `transforms/lookup_prior.py`** (17%).
- **R6.7's three end-to-end reuse tests.** Owed, not deferred by choice: R6.7 acceptance 4
  records the measurement. The refusal branches of the reuse gate are covered at the pure
  helper and not end to end, so a change that broke `run_job`'s wiring to the gate while
  leaving `_reuse_eligible_dir` correct would pass. Cheap to land and left out only because
  it was discovered at review rather than written with the requirement.
- **R6.5 acceptance 6's Greenwood clause is unmeetable as written** and is struck rather than
  claimed. The `np.inf` sentinel at `kaplan_meier.py` and the `np.isfinite(greenwood)` clause
  in `_loglog_band`'s mask are both dead - neutering either leaves the suite green - because
  `denom == 0` implies `deaths == n_j`, which sets `S = 0` and is already excluded by the
  `survival > 0.0` mask. And `greenwood` is a local list, never stored on
  `KaplanMeierCurve`, so "assert `greenwood[-1]` is `inf`" cannot be asserted against the
  shipped artifact at all. Either put it on the artifact or drop the clause; the test now
  pins the exclusion set, which is what is observable.
- **The tier-3 definition was widened** from "its p-value holds its nominal level" to also
  cover "a band's coverage" (`analyzers/instrument_validation.py`), which R6.5 licensed only
  as reusing `TierRow` and the `TIER_*` verdicts. Recorded here as a decision taken during
  implementation, dated with this phase.
- **The `tlf` dwell oracle's noise boundary.** Nothing drives `tlf.run` at separations where
  the per-read MAP misassigns, so nothing establishes whether the dwell statistics degrade
  smoothly or silently report three times too short. R6.4 accepted the noise-free draw as a
  restriction. The misassignment rate at which the oracle stops holding is NOT yet filed
  anywhere; §7 of `spec/quebraplan.md` carries the 1/f arm, the median-spacing defect and the
  `allan` denominator, not this. Recorded here as owed.
- **A `tests/regression/` tier and any golden values from private data.** It asks a data-publication
  question about embargoed records that nobody has answered, and neither precondition exists: no
  tags, no `published/`. The marker is declared so the tier can be populated the day a public record
  ships.
- **An end-to-end validation job with known truth.** The wiring is covered by `test_nesting.py`,
  `test_reuse_*` and `test_path_resolution.py`; the estimator by R6.5; and the one place their
  composition can be wrong is the carve-to-KM handoff, which R6.5 tests directly at the cost of one
  test rather than a job, a fixture and a sink.
- **Populating the `r` marker, and any R CI job.** `quebraplan.md` Phase 6, reserved as SPEC 0007.
  The path past `c3_serial_copula._invoke_rscript` has never executed here, and "no members, reason
  given" must not be read as "R is covered".
- **Nelson-Aalen, log-rank, RMST, MCF.** Not implemented; `AGENTS.md's not-implemented list` records it.
- **Changing which survival estimator the within-calibration panel draws**, and populating
  `ReliabilityBand.band_lower` / `band_upper`. R6.5 produces the numbers that decision needs and does
  not make it.
- **Fixing the shared median-spacing defect in `tlf.py:134` and `allan.py:20-25`**, and the
  `fractional_adev` denominator. Recorded in `spec/quebraplan.md` §7; fixing them changes shipped
  figures.
- **Typing the `diagnostics: dict` fields on `allan`, `fidelity`, `t2star` and `windows`**, which
  `specvalidity08.md` assigned to Phase 5. It is a typing widening with no evidential content and
  belongs with the mypy scope question, which `Makefile` already defers with its reason.
- **The CI gate weaknesses `specvalidity08.md` records**: mypy scoped to 11 of 81 files, the minimal
  ruff select missing `B905`, and the `python_version` rationale. A small separate pass.
- **Moving the row-key vocabulary out of `analyzers/independence_survey.py`.**
  `spec/quebraplan.md` §9.2 sizes it and gives three options; R6.5 adds no second tier vocabulary,
  so this phase neither worsens nor fixes it.
