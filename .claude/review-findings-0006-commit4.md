# Commit 4 (CHECKPOINT 6.8 + 6.10) - two review rounds applied, ALL findings closed

## Status: gates green, ready to commit

lint 0 | types 0 | arch 0 | test 0 (590 passed, 2 skipped, 592 collected) | deps 0 | cov 0 (70%)
acceptance: 7 failures, same node ids as the pre-existing baseline (R6.0.11). Unchanged.

Phase 5 total: 535 -> 592 = +57, inside the stated +44 to +60.

## Round 1: single cold reviewer, DO NOT SHIP, 4 CRITICAL + 7 IMPORTANT. All fixed.

- scipy floor was FABRICATED at 1.17. chatterjeexi shipped in 1.15.0 (verified against the
  1.15.0 release notes, independently, twice). Now `scipy>=1.15`.
- The guard missed the BARE citation form, leaving two live stale citations in
  `src/quebra/analyzers/checks/{c1_lewis_robinson,c2_anderson_darling}.py`. Both fixed and
  the pattern broadened.
- "19 distinct modules" was the pre-fix count (18). "Thirty-two KM tests" was 34.
- ci.yml hand-copied `make cov` and had dropped `require-selector`; now runs the target.
- MIN_CITATIONS floor could not catch a truncated SCOPE.
- Plus: the 48/482 sentence deleted, the five-stale enumeration fixed, "31 tracked
  references" fixed.

## Round 2: 5-dimension workflow + adversarial refuters. 19 findings, 17 held. All fixed.

Run ID `wf_bffe18aa-e96`. 36 of 43 agents completed; 7 refuters died on the session limit,
but all 5 dimension reports landed. Raw findings preserved at
`.claude/commit4-fixlayer-review-partial.md`.

TWO CRITICALS, both mine, both fixed:
1. `tests/test_stale_references.py:5` cited `tests/test_oracle_audit.py`, which has never
   existed in any commit - the exact invented-locator defect the guard exists to catch,
   inside the guard's own docstring, invisible to it because `tests/` is out of SCOPE.
2. The per-prefix "unread" assertion could NOT catch a DELETED SCOPE entry, because it
   iterated over SCOPE itself. Dropping `src/` left the suite green. My comments claiming
   it closed that hole were false. Replaced with `MIN_PER_PREFIX`, whose KEYS are compared
   against SCOPE, so a deleted entry now fails.

MUTATION BATTERY, all five now RED (four were green before):
  drop src/ | drop docs/ | mistype srcc/ | remove the lookbehind | identity _canonical

Also fixed: the 1.17 stragglers at `spec:1041`, `spec:1185` (budget row) and
`tests/test_r_cross_implementation.py:255`; the unreachable importorskip reason string;
`spec:999` 587 -> 589; the spec/ stale enumeration re-derived as 9 sites on 7 lines with the
shipped pattern; `.claude/` count corrected; the docstring's opening scope sentence narrowed
to what is actually walked; ci.yml now reads PIPESTATUS so a failed run is not an empty
fenced block, and its drafting-history comment replaced with the constraint (AGENTS.md s10);
c2's "float precision" replaced with the enforced rel=1e-9 and measured 1e-16 to 1e-13;
arms.py's citation reworded to say the test re-implements the construction rather than
guarding the generator; CI cost restated as a 1.3-1.5x ratio instead of seconds that did not
reproduce on a second measurement.

NEW TEST: `test_citation_pattern_accepts_and_rejects_the_forms_it_claims` (+1 collect, which
is why R6.10 is +3 not +2). The lookbehind had no test and deleting it left the suite green.

REFUTED (2), not acted on:
- c2's rel=1e-9 tolerance being loose: one refuter called the proposed tightening unsound.
  Resolved by rewording the docstring to the enforced value rather than changing the test.
- The ci.yml tee finding was refuted on relevance by one lens but held by the other; the fix
  was cheap and strictly better, so applied anyway.

## Known blind spots, recorded not fixed

- `tests/` and `pyproject.toml` are outside SCOPE. A stale citation inside `tests/` goes
  unseen; one did (CRITICAL 1 above). Stated in the guard's docstring.
- `spec/specvalidity08.md:117` and `:158` cite `tests/test_calendar_tau_truncation.py`,
  which never existed. Out of scope; recorded in the docstring and the spec.
- `my-test_run.py` still leaks as `test_run.py` (a hyphen is not a word character). Asserted
  as a recorded decision in the pattern table test.
- Relative forms (`./tests/test_x.py`) are not matched. Recorded.
- R6.7's three end-to-end reuse tests, unwritten. R6.5 acceptance 6's Greenwood clause,
  unmeetable as written. Kaplan-Meier raises on a zero-in-spec-window threshold where the
  check ledger and reliability_band both degrade gracefully.

## Commit

    git add -A
    git commit -m "test(policy): report coverage in CI, fix the scipy floor, guard citations"

Durable snapshots beside this file: `commit4-working-diff.patch`, `commit4-status.txt`,
`commit4-fixlayer-review-partial.md`.
