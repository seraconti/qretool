SCOPE: check_ledger.py + 8 test files + pyproject/Makefile/scripts/docs/ci (SPEC 0006 CP 6.9+6.1+6.2+6.3)
COMMIT: 72a3aae
## Manifest

## Reviewed (all)
- src/quebra/analyzers/check_ledger.py
- tests/test_within_calibration_builder.py
- tests/test_check_ledger.py
- tests/test_checks_cvm.py
- tests/test_assumptions.py
- tests/test_checks_statistics.py
- tests/test_data_manifest.py
- tests/test_windows_carve.py
- tests/test_marker_discipline.py
- pyproject.toml
## Findings

MINOR | src/quebra/analyzers/check_ledger.py:230-243 | `stream_for` is behaviour-preserving
(byte-identical expression, single call site at :403, no other module derives a stream). But the
docstring's justification for publicness - "only testable if a test can call the derivation" - is
false in this repo: `tests/test_check_ledger.py:136` imports the private `_tie_stats` from this
same module, and `_verdict` at :19. Extraction is what made it testable; the missing underscore
buys nothing and widens the module API for zero consumers. | Rename to `_stream_for`, or drop the
paragraph and keep it public on API grounds.

MINOR | src/quebra/analyzers/check_ledger.py:238-242 | Last docstring paragraph ("Inlined, it was
guarded by a test that re-typed the formula...") is debugging history, which AGENTS.md section 10
rules out of docstrings; the constraint it implies is already carried by the crc32 paragraph. |
Delete the sentence after "Public rather than private because ...".

IMPORTANT | tests/test_check_ledger.py:101-133 vs check_ledger.py:403 | The rewritten test pins
`stream_for` but nothing pins that the ledger's rng USES it. Mutating :403 to
`stream = hash(f"{label}|{clock}") & 0x7FFFFFFF` leaves `stream_for` intact and the suite green,
so the spec's own acceptance ("changing check_ledger.py:391 makes it fail") holds only for
mutations landing inside the extracted function - extraction narrowed the mutable surface rather
than covering it. | Add one assertion in the same test: monkeypatch `check_ledger.stream_for` to a
constant and assert two different threshold labels then produce identical ledger p-values.

MINOR | tests/test_check_ledger.py:122 | Three PYTHONHASHSEED values where two suffice to
falsify `hash()`; measured 3.06 s of a 4.04 s single-test run, all of it subprocess start plus
numpy/pandas import. Subprocesses are the right mechanism (hash randomisation is per-process and
nothing in-process can detect it), and the file is `unit` with no `slow` marker. | Drop "12345";
2.0 s for the same discriminating power.

IMPORTANT | tests/test_marker_discipline.py:3 and :99-102 | Docstring names `pyproject.toml`'s
marker list as the oracle, but no test reads it: `TIER_MARKERS` and `COST_MARKERS` are re-typed
literals and `test_the_two_axes_do_not_overlap` only checks they are disjoint. Deleting
`regression` (zero members) from `pyproject.toml` leaves this file green while the declared axis
and the asserted axis disagree - the same "names an oracle it cannot consult" defect class R6.1
exists to remove. | Assert `TIER_MARKERS | COST_MARKERS` equals the names parsed from
`request.config.getini("markers")`.

MINOR | tests/test_marker_discipline.py:88 | "Without it the guard above passes whenever
collection is empty" - the guard is itself a collected item, so `request.session.items` is never
empty while it runs. The control's real value is that `_violations` detects zero and two tiers,
which is what the body asserts. | Reword to what the control demonstrates.

MINOR | tests/test_marker_discipline.py:67,84,97 | Single-tier file decorated per test; SPEC 0006
R6.2 prescribes module-level `pytestmark` where a file is single-tier. | `pytestmark =
pytest.mark.policy`, drop the three decorators.

GREEN | tests/test_marker_discipline.py:37-39 | `_FakeItem` is faithful for the surface used:
`tier_markers_of` touches only `mark.name`, and real `iter_markers()` extras (parametrize, skipif,
pytestmark, cost marks) are intersected away. Same-name duplication (module `pytestmark` plus a
matching decorator) collapses in the set, which is the right reading. Measured: 540 collected,
0 items carry no tier marker, `-m real` selects exactly 9.

MINOR | collect delta | 540 collected against the 535 baseline: +1 occupancy, +1 net cvm, +3
marker_discipline. R6.2's envelope for the guard is "+1 to +2" and it landed +3 (1.5x, under the
2x halt). | State it on the checkpoint banner's Budget line rather than absorbing it.

