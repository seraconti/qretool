# AGENTS.md

QUEBRA is a reliability-statistics toolkit for qubit quality time series. It carves
threshold-excursion durations out of a metric record and applies survival and repairable-systems
statistics to them. Correctness, reproducibility and provenance come first. Python 3.11+.

The pipeline is a lazy DAG: nothing runs until a sink (figure or materialize) resolves.

**Implemented today:** Kaplan-Meier, MTBF and MTBC, window carving with an explicit gap policy,
an independence check battery, and the metric analyzers.
**Not implemented:** Nelson-Aalen, log-rank, RMST, MCF. `grep -rli` finds no module for any of
them. Do not describe them as shipping.

This is the only agent-facing file. `CLAUDE.md` is a symlink to it. Read it every session. Read
`spec/PLAN.md` only when told which phase to work on.

---

## 1. Hard rules

**Never run `git add`, `git commit`, `git push`, `git tag`, `git reset`, `git checkout`.**
Sera commits. You stop at checkpoints and say so. These are denied at user scope, so an attempt
will fail. Do not work around it by invoking git through Python or a shell script.

**Never write into `tool/datasets/`, `output/`, `output_backup/` or `output_backup2/`.** You may
read all of them. You may write code that reads and writes them at runtime. You may not edit a
dataset or a materialised artifact directly. Machinery, never evidence. (A three-way `data/`
split replaces `tool/datasets/` in SPEC 0003; until then these are the real paths.)

**Never modify `.claude/settings.json`, `.claude/hooks/`, or your own permissions.**

**Do not self-review deterministic properties.** If a property can be checked by running a
command, run it and report the exit code. Do not assert that lint passes, that types check, or
that tests pass without having run them.

**Ask before installing anything.** No `pip install`, no new dependency, without approval.

---

## 2. Commands

```
pytest                                        # full suite
ruff check --fix . && ruff format .           # lint and format
quebra run jobs/active/<job>.py               # run one job
quebra run --all                              # every job declaring JOB_SWEEP = True
quebra run --all --family t2star              # every job in one family, sweep opt-out included
quebra inspect [job_file]                     # print the graph without running it
```

`make lint`, `make test` and `make clean` wrap the first two. `make types` and `make arch` exist
in the Makefile but do not pass yet: they depend on the `src/` layout (SPEC 0002) and the
import-linter contract (SPEC 0004). A failure from those two tells you which phase you are in.

---

## 3. Principles

Each carries its reason, so it holds as the code grows. Judge against these, not against current
state.

**Steps are pure compute.** The DAG caches and re-runs steps by content hash, so a step must be a
deterministic function of its inputs. Input and output therefore live at the edges: disk access
in loaders, file writes in render targets, drawing in plot and panel classes. A step never reads
disk and never imports matplotlib or plotly.

Panels and plots **are** the render layer and they draw only. Every data-derived quantity lives
in the typed artifact, computed by an output-builder such as
`panels/_within_calibration_compute.build_within_calibration_panel_data`. The renderer keeps only
functions of axes and theme: adaptive limits, decade-guide ticks, colours. Cumulative time and
its relatives are data, not render-local views.

**Physical quantities carry unit suffixes** (`_hz`, `_rel_s`, `_unix_s`, `_local_dt`, `_utc_dt`).
Unit and clock mismatch is the costly bug class here; see `docs/TIME_SEMANTICS.md`. Canonical
frequency keys: `rabi_hz`, `qubit_frequency_hz`, `raw_frequency_hz`, `delta_hz`.

**Errors are raised, not swallowed.** This is a reproducibility tool, so a silent fallback yields
a wrong-but-plausible result. `Job.load()` raises rather than defaulting `run_start` to
`t_raw[0]`, which would be roughly 1970.

**Results are typed dataclasses, not raw dicts**, each defined in the file with the step that
returns it. Analyzers use `make_inputs_from_norm(...)` then `run(inputs)`.

**Formats and render targets are added by registering** (`loaders/registry.py`,
`plots/targets.py`), not by ad-hoc code elsewhere. Schema validation goes through pandera. One
decorated function adds a format or a target with zero other changes.

**Provenance and outputs are append-only.** Every figure sink and every materialize emits
`.prov.json` and `.prov.md`, and `output/` is never deleted. Step kwargs that affect output
appear on the Mermaid label.

