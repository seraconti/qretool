# SPEC 0008 - The validity contract

**Phase:** 4
**Budget:** 16-26 h. Above `quebraplan.md`'s 10-18 h: R8.1 is a measurement the plan did not
scope, and R8.3/R8.4 replace the licensing gate with two selectors, an output-builder and a render path.
**Depends on:** SPEC 0005 complete and committed (`ab885a0`)
**Feeds:** `quebraplan.md` 5.3 (five-layer estimator validation).
**Blocks:** `quebraplan.md` 8.2, whose reference material is "estimator signatures and assumptions"
and consumes R8.2 directly.
**Reference:** `spec/quebraplan.md` §2, Phase 4

**Numbering.** 0006 is claimed by three references as test architecture (`specidentity05.md:6`,
`:516`, `specboundaries04.md:342`) and `specinstallabity02.md:68` reserves 0007 for the R boundary.
This spec takes the next free number so all four references stay correct.

Rationale lives in `spec/quebraplan.md`. This file contains requirements and acceptance criteria
only. Do not re-derive or re-argue the decisions below.

The governing constraint: **the band is always computed and always drawn. The check outcome is a
visual input on how much to trust it, never a gate that hides it.**

---

## Preconditions

Baseline on `dev` at `ab885a0`, measured rather than assumed:

- `pytest --collect-only -q` gives **457 tests**. Every requirement states its collect delta.
- `make check` exits 0 (455 passed, 2 skipped). `make deps` exits 0. `make check-ci` exits 0.
- Zero tests carry the `slow` / `heavy` / `real` / `r` markers, so the fast selector excludes
  nothing and `make test` is the whole suite.
- True CI shape - tracked files only, no `output/`, no Rscript - gives 454 passed, 3 skipped.
- **No test in `tests/` reads private data.** The only one that touches it skips
  (`tests/test_data_manifest.py:29`). R8.1 must not change that.

---

## R8.0 - Five premises in the plan do not survive contact with the code

### R8.0.1 The k-sample log-rank comparison does not exist

`AGENTS.md:11-12` already records this and no `.py` file matches `log.?rank|logrank`.
`kaplan_meier.compare()` is deliberately not a test: `kaplan_meier.py:126-127` says "`separation`
is a DISTANCE, not a test: no p-value is attached and none is implied".

`AGENTS.md` §5 describes the band and the log-rank comparison as "two consequences of one
assumption ... revoked together". That pair has one member today. **The mechanism is built for one
consumer with a named extension point**, and §5 is amended in R8.7 rather than left contradicting
the code.

### R8.0.2 The bench and the shipped ledger disagree about the calendar-clock truncation time

**WITHDRAWN as "the most consequential finding in this phase".** The mechanism is real; R8.1
measured the effect as small. See R8.1 for the numbers and for the defect measuring it surfaced.

`jobs/bench/arms.py:296-317` passes `observation_end_s=n_reads * READ_DT_S`, with the reason in
its own docstring:

> The observation interval is `[0, n_reads*dt)` - one full read interval PAST the last read - not
> `[0, t_last]`. That distinction is the difference between a truncation time chosen in advance and
> one read off the data: ending at the last read makes `tau` an event-determined boundary, and when
> the final window is a single read it collapses to `tau == T_N`, where eq (7) is singular.
> Measured: that hits 25% of Arm B replicates on the calendar clock.

`analyzers/check_ledger.py:340-345` passes no `observation_end_s`. Arms B and C are the only source
of `clock=calendar` acceptance cells, so **every real calendar C1/C2/CvM verdict is scored against
bench cells calibrated under a truncation rule the production path does not use.**

### R8.0.3 "Non-empty risk set" is already deliberately not a raise

`quebraplan.md` 4.2 lists it as a contract candidate. `analyzers/kaplan_meier.py:237-240` lets a
fully consumed risk set produce `inf`, and defends the result: NaN "propagates into the band and
the renderer draws no band there, which is the honest rendering of 'the variance is not defined
here'". A precondition there would delete a documented decision. **Dropped from the candidate
list.**

