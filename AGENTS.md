# AGENTS.md

QUEBRA is a reliability-statistics toolkit for qubit quality time series. It carves
threshold-excursion durations out of metric series and applies survival and
repairable-systems statistics to them.

Implemented today: Kaplan-Meier, MTBF and MTBC, window carving with an explicit gap policy,
and an independence check battery. Nelson-Aalen, log-rank, RMST and MCF are NOT implemented;
`grep -rli` finds no module for any of them. Do not describe them as shipping.

Read this file every session. Read `spec/PLAN.md` only when told which phase to work on.

---

## 1. Hard rules

**Never run `git add`, `git commit`, `git push`, `git tag`, `git reset`, `git checkout`.**
Sera commits. You stop at checkpoints and say so. These are also denied at user scope, so an
attempt will fail; do not work around it by invoking git through Python or a shell script.

**Never write to `data/` or `outputs/`.** You may read anything under `data/`, including
`data/real_private/`. You may write code that reads and writes those trees at runtime. You may
not edit a dataset or a materialised artifact directly. Machinery, never evidence.

**Never modify `.claude/settings.json`, `.claude/hooks/`, or your own permissions.**

**Do not self-review deterministic properties.** If a property can be checked by `make check`,
run it and report the exit code. Do not assert that lint passes, types check, or tests pass
without having run them.

**Ask before installing anything.** No `pip install`, no new dependency in `pyproject.toml`
without approval.

---

## 2. Where things live

| Directory | Contains | Rendered in docs? | Ships in wheel? |
|---|---|---|---|
| `src/quebra/` | the package | API reference only | yes |
| `tests/` | the six test tiers, see §5 | no | no |
| `docs/` | user-facing documentation (Sphinx) | yes | no |
| `spec/` | the plan and per-phase requirement specs | **no** | no |
| `docs/adr/` | architecture decision records | **no** | no |
| `data/` | datasets, three-way split | no | no |
| `outputs/` | materialised run artifacts | no | no |

`spec/` and `docs/adr/` are in `exclude_patterns` and in the hatch `exclude` list. They are
tracked in git and never published. Prose belongs in `spec/`, never in `.claude/`, which holds
configuration only.

Thesis and paper LaTeX live outside this repository and cite a git tag. Never reference them.

**Write specs and docs in Markdown, not LaTeX.** What makes a spec work is numbered
requirements, explicit acceptance criteria, and a done-when clause per item, not the markup.

---

## 3. Architecture invariants

**Layering.** `core` sits beneath everything. `core` must not import from `loaders`,
`transforms`, `plots`, `analyzers`, or `jobs`. This is currently violated by `core/job.py` and
is being repaired; `lint-imports` is the authority, not your judgement.

**Identity.** Logical job ID determines the graph node. Content hashes determine identity.
Filesystem location is **never** identity. Never key a cache on a path string or a module name.

**Plot contract.** Every plotting function accepts an optional `ax`, draws into it, and returns
the `Axes`. Never call `plt.show()` or `fig.savefig()` inside library code.

**No class hierarchies for job families.** Categorisation is a module-level `JOB_FAMILY`
constant plus auto-discovery. Do not introduce `ValidationJob`/`SurveyJob` base classes.

---

## 4. Domain invariants

Violating these is a scientific error, not a style problem.

**In-spec means the metric is at or above the threshold.** For T2\*, in-spec is
`T2* >= threshold`. Never invert this.

**Never resample a metric time series onto a uniform grid.** Resampling destroys and invents
threshold crossings; measured loss is roughly 25 to 45 percent of real crossings at working
thresholds. If a function needs regular spacing, it is the wrong function.

**Locked vocabulary. These are not synonyms and must never be substituted:**