**No class hierarchies for job families.** Categorisation is by directory and a discriminator,
never by subtype polymorphism. Do not introduce `ValidationJob` / `SurveyJob` base classes.

---

## 4. Claims discipline

Each of these has recurred across sessions. The instance is kept so the rule sticks.

**Never call a mean "the cell".** If a filter leaves a factor varying, the number is a pooled
mean: name the factor and carry the spread. Recurred three times: `report.size_by_n`,
`censoring_effect`, then `calibration_summary.size_vs_n` AFTER the first two were fixed. At n=20
the two Weibull shapes give 0.0650 and 0.0865; a single line labelled "the primary null cell" hid
a spread wider than the effect being drawn.

**A measured number in a docstring must come from the artifact it cites, in the state it ships.**
Quoting a scratchpad run is the same defect as inventing it. Instances: "0.0607" (no such cell;
the table says 0.0757), "44-90 null cells" (44-70), "z_crit 3.3-3.5" (3.25-3.38), a test pinning
0.061 borrowed from a different generator (measured 0.0634). Compute it into the prose, or cite
the table and stop.

**Fix every site of a class, not the one that failed.** A guard at one comparison and not its
twin is not a fix. Instances: `TAU_MARGIN` applied to `tau <= T_N` but not `tau < T_N` (refused
valid records 23% of the time); gap truncation applied to interior segments but not the final
one; the negative-variance split applied to `gamma_hat` but not `gamma_hat_batch`.

**A positive control must fail when the thing it guards is broken.** Assert against the REAL
output, not a copy of the reference. Instances: the carve control compared `reference` to
`reference` and passed with a deliberately broken carve; the AST walk missed `importlib` and
relative imports that its own docstring named; `check_agreement` aligned on a key missing `clock`
and INVENTED 36 pairings.

**State the aggregation and the multiplicity before reading a verdict off it.** Max-over-grid
flattered power by 7x; a flat +/-0.01 size band rejected all seven rows because the max of 44-90
deviations is roughly 3 SE by chance. Say which aggregate gates, and correct for how many cells
it saw.

**When a claim cannot be cheaply verified, write it as the open question it is.** "I have not
measured this" is cheaper than the review that finds it false.

---

## 5. Domain invariants

Violating these is a scientific error, not a style problem. None of them fails a test.

**In-spec means the metric is at or above the threshold.** For T2\*, in-spec is
`T2* >= threshold`. Never invert this.

**Never resample a metric time series onto a uniform grid.** Resampling destroys and invents
threshold crossings; measured loss is roughly 25 to 45 percent of real crossings at working
thresholds. If a function needs regular spacing, it is the wrong function.

**Statistical licensing.** The Kaplan-Meier confidence band and the k-sample log-rank comparison
are two consequences of one assumption. A failed serial-independence check revokes both together.
Never report a band from a scan whose checks failed.

**Locked vocabulary.** These are not synonyms and must never be substituted.

- `within-calibration`: metric series, KM and NA estimators, threshold excursion windows.
- `across-calibration`: calibration event records, MCF, repair effectiveness.
- Do not use `repairable` / `non_repairable` as OUR vocabulary. The rename landed on 2026-08-23
  (SPEC 0001 R0.4). The literature's own term is a separate matter: `repairable system` is
  standard usage from Ascher and Feingold and from Rigdon and Basu, and it stays in prose that
  cites that field, because rewriting it there would make the sentence false.
  `panels/across_calibration.py` carries the canonical note on why our tiers are named after the
  calibration boundary instead. Twelve lines remain in `*.py` for that reason.
- `in-spec fraction` for the within-calibration quantity. `availability` is reserved for the
  across-calibration systems tier.
- Load-bearing terms, never reworded: **window, read, bag, check, band, scan clock, window age,
  birth type**.

---

## 6. The codebase

### Layout (real)

SPEC 0002 moved the packages under `src/quebra/`. Paths below are relative to that, except
`jobs/`, `tests/`, `scripts/` and `docs/`, which stay at the repository root: `jobs/` is the
researcher's analysis configuration rather than library code, and keeping it out of the
wheel is what stops `output/` being written into site-packages.