### R8.0.4 "Binary event codes" is real but unreachable from any shipped job

Birth and death codes are strings (`analyzers/windows.py:39-47`) consumed by equality and never
validated against the enum. `analyzers/kaplan_meier.py:183` makes an unrecognised `death_type`
silently `False`, that is censored; `:195` coerces any nonzero float to an observed death.

But `windows.carve` is the only producer and emits only the three enum values, so both paths need a
hand-constructed `KaplanMeierInputs`. A legitimate dataclass contract, **reachable by a caller and
not by a job**, and the spec says so rather than billing it as a live defect.

### R8.0.5 The reduction problem is dissolved, not solved

`check_ledger.run` emits one row per `(dataset_id, threshold_label, clock, check_id, calibration,
variant)` (`check_ledger.py:80-102`), crossing each threshold with both clocks and the nine
`battery.ROW_KEYS` plus a C3 row (`check_ledger.py:265-268`): **20 rows per dataset** at one
threshold, 100 across `km_poster_6d2s`'s five.

No rule collapses those to one licence without revoking always. C3 reads `not computed` on any
machine without Rscript, and `check_ledger.py:15-18` measures in-spec C1/C2 as singular at roughly
73% of synthetic replicates. Advisory display replaces the collapse; promotion to a gate is
deferred and given a home in R8.7.

---

## R8.1 - Measure the truncation-time disagreement first

The opening step of the phase, before any mechanism is built on calendar-clock verdicts.

Run `segments_from_windows` on a real threshold's window table, calendar clock, with and without an
`observation_end_s`, and compare the resulting C1 / C2 / CvM p-values and verdicts.

**The observation end is the last `t_read_s` PLUS one median read interval.** Two wrong answers
were considered and both are ruled out by measurement:

- `n_reads * median_spacing_s` equals the record end only on the bench's gap-free synthetic arms
  (`jobs/bench/arms.py:316`); on a gapped record it makes the delta an artifact of the gaps.
- **The last `t_read_s` alone**, which this spec originally prescribed, is exactly where a
  zero-duration final window is born, so it leaves `tau == T_N` untouched and clears nothing.

One read interval past the last read is what `jobs/bench/arms.py:296-317` already does and says it
does. `tests/test_calendar_tau_truncation.py` asserts all three branches so the wrong prescription
cannot return unnoticed.

### R8.1 measured result

Five records, the ones `jobs/active/km_poster_6d2s.py` draws, at 3.0 us, calendar clock, seed 777,
999 permutations, both rules sharing ONE permutation set because `observation_end_s` changes only
`tau` and never the events, so the segment sizes are identical.

| Quantity | Measured |
|---|---|
| Rows compared | 45 (5 datasets x 9 `ROW_KEYS`) |
| Computed under both rules | 38 |
| Rows whose p-value moved at all | 6, all on `280623_6D2S_qubit2` |
| max abs delta p | **0.034** (mean 0.0028) |
| Rejection flips at alpha = 0.05 | **0** |
| Rejection flips at alpha = 0.01 | **0** |
| Computed-vs-not-computed flips | **0** |

Four of the five records do not move at all, because their final window dies at the last read, so
the two rules coincide. Only `280623_6D2S_qubit2` ends out of spec, leaving 75.0 s of trailing
reads: its `tau` goes 40173.2 to 40248.2 against `T_N` = 40154.4.

**So the truncation-rule mismatch changes no verdict on the shipped records, and this phase does
not correct production on its account.** The scope of that statement is five records at one
threshold; the ledger runs a ladder and `independence_survey` covers 34 datasets, so it is not a
claim about the survey.

### The defect the measurement did surface

**A zero-duration window ends a block, and then `tau == T_N` exactly on the calendar clock,
whatever the truncation rule.** The events are births, so `tau - T_N = t_death[-1] - t_birth[-1]`,
which is zero when a window is born and dies at the same read.

