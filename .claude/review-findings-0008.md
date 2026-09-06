SCOPE: src/quebra/analyzers/{assumptions,check_selection,check_outcome,check_ledger,kaplan_meier}.py src/quebra/analyzers/checks/{_permutation,battery,c1_lewis_robinson,c2_anderson_darling,c5_rank_autocorr,c6_exchangeability,cvm_cramer_von_mises,__init__}.py src/quebra/plots/{check_outcome_plot,theme}.py jobs/active/km_with_checks_6d2s.py
COMMIT: ab885a0
## Manifest
## Reviewed
- [x] jobs/active/km_with_checks_6d2s.py
- [x] src/quebra/analyzers/assumptions.py
- [x] src/quebra/analyzers/check_selection.py
- [x] src/quebra/analyzers/check_outcome.py
- [x] src/quebra/plots/check_outcome_plot.py
- [x] src/quebra/analyzers/check_ledger.py
- [x] src/quebra/plots/theme.py
- [x] src/quebra/analyzers/kaplan_meier.py
- [x] src/quebra/analyzers/checks/_permutation.py
- [x] src/quebra/analyzers/checks/c1_lewis_robinson.py
- [x] src/quebra/analyzers/checks/c2_anderson_darling.py
- [x] src/quebra/analyzers/checks/cvm_cramer_von_mises.py
- [x] src/quebra/analyzers/checks/c5_rank_autocorr.py
- [x] src/quebra/analyzers/checks/c6_exchangeability.py
- [x] src/quebra/analyzers/checks/battery.py
- [x] src/quebra/analyzers/checks/__init__.py
## Findings

### src/quebra/analyzers/checks/_permutation.py + six call sites + __init__.py
Behaviour-preservation verdict on `resolve_perm`: PRESERVED.
- `segment_sizes` (result.py:190) returns `list[int]` of plain ints, so `tuple(int(s) ...)`
  changes no value; `block_permutations` iterates `sizes` in the same order either way, so the
  RNG draw order and hence every permutation p-value is unchanged.
- `perm is None` -> delegates to `block_permutations`, which still raises ValueError on
  `rng=None` (_permutation.py:83). Not swallowed, not defaulted.
- Mismatch branch still raises ValueError with the same content; matching branch returns the
  SAME object (`return perm`, line 216), so the battery's shared-permutation identity holds.
- All six sites replaced with the identical call; no site left on the old spelling.
`ruff check src/quebra jobs/active/km_with_checks_6d2s.py` exits 0.
No findings.

### src/quebra/analyzers/kaplan_meier.py
icontract reasoning VERIFIED: `icontract.ViolationError.__mro__` is
(ViolationError, AssertionError, Exception, ...), so it is not caught by the
`except (ValueError, KeyError)` sites at check_ledger.py:353/390/400/448. Those sites never
call `kaplan_meier.run` anyway. `icontract.require(..., enabled=True)` is the library default
(not `__debug__`), so `python -O` does not silently disable it.
Contract cannot fire from a normal job run: the only two callers (jobs/active/km_poster_6d2s.py:84,
jobs/active/km_with_checks_6d2s.py:118) go through `make_inputs_from_windows`, whose
`death_observed` is an ndarray `== DEATH_DOWN_CROSSING` comparison, i.e. bool dtype, empty
included.
`KNOWN_DEATH_TYPES` (line 51) matches exactly the three codes windows.py:45-47 defines, so the
new guard cannot reject a legitimate carve.
MINOR | src/quebra/analyzers/kaplan_meier.py:225 | docstring says the contract is used "because
  ... icontract reports the offending dtype without a hand-written message", but a hand-written
  three-line `description=` sits in the same decorator (lines 216-220) | reword to "without a
  hand-written repr of the offending value".