- `within-calibration` - metric series, KM/NA estimators, threshold excursion windows
- `across-calibration` - calibration event records, MCF, repair effectiveness
- Do **not** use `repairable` / `non_repairable` as OUR vocabulary. The rename landed on
  2026-08-23 (SPEC 0001 R0.4). The literature's own term is a separate matter: `repairable
  system` is standard usage from Ascher and Feingold and from Rigdon and Basu, and it stays
  in prose that cites that field, because rewriting it there would make the sentence false.
  `panels/across_calibration.py` carries the canonical note on why our tiers are named after
  the calibration boundary instead. Twelve lines remain in `*.py` for that reason.
- `in-spec fraction` for the within-calibration quantity. `availability` is reserved for the
  across-calibration systems tier.
- Load-bearing terms, never to be reworded: **window, read, bag, check, band, scan clock,
  window age, birth type**.

**Statistical licensing.** The Kaplan-Meier confidence band and the k-sample log-rank comparison
are two consequences of one assumption. A failed serial-independence check revokes both
together. Never report a band from a scan whose checks failed.

---

## 5. Tests

Six tiers, each answering a different question:

| Tier | Directory | Question | Marker |
|---|---|---|---|
| Unit | `tests/unit/` | does this function do its small thing? | none |
| Properties | `tests/properties/` | do the invariants hold under arbitrary input? | none |
| Statistical | `tests/statistical/` | is the estimator correct? | `slow` for full grids |
| Integration | `tests/integration/` | does the machinery wire up? | none |
| Validation jobs | `tests/jobs/` | does an end-to-end job reach the right verdict? | `heavy` if large |
| Regression | `tests/regression/` | did a refactor change a published number? | `real` |

**Oracle rule.** Every test in `statistical/` and `jobs/` must name its oracle - an analytic
value, a reference implementation, or a simulation truth - in the test name or the first line of
the docstring. A test that cannot name an oracle belongs in `unit/` or should not exist. Do not
write tests that assert what the code currently returns.

`real` and `r` tests **skip** when the prerequisite is absent. They never pass with mocked
values. CI never sees `data/real_private/`.

---

## 6. Commands

```
make check     # lint + types + arch + fast tests. Run before every checkpoint.
make lint      # ruff check + format check
make types     # mypy on src/quebra/core
make arch      # lint-imports
make test      # pytest -m "not slow and not heavy and not real and not r"
make test-all  # everything except real
make docs      # sphinx-build -W --nitpicky
make clean     # remove __pycache__
```

---

## 7. Checkpoint protocol

Work is cut into numbered checkpoints defined in the phase spec. At a checkpoint, stop and print
exactly this, then wait:

```
CHECKPOINT <n.n> - <one line: what this checkpoint achieved>

  Changed:      <paths>  (<count> files)
  Gates run:    ruff <exit> | mypy <exit> | lint-imports <exit> | pytest <exit> (<n> passed)
  Not done:     <what a reader might assume was done but was not>
  Known risk:   <what could break, especially cached identities>
  Suggested:    <conventional-commit message, one line>

  Review `git diff` and commit if you see fit. I will not proceed until you say so.
```

`Not done` and `Known risk` are mandatory and must not be "none" unless that is literally true.
They are what makes the diff review fast. Do not proceed past a checkpoint on your own
initiative, even if the next step seems obvious.

---

## 8. Writing rules

These apply to every docstring, comment, spec, ADR and doc page you write.

- **No em dashes anywhere.** Use spaced hyphens.
- No "surfacing", "brings into view", "data-driven", "delve", "leverage" as a verb, "firstly" as
  an orphaned ordinal, or "excellent" as hyperbole.
- No overclaiming. "To our knowledge" is used deliberately and sparingly, not as a hedge.
- Short declarative paragraphs. Colon expansions over dense subordinate clauses.
- Never invent a section number, equation number, figure number, or citation. If you do not know
  the locator, write "no source located".
- Statistical docstrings carry a `Validity assumptions` section with four fields per assumption:
  assumption, diagnostic, consequence of violation, reference.