Measured on `070723_6D2S_qubit4`: 2 of 418 windows have `duration_s == 0.0`, one dying at
`gap_start` and one at `scan_end`. C2 refuses both segments, the ledger's fallback fires
(`check_ledger.py:381-419`) and **5 of that record's 9 rows are dropped; 4 survive.** That is a
whole dataset losing C1 and C2 on this clock, and it is live today.

`observation_end_s` cannot be the whole fix: it applies to the FINAL block only
(`_multiprocess.py:222-229`), so the interior one stays degenerate however far it is pushed.
`tests/test_calendar_tau_truncation.py` pins that too.

**Not decided here.** Whether the carve should emit zero-duration windows at all, whether a block
boundary should be advanced one read interval in general, and whether `n_censored = 1` on this
clock should become a measurement are all downstream of the same question and are Sera's call.

**Recorded without being decided here:** interior censoring is unchecked on the calendar clock.
`n_censored = 1` is hardcoded at `checks/_multiprocess.py:319` while `Segment` documents
`n_censored_dropped` as 0 or 1 and, in the code's own words, "nothing enforces it". The interior
case is already settled as gap-start (`_multiprocess.py:279-281`, pinned by
`test_interior_segments_are_truncated_at_the_gap_start_not_at_an_event`); only the **final** block
is open.

**Acceptance.**

1. The delta is reported as a number, not a direction.
2. If verdicts move, the spec states plainly that published calendar-clock rows were scored against
   mismatched bench cells. Whether this phase corrects them is a checkpoint stop, not an
   implementation decision.
3. The pinning test **skips on absent `data/real_private/`**, following
   `tests/test_data_manifest.py:29`, or runs off a committed fixture. Naming which is mandatory,
   or CI goes red at CHECKPOINT 8.1.
4. Collect delta: +1 to +3.

---

## R8.2 - The assumption record

`src/quebra/analyzers/assumptions.py`, a frozen dataclass carrying the four fields `AGENTS.md` §10
already mandates for statistical docstrings, plus the disposition `quebraplan.md` 4.1 adds:

```
Assumption: id, statement, diagnostic, consequence, reference, disposition
```

- `id` follows the repo's existing lowercase convention (`a1_renewal_durations`), matching
  `CHECK_NAME` strings and the `C1_*.md` doc pages, so one grep spans code, tests and docs. This
  declines `quebraplan.md` 4.4's uppercase `test_A3_*` style deliberately.
- `disposition` is closed at **`raises` / `reports` / `undetected`**. `warns` is excluded: its one
  instance in the package is a schema clock warning, so among assumption records it would have zero
  members. Add it when something needs it.

  **Amended during R8.2.** This spec first closed the vocabulary at two values. A2 has no
  diagnostic, so neither fits: `reports` would claim a report nothing emits, which is the section 4
  defect this phase exists to prevent. `undetected` is the honest third value and is not a
  placeholder - it states that the package cannot see this assumption fail.
- The registry is a module-level id to `Assumption` mapping, imitating `CHECK_LABELS`.

### One record, and the infrastructure to add more cheaply

**Amended during R8.2.** This spec first required two records. `a2_noninformative_censoring`
is NOT shipped: stating it in the package means stating the justification for treating
censoring as non-informative here, that justification is a scheme-level argument held outside
this framework, and it has not been written down. A record asserting a reason its author did
not give is worse than no record. The idea is parked in `spec/quebraplan.md` section 9.1 to be
reasoned about separately.

What R8.2 owes instead is that adding the next record is cheap. `diagnostic_checks` lives ON
the `Assumption`, so there is no second registry to keep in sync; the id shape
`a<number>_<snake_case>` is enforced so a new record cannot fall outside the trace grep; and
the `undetected` disposition already exists for an assumption the package cannot see fail. A
record with empty `diagnostic_checks` is constructible today and is refused only if it also
claims to report or raise something. `tests/test_assumptions.py` asserts each of those against
the constructor rather than only against the shipped registry.

