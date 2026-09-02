# SPEC 0001 - Hygiene

**Phase:** 0
**Budget:** 6-10 h
**Blocks:** everything
**Reference:** `spec/PLAN.md` §2, Phase 0

Rationale lives in `spec/PLAN.md`. This file contains requirements and acceptance criteria only.
Do not re-derive or re-argue the decisions below.

---

## Preconditions

- P1. `~/.claude/settings.json` and `.claude/settings.json` are in place. **Done manually.**
- P2. GitHub repository renamed. **Done manually.**
- P3. Working tree is clean before starting. Verify with `git status`.

---

## R0.1 - Repository ignore rules

**R0.1.1** `.gitignore` must not exclude `.*`, `*.md`, or `tests/`.

**R0.1.2** `.gitignore` must exclude, from this commit onward:
`data/real_private/` except `data/real_private/MANIFEST.toml`; `data/simulated/` except
`*.toml` and `*.json` manifests; `output/`; `__pycache__/`; `*.py[cod]`; `.venv/`; `build/`;
`dist/`; `*.egg-info/`; `.claude/settings.local.json`; `.ruff_cache/`; `.mypy_cache/`;
`.pytest_cache/`; `docs/_build/`.

**R0.1.3** The target file is given in Appendix A. Use it verbatim unless a rule conflicts with
something already tracked, in which case stop and report the conflict rather than resolving it.

**R0.1.4** Any file currently tracked that the new rules would ignore must be untracked with
`git rm --cached`, never deleted from disk.

**Acceptance**
- `git check-ignore -v tests/` returns nothing.
- `git check-ignore -v README.md` returns nothing.
- `git check-ignore -v .github/workflows/ci.yml` returns nothing.
- `git ls-files | grep -c '\.pyc$'` returns 0.
- `git status --porcelain` lists no deletions of files that should still exist on disk.

---

## R0.2 - Tracked build artifacts

**R0.2.1** No `.pyc`, `__pycache__`, `.egg-info`, or `.DS_Store` may remain tracked.

**R0.2.2** Report the count removed. Do not run `make clean` as a substitute; that removes files
from disk without untracking them.

**Acceptance**
- `git ls-files | grep -E '(__pycache__|\.pyc$|\.egg-info|\.DS_Store)' | wc -l` returns 0.

> **CHECKPOINT 0.1** - ignore rules and artifact untracking. Stop here.
> Suggested: `chore: correct .gitignore and untrack build artifacts`

---

## R0.3 - Development ledger

**R0.3.1** Create `spec/ledger/` and copy the existing Claude Code session transcripts
(`~/.claude/projects/<project-slug>/*.jsonl`) into it. These are subject to a retention sweep
and cannot be recovered once deleted.

**R0.3.2** Write `spec/ledger/README.md` stating what these files are, why they are retained,
and that they are the evidence base for the JOSS AI usage disclosure section and the thesis
methods chapter.

**R0.3.3** Write `spec/ledger/INDEX.md` with one row per session: date, agent and model version,
task, spec or issue referenced, files changed, and the resulting commit hash. Backfill what is
recoverable from the transcripts; leave unknown fields as `unknown`, never as a guess.

**R0.3.4** Redact nothing without asking. If a transcript contains a credential or a private
dataset path, stop and report it rather than editing.

**Acceptance**
- `ls spec/ledger/*.jsonl | wc -l` is greater than 0.
- `spec/ledger/INDEX.md` has one row per `.jsonl` file.

> **CHECKPOINT 0.2** - ledger preserved. Stop here.
> Suggested: `docs(spec): preserve agent development ledger`

---

## R0.4 - Vocabulary correction

The code says `repairable` / `non_repairable`. The thesis says `across-calibration` /
`within-calibration`. These must agree, and the rename is cheapest now, before the source tree
moves in Phase 1.

**R0.4.1** Produce an inventory first. List every module, class, function, variable, string
literal, docstring and filename containing `repairable`, `non_repairable`, `nonrepairable`, or
`non-repairable`. Group by proposed new name. **Stop and present the inventory. Do not rename
anything yet.**