GREEN | pyproject.toml:95-107 | Seven tier markers match R6.2's text verbatim, orthogonality
comment present, `real` text corrected from "never runs in CI" to "CI has none, so these skip
there". `--strict-markers` already on, so a typo fails collection.

GREEN | tests/test_within_calibration_builder.py:92-107 | Arithmetic verified against the real
`_threshold_in_spec_frac` + `_observed_dt_h`: dt=[1,1,1,1], observed_h=4, oos = s<5 =
[F,F,T,T,F], oos[:-1]=[F,F,T,T] -> oos_h=2, frac=1-2/4=0.5 exactly. Left-endpoint charging claim
is right (`oos[:-1]` indexes the interval by its left reading). Measured under a runtime mutation
of `_out_of_spec_mask` (`<` -> `<=`): 1 failed, 528 passed - this really is the only test in the
suite pinning that boundary, exactly as the docstring claims, and `test_in_spec_frac_matches_
summary` stayed green under it, confirming its new "NOT an oracle" docstring.

MINOR | tests/test_within_calibration_builder.py:99-100 | Docstring says the case pins "AGENTS.md
section 5's in-spec boundary", but that convention has TWO implementations and this pins one:
`windows.in_spec_mask` (windows.py:242-259) is the carve's, with a documented divergence at exact
equality. Measured: mutating `in_spec_mask` `>=`->`>` and `<`->`<=` leaves the suite fully green
(529 passed), so the twin site is unguarded. | Say "`_out_of_spec_mask`'s convention" rather than
the general rule, or add the twin case against `windows.in_spec_mask`.

GREEN | tests/test_checks_cvm.py:190-227 | The replacement pair asserts something nothing else
did: `p_saturated` appears at exactly one source site (cvm_cramer_von_mises.py:236) and in no
other test. Measured: positive case statistic 56.67 (cutoff 5.0), p exactly 0.0, note present;
negative case statistic 0.060, p 0.81, note absent, and over 50 seeds the null statistic maxes at
0.67, so the control is not near the cutoff and will not flake. Nothing was lost: the deleted
assertion (`1 - cdf(794.4) == 0.0`) is the same guard-clause branch the new `p_value == 0.0`
exercises, and both tests compare against `cvm._SERIES_Z_MAX` rather than a re-typed 5.0, so
moving the constant turns them red rather than vacuous.

MINOR | tests/test_checks_cvm.py:212-213 | 682 and 341 are unexplained magic sizes (any n with a
step gives z >> 5). | Say "any n" or use a round 200/100 split.

IMPORTANT | tests/test_windows_carve.py:34 | Whole file tagged `statistical`, but its own module
docstring calls it "Carving semantics" and the members are deterministic small-function tests:
`test_spacing` (:67), `test_duplicate_timestamps_do_not_collapse_the_threshold` (:113),
`test_equality_is_not_a_gap` (:131), `test_gap_beats_a_simultaneous_down_crossing` (:121) assert
no estimator against no oracle - they are `unit`. `test_the_two_job_configurations_agree_on_the_
real_records` (:239) is a two-configuration agreement on real records, so `integration` or
`validation`. SPEC 0006 R6.2 names this file as one of the two "known to be mixed" and prescribes
per-test decoration; flattening it to one tier puts 9 items into `statistical` that answer a
different question, which is what `make tier-statistical` will now report. | Decorate per test.

MINOR | tests/test_assumptions.py:62 | `test_the_shipped_check_names_are_the_six_modules_own_
constants` is marked `policy`, but unlike its two file-mates (`:205`, `:222`, which run the
`_citations` AST scan over `tests/`) it only compares two in-process constants. That is `unit`.
| Retag `unit`.

MINOR | tests/test_assumptions.py, tests/test_checks_statistics.py:679 | `policy` now has members
outside the seven files R6.2 enumerates as its membership (3 here, 1 in test_checks_statistics).
The assignments at :205/:222/:679 are defensible - all three are AST scans - but the spec's
enumerated membership is now false, and R6.2 named only two files as mixed while three are. |
Record the deviation at the checkpoint; amend R6.2's membership sentence.