```
core/        dataset.py, job.py, runner.py, types.py (Norm, Measurement, CalibrationEvent)
provenance.py
loaders/registry.py            built-ins: .csv  .yaml/.yml  .h5/.hdf5  .pkl/.pickle
schemas/     base.py, track912.py (912-day Ramsey), calibration_log.py
transforms/  filter.py, interpolate.py, lookup_prior.py (public check_unix_s lives here)
analyzers/   allan.py, fidelity.py, t2star.py, tlf.py, mtbf.py, psd.py (stub)
             windows.py  in-spec window carving: gap policy, censoring, read table
             signal_band.py, distinguish_band.py, reliability_band.py  the three nested
             band contracts of the within-calibration panel; shape_stats.py
             calibration_summary.py  reshapes the bench tables into the four typed
             artifacts the calibration figures draw; also re-simulates the P-P curve
             checks/  C1 Lewis-Robinson, C2 Anderson-Darling, C3 copula-via-R (needs
             Rscript, absent here), C5 rank autocorrelation, C6 exchangeability.
             battery.py runs the four permutation checks off ONE shared permutation set.
             These are steps: pure compute, and the pipeline may import them.
             Permutation calibration needs an explicit rng. block_permutations raises on
             None, because defaulting to OS entropy made p-values irreproducible while the
             run identity stayed unchanged.
panels/      within_calibration.py, across_calibration.py   generic render components;
             adapters feed them. Renamed from non_repairable/repairable on 2026-08-23.
             _within_calibration_compute.py builds the artifact;
             _within_calibration_render.py is the functions-of-axes half;
             _within_calibration_data.py is the typed contract.
plots/       base.py, targets.py, theme.py, *_plot.py   targets: static, academic, interactive
jobs/active/ ramsey_*.py, ramsey_2x2_*.py, t2star_*.py, mtbf_*.py, check_calibration.py
jobs/composite/ compare_*.py   job.include + .ref across datasets; declares JOB_SWEEP = False
src/quebra/recipes.py          RAMSEY_CONFIG + configure_ramsey_job orchestrator.
                               Moved out of jobs/ in SPEC 0002: it is reusable library
                               code, and leaving it in jobs/ forced the CLI to put the
                               caller's directory on sys.path, which R1.1.4 forbids.
src/quebra/cli.py              the CLI, installed as the `quebra` console script.
                               Anchors output/ and the --all glob on the WORKING
                               DIRECTORY, never on __file__, so an installed copy
                               cannot write into site-packages.
scripts/acceptance.sh          clean-venv acceptance: builds the wheel, installs it
                               outside the repo, and runs the suite from a directory
                               that is not the repository.
tests/                         TRACKED since 2026-08-23 (SPEC 0001 R0.1)
```

`jobs/reference/` holds TRACKED external validation data consumed by both the suite and a
figure: the published load-haul-dump record (Kvaloy and Lindqvist Section 6.1) and the R
reference values written by `jobs/rscripts/reference_values.R`. It sits beside the jobs that
declare it as a Dataset. `reference_values.R` is never run by the test suite; the fixtures are
committed so pytest works without R.

`jobs/bench/` holds a TRACKED calibration study for `analyzers/checks/`: five generating arms,
the real carve via `analyzers/windows.py` primitives, `results/` (`size_table.csv`,
`power_table.csv`) and `promotion_report.md`. It is a study, not a pipeline layer. NOTHING
outside `jobs/bench/` may import it; `tests/test_bench_isolation.py` asserts this across every
pipeline package. Figures needing its numbers declare `jobs/bench/results/*.csv` as a Dataset and
`job.load_df` it, so the dependency runs through provenance instead of around it.

Gitignored: `output/`, `output_backup/`, `output_backup2/`. Generated, append-only.
`monoliths/` and `jobs_old/` were deleted and no longer exist. `scripts/` was
recreated by SPEC 0002 and now holds `acceptance.sh` only.

Note: `provenance.py` reports the tree clean while it changes.

### Job shape

See any `jobs/active/ramsey_*.py`.

- Load the main dataset with `job.load(ds) -> norm`; load the companion with
  `job.load_df(ds) -> DataFrame`.
- Enrich with `lookup_prior(main, comp, fields=[...], aliases={...})`. Source columns
  (`frequency`, `Rabi_frequency`) stay as-is and map to `qubit_frequency_hz` / `rabi_hz` via
  aliases.
- Either call `configure_ramsey_job(job, enriched, profile=..., include_fidelity=..., ...)` or
  wire steps by hand with `job.step(fn, *inputs, name=...)`.