### The record that ships

**`a1_renewal_durations`**, transcribed from the prose that already states it at
`docs/iid_checks/iid_checks_basics.md:13-19` ("independent, identically distributed, no trend").
Diagnostic: the six checks. Disposition: `reports`.

### One thing the record states rather than assumes

The checks and the band are computed on different samples.
`kaplan_meier.make_inputs_from_windows` keeps `birth_type == BIRTH_UP_CROSSING` and retains
censored windows as censored observations (`kaplan_meier.py:180-188`). In-spec
`segments_from_windows` uses `x = durations[complete]`, folds the censored window into `tau` and
keeps every birth type (`_multiprocess.py:294-310`); on the calendar clock the events are births
and `x = np.diff(t_birth)`.

So a verdict about one sample is displayed beside a band estimated on another. The record states
whether that transfer is valid, or that it is unresolved.

### Scope

`kaplan_meier` and `mtbf`. **Not `reliability_band`**: it ships `ESTIMATOR_CRUDE`
(`reliability_band.py:187`), whose estimator drops censored windows (`:218`), and its band bounds
are `None`, so a record attached there would describe a different estimator than KM. Revisit at the
KM pass.

**Acceptance.** `a1_renewal_durations` exists with every field non-empty; a record naming no
check is constructible only with the `undetected` disposition; an id outside the grep shape is
refused. Collect delta: +3 to +5.

---

## R8.3 - One modular point: two independent selectors

Two separate tuples over the **full `(check_id, calibration, variant)` row key**, keyed on
`SURVEY_KEYS` so C3 is inside the vocabulary:

- **run-set**: which rows the battery computes.
- **display-set**: which rows reach a figure. Independent of the run-set, and a subset of it.

Full row-key granularity is what lets C1-permutation display while C1-asymptotic does not, which
matters because the asymptotic rows are the ones measured as oversized at these event counts
(`docs/iid_checks/C1_lewis_robinson.md:36-40`).

**The run-set subsumes the three existing booleans rather than joining them.** `include_c3`
(`check_ledger.py:168`), `include_c2_asymptotic` and `include_tau_checks` (`checks/battery.py:98-99`)
are derived from the run-set, so this is one modular point and not a fourth knob. Where a boolean
must survive because the battery drops a row at runtime for a mathematical reason, say so
explicitly.

**Both are step kwargs on the output-builder, not a filter on a sink loop.** Tuples of strings are
rendered by `core/closure.py:219-235`, so they enter the run identity and reach the Mermaid label,
which the runner builds from `node.kwargs`. A filter on a `job.figure` loop in the job file would
reach neither. A typed licence object could not be a kwarg at all: that allowlist raises
`TypeError` on anything but scalars and containers of scalars.

Selection resolves in the output-builder, never in the renderer, per `AGENTS.md` §3.

**A displayed row that produced no answer still renders**, as its `not computed` cell with the
reason attached. Rows legitimately vanish at runtime: C1 and C2 are dropped when tau is singular,
and C2-asymptotic for m > 1 (`battery.py:171`, `check_ledger.py:403-419`). Absent and
not-asked-for must not look the same.

**Acceptance.**

1. A run-set smaller than `SURVEY_KEYS` computes fewer rows, and the switches that do it are
   derived from it rather than set by hand. MEASURED: `PERMUTATION_KEYS` declares 6 rows and
   takes the battery from 9 to 8. The 2-row overshoot is `include_tau_checks` being
   all-or-nothing over five rows, so the run-set names AT MOST what ran. Stated, not implied.
2. A display-set smaller than the run-set changes what renders and nothing else.
3. The two are independently settable.
4. Both appear in `.prov.json` and on the Mermaid label.
5. A display-set naming a row outside the run-set raises.
6. Collect delta: +6 to +10.

---

## R8.4 - The output-builder and a separate, Phase-7-readable plot

**Data side.** An output-builder resolves the display-set into the verdict grids to
draw and emits one typed artifact. The selection logic lives here, so the render layer only draws.