MINOR | tests/test_checks_statistics.py:352 | `test_statistic_batch_reproduces_the_statistic_
under_the_identity_permutation` is marked `statistical` but its docstring describes a
segments-to-blocks alignment bug: it is an identity between two code paths with no named oracle,
which is `unit`. Same reading applies to `test_permutation_p_value_is_tie_corrected` (:245). |
Retag `unit`.

GREEN | tests/test_data_manifest.py:23-88 | Module `policy` (its four tests are filesystem+digest
scans), `real` on exactly the four tree-readers, and the two monkeypatched synthetic controls at
:97 and :130 correctly left unmarked, as R6.3 requires. With test_windows_carve's 5 parametrised
items that is the 9 measured by `pytest -m real`. Every marked test keeps its `pytest.skip`.

IMPORTANT | Makefile:8 + scripts/check_ci.sh:80 + scripts/acceptance.sh:97 | Missing selector file
is a SILENT fallback. Measured: with the path absent, `$(shell cat ...)` yields empty, the recipe
becomes `pytest -m ""`, and pytest treats an empty `-m` as no filter - 540 collected, exit 0. The
`cat:` error goes to stderr and nothing fails. Same in both scripts (`set -u` only, no `set -e`,
and a failed command substitution in a word does not abort under `set -e` either). Harmless today
because `slow`/`heavy`/`r` are empty; the moment they gain members a lost file silently runs them
in the gate. | Guard once: `ifeq ($(strip $(FAST_EXPR)),)` / `$(error ...)` in the Makefile and
`[[ -s "${REPO}/scripts/fast-selector.txt" ]] || exit 1` in the two scripts.

IMPORTANT | scripts/fast-selector.txt, spec/spectests06.md | Both are UNTRACKED in the working
tree. If the commit misses `git add scripts/fast-selector.txt`, CI's `make check` runs
`pytest -m ""` (the whole suite, unfiltered) and still exits 0 per the finding above, and
AGENTS.md:300 plus CONTRIBUTING.md:51 cite `spec/spectests06.md`, a file not in the repository. |
Stage both with the checkpoint.

GREEN | Makefile:8, scripts/check_ci.sh:80, scripts/acceptance.sh:97 | Single-sourcing is
otherwise correct. `FAST :=` is simply-expanded so `$(shell cat)` runs once per make invocation,
not per target. Quoting survives the spaces: make does not interpret the quotes and the shell
gives pytest one argument; both scripts quote the substitution. Trailing newline is stripped by
`$(shell)` and by `$( )`. Both scripts resolve `${REPO}` from `BASH_SOURCE`, so cwd does not
matter. Measured `make -n test` -> `pytest -m "not slow and not heavy and not r"`, selecting 540.

MINOR | Makefile:8 | The path is relative to cwd, so `make -f /abs/path/Makefile` from elsewhere
hits the silent-empty path above. | `$(dir $(lastword $(MAKEFILE_LIST)))scripts/fast-selector.txt`.

IMPORTANT | Makefile:66-70 | Three tier targets fail, not one. Measured `make tiers`: unit 212,
properties 0, statistical 178, integration 86, validation 0, regression 0, policy 64. `make
tier-regression` exits 2 (pytest exit 5), and `tier-properties` and `tier-validation` will do the
same. R6.2 records a reason only for `regression`; `properties` and `validation` ship empty with
none, against this file's own comment that "a target reporting 'selected nothing' as success is
how an unrun tier rots unnoticed". `validation` ("end-to-end job reaches the right verdict on
known truth") is empty while `test_tier3_calibration.py` and `test_instrument_validation.py` are
both filed `statistical` - the latter's own docstring says "most of these tests are about honesty
rather than arithmetic". | Record the reason for each empty tier, or move the two files.

MINOR | Makefile:5 | The seven `tier-%` targets are not in `.PHONY` (only `tiers` was added). |
`.PHONY: $(addprefix tier-,$(TIERS))`.

GREEN | .github/workflows/ci.yml:38-43 | "Nine tests carry `real`" measured exactly 9, and the
replacement statement is the one R6.3 asks for: not excluded from the fast selector, per-test
skip is the mechanism, no tree on the runner is the enforcement.