**R0.4.2** The intended mapping is:

| Current | New | Tier |
|---|---|---|
| `non_repairable` | `within_calibration` | metric series, KM/NA, threshold excursion windows |
| `repairable` | `across_calibration` | calibration event records, MCF, repair effectiveness |

Confirm this mapping against each usage site before applying it. If any site does not fit the
tier description, flag it rather than renaming it. An inverted mapping silently inverts the
entire vocabulary of the thesis.

**R0.4.3** Apply the rename with `git mv` for files so history is preserved.

**R0.4.4** `availability` must not be used for any within-calibration quantity. The
within-calibration quantity is `in_spec_fraction`. Report any violation found; do not fix it in
this pass unless it is a pure rename.

**R0.4.5** After the rename, no occurrence of `repairable` may remain outside
`spec/`, `docs/adr/`, and `spec/ledger/`.

**AMENDED 2026-08-23.** The literature's own term is exempt. `repairable system` is standard
usage in reliability theory, and rewriting it inside a sentence that cites that theory makes
the sentence false. It stays in prose that names the field, and in the test docstring that
has to name the pre-rename module to explain why 82 artifacts no longer load.
`panels/across_calibration.py` carries the canonical note. Twelve lines remain, across five
files.

**Acceptance**
- `grep -rn "repairable" --include="*.py" . | wc -l` returns 12, and every one is either
  the mapping note, a cross-reference to it, prose citing reliability theory, or the
  artifact-guard docstring. Zero are our own vocabulary. (Was: returns 0. See the
  amendment above.)
- `make test` exit code is unchanged from before the rename (record both).
- Every renamed file appears in `git status` as a rename, not as add plus delete.

**Known risk to report in the banner:** every cached job identity is invalidated by this change,
because the content hash covers module source.

> **CHECKPOINT 0.3** - vocabulary aligned. Stop here.
> Suggested: `refactor: rename repairable/non_repairable to across/within-calibration`

---

## R0.5 - Project identity

**R0.5.1** Replace the README. It must contain: what QUEBRA does in two sentences, a statement
of need, install instructions (marked "from source until v0.2.0"), a minimal usage example, a
link to the documentation once it exists, and a citation block.

**R0.5.2** Add `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and `CITATION.cff`. `CONTRIBUTING.md`
must cover the three things JOSS checks: how to contribute, how to report a bug, how to get
support.

**R0.5.3** Add `LICENSE`. **Sera chooses the licence. Do not pick one.** Stop and ask if it is
not present.

**R0.5.4** Do not tag. Sera tags `v0.1.0` manually after review.

**Acceptance**
- `README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CITATION.cff`, `LICENSE` all exist and
  are tracked.
- No file contains an em dash.
- No file claims the package is pip-installable.

> **CHECKPOINT 0.4** - project identity files. Stop here.
> Suggested: `docs: add README, contributing, code of conduct, citation`

---

## Done when

All four checkpoints are committed, `make test` passes at the same rate as before Phase 0
started, and `git ls-files` shows `tests/`, `*.md` and `.github/` as tracked.

**Explicitly not in this phase:** no `pyproject.toml`, no `src/` layout, no path resolution
changes, no CI. Those are SPEC 0002. Do not start them.

---

## Appendix A - target `.gitignore`

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
build/
dist/
.venv/
venv/

# Tooling caches
.ruff_cache/
.mypy_cache/
.pytest_cache/
.coverage
htmlcov/

# Docs
docs/_build/

# Agent
.claude/settings.local.json

# Data: private data never leaves this machine, but its manifest does
data/real_private/*
!data/real_private/MANIFEST.toml

# Data: simulated payloads are regenerated, their manifests are not
data/simulated/*
!data/simulated/*.toml
!data/simulated/*.json

# Outputs: artifacts are too large to track; run manifests are committed by hand
output/

# OS
.DS_Store
```