**Render side.** One concise plot class drawing the displayed grids, reusing `theme.verdict_color`.
It is a **separate figure** from the survival band, not composed onto one canvas: `job.figure`
binds one plot class to one node, and pulling `quebraplan.md` 7.1's optional-`ax` contract forward
is out of scope here. Write it so Phase 7.1 can adopt it exactly as it adopts the other plots: keep
the drawing in one method whose only inputs are axes, theme and the artifact, so gaining an `ax`
parameter is mechanical.

This leaves `plots/km_survival_plot.py:19-25` alone, which records that in-panel exclusion text was
removed **on the author's instruction**. Nothing goes into the survival panel.

### The job: re-derive the carve deliberately, then verify it

A new job re-derives `km_poster_6d2s`'s carve and steps rather than rewiring it;
`km_poster_6d2s` is treated as reference scaffolding. This knowingly departs from
`jobs/composite/check_ledger_q1.py:3-8` ("Re-deriving the carve here would mean fifty lines that
must stay byte-identical to those jobs forever, or the ledger and the panel would silently describe
different windows"), so the departure is paid for:

- **A differential check runs before the rest of R8.4 is written.** Carve both ways on one dataset
  and diff the window tables. The parameters already differ: `jobs/active/km_poster_6d2s.py:121`
  passes only `gap_mult=10.0`, so `k` and `use_uncertainty` take their defaults
  (`windows.py:277-278`), while `jobs/composite/independence_survey.py:84` sets
  `USE_UNCERTAINTY = True`. The new job picks one deliberately and says why.
- **A test asserts the two carves agree on their output**, not merely on their parameters.
  **If they disagree, that is a finding to report, not a mismatch to paper over.** It may be a
  defect in the original job, and the spec says so rather than silently aligning to whichever is
  newer.
- Adding a `job.materialize` to `km_poster_6d2s` is acceptable if the differential check needs it.
  Its one-time identity move is an accepted cost, not a thing to avoid.

The new job declares `JOB_SWEEP = False`, for the reason `check_ledger_q1.py:32` already does: it
is long, and `discovery.swept` is opt-out (`core/discovery.py:165-169`).

**Acceptance.**

1. The job runs end to end and renders.
2. The band is present and drawn in every case, including when a displayed check reads `fail`.
3. The differential result is reported either way.
4. Collect delta: +4 to +6.

---

## R8.5 - Hard invariants, and the contract question kept honest

### R8.5a De-duplicate without a library

The permutation-set check is copied **six** times, in two variants:

| Site | Sizes expression |
|---|---|
| `c1_lewis_robinson.py:139-145` | `segment_sizes(segments)` |
| `c2_anderson_darling.py:227-233` | `segment_sizes(segments)` |
| `cvm_cramer_von_mises.py:238-244` | `segment_sizes(segments)` |
| `c5_rank_autocorr.py:97-103` | a precomputed `sizes` |
| `c6_exchangeability.py:73-79` | a precomputed `sizes` |
| `battery.py:131-137` | a precomputed `sizes` |

Six, not five: `cvm_cramer_von_mises.py` is easy to miss because it was promoted after the other
copies were written. Missing it would be the `AGENTS.md` §4 defect this repo keeps re-fixing, a
guard applied at one comparison and not its twin.

It is a **construct-or-validate** idiom, not a precondition: the `if` branch builds the missing
argument and only the `elif` validates, so `icontract.require` cannot express half of it.

Extract `_resolve_perm(sizes, perm, n_perm, rng)` into `checks/_permutation.py`, taking the sizes
already computed so both variants collapse onto it. No dependency is needed and the duplication is
then gone.

### R8.5b Evaluate `icontract` against a genuine precondition

The surviving candidate is R8.0.4's: reject an unrecognised `death_type` and a non-boolean
`death_observed` rather than silently reading them as censored or observed. Implement it twice,
once with the bare-`raise` idiom `validate_segment` models and once with `icontract`, in one
checkpoint diff with a comparison table.

The table must carry two costs:

- `checks/result.py:21-22` says "Nothing here prints - the bench calls these hundreds of thousands
  of times", so per-call decorator overhead in `checks/` is a measurable bench cost. Measure it.
- Adoption makes `icontract` a **runtime** dependency of modules inside the identity closure, which
  moves `pyproject.toml`, deptry's `DEP002` list and `make check-ci`'s clean resolve.

**No install without an explicit ask at the checkpoint**, scratch venv included. `AGENTS.md` §1 is
unconditional. Sera installed `icontract` 2.7.3 (MIT; pulls `asttokens`, `typing_extensions`) at
CHECKPOINT 8.5b and directed that it be declared as a dependency.

### R8.5b outcome: adopted, narrowly, with an enforced boundary

Measured on the happy path, 20000 reps, the same invariant both ways:

| | bare raise | `icontract` |
|---|---|---|
| Rejects the bad input | yes | yes |
| Exception type | `ValueError` | **`ViolationError`, a subclass of `AssertionError`** |
| Message | one hand-written line | description + condition + every subexpression's value, automatically |
| Added per-call cost | +0.283 us | +5.197 us (2.59x) |
| At 5 calls (one KM figure) | 0.000 s | 0.000 s |
| At 100,000 calls (bench scale) | - | +0.49 s |
| New runtime dependencies | none | 3 |

**The exception type decided this, not the overhead.** `ViolationError` is not a `ValueError`,
and `analyzers/check_ledger.py` catches `(ValueError, KeyError)` at four sites to turn a check
failure into a REPORTED ROW instead of aborting. A contract inside `analyzers/checks/` would
raise straight past those handlers and kill the run - the exact control flow this phase exists
to prevent.

**So the boundary is where a violation SHOULD abort.** `icontract` is used in exactly one place,
`analyzers/kaplan_meier.py`, on a precondition whose violation means the caller asked for an
estimate of something else. It is FORBIDDEN under `analyzers/checks/`, and
`tests/test_contract_boundary.py` enforces that by AST scan rather than by comment, reads
`ViolationError`'s MRO and the ledger's actual `except` clauses at runtime so the reason cannot
go stale, and carries a positive control so the boundary test cannot pass on a package that
quietly dropped contracts altogether.

The other half of the same invariant - an unrecognised `death_type` - stays a bare raise in
`make_inputs_from_windows`, because it inspects a frame column and the useful message names the
offending values. Same invariant class, different tool, and that split is the finding rather
than an inconsistency.

**Acceptance.** The six sites become one helper with behaviour unchanged, pinned by test; the
comparison is a table with measured overhead rather than an opinion. Collect delta: +4 to +8.

---

## R8.6 - Traceability by test naming

Assumption ids appear in test names and in the first docstring line, so grep is the trace query.
This extends a live convention: 15 test names already carry check or equation ids, reproducible
with

```
grep -rhoE "def test_(eq[0-9]+|c[0-9]+|cvm)_[a-z_0-9]*" tests/
```

One liveness guard asserts every registered assumption id is cited by at least one test name or
first docstring line, modelled on `test_every_surveyed_key_has_a_label_and_a_stated_null`
(`tests/test_independence_survey.py:271`). Without it the trace query rots silently, which is the
failure the anti-resampling liveness test exists for.

**Acceptance.** The guard fails when an id is added with no citing test. Collect delta: +1 to +2.

---

## R8.7 - Docs, vocabulary, and a home for the deferred decision

**`AGENTS.md` §5 is amended, not deleted, and amended with teeth.** "A band is never reported
without its check outcome attached" is satisfiable by a grid of `not computed` cells, which is the
default without Rscript and the measured state for in-spec C1/C2. Under `quebraplan.md` Phase 6,
where C3 moves behind an extra, that becomes normal for a core install. So the rule additionally
requires the attached outcome to **name which checks were asked for and which produced no answer**,
which the run-set makes expressible. Annotate that log-rank is not implemented and that the same
rule applies when it is, so the constraint stays forward-binding rather than becoming a ship claim.

**Vocabulary: "check outcome", not "trust annotation".** The code's word is `verdict` (`VERDICT_*`,
`theme.verdict_color`, `VERDICT_ORDER`), and both the ledger and the survey exist to stop a
non-rejection reading as reassurance (`check_ledger.py:12-13`, `independence_survey.py:8-13`).
"Trust" invites exactly that reading. Add **run-set** and **display-set** to
`docs/FIGURE_STANDARD.md`'s term table, which admits only terms with code behind them.