GREEN | AGENTS.md:297-337, CONTRIBUTING.md:48-56 | R6.9's three-part deletion discipline lands
verbatim, the two axes are stated with the orthogonality sentence, CONTRIBUTING's wrong locator
("the six-tier layout described in AGENTS.md") is corrected to `spec/quebraplan.md`, and
`tests/test_marker_discipline.py` is a correct locator. No em dashes.

MINOR | AGENTS.md:300 vs spec/quebraplan.md:206-215 | AGENTS.md now says the six-directory layout
was "declined"; `quebraplan.md` 5.1 still presents it as the plan, table of directories and all,
with no pointer to the decision. A reader landing there sees an overruled design as normative. |
One line at quebraplan 5.1 pointing to the decline.

---

## Extensive review, SPEC 0006 commits 2 and 3 (checkpoints 6.5a-d, 6.4, 6.6, 6.7)

26 findings from 4 lenses; 13 important execution-checked (11 CONFIRMED, 2 PARTLY); survivors
then adversarially refuted. Zero critical.

# SPEC 0006 commits 2 and 3 - review verdict

## 1. Verdict

**DO-NOT-SHIP** - two of the six new tests are positive controls that cannot fail when the code they guard is broken (the `tlf.py` label map is unguarded across the entire suite), which is the exact defect class this phase exists to remove.

## 2. Must fix before commit

Survived both the execution check and the adversarial pass. Ranked.