- End in `job.figure(Panel, panel_node, targets=["static","academic"], title=...)`.

### Data

- Main 912-day Ramsey: `tool/datasets/6D2S/{DDMMYY}_6D2S_qubit{N}.pickle`
- Companion calibration pickles: `FOR ZENODO/Main/Fig 2/qubit{N}.pickle`
- Dataset pickles are read-only inputs.

---

## 7. Tests

`tests/` is flat today. The six-tier layout lives in `spec/PLAN.md` Phase 5 and is not built;
do not reorganise it without a spec.

**Oracle rule, effective now.** Any test asserting a statistical result must name its oracle in
the test name or the first line of the docstring: an analytic value, a reference implementation,
or a simulation truth. A test that cannot name an oracle is a change detector, not evidence.
Do not write tests that assert what the code currently returns.

Tests requiring R **skip** when `Rscript` is absent. They never pass with mocked values.

---

## 8. Docs hygiene

This repo has drifted here before. Hold the line.

- `docs/` holds reference docs: `TIME_SEMANTICS`, `PANEL_CONTRACT`, `FIGURE_STANDARD`.
  Architecture rationale lives there, not in this file. Refresh docs; do not narrate evolving
  architecture here.
- Every `.md` file is tracked. The blanket `*.md` and `.*` ignore rules were removed in SPEC 0001
  R0.1, so `.md` needs no `!` exception. The three `!` rules that remain are data-manifest
  carve-outs, not doc ones.
- `FIGURE_STANDARD` binds figures you add or edit. The existing panels are not yet conformant and
  that doc says so.
- Do not create new long `.md` docs unprompted.
- Every claim in a doc must match the code. If unsure, verify against the code; do not assert.
- Do not document deferred or speculative design as if normative. Label it deferred, and keep it
  out of this file.
- No status or progress tables in agent-facing docs; they go stale. Track status in commits and
  issues.
- Prefer small, single-purpose files. The reviewer flags files that have grown unwieldy.

---

## 9. Checkpoint protocol

Work is cut into numbered checkpoints defined in the phase spec. At a checkpoint, stop and print
exactly this, then wait:

```
CHECKPOINT <n.n> - <one line: what this checkpoint achieved>

  Changed:      <paths>  (<count> files)
  Gates run:    ruff <exit> | pytest <exit> (<n> passed) | <other> <exit>
  Not done:     <what a reader might assume was done but was not>
  Known risk:   <what could break, especially cached identities>
  Suggested:    <conventional-commit message, one line>

  Review `git diff` and commit if you see fit. I will not proceed until you say so.
```

`Not done` and `Known risk` are mandatory and must not read "none" unless that is literally true.
They are what makes the diff review fast. Do not proceed past a checkpoint on your own
initiative, even when the next step seems obvious.

---

## 10. Writing rules

These apply to every docstring, comment, spec, ADR and doc page you write.

- **No em dashes anywhere.** Spaced hyphens.
- No "surfacing", "brings into view", "data-driven", "delve", "leverage" as a verb, "firstly" as
  an orphaned ordinal, or "excellent" as hyperbole.
- No overclaiming. "To our knowledge" is used deliberately and sparingly, not as a hedge.
- Short declarative paragraphs. Colon expansions over dense subordinate clauses.
- Never invent a section number, equation number, figure number, or citation. If you do not know
  the locator, write "no source located".
- Statistical docstrings carry a `Validity assumptions` section with four fields per assumption:
  assumption, diagnostic, consequence of violation, reference.
- Specs and docs in Markdown, not LaTeX. What makes a spec work is numbered requirements,
  explicit acceptance criteria and a done-when clause, not the markup.

---

## 11. Scope and workflow

Do not build deferred or speculative work unprompted: composite job machinery beyond what exists,
a real `psd.py` (currently a stub), or large new subsystems. If you ARE asked to, implementing it
is correct and welcome. These are scope calls, not standing prohibitions.

- New functionality: Plan mode (Shift+Tab). The plan is approved by Sera before any edit.
- Implement on Sonnet by default, Opus when Sonnet is not enough.
- Before a checkpoint: `/review` (Opus reviewer, fresh context). ruff and tests green.
- Cold second opinion on a plan or architecture: `/plan-critique`.
- Check a doc against the code: `/doccheck`.