**The deferred gate decision gets a home.** Nothing in `quebraplan.md` Phases 5 to 9 owns "promote a
check to a band gate": 5.3 validates estimators and 9.1 records decisions already made. Add it to
`spec/quebraplan.md` §7 "Open questions, ordered by value", which is the repo's existing home for
undecided things, and name it as an ADR Phase 9.1 will write. Without that, the §5 amendment reads
as settled while the question behind it is open, which is the state `AGENTS.md` §4's last rule
tells you to avoid.

**Doc destinations.** "How a check's verdict reaches a panel" folds into `docs/PANEL_CONTRACT.md`,
which mentions checks nowhere today. Keeping the `docs/iid_checks/` pages as the citation home for
assumption records is a deliberate **deviation** from `docs/iid_checks/iid_checks_basics.md:4-5`
("the durable parts fold into `docs/PANEL_CONTRACT.md` ... and the rest is deleted"), recorded as
one rather than read selectively.

**Dropped claim.** This phase does **not** settle the seam at `panels/_check_ledger_render.py:24-31`.
Its blocking half is `statistic_series` taking the minimum p-value over calibrations, on a
different figure in a different job.

**Acceptance.** No doc claim in the diff contradicts the code, and the `AGENTS.md` §5 edit is
presented for approval as a domain-invariant change rather than landed as a detail.