1. **`tests/test_tlf_dwell_law.py:117`** - `test_the_two_states_are_ordered_low_then_high` sorts the means it is testing and then compares two quantities that are equal by symmetric construction; inverting `tlf.py:144` leaves the **full suite at 585 passed**. Replace the symmetric draw with `p01=0.15, p10=0.45` and assert `mean_dwell_s0 â dt/p01`, `mean_dwell_s1 â dt/p10` (verified: passes clean, fails inverted); do not assert `switching_rate` on the asymmetric fixture, and record the exception to the `lambda = mu` justification in the module docstring.
2. **`tests/test_carve_duration_law.py:40,93`** - at `IN_SPEC_P = 0.5` a swap of `windows.in_spec_mask`'s branches passes (chi2 7.30, p=0.199), so the one end-to-end recordâcarveâduration-law test carries no in-spec polarity. Set `IN_SPEC_P = 0.3` **and** generalise the pmf to `(1-p)*p**(k-1)` with tail `p**5` (a bare constant swap makes `chisquare` raise, not assert); verified n=1664, p=0.874 clean, p=0 inverted. This one edit also closes the duplicate "occupancy 1/2 only" absence finding.
3. **`src/quebra/analyzers/kaplan_meier.py:235`** - `birth_type` is filtered by bare equality with no known-value guard, so `up_crosing` silently returns `n_unobserved_birth_dropped=2` and drops the window while the same typo on `death_type` raises; add `KNOWN_BIRTH_TYPES` beside `KNOWN_DEATH_TYPES` and validate in the same loop.
4. **`src/quebra/core/job.py:452,462`** - `figure()` and `materialize()` check `isinstance` and `job_ref` but never `node_id in self.dag`, so a ghost sink ref is accepted, creates the timestamped run directory, then dies as `KeyError` at `runner.py:111` - the replacement that the guard's own comment and `test_dag_contract.py`'s docstring assert in the past tense; extract the ownership+membership check into one helper and call it from all three sites.
5. **`tests/test_kaplan_meier_properties.py:126`** - the fourth property duplicates `tests/test_kaplan_meier.py:122` verbatim (same oracle line, same three assertions, passes and fails together under both sort mutations), and no property with arithmetic content sees censoring: ignoring `death_observed` entirely gives 4 passed. Replace the fourth property with the censoring-shift invariance property (verified: passes clean over 300 draws, fails the mutant) - a replacement, not an addition, since R6.6's envelope is +3 to +4.
6. **`src/quebra/analyzers/instrument_validation.py:645`** - the KM tier-3 row divides by `BAND_COVERAGE_REPLICATES` while the coverage came from the parameter (at `replicates=200` it prints Â±0.0029 against a true Â±0.0147, understated 5x), and the three asymptotic rows hardcode `tau=20` while `asymptotic_size_tau` is a live parameter; quote the parameter in all four rows. Latent, not shipped - no caller overrides today.
7. **`spec/spectests06.md:963` (R6.7 acceptance 4)** - the three end-to-end tests that "drive `run_job` twice for real" do not exist anywhere (an AST scan of test functions *and* helpers finds five double-`run_job` tests, none of them a refusal under a code, content or dirty-tree mismatch; every end-to-end `is_tree_clean` is monkeypatched to `True`), landing +5 against +7 with no amendment. Land them or amend R6.7 the way R6.5 acceptance 7 was amended.
8. **`spec/spectests06.md:1112,1118,1120`** - the phase budget table still reads R6.5 `+14 to +18`, total `+28 to +39`, "535 becomes 563 to 574" while acceptance 7 now says +30 to +38 and the suite collects **587**, 13 above a ceiling the table's arithmetic can no longer reach; update the row, the total and the 535âN sentence. The phase is inside its *amended* envelope - the table is the only thing saying otherwise, and it is the number a reader consults before deciding whether the section 9 STOP fired.
9. **`tests/test_carve_duration_law.py:1,10`** - the docstring claims "Oracle: Arm B's construction" and a coupling that does not exist (mutating `jobs/bench/arms.py`'s `IN_SPEC_P` or its thresholding rule leaves the file green), and claims arm C never touches a threshold when `arm_c` carves identically to B. Fix the docstring to claim the analytic oracle it actually has, and record the R6.4 deviation (2 files, +6 against Files 1, +2 to +4). Do **not** add the `arm_b` import - see Refuted.
10. **`jobs/bench/results/instrument_report.md:37`** - the shipped `0.9462` agrees with the code by nobody's assertion; a same-law stream change moves it to 0.9464 with the full suite green, and the report is modified in the working tree right now. Add a `policy`-tier guard that regenerates the row and compares it to the committed file. Do not pin the literal.
11. **`tests/test_kaplan_meier.py:23`** - the module-level `statistical` mark covers a rendering-contract test, a wiring/composition test and an MTBF raise, breaching R6.2's "per test where it is not" rule and inflating the reported `statistical 203` by ~5. Cheapest honest option: drop the module mark and mark all 30 tests individually (the marks cannot be layered - `test_marker_discipline.py` rejects two tiers on one item). Lowest value per unit of edit on this list; fix it or record the deviation, but do not leave the count reported as if it were clean.

## 3. Refuted - do not re-raise

- "The figure reports dropped births to the reader as an endurance bag" - **execution + refutation**: zero consumers of `n_unobserved_birth_dropped` in `panels/` or `plots/`; prospective only.
- "No generated input in the properties file carries a single censored observation" - **execution**: `_records()` draws `st.booleans()`; 171 of 200 probe draws were censored. The true cause is that no property with *arithmetic content* sees censoring.
- "The asymptotic rows carry no such hazard" - **execution + refutation**: they carry the same class on `tau` (literal `tau=20` at :515, :535, :596).
- "An off-by-one that trades a birth for a death cannot be separated at occupancy 1/2" - **execution**: the `e=j` mutant turns the file red. **Refutation caveat**: it fails via scipy's frequency-sum guard, not the shape test the docstring claims; rescaled to equal totals it passes at p=0.722. Do not credit the docstring's stated mechanism.
- "The suite cannot see an in-spec inversion" (never claimed, but implied by framing) - **execution + refutation**: 21 tests fail under the mutation, including `test_windows_carve.py::test_a_reading_exactly_at_the_threshold_is_in_spec_and_the_asymmetry_is_deliberate`. The gap is local to the end-to-end test.
- Remedy "relocate the properties into `tests/test_kaplan_meier.py`; it was available at no cost" - **refutation**: costs a ~34-test per-item marker rewrite, and section 7's index (oracle *and* subject) supports keeping algebraic properties apart from scipy/hand-derivation oracles.
- Remedy "import `jobs.bench.arms.arm_b`" (R6.4's own plan) - **refutation**: `arm_b` routes through `jobs/bench/carve.py`, returns `list[Segment]` already filtered by `min_events` and stripped of the trailing censored window, so it would test the bench carve (already pinned by `test_bench_uses_real_carve.py`) and lose the birth/death taxonomy. `windows.run` is the right subject; only the docstring is wrong.
- Remedy "`assert coverage == approx(0.9462)`" - **refutation**: that is section 7's banned change detector and turns any numpy stream change into a contentless failure.
- Remedy "set `IN_SPEC_P = 0.3`" as a bare constant swap - **execution + refutation**: `chisquare` raises on the frequency-sum check; the pmf must generalise with it.
- "`tlf_dwell_law` marks all four tests statistical against its own docstring" - **execution + refutation**: two of the four do assert simulation truth of the generating process; only the switching-rate consistency check and the ordering test are unit-shaped.
- "Nothing pins the coverage number at all" - **execution + refutation**: `tests/test_kaplan_meier.py:374` bounds it to [0.94075, 0.95925]. What is unpinned is the fourth decimal and the report's agreement.
- Cite `runner.py:110` for the `KeyError` - **execution**: it is `:111`; `:110` is the cycle raise, and the cycle branch is genuinely unreachable through public calls, so `test_dag_contract.py`'s docstring claim about it stands.

## 4. Absences worth recording

**This phase:**
- **R6.7's three end-to-end reuse tests** (item 7 above). Either land or amend - the Done-when is currently false.
- **R6.5 acceptance 6 is unmeetable as written.** The `np.inf` Greenwood sentinel (`kaplan_meier.py:311`) and the `np.isfinite(greenwood)` mask clause (`:370`) are both dead - neutering both leaves 585 passed - and `greenwood` is a local list never stored on `KaplanMeierCurve`, so "assert `greenwood[-1]` is `inf`" cannot be asserted against the shipped artifact. Either put `greenwood` on the artifact or strike the clause; do not carry the criterion as satisfied.
- **The tier-3 definition was widened** from "its p-value holds its nominal level" to also cover "a band's coverage" (`instrument_validation.py:9`) with no record in R6.5, which only licensed reusing `TierRow` and the `TIER_*` verdicts. Record the widening as a dated decision.
- **Two spec locators no longer resolve**: R6.5:701 and R6.4:755 cite `AGENTS.md:308-310` for the indexing rule; commit 1 moved it. Cite section 7 by section, not by line.

**Not in this phase:**
- **The tlf dwell oracle's noise boundary.** Nothing drives `tlf.run` at separations where the MAP misassigns, so nothing establishes whether the dwell degrades smoothly, raises, or reports three times too short. R6.4 accepted the noise-free restriction as a restriction; log the measured misassignment rate at which the oracle stops holding in `spec/quebraplan.md` section 7.
- **Cross-process / cross-numpy determinism of `measure_band_coverage`.** Holds today in fact (0.9462 in two interpreters, numpy 2.4.4) and is not asserted. The policy guard in item 10 covers the shipping risk; a determinism oracle is a separate question.
- **Recomputation guards for the other `jobs/bench/results/*` artifacts.** None has one, because those studies run about an hour. `measure_band_coverage` runs in about a second, which is why item 10 is affordable and the others are not.

## 5. The honest verdict on the evidence

After commits 2 and 3 the Kaplan-Meier product-limit estimator and its log-log band are genuinely validated against two independent oracles - hand derivation re-checked digit for digit, and scipy's ECDF and log-log interval on a union grid across five distinct censoring shapes - and `windows.run`'s carve is, for the first time, pinned end to end from a metric record to a duration law. The strongest single piece of evidence is the scipy band comparison: it is direction-safe, its positive control demonstrably fails, and it catches the Greenwood `n_j**2` mutation at six node ids, which the property file catches at none. The biggest remaining gap is that the three tests added *outside* Kaplan-Meier are weaker than their docstrings claim: the tlf ordering test cannot fail when the label map it names is inverted (unguarded suite-wide), the carve law is blind to the one domain invariant the repo calls a scientific error, and the property module's arithmetic content never sees a censored observation - so the new coverage is concentrated almost entirely in `kaplan_meier.py`, and the phase's own conformance record (R6.4's coupling, R6.7's three tests, the budget table, the tier counts) overstates what landed. Nothing here is unfixable and most of it is a day's work, but the phase as it stands would ship four claims that execution refutes.