### src/quebra/analyzers/check_ledger.py, src/quebra/plots/theme.py
`VERDICTS` has exactly one consumer, panels/check_ledger.py:134 (legend), and nothing anywhere
validates a row's verdict against `VERDICTS`, so omitting `VERDICT_ABSENT` misses nothing.
`theme.verdict_color` (theme.py:314) raises on any key outside `VERDICT_COLORS`; "no row" is now
in the dict, so the new value is coverable. (Whether check_outcome can emit some OTHER string is
checked with check_outcome.py.)
MINOR | src/quebra/plots/theme.py:310 | "not computed" #D8D8D8 and "no row" #F0F0F0 differ by 24
  luminance levels out of 255; the stated R8.3 requirement is that the two be distinguishable to
  a reader, and at cell size on paper they are near-identical | darken "no row" toward white with
  a visible hatch or push "not computed" darker (e.g. #C0C0C0).

### src/quebra/analyzers/check_selection.py
Verified `TAU_DEPENDENT_KEYS` (lines 44-52) against battery.py:146-196: the five keys are exactly
the rows inside the `if include_tau_checks:` gate (c1 asym, c1 perm, c2 asym, cvm asym, c2 perm).
The claim holds. `ALL_KEYS` = 9 ROW_KEYS + C3 = 10; the "five of nine" and "nine rows" prose is
right. `resolve` refuses a display-set outside the run-set (line 111) and an empty run-set.
MINOR | src/quebra/analyzers/check_selection.py:161 | `missing_rows` iterates `ALL_KEYS`, so any
  run_set key outside `ALL_KEYS` can never be reported missing - it drops out silently instead of
  raising | iterate `run_set` and raise on a key not in `ALL_KEYS`, or document that callers must
  pass a `normalise`d run_set.
MINOR | src/quebra/analyzers/check_selection.py:147 | `select_rows` indexes `order[key_of(row)]`,
  which raises a bare `KeyError((...))` with no message if a row carries a key outside `ALL_KEYS`
  | reuse the `normalise` message or filter on `order` membership.

### src/quebra/analyzers/check_outcome.py
The "never raise on a check RESULT" rule mostly holds: empty ledger, empty `at_threshold`, missing
cell, NaN p_value and NaN notes all take non-raising paths (lines 146-181). `_artifact_guard.py:52`
confirms the `self.__dict__.update` restore, so the deliberate non-slots choice at line 87 is
correct and the comment at 83-86 is accurate.
IMPORTANT | src/quebra/analyzers/check_outcome.py:146 | a threshold_label that is absent from the
  ledger silently produces a full grid of `VERDICT_ABSENT`, which renders as an honest-looking
  figure; the module docstring (line 15) claims this case raises, and the sibling
  `kaplan_meier.make_inputs_from_windows:181` raises on exactly this mistake for exactly this
  reason | when `len(ledger_rows)` and `threshold_label` is not in
  `ledger_rows["threshold_label"]`, raise as KM does.
IMPORTANT | src/quebra/analyzers/check_outcome.py:130 | `alpha: float = 0.05` defaults instead of
  coming from the `CheckLedger.alpha` that actually turned p-values into verdicts
  (check_ledger.py:123); a job running at alpha=0.01 silently stamps 0.05 onto the artifact that
  outlives it | make `alpha` a required keyword-only argument.
MINOR | src/quebra/analyzers/check_outcome.py:108 | `CheckOutcome.check_thresholds` has no caller
  anywhere (the other three, within_calibration_data.py:69-70 and check_ledger.py:299, are
  called), so the guard it claims to "match" does not run | call it from `build_check_outcome`,
  or delete it.
MINOR | src/quebra/analyzers/check_outcome.py:69 | `OutcomeGrid.counts` is unused and its docstring
  says "The renderer states this; it does not derive it" - the renderer never reads it | use it in
  `CheckOutcomePlot._caption` (as independence_survey_plot.py:84-88 does) or delete the property.
MINOR | src/quebra/analyzers/check_outcome.py:102 | `asked_but_unanswered` is pooled over datasets
  AND clocks, so a key answered for one dataset and absent for four is reported as answered; the
  field docstring says only "a row that was run and produced nothing" | name the aggregation in
  the docstring ("...anywhere in the drawn set"), matching the caption which already says
  "anywhere".
MINOR | src/quebra/analyzers/check_outcome.py:106 | `notes: list[str]` is never populated by the
  builder and never read by the plot | drop the field.

### src/quebra/plots/check_outcome_plot.py
Layer is clean: matplotlib only, every drawn value is a field of `CheckOutcome`, no pandas.
`theme.verdict_color` cannot raise here: ledger verdicts come only from `_verdict`
(check_ledger.py:228-262), whose five returns plus `VERDICT_ABSENT` are all in `VERDICT_COLORS`.
IMPORTANT | src/quebra/plots/check_outcome_plot.py:124 | `f"{p_value:.2f}"` prints "0.00" for any
  p below 0.005, a value a permutation p-value cannot take (its floor is 1/(B+1)); the same figure
  family already formats with `independence_survey._fmt_p`, which yields "<.001" | call `_fmt_p`.
IMPORTANT | src/quebra/plots/check_outcome_plot.py:127 | cell text is unconditionally
  `ON_FILL_TEXT["color"]` = #333333, drawn on the dark `pass` (#12776A) and `fail` (#7E1A11)
  fills; independence_survey_plot.py:140-142 switches to white for exactly those two verdicts |
  copy that conditional.
IMPORTANT | src/quebra/plots/check_outcome_plot.py:64 | no legend: colour is the only encoding of
  the verdict and nothing on the figure maps colour to verdict, while the sibling grid figure
  builds one from VERDICT_ORDER (independence_survey_plot.py:73-83). "no row" (#F0F0F0) and
  "not computed" (#D8D8D8) are then indistinguishable in practice | add the Patch legend as the
  sibling does, or state the per-verdict tally from `grid.counts` in the caption.
MINOR | src/quebra/plots/check_outcome_plot.py:84 | caption says "{n} of {m} checks shown; all of
  them are in the artifact", but only the display-set's RESULTS are on `CheckOutcome`; the
  run-set's non-displayed rows appear as key tuples only | say "all of them are named in the
  artifact" or drop the clause.

### src/quebra/analyzers/assumptions.py
Validation in `__post_init__` is sound and every raise is structural. The arXiv locator
(1802.08339) matches the existing citations in c1_lewis_robinson.py:3 and
c2_anderson_darling.py:3, so it is not invented. `SHIPPED_CHECK_NAMES` is derived from the check
modules, so a record cannot name a check that does not ship.
MINOR | src/quebra/analyzers/assumptions.py:163 | `ASSUMPTIONS = {r.id: r for r in _RECORDS}`
  silently drops a record whose id duplicates an earlier one, which is exactly the failure the
  one-literal-one-line workflow invites | raise when `len(ASSUMPTIONS) != len(_RECORDS)`.
MINOR | src/quebra/analyzers/assumptions.py:145 | writes "no locator located"; AGENTS.md section
  10 fixes the phrase as "no source located" | use the mandated phrase so a grep finds it.
NOTE: nothing in `src/` or `jobs/` imports this module yet; it is consumed only by the new tests.

### jobs/active/km_with_checks_6d2s.py
Carve parameters VERIFIED identical to jobs/active/km_poster_6d2s.py: same THRESHOLD tuple
("3.0 µs", 3.0e-6, True), same five DATASETS with the same qubits and labels, same
load/_filter_step/_final_stage/_t2star_run chain, byte-identical `_windows_run` bodies, and
`gap_mult=10.0` both sides. Neither passes `sigma_col`, `k` or `use_uncertainty`, so both take
windows.make_inputs_from_frame's defaults (sigma=None, k=1.0, use_uncertainty=False).
Run identity VERIFIED: `run_set`/`display_set` are step kwargs (lines 220, 237-238) and
`core/closure.py:221` recurses into tuples, so a tuple of string triples renders into the
parameter row. `seed=SEED` is a declared step kwarg, not a default.
IMPORTANT | jobs/active/km_with_checks_6d2s.py:243 | comment claims the materialized artifact
  holds "the full check outcome including the rows that ran but are not shown", and
  check_outcome_plot.py:84 prints the same claim on the figure; `CheckOutcome.grids` is built
  from `display` only (check_outcome.py:159), so the non-displayed rows survive as key tuples
  and nothing else | say the run-set is NAMED in the artifact, not that its results are.
IMPORTANT | jobs/active/km_with_checks_6d2s.py:140 | `_ledger_run` derives only `include_c3`
  from the run-set and never applies `check_selection.select_rows`, whose own docstring says it
  "is what makes the result match the run-set exactly"; with RUN_SET = PERMUTATION_KEYS the
  battery's `include_tau_checks` gate still emits the c1-ASYMPTOTIC row (battery.py:148-155) and
  the cvm-asymptotic row, so the materialized ledger carries rows the declared run_set excludes
  on the stated grounds that they are oversized | filter the ledger frame to `run_set` before
  returning, or state in the comment that the ledger is the coarse battery output.
IMPORTANT | jobs/active/km_with_checks_6d2s.py:50 | comment says GAP_MULT "MUST equal
  jobs/active/km_poster_6d2s.py - the differential test is what holds them equal", but
  tests/test_carve_differential.py:40 hardcodes `POSTER_CARVE = {"gap_mult": 10.0, ...}` instead
  of importing either job's value, and km_poster_6d2s.py:121 is an inline literal; editing either
  one breaks the equality with nothing failing | reference one constant from both jobs.
MINOR | jobs/active/km_with_checks_6d2s.py:11 | "the two live carve configurations" reads as
  km_poster vs this job, but the test compares POSTER_CARVE vs SURVEY_CARVE
  (independence_survey, use_uncertainty=True); this job's carve is textually km_poster's, so the
  uncertainty rationale is not what makes THEM agree | name the two configurations compared.

### Severity correction
The `alpha` default finding (check_outcome.py:130) is downgraded to MINOR: this job does pass
`alpha=ALPHA` explicitly, so the default is a latent trap rather than a live defect.