---

## Checkpoints

Aligned so checkpoint N delivers R8.N, except 8.6, which delivers R8.6 and R8.7 together:
the trace guard and the doc reconciliation are one review pass over the same claims.

> **CHECKPOINT 8.0** - this spec lands, recording the five premises in R8.0. No behaviour change.

> **CHECKPOINT 8.1** - the truncation delta is measured and reported. **Stop:** if verdicts move,
> whether to correct them here is Sera's call.

> **CHECKPOINT 8.2** - `a1_renewal_durations` exists and is tested. No estimator changed.

> **CHECKPOINT 8.3** - the two selectors, analyzer side only. Nothing renders differently.

> **CHECKPOINT 8.4a** - the carve differential: both carves diffed, result reported. **Stop if they
> disagree** - it may be a defect in the original job.

> **CHECKPOINT 8.4b** - the output-builder, the plot and the new job.

> **CHECKPOINT 8.5a** - the helper extraction. Behaviour-preserving.

> **CHECKPOINT 8.5b** - both contract prototypes and the comparison table. **Stop for the dependency
> decision.**

> **CHECKPOINT 8.6** - the trace guard and the doc reconciliation.

Every checkpoint prints the `AGENTS.md` §9 banner including the mandatory `Not done` and
`Known risk` lines, neither reading "none" unless that is literally true.

---

## Verification

Deterministic gates, run and reported by exit code:

- `make check` **and `make deps`** at every checkpoint. `make check` is `lint types arch test` and
  omits deptry, which CI enforces as a separate step, so the two are not interchangeable.
- `make check-ci` before any push. It does not reproduce CI's 3.11 and 3.12 matrix legs, so a
  floor-only failure stays invisible locally.
- `quebra run <new job>` resolves and renders; `quebra inspect` shows the run-set and display-set on
  the Mermaid label.
- The collect count moves from 457 by the sum of the per-requirement deltas above, with any
  difference explained rather than absorbed.

Tests, each naming its oracle per `AGENTS.md` §7:

