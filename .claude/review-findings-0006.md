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