- **A liveness control, not only a negative one.** A displayed check reading `fail` must still
  produce a drawn band with its grid present, and the guard must fail if the display-set stops
  selecting anything, so it asserts a non-empty selection on the real job. A control of the form
  "an unlicensed scan must not yield a licensed band" would pass trivially under any rule that
  never licenses.
- The run-set and display-set are independent.
- A displayed row that produced no answer renders as `not computed` with its reason, distinct from
  a row that was never asked for.
- The two carves agree on their window tables, or the disagreement is reported (R8.4).
- The two truncation rules give measurably different p-values, pinned on a synthetic carve that
  runs in CI (R8.1).
- An unrecognised `death_type` and a non-boolean `death_observed` are rejected (R8.5b).
- The trace guard fails on an uncited assumption id (R8.6).

**Known risk to carry at every checkpoint.** At one threshold and two curves, most displayed grids
will be sparse, and on the in-spec clock many cells carry no C1 or C2 answer at all. A figure that
is mostly grey is the honest rendering, but it must be checked that it reads as "nothing was
established" rather than as a broken plot.

---

## Done when

1. `a1_renewal_durations` ships, and adding a further record is one literal plus one line.
2. Run-set and display-set are independently settable, subsume the three existing booleans, enter
   the run identity and appear on the Mermaid label.
3. The band ARTIFACT carries its check outcome (`checks_asked`, `checks_unanswered`,
   `check_verdicts`, `assumption_id`), which is `quebraplan.md` 4.3 as written - the estimator
   exposes the diagnostic rather than a sibling figure carrying it. The grids remain a separate
   figure. The band is drawn in every verdict state.
4. The carve differential is reported, and any disagreement is raised rather than aligned away.
5. The truncation delta from R8.1 is a reported number.
6. The six permutation-set copies are one helper.
7. The contract comparison table exists and the dependency decision is recorded either way.
8. Every registered assumption id is cited by a test, enforced by the guard.
9. `AGENTS.md` §5, `docs/FIGURE_STANDARD.md` and `docs/PANEL_CONTRACT.md` match the code, and the
   deferred gate decision has a home in `spec/quebraplan.md` §7.
10. `make check`, `make deps` and `make check-ci` all exit 0.

---

## Not in this phase

- **Promoting any check to an actual band gate.** It needs the device survey analysed, and R8.7
  gives it a home.
- Composing the band and its grids onto one canvas, and `quebraplan.md` 7.1's optional-`ax`
  contract. R8.4 writes the plot to be adopted by it, not to pre-empt it.
- Nelson-Aalen, log-rank, RMST, MCF.
- Populating `ReliabilityBand.band_lower` / `band_upper`, and an assumption record for it. R8.2
  states why.
- The `statistic_series` minimum-over-calibrations fix and CvM's ladder key. R8.7 states why.
- Typing the `diagnostics: dict` fields on `allan`, `fidelity`, `t2star` and `windows`. That is
  Phase 5.
- Test tiering, and applying the four unused pytest markers. Phase 5, and `AGENTS.md` §7 forbids
  reorganising `tests/` without its own spec.
- **Moving the row-key vocabulary out of `analyzers/independence_survey.py`.** This phase is
  what turned that figure builder into the shared home for `C3_KEY`, `SURVEY_KEYS`,
  `CHECK_LABELS` and `CHECK_NULL`: before it, the only importer was its own plot. Nothing is
  broken and the arch contract is intra-layer, so it is recorded rather than fixed. Sized,
  attributed and given three options in `spec/quebraplan.md` section 9.2. **Decide it at the
  phase-4 review**, not inside the phase.
- The CI gate weaknesses measured while planning this phase: mypy scoped to 11 of 81 files (2201 of
  17242 lines), the minimal ruff select missing `B905` at 21 sites in `src/`, and the
  `python_version = "3.12"` rationale that does not reproduce at mypy 2.3.1 with numpy 2.4.4. A
  small separate pass.
