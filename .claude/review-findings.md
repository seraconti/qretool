# P5 review findings

Appended at the moment of discovery, not batched. Format:
`SEVERITY | file:line | problem | minimal fix`

Severities: CRITICAL (wrong number reaches an artifact), IMPORTANT (wrong claim, or a
defect that will fire), MINOR (accuracy, naming, dead reference).

Authority for "what it should be": qre_checks_reference_PREVIEW.pdf, 15 pp.

---

## Increment A - audit

IMPORTANT | analyzers/shape_stats.py:85 | `chatterjee_xi` computes `1 - 3*sum|dr|/(n^2-1)`, which is the TIE-FREE reduction. Reference eq (8) is `1 - n*sum|dr| / (2*sum l_i(n-l_i))`. The two agree only when Y has no ties; our durations are lattice-valued and heavily tied at loose thresholds. | Implement eq (8). Increment B.

IMPORTANT | analyzers/shape_stats.py:104-112 | `xi_p_value` divides by `XI_NULL_VARIANCE = 2/5` unconditionally. That null is derived for continuous tie-free data; reference 10.3 caveat 1 says under ties "the closed-form p-value must not be used and a permutation calibration should replace it". | Permutation-calibrate. Increment B, same increment as the estimator - fixing one without the other is worse than fixing neither.

MINOR | analyzers/shape_stats.py:82 | Only constant X is guarded. Under eq (8) a constant Y makes `l_i = n` for all i, so the denominator `2*sum l_i(n-l_i)` is exactly 0. Harmless today, division by zero the moment eq (8) lands. | Add the constant-Y guard with eq (8).

MINOR | analyzers/checks/c1_lewis_robinson.py:26-30, c2_anderson_darling.py:28-34 | Both docstrings argue for the permutation calibration on their own authority. It is the source paper's OWN prescription (its Section 7), citing Lawless, Cigsar and Cook, Technometrics 54, 2012, for validity under time censoring - reference Section 4. A claim with no locator, in a repo whose rule is that every doc claim match a source. | Add the citation to both docstrings.

MINOR | docs/iid_checks/C5_rank_autocorr.md:16 | Says the studentization "follows the Chung-Romano / Romano-Tirlea argument". Reference Section 7 states explicitly that it is NOT Romano-Tirlea studentization: ours is a lag-comparability correction (different lags have different pair counts), theirs restores level under an uncorrelated-but-dependent null. My own misattribution, written in P4b. | Reword to lag-comparability and name the distinction.

IMPORTANT | analyzers/check_ledger.py:409 | Catches only `(ValueError, KeyError)`. `c3._invoke_rscript` raises `RuntimeError` in five places (c3_serial_copula.py:92,118,123,130,135) and `subprocess.run(timeout=120)` raises `TimeoutExpired`. R is now installed, so `rscript_path()` is non-None and this call executes for real: a failed R invocation KILLS the ledger job instead of writing a `not computed` row. | Widen the except. Increment B.

MINOR | analyzers/check_ledger.py:271 | `r_version` is assigned `str(r_path)` - the PATH to Rscript, not a version - while the module docstring (:20-21) says "the R version is discovered at runtime and lives in CheckLedger.r_version". Field name and docstring both describe something the code does not store. | Capture `Rscript --version`, or rename the field to `r_path`.

IMPORTANT | core/job.py:293-304 with panels/_artifact_guard.py:36 | `Job.code_hash` hashes ONLY the job's own source file, and `StaleArtifactGuard` compares field NAMES only. So editing any analyzer changes every downstream number while the run `identity` stays byte-identical and old pickles keep loading. Nothing in the pipeline signals an analyzer edit. | Out of P5's scope to fix, and larger than it looks. Recorded because it is why the xi change must have its test written first, and it belongs in the Part 7 list.

MINOR | reference PDF Section 5.2 eq (7) | The CvM middle term prints `- i N (T^2_{i+1} - T^2_i)/tau`, which is dimensionally inconsistent: the first term `i^2 X_{i+1}/tau` is dimensionless. Deriving `integral_0^1 (N(s tau) - sN)^2 ds` gives `/tau^2`, and reproduces the document's own tail `N^2[u_N^2 - u_N + 1/3]` exactly. Either a typo or a dropped superscript in extraction. | Correct the reference. Derive rather than transcribe in Increment B.

GREEN | analyzers/checks/c1_lewis_robinson.py:72-88 | Eq (16) transcribed correctly, and only eq (16) exists - the m=1 collapse to eq (4) is asserted numerically by test rather than by a second code path. | none
GREEN | analyzers/checks/c2_anderson_darling.py:69-118 | `ad_limiting_cdf` is Marsaglia-Marsaglia `adinf` alone; `errfix` is deliberately absent and the docstring says why (the statistic is divided by an estimated gamma^2, so the finite-N null is not the finite-N AD null). Matches reference Section 4. | none
GREEN | analyzers/checks/_permutation.py + _rank_serial.py | Permutation never crosses a segment boundary: measured over 500 draws at sizes [4,5,3], every index stays in its own block. Lag pairs likewise - lag-1 gives 9 pairs (sum of size-1), not 11 (total-1). | none
GREEN | analyzers/shape_stats.py:167-181 | `dcor` is the Szekely-Rizzo-Bakirov (2007) double-centred V-statistic and returns R, not R^2 - the same convention as `energy::dcor`, so the Tier 4 comparison is direct. | none
GREEN | analyzers/check_ledger.py LEDGER_COLUMNS | Reference Section 6 requires the ledger report C3's dropped-censored count; `n_censored_dropped` is a ledger column and C3 populates it. | none

IMPORTANT | analyzers/checks/ (m > 1 path) | The multi-process eq (16) route has NO external validation. The only published worked example is Kvaloy and Lindqvist Section 6.2 (Aalen and Husebye 1991 bowel motility, m = 19), whose raw data is in neither the paper nor any repository or R package located on 2026-08-12. Everything we have at m > 1 is internal consistency, which cannot catch a shared transcription error. | `test_small_bowel_motility_multiprocess` skips with the targets and an activation recipe. Obtain the data, or accept the gap explicitly in the instrument report.

MINOR | tests/ | The `m > 1` Anderson-Darling route is an UNWEIGHTED SUM of per-segment eq (7) values, calibrated by permutation. That is an extension beyond the source: the paper drops AD for m > 1 in favour of Cramer-von Mises and offers no multi-process AD form. Documented in c2's docstring, but carries no published evidence of any kind. | Cramer-von Mises (Increment B) gives the first comparator.

---

## Part 1 fidelity table

| routine | claimed source (eq) | what the code computes | agree? | note |
|---|---|---|---|---|
| C1 `statistic` | K-L eq (16); eq (4) at m=1 | `sqrt(12)*sum_j[sum_i T_ij - (N_j/2)tau_j] / sqrt(sum_k g_k^2 tau_k^2 N_k)` | YES | only eq (16) exists; the m=1 collapse is asserted numerically, not by a second code path. Now also pinned to published Table 2 values. |
| C1 calibration | K-L Section 7; Lawless, Cigsar and Cook 2012 | asymptotic N(0,1) + within-segment permutation | YES | but the docstring argues it on its own authority and carries NO locator. Finding logged. |
| C2 `_eq7` | K-L eq (7) | matches term for term; equals the textbook `A^2` at gamma=1 to 1e-15 | YES | pinned by `test_eq7_is_the_classical_anderson_darling` at five n. |
| C2 `ad_limiting_cdf` | Marsaglia and Marsaglia JSS 9(2) 2004 | `adinf` ALONE; `errfix` absent by design | YES | reference Section 4 agrees this is correct: the statistic is divided by an estimated gamma^2, so the finite-N null is not the finite-N AD null. Four critical values pinned. |
| gamma estimators | K-L Appendix 1, eqs (10), (11) | 1: population (1/N) complete gaps. 2: eq (10). 3: ABSENT. | PARTLY | estimator 3's absence matches reference Section 2.3 exactly. But the DIVISOR is ours, not the paper's: reference 2.3 calls estimator 1 the "sample mean and standard deviation", which reads as 1/(N-1), and all three of Table 2's complete-gap numbers land on 1/(N-1) together. See the new findings below. |
| C3 | Ghoudi-Kulperger-Remillard 2001; Genest-Remillard 2004; Kojadinovic-Yan 2011 | imports `copula::serialIndepTest` over a file bridge | N/A | imported, not transcribed. Never executed until now. Censored windows dropped, and the ledger does report the dropped count as reference Section 6 requires. |
| C5 | rank autocorrelation + permutation; reference Section 7 | max over lags of lag-standardised `r_h`, within-segment permutation | YES | permutation and lag pairs both verified never to cross a segment boundary. The "studentized" naming is lag-comparability, NOT Romano-Tirlea - our own doc misattributes it. |
| C6 | portmanteau `Q = sum_h m_h r_h^2`, exact permutation | matches | YES | the one check whose validity rests on no approximation and no citation. |
| Spearman `_spearman` | classical | `scipy.stats.spearmanr` equivalent on ranks | YES | no test of its own. |
| xi `chatterjee_xi` | Chatterjee 2021 eq; reference eq (8) | `1 - 3*sum|dr|/(n^2-1)` = the TIE-FREE reduction | **NO** | reference eq (8) is the tie-corrected form. Our durations are heavily tied. Increment B. |
| xi `xi_p_value` | `sqrt(n) xi -> N(0, 2/5)`, tie-free | uses 2/5 unconditionally | **NO** | reference 10.3 caveat 1 forbids the closed form under ties. Increment B. |
| dcor | Szekely, Rizzo and Bakirov 2007 | double-centred V-statistic, returns R | YES | same convention as `energy::dcor`, so the Tier 4 comparison is direct. No test of its own. |

---

## Part 7 - ranked test proposals (deliverable; NOT implemented in this pass)

Ranked by probability of a wrong number reaching an artifact, times its severity.

1. **Golden-value pins on the shape statistics.** Nothing in `tests/` touches `shape_stats`.
   Catches: exactly the xi tie-free error found in this pass, which has been shipping into
   every `DistinguishBand` since P3; a dcor double-centring error; a `peak_frac` off-by-one.
   This is rank 1 because the defect is already confirmed present and was invisible.
2. **A pin that fails when an analyzer changes a panel number.** `Job.code_hash` hashes only
   the job file and `StaleArtifactGuard` compares field names, so an analyzer edit changes
   every downstream number silently. Catches: any future edit to `shape_stats`, the bands or
   `_within_calibration_compute` that moves a figure without moving the identity.
3. **`segments_from_windows` against a REAL gapped record.** Currently exercised only on
   synthetic tables. Catches: a wrong interior `tau`, a mis-placed split, the `gap_resume`
   taxonomy diverging from `gap_spans_s`.
4. **Cross-check the m > 1 AD sum against CvM on the same segments.** The AD multi-process
   route is an extension beyond the source with no published evidence. Catches: a shared
   error in the per-segment sum that both self-consistency and the bench would miss.
5. **Degenerate-input matrix, one test per case.** Every duration identical; a segment with
   exactly `min_events`; `tau` within float noise of `T_N`; a single-read window with
   `duration_s == 0`. Partly covered by `TAU_MARGIN` work, never systematically.
6. **Permutation-set provenance.** `check_permuted` guards SHAPE only; a same-shape matrix
   built from a different record is undetectable. Catches: silent corruption of every
   permutation p-value in a run, the exact failure the shared-permutation optimisation risks.
7. **C3 CSV round trip with R present.** The write/parse path in `_invoke_rscript` has never
   run. Catches: a locale decimal separator, a column-name mismatch, an R-side error that
   exits 0.
8. **`dcor_with_reason`'s four reason codes.** Catches: a NaN attributed to "constant" when
   the real cause was non-finite input - a wrong reason in a typed contract.
9. **`window_stats` completeness.** Catches: a key silently dropped from the shape row, which
   the panel would render as an empty annotation rather than an error.
10. **Ledger verdict precedence under combined failures** (ties AND too few events AND
    bench-rejected simultaneously). Catches: a precedence inversion that reports the least
    important reason.

---

## Increment A - reviewer pass (independent, fresh context, 2026-08-13)

Scope reviewed: tests/fixtures/__init__.py, tests/fixtures/load_haul_dump.py,
tests/test_checks_published_values.py, this ledger. All gitignored; read directly.

DATA VERDICT: the 36 cumulative times are correct. Strictly increasing, min gap 3 h,
T_36 = 1970, mu = 1970/36 = 54.7222, and SEVEN independent published quantities reproduce
to printed precision (54.72, 47.23, 0.850, 0.605, 0.774, 48.61 via Bessel, 0.888, 0.681).
No transcription error in the fixture.

IMPORTANT | tests/test_checks_published_values.py:22-28 and this ledger:53 | "their Appendix 1 DEFINES the population (1/N) form" has no locator and the cited authority points the other way: reference 2.3 estimator 1 is "sample mean and standard deviation of the completely observed gaps", and ALL THREE of Table 2's complete-gap numbers (48.61, 0.888, 0.681) land on 1/(N-1) simultaneously. The parsimonious reading is that GAMMA_COMPLETE's 1/N is OUR deliberate choice (_multiprocess.gamma_hat:80-81 says exactly that: to match eq 10's divisor), not the paper contradicting its own appendix. Asymptotic C1 is then inflated by sqrt(N/(N-1)): 1.4% at N=36, 12% at N=5, anti-conservative, unflagged. | Add the Appendix-1 locator, or restate as our divisor choice.

IMPORTANT | analyzers/checks/_multiprocess.py:54 vs :57 | Signature default is `estimator=GAMMA_TRUNCATED`; the docstring's first line says "`GAMMA_COMPLETE` is the DEFAULT". Both live call sites (c1:83, c2:171) pass explicitly, so nothing is wrong today; the next caller that omits it silently gets eq (10), which the same docstring says goes negative at small N. The fidelity table's gamma row does not record this. | Fix the signature or the sentence; note it in the row.

IMPORTANT | this ledger:49 | "Now also pinned to published Table 2 values" overstates. Pinned: `c1.statistic`, m=1, GAMMA_COMPLETE only. Not pinned: m>1 eq (16) (the gap already logged at :39), `statistic_batch`, `run`'s p-values, GAMMA_TRUNCATED inside C1. And the directly asserted 0.691 is NOT a published value - the published 0.681 is reached only through the sqrt((N-1)/N) bridge. | Qualify the cell to "m=1, complete-gaps, statistic() only".

MINOR | tests/test_checks_published_values.py:96-101 | "a transcription error in the sqrt(12)/(tau*sqrt(N)) factor would show up here and nowhere else in this file" is false - line 75 and the eq (11) test carry the same factor. "computed independently" also misleads: gamma_hat cancels exactly. The test is NOT circular (the cancellation is what leaves a clean pin on the numerator) but it is nearly implied by the other two pins (0.876 x 0.691 = 0.6053, inside the 0.001 band). | Reword to "pins the numerator and its scaling; gamma cancels by construction".

MINOR | tests/test_checks_published_values.py:88-91 | `gamma_tilde * tau / N` IS reference 2.3's definition (mu_tilde = tau/N), so it is not question-begging - but given the pin at :63 it is the same assertion rescaled (47.23/(2000/36) = 0.85010). Its only independent content is that the paper's printed pair is mutually consistent and that TAU_H and N are right. | Say that, rather than "genuine check ... weaker than a direct pin".

MINOR | tests/test_checks_published_values.py:112-125 | The second assertion is arithmetic on the first; at one N, sqrt(N/(N-1)) = 1.0142 is not separable from any other factor within the 0.01 band, so "identifies the difference as the divisor and nothing else" overstates. What actually identifies it is the simultaneous agreement of 48.61, 0.888 and 0.681 - which the test does assert. | Reword the reasoning; the conclusion stands.

MINOR | tests/test_checks_published_values.py:176,198 | `request` is unused and the skip is unconditional, so the "TO ACTIVATE" recipe activates nothing: adding `SMALL_BOWEL_SEGMENTS` leaves the test skipping until someone rewrites the body. `SMALL_BOWEL_PUBLISHED` (fixture:73-82) is never imported and its numbers are duplicated verbatim in the test docstring. | `seg = getattr(fx, "SMALL_BOWEL_SEGMENTS", None); if seg is None: pytest.skip(...)`, assert against SMALL_BOWEL_PUBLISHED, drop `request`.

MINOR | tests/fixtures/load_haul_dump.py:3-5 | "Technometrics 62(1):101-115" and "Table 1" are unverifiable offline and the volume/issue/pages look wrong for this paper. A thesis citation hardens from here. | Check against the journal record.

MINOR | tests/test_checks_published_values.py, tolerances | Measured margins (used/allowed): mu 0.0022/0.01, sigma_tilde 0.0022/0.01, gamma_tilde 1.0e-4/1e-3, laplace 6.3e-5/1e-3, gamma_pop 1.1e-5/1e-3, LR 2.1e-4/1e-3, sigma bridge 8e-4/0.01, gamma bridge 3.2e-4/1e-3, LR bridge 1.3e-4/1e-3, eq11 1.4e-4/1e-3. Each is ~2x the print half-width - correct order. Discrimination measured by perturbation: a +/-10 h error at any single failure time fails at least one assertion; a +/-1 h error is caught at indices 10, 17, 34 but NOT at 0, 5, 25. | No change; state the +/-1 h residual as the bound this tier certifies.

GREEN | tests/test_checks_published_values.py:139-160 | `_sigma_star_squared` matches reference 2.3 estimator 3 term for term, and reproducing 0.774 is the file's only pin on the gap ORDER (eq 11 is order sensitive, gamma is not). The docstring undersells it as "the surrounding machinery". | none
GREEN | claims verified | `pytest tests/` = 196 passed, 2 skipped. Increment A touched nothing outside tests/ and .claude/ (core/paths.py and .gitignore differ from HEAD but predate it by a day). Permutation confined to blocks, reproduced at sizes [4,5,3] over 500 draws. eq (11) unreachable: GAMMA_ESTIMATORS is exactly the two labels and the ValueError text matches. NOTE: a bare `pytest` from the repo root dies with INTERNALERROR importing monoliths/v13fig/test_carve.py (SystemExit at import); the green claim holds only when scoped to tests/. | none

---

## Post-review corrections (reviewer pass, 2026-08-13)

IMPORTANT | analyzers/checks/_multiprocess.py:54 | Signature is `estimator: str = GAMMA_TRUNCATED`, while the docstring's first line says "`GAMMA_COMPLETE` is the DEFAULT". Both current call sites pass explicitly (c1:83, c2:171) so no shipped number is wrong today - but the next caller that omits the argument silently gets eq (10), which the same docstring warns goes negative at small N. | Change the signature default to `GAMMA_COMPLETE`. Increment B, where source may be touched.

IMPORTANT | tests/test_checks_published_values.py (docstring, now corrected) | An earlier draft asserted "their Appendix 1 DEFINES the population (1/N) form while Table 2 uses 1/(N-1)". That claim came from the P5 brief and is supported by NO source in hand: reference Section 2.3 calls the paper's estimator 1 the "sample mean and standard deviation" of the complete gaps, which reads as 1/(N-1), and says nothing about Appendix 1's divisor. The parsimonious reading is the opposite - 1/N is OUR deliberate choice, made to match eq (10)'s divisor, and `_multiprocess.py:80-81` says exactly that. | Withdrawn from the docstring and restated as observation plus our own choice. Verify against the journal text before the thesis cites it.

IMPORTANT | analyzers/checks/_multiprocess.py (divisor consequence) | Following from the above: our `gamma_hat` is smaller than the paper's estimator 1 by sqrt((N-1)/N), so our C1 statistic is LARGER by sqrt(N/(N-1)) - 1.4% at N = 36, ~12% on a five-event segment. That direction is anti-conservative, and short segments are routine on gapped records. It is a divisor choice and not an error, but it is a difference from the source. | No code change (the reason for 1/N is sound). State it in the instrument report, Increment C.

MINOR | tests/test_checks_published_values.py:96-101 (corrected) | The Laplace test's rationale claimed gamma_hat was "computed independently" - it cancels exactly, being the same call on the same floats. What the test genuinely pins is the `sqrt(12)*(sum T_i - N*tau/2)/(tau*sqrt(N))` scaling, which is real and non-circular. The reviewer also noted the eq (11) test is this file's ONLY pin on gap ORDERING, since eq (11) is order-sensitive and gamma is not - the docstring undersold it. | Rationale corrected.

MINOR | tests/test_checks_published_values.py:198 (corrected) | The skipped m>1 test took an unused `request` fixture and skipped unconditionally, so its "TO ACTIVATE" recipe could never fire - adding the data would not have un-skipped it. | Now reads `SMALL_BOWEL_SEGMENTS` from the fixture and self-activates; asserts against `SMALL_BOWEL_PUBLISHED` rather than re-typing the targets.

MINOR | (out of scope, pre-existing) | A bare `pytest` from the repo root dies with INTERNALERROR importing `monoliths/v13fig/test_carve.py`. The suite is green only when scoped to `pytest tests/`. | Add `monoliths` to a pytest norecursedirs, or keep invoking `pytest tests/`.

GREEN | tests/fixtures/load_haul_dump.py:21-28 | Fixture data verified independently by the reviewer: 36 entries, strictly increasing, min gap 3 h, T_36 = 1970, and seven published quantities reproduce simultaneously. A transcription error large enough to matter cannot survive that many agreements. | none
GREEN | tolerance audit | Every assertion's used margin is 1-2 orders inside its bound; each tolerance is ~2x the published print half-width. A +/-10 h error at any single failure time fails at least one assertion; a +/-1 h interior error is not always caught, which is below Table 2's printed resolution anyway. | state the bound in the instrument report

---

## Increment B - measured before changing anything

MEASURED | analyzers/shape_stats.py | The xi defect is REAL but DORMANT on this dataset. Measured across the whole T2* ladder: 279 windows at 3 us, 30 at 4 us, 1 at 5 us - and **zero windows with a tied X (margin) or a tied Y (forward time)**, on either axis. Reads sit at jittered timestamps so forward time takes distinct values, and margin is a continuous measurement. Where there are no ties, reference eq (8) reduces algebraically to `1 - 3*sum|dr|/(n^2-1)`, so the shipped estimator has been numerically CORRECT on every artifact produced so far, and the 2/5 null is the right null for tie-free data. | Fix it anyway: the tie-free form is right here only by accident, and the reference's caveat targets QUANTISED metrics (a fidelity ladder where most windows are one read long). But the fix must be verified as a no-op on real data, not assumed to be one, and the Part 5 tie experiment must use synthetic tied inputs because this data has none.

---

## Increment B - changes made

DONE | analyzers/checks/_multiprocess.py:54,116 | `gamma_hat` and `gamma_hat_batch` signature defaults changed GAMMA_TRUNCATED -> GAMMA_COMPLETE, matching their own docstrings. Verified no shipped number moves: every call site passes the estimator explicitly. | -
DONE | tests/test_shape_stats.py | NEW, 20 tests, written BEFORE the xi change because nothing else could have caught it. Covers xi (tie-free and tied), the exact finite-n ceiling `1 - 3/(n+1)`, tie_fraction, dcor and its four reason codes. Closes rank 1 of the Part 7 list. | -
DONE | analyzers/permutation.py | NEW shared paired-permutation step wrapping `scipy.stats.permutation_test(permutation_type="pairings")`. Seed required, never defaulted. Distinguished in its docstring from `analyzers/checks/_permutation.py`, which is segment-blocked and for duration vectors. | -
DONE | analyzers/shape_stats.py chatterjee_xi | Now reference eq (8), the tie-corrected form, with a constant-y guard. Verified three ways: matches an independent eq (8) reference on tied data, matches the old tie-free form exactly on tie-free data (4 seeds), and max |new - old| = 0.000e+00 across 279 real windows. | -
DONE | analyzers/shape_stats.py xi_p_value | Calibration now chosen by measuring ties: tie-free -> closed form, tied -> permutation. `xi_p_method` records which, as a new column. `xi_p_value_asymptotic` keeps the closed form for the Part 5 comparison and is labelled tie-free-only. | -
DONE | analyzers/check_ledger.py | Now catches `RuntimeError` and `subprocess.TimeoutExpired` from the C3 bridge, so a failed Rscript writes a `not computed` row instead of killing the job. | -
DONE | analyzers/shape_stats.py NON_NUMERIC_STAT_COLUMNS | Found while wiring `xi_p_method`: `for_windows` medianed EVERY column via `to_numpy(dtype=float)`, which raises on a categorical. The new set names the two non-statistic columns. | -
DONE | seed threading | `xi_seed` reaches `DistinguishBandInputs` -> `make_inputs_from_windows` -> `build_within_calibration_panel_data`. Not yet declared at job level, because on tie-free data the seed is never consulted; a job that meets tied data should declare it as a step kwarg.

OUTSTANDING | Cramer-von Mises (B3) | Not started. It is a whole instrument - derive the statistic from the bridge integral, cross-check against `scipy.stats.cramervonmises` at gamma=1, transcribe and pin the limiting CDF at 0.34730/0.46136/0.58061/0.74346, and write its tests. Deliberately not rushed at the end of a long session in a pass whose entire purpose is fidelity. | Next session, before the Increment B review gate.

MEASURED | analyzers/shape_stats.py xi_p_value | Design question: always-permute, or branch on ties? Measured over all 315 windows of the T2* ladder (median n = 8): closed form 0.17 s, always-permute 128 s - a 760x slowdown per panel render, and the panel renders per dataset and per composite. The branch stays. Note the cost is dominated by scipy's per-call overhead (the xi work itself is ~6 s), so an always-permute path is a tight loop away if ever needed. The ESTIMATOR is unbranched - eq (8) is the complete form and reduces to the tie-free one algebraically - so only the calibration branches, and only where the article says it must.

---

## Increment B - reviewer pass (independent, fresh context, 2026-08-13)

Scope: analyzers/shape_stats.py, analyzers/permutation.py, analyzers/checks/_multiprocess.py,
analyzers/check_ledger.py, analyzers/distinguish_band.py, panels/_within_calibration_compute.py,
tests/test_shape_stats.py. All gitignored; read directly, verified by measurement.

IMPORTANT | analyzers/permutation.py:96-100 | The `-np.inf` substitution for a non-finite resample statistic is ANTI-conservative and does the opposite of its own comment ("must not silently become a rejection"): a -inf null can never be >= the observed, so it is dropped from the numerator and the p-value SHRINKS. Measured on a statistic degenerate on ~half the pairings: p = 0.034 with -inf against 0.506 with the conservative +inf. Dormant for xi and dcor (pairings preserve both marginals, so degeneracy is all-or-nothing) but this module advertises itself to "any analyzer". | Raise, or substitute +inf so a degenerate resample counts as at least as extreme.
IMPORTANT | analyzers/permutation.py:79-82, :49-55 | "The null is always SAMPLED, never enumerated" is false at n <= 4, where (n!)^2 <= 999: measured n = 3 -> 36 enumerated draws, n = 4 -> 576. scipy drops the +1 adjustment on an exact test, so `resolution` = 1/(B+1) misstates the floor (reports 0.02703 at n = 3; the true floor is 1/36 = 0.02778) and `n_resamples` reports 36 rather than the 999 requested. 3-read windows are the modal case here. | Set `exact` from `n_resamples >= factorial(n)**2` and compute `resolution` accordingly, or state the enumeration in the docstring.
IMPORTANT | tests/test_shape_stats.py:99-146 | `_xi_eq8_reference` is never compared to `chatterjee_xi`. `test_the_two_forms_diverge_once_y_is_tied` compares the two test helpers to each other and never calls the implementation, so the ONLY behaviour this increment changed - tied y - is unpinned. (Verified good independently: max |impl - brute eq (8)| = 0 over 3000 random tied grids.) | One line: `assert chatterjee_xi(x, y) == approx(_xi_eq8_reference(x, y))` on the tied fixture.
IMPORTANT | tests/test_shape_stats.py | No test touches `xi_p_value`, `xi_p_method`, the new constant-y guard (shape_stats.py:114-118) or `analyzers/permutation.py`. The tie branch, the method string, and seed reproducibility ship unpinned in the same increment that added them - and per this ledger:29 an analyzer edit leaves the run identity byte-identical. | Three tests: tied -> `permutation`, tie-free -> `asymptotic`, same seed -> same p.
IMPORTANT | analyzers/t2star.py:175-186, analyzers/fidelity.py:248-258 | `xi_seed` is NOT threaded: both step functions call `build_within_calibration_panel_data` without it, so its default 0 is unreachable from any job and never reaches a Mermaid label. `fidelity` is exactly the quantised ladder that motivated the tie branch. This ledger:168 says only "not yet declared at job level", which understates it. Compounding: distinguish_band.py:158-162 says the field is "a constructor field rather than a default" while the code reads `xi_seed: int = 0`. | Add `xi_seed` to both step signatures and pass it; the docstring claim follows.
IMPORTANT | analyzers/shape_stats.py:369 | `pooled_xi` discards the calibration label (`p_pooled, _method = ...`), so the pooled p in the artifact's 4-tuple has no method beside it - contradicting `xi_p_value`'s own "the method is part of the answer, not metadata". Pooled samples are far more tie-prone than per-window ones (3480 reads at 3 us). | Widen the tuple to 5, or return a small dataclass.
IMPORTANT | analyzers/shape_stats.py:90-92 and tests/test_shape_stats.py:54-67 | The `1 - 3/(n+1)` ceiling is the TIE-FREE ceiling, now stated unconditionally on a tie-corrected estimator. Measured counterexamples: n = 12 with two distinct y gives xi = 0.8333 against a claimed ceiling of 0.7692; n = 20, four distinct y gives 0.8800 against 0.8571. The test named "hits the exact finite-n maximum" only pins the tie-free case. | Qualify the docstring "tie-free y" and rename or extend the test.
IMPORTANT | analyzers/shape_stats.py:202-210 | The branch measures ties and never n, so reference 10.3 caveat 2 (small-sample convergence contested; permutation-calibrate in the disputed range) is neither implemented nor recorded. The median window is ~7 reads. Measured type-I of the closed form on independent pairs: 0.0118 at n = 7, 0.0356 at n = 10, 0.0418 at n = 20, 0.0508 at n = 200, all at nominal 0.05 - CONSERVATIVE, so nothing is over-stated, but at n = 5 the smallest attainable p is 0.0385 and the test can barely reject at all. | Add an n floor to the branch, or log caveat 2 as a knowing deviation with these numbers.
IMPORTANT | this ledger:17 | "This p-value is what the panel annotation shows" is false. The shape annotation is rho2 / xi / limb rho / peak (_within_calibration_render.py:99-102) and the xi heatmap plots median and pooled xi (non_repairable.py:632 unpacks `_p` and discards it). No xi p-value reaches any figure today. The fix was still right; its stated urgency was not. | Correct the entry.

MINOR | this ledger:167 | "`for_windows` medianed EVERY column" is contradicted by the pre-change artifact: output/t2star_q1_070423_..._20260808_124131 has median keys WITHOUT `window_index`, so the old code already skipped it and the change generalised one skip into a set. Verified no key was lost: old and new median and defined key sets are identical. | Restate as generalising an existing skip.
MINOR | analyzers/shape_stats.py:149-154 | "this is where it stops being usable, not where it starts being wrong" describes a cutoff above zero; the value is 0.0, where the two coincide. | Reword or set the constant deliberately above 0.
MINOR | analyzers/shape_stats.py:202 | `max(tie_fraction(x), tie_fraction(y))` is stricter than the cited authority requires: Chatterjee's Thm 2.1 needs Y continuous, and a FIXED tie-break on X leaves the null distribution unchanged under independence. X-only ties buy a 760x-slower calibration for no validity gain. Harmless (the permutation is valid), but the docstring justifies it by the 2/5 null, which is a Y-ties argument. | Say why X ties count too, or branch on y alone.
MINOR | analyzers/shape_stats.py:206 vs analyzers/permutation.py:79 | "exact whatever the ties" against "the null is always SAMPLED". With 999 sampled draws the p is level-valid, not exact. | Align the two sentences.
MINOR | analyzers/check_ledger.py:416 | `RuntimeError` also catches `RecursionError` and `NotImplementedError`, so a genuine bug inside `c3.run` becomes a `declined:` row rather than a traceback - the same failure mode this repo's raise-don't-swallow rule exists to prevent. | Give the bridge its own exception class and catch that.
MINOR | analyzers/shape_stats.py:204 | Function-level import of `analyzers.permutation`. No cycle exists (permutation imports nothing from analyzers), so it can be top-level; a hidden import is harder to see. | Move it up.
MINOR | analyzers/shape_stats.py | 468 lines now carrying estimator, calibration, per-window aggregation and the shape curve. Approaching the unwieldy line; the calibration half (xi_p_value*, XI_* constants) is the natural split. | Watch it.

GREEN | analyzers/shape_stats.py:74-126 | Eq (8) matches reference 10.2 verbatim. `method="max"` is right for BOTH: `rankdata(y,"max")` = #{j : y_j <= y_i} and `rankdata(-y,"max")` = #{j : y_j >= y_i}; `ell` is correctly NOT reordered (the l-sum is over all i, permutation invariant). Agrees with a brute-force counting implementation to 0.0 over 3000 random tied grids, and is BITWISE equal to the old tie-free form on 2000 tie-free samples. | none
GREEN | regression claim, verified independently | output/t2star_q1_070423_57fb5e_20260808_124131 (pre-change) against ..._20260813_101723 (post): pooled xi AND pooled p bit-identical at all 10 thresholds, max |dxi| = 0 and max |dp| = 0 over all 234 windows. `xi_p_method` is in the artifact (231/2/1 windows, all `asymptotic`, max tie fraction 0.0). | none
GREEN | analyzers/checks/_multiprocess.py:54,116 | Default change cannot move a number: every call site passes the estimator explicitly (c1:83,110; c2:171,191; tests), and bench/ never calls `gamma_hat` at all. | none
GREEN | analyzers/permutation.py | `permutation_type="pairings"` is the right null (both marginals fixed, only the pairing destroyed); `alternative="greater"` is right for xi and dcor; seeding reproduces (same seed -> identical p, different seed -> different p). `ruff` clean, `pytest tests/test_shape_stats.py` = 20 passed. | none

---

## Increment B - reviewer findings, and what was done

CORRECTED | .claude/review-findings.md (my own earlier entry) | I wrote that xi's p-value "is what the panel annotation shows". It is NOT: `shape_annotation` renders rho2, xi, limb_rho and peak, and `non_repairable.py` unpacks the pooled p and discards it. No xi p-value reaches any figure today. The defect was still worth fixing - the p-value is in the materialized artifact and the ledger-style consumers read it - but the stated consequence was wrong. | claim removed.

FIXED | analyzers/permutation.py | `-inf` substitution for a non-finite resample statistic was ANTI-CONSERVATIVE and inverted its own comment: a -inf draw can never exceed the observed value, so it shrinks p. Measured by the reviewer at p = 0.034 with -inf vs 0.506 with +inf. Now raises: a statistic that cannot be evaluated on a resample of its own data is broken, and the caller must know.
FIXED | analyzers/permutation.py | "The null is always SAMPLED, never enumerated" was FALSE at n <= 4, where `(n!)^2 <= 999`: measured 36 draws at n=3 and 576 at n=4. scipy drops the +1 on an exact test, so `resolution` misstated the floor (0.02703 vs the true 1/36 = 0.02778). A three-read window is the MODAL case here, so this was the common path. New `exact` field; `resolution` now reports the floor that applied.
FIXED | tests/test_shape_stats.py | `_xi_eq8_reference` was never compared to `chatterjee_xi` - the tied path, the only behaviour this increment changed, was unpinned. Added `test_the_implementation_matches_eq8_on_TIED_data` over four seeds.
FIXED | tests/test_shape_stats.py | Nothing tested `xi_p_value`, `xi_p_method`, the constant-y guard, or `analyzers/permutation.py`. Added 13 tests: both calibration branches, the method label never lying, degenerate input, seed reproducibility, the -inf refusal, and the exact-enumeration regime at n <= 4.
FIXED | analyzers/t2star.py, analyzers/fidelity.py | `xi_seed` was not threaded through either adapter, so it was unreachable from any job and could never reach a Mermaid label - a violation of this repo's own seed rule, and `fidelity` is precisely the quantised ladder that motivates the tie branch. Both now accept and forward it.
FIXED | analyzers/shape_stats.py pooled_xi | Discarded the calibration label. Now returns it as a fifth tuple element; `DistinguishBand.pooled_xi_per_threshold` and the renderer's unpack updated to match.
FIXED | analyzers/shape_stats.py chatterjee_xi | The `1 - 3/(n+1)` ceiling is the TIE-FREE ceiling; the docstring asserted it unconditionally on a tie-corrected estimator. Measured counterexample: n=12, two distinct y -> 0.833 against a claimed 0.769. Both docstring and test now say tie-free.

OPEN | analyzers/shape_stats.py xi_p_value | The branch measures ties and never n, so reference 10.3 caveat 2 (n in 35-355 "sits squarely in the disputed range") is neither implemented nor recorded. Measured type-I of the closed form on independent pairs at nominal 0.05: 0.0118 (n=7), 0.0356 (n=10), 0.0418 (n=20), 0.0508 (n=200) - CONSERVATIVE, so nothing is overstated. Left open deliberately: adding an n floor would send every window to the 760x-slower path for a bias that runs the safe way. | Record in the instrument report.
OPEN | analyzers/check_ledger.py:416 | `RuntimeError` also catches `RecursionError` and `NotImplementedError`, so a genuine bug in `c3.run` becomes a `declined:` row. | A dedicated bridge exception would keep the widening honest. Increment C.
OPEN | analyzers/shape_stats.py | 468 lines carrying estimator + calibration + aggregation + curve. The calibration half is the natural split. | Not this pass.

---

## Increment B3 - Cramer-von Mises (new instrument)

NEW | analyzers/checks/cvm_cramer_von_mises.py + tests/test_checks_cvm.py | The fourth
functional of the same Brownian bridge as C1 and C2. Reference 5.2 calls its omission "harder
to defend" and recommends implementing it, because for m > 1 the source paper REVERSES its
single-process preference and drops Anderson-Darling "as the Cramer-von Mises test had better
level properties in this case". Gapped records are routine here and m > 1 IS the gap case.
16 tests, 247 passing overall.

CONFIRMED | reference PDF eq (7), CvM middle term | The document prints
`- i N (T^2_{i+1} - T^2_i)/tau`, dimensionally inconsistent with its own first term
`i^2 X_{i+1}/tau`. Deriving `integral_0^1 (N(s tau) - sN)^2 ds` from the definition gives
`/tau^2` and reproduces the document's own tail term `N^2[u_N^2 - u_N + 1/3]` exactly.
Settled by THREE independent routes, not by preference:
  - piecewise `scipy.integrate.quad` on the step function  -> 0.117508047340
  - the closed form implemented here                       -> 0.117508052657
  - `scipy.stats.cramervonmises(T/tau,"uniform")` at gamma=1 -> 0.117508052657
`test_the_bracket_is_the_bridge_integral` pins route 1 against route 2 permanently, so this
never has to be re-litigated. Transcribing the printed equation literally would have sent the
pass hunting a bug in the authoritative document. Log against the reference, not the code.

GREEN | limiting CDF | Anderson-Darling (1952) series with `kv(0.25, .)`. Reproduces all four
published critical values: 0.34730 -> 0.100003, 0.46136 -> 0.050000, 0.58061 -> 0.025001,
0.74346 -> 0.010000. Max error 3.08e-06. No finite-N correction, for the same reason `adinf`
carries none: the statistic is divided by an ESTIMATED gamma_hat^2, so the finite-N null is
not the finite-N CvM null and a fitted correction would be a precision claim the derivation
cannot carry.

GREEN | external cross-check | At gamma = 1 the statistic equals `scipy.stats.cramervonmises`
to 4.4e-16 / 5.3e-16 / 6.8e-15 at n = 13 / 36 / 120. That is an independent implementation
reached by a different route, which is stronger evidence than a second transcription of the
same formula - the same standard `_classical_ad` already holds C2 to.

GREEN | the m > 1 motivation, made concrete | `require_strict_tau=False` is not a relaxed
guard: eq (7) carries a `1/(s(1-s))` weight so `ln(tau/(tau - T_N))` is +inf when the last
event lands on the truncation time, and C2 REFUSES that record. CvM's integrand has no such
weight and returns 0.165156 on the same input. On the in-spec clock of a carved record that
case is the common one, not a corner. `test_it_survives_a_record_that_c2_declines` pins it.

DELIBERATE | battery.ROW_KEYS | CvM is NOT registered, per the plan. ROW_KEYS is the schema of
the bench tables; an unregistered check makes `bench_acceptance_at_n` return None, so every CvM
ledger row would read `underpowered / no bench cell`. Promotion is one line here plus a ~106
minute bench re-run, and is a separate decision.
KNOWN GAP | asymptotic calibration | Refused for m > 1 and it raises rather than degrading: the
paper's normal approximation is to the WEIGHTED sum, and this implementation sums unweighted,
exactly as our C2 multi-process route does. Permutation is exact under iid gaps and needs no
limit. The unweighted m > 1 sum remains the one construction with no external validation
anywhere - same gap the skipped small-bowel test records.

---

## Increment B - review gate: MUTATION TESTING (the /review subagent died mid-pass)

The code-reviewer subagent hit the session limit at the exact moment it began mutation testing,
after ~9 minutes and 39 tool calls. It wrote NOTHING to this ledger, so nothing from that run is
salvageable and its reading passes are not recorded. Mutation testing was completed directly
instead, since that was the one step outstanding and it needs measurement, not fresh context.

Method: 14 deliberate defects introduced one at a time into `shape_stats.py`,
`cvm_cramer_von_mises.py` and `permutation.py`; the guarding test module run against each; the
file restored from the original source string in a `finally` block. Working tree verified intact
afterwards (`git status` shows only the pre-existing ruff-format re-wraps; 249 passed).
This is the standard CLAUDE.md demands - "a positive control must fail when the thing it guards
is broken" - applied to this increment's tests rather than asserted of them.

CAUGHT (12 of 14, each naming the test that caught it):
  xi  ell min-ranks instead of max        -> test_the_implementation_matches_eq8_on_TIED_data
  xi  r average-ranks (the tie-free habit)-> test_the_implementation_matches_eq8_on_TIED_data
  xi  factor 2 dropped from denominator   -> test_a_perfect_function_hits_the_exact_finite_n_maximum
  xi  XI_TIE_CUTOFF 0.0 -> 1.0            -> test_a_tied_window_switches_to_permutation
  cvm /tau^2 -> /tau (THE PDF's TYPO)      -> test_at_gamma_one_it_is_the_classical_cramer_von_mises
  cvm 1/3 tail term dropped               -> test_at_gamma_one_it_is_the_classical_cramer_von_mises
  cvm gamma^2 -> gamma                    -> test_statistic_batch_reproduces_the_statistic_under_the_identity
  cvm batch blocks misaligned             -> test_statistic_batch_reproduces_the_statistic_under_the_identity
  cvm CDF series 4j+1 -> 4j+3             -> test_the_limiting_cdf_reproduces_the_published_critical_values
  cvm m>1 asymptotic refusal removed      -> test_the_asymptotic_calibration_is_refused_for_multiple_segments
  perm -inf substitution reinstated       -> test_paired_permutation_refuses_a_statistic_that_goes_non_finite
  perm exact flag forced False            -> test_small_windows_get_an_enumerated_exact_null
The CvM typo mutant is the one that matters most: reintroducing the reference document's printed
`/tau` is caught immediately by the scipy cross-check, so that transcription can never come back.

FALSE CATCH, corrected | the 13th mutant | "ell reordered by argsort(x)" was reported CAUGHT, but
the mutation script injected an undefined name and the tests died on `NameError`, not on the
claim. Redone properly (`ell = rankdata(-y,"max")[order]`): the reorder is EXACTLY a no-op, max
|diff| = 0.000e+00 over 400 heavily-tied grids. The earlier GREEN entry - that the l-sum is over
all i and therefore permutation invariant - is independently confirmed, and a test asserting
otherwise would be wrong. Recorded because a mutation that dies on an error is not evidence.

FIXED | tests/test_shape_stats.py | THE SURVIVOR, and a real gap. Replacing the asymptotic null
variance `2.0/5.0` with `1.0/5.0` left all 35 tests passing. That constant scales every p-value
the tool actually emits: all 279 windows of the real T2* ladder are tie-free, so `xi_p_method`
is `asymptotic` on every one and this is where their significance is decided. The two tests that
existed only asserted `xi_p_value` agrees with `xi_p_value_asymptotic` - the same arithmetic
twice, which is exactly why the mutant slipped through.
Two tests added, both SIMULATED so they are an independent route to the constant rather than a
restatement of it: `test_the_asymptotic_null_variance_is_two_fifths` (Chatterjee Thm 2.2,
measured var(sqrt(n) xi) = 0.4117 at n=100 and 0.3982 at n=400 against the nominal 0.4) and
`test_the_closed_form_holds_its_nominal_level_under_independence` (type-I 0.049 at nominal 0.05,
0.055 at n=400; at n=60 the level holds one-sided). The 1/5 mutant is now CAUGHT.

STATED LIMIT | tests/test_shape_stats.py | A subtler mutant, `2/5 -> 0.45`, still SURVIVES. That
is the Monte Carlo resolution of 1500 replicates, not an oversight: the SE of the variance
estimate is about 0.015, so a 12.5% shift sits inside the band. Tightening the band to catch it
would make the test flaky, and raising the replicate count buys resolution at suite runtime. The
test catches a WRONG constant, not a slightly-off one, and this line says so rather than letting
the next reader assume more.

STATE AT THE GATE | 249 passed, 2 skipped. ruff at the one known pre-existing F841 (`raw_meta`).
Style ratchet test green at 17. Working tree carries no mutation residue.

STILL UNREVIEWED BY A COLD READER | Increment B never received a completed adversarial read. The
mutation evidence above is strong on the STATISTICS, and weaker on everything a reviewer reads
for and a mutant cannot express: the seed threading through `t2star`/`fidelity`/
`_within_calibration_compute`, the 5-tuple unpack sites, `check_ledger`'s widened except, and whether
the docstrings claim more than the code does. Respawn `/review` on exactly that scope when the
limit resets, before Increment C is committed on top of it.

---

## Increment B - COLD-READ reviewer pass (independent, fresh context, 2026-08-13)

Scope: the four things mutation testing is blind to - seed threading, the 5-tuple arity,
`check_ledger`'s widened except, `_multiprocess` defaults - plus docstring honesty.
Verified by measurement where measurable. Gitignored files read as explicit paths.

IMPORTANT | analyzers/t2star.py:139, analyzers/fidelity.py:227, panels/_within_calibration_compute.py:402, analyzers/distinguish_band.py:163,177, analyzers/shape_stats.py:276,345,416 | `xi_seed` is threaded through the adapters but is UNREACHABLE FROM ANY JOB and therefore never on a Mermaid label. `jobs/active/t2star_q1_070423.py:74-88` and `:100`, its 100423 twin, and `jobs/common.py:174-184` are the only step wrappers; none of the three takes or forwards `xi_seed`, so the value is `0` by default at all seven levels. runner.py:46-48 builds the label from `node.kwargs` only, so a defaulted argument cannot appear. This is exactly the rule the same job file states two lines above at t2star_q1_070423.py:107 ("Declared here, not defaulted in the builder, so both reach the provenance label") for `shape_min_reads`. Ledger:215 ("Both now accept and forward it") is true of the analyzer layer and NOT of the job layer, where the seed rule actually binds. | Add `xi_seed: int` to `_t2star_panel_data` / `_fidelity_panel_data` and declare `xi_seed=0` in the `job.step(...)` call, as `shape_min_reads` already is.

MINOR | analyzers/shape_stats.py:284,380,456 | One seed serves every window and the pooled sample. Measured: two DIFFERENT datasets of the same n at the same seed draw a BIT-IDENTICAL permutation sequence (50/50 draws matched). So per-window p-values are not independent draws - windows of equal n share their Monte-Carlo error, which then does not average down in `medians["xi_p_value"]` (for_windows:463-475 medians that column) nor in any count of significant windows. Dormant on T2* (all windows tie-free -> asymptotic branch) but live on the fidelity ladder, the quantised case the tie branch exists for. At B=999 the shared noise is ~0.01 in p, so this changes no verdict today. | Derive the per-window seed, e.g. `seed=xi_seed + window_index`, or state in `for_windows` that the MC error is common across windows by design.

MINOR | analyzers/shape_stats.py:360 | `pooled_xi`'s docstring still says "Returns (xi, p_value, n_reads_pooled, n_windows_pooled)" - four elements - while the signature and the body return five. The arity change of this increment is unstated in the one place a consumer reads. | Add `method` to the Returns line.

IMPORTANT | panels/within_calibration.py:676-678 | The thin-pooling caveat is keyed on a LEAKED loop variable. `label` is exhausted by the `for label in labels` loop at :626, so the `for col, ... in enumerate(notes)` loop at :676 tests `pooled_is_thin_per_threshold[LAST label]` on every column and appends the LAST label. Measured on the shipped artifact output/t2star_q1_070423_57fb5e_20260813_105641: thresholds 4-9 us are all thin, `10 us` is not - so `thin_pooling` comes out EMPTY and the figure prints NO thin-pooling warning at all. The caveat that six of ten pooled cells are not within-excursion statistics is silently suppressed on the real data; had the last threshold been thin instead, the note would have named it ten times. `thin_pooling` does not exist in HEAD, so this is new in this working tree. | Loop `for col, label in enumerate(labels)` (or zip labels with notes) and test that label.

MINOR | panels/within_calibration.py:178-180 | `pooled_lookup` defaults to a ONE-tuple `(float("nan"),)` and slices `[0]`. It therefore keeps working under any arity change to `pooled_xi_per_threshold` - the exact silence the 5-tuple change should have been able to trip. The sibling unpack at :636-640 does name five and would have failed loudly. | Default to the same 5-tuple the unpack site uses, so both sites break together.

MINOR | panels/_artifact_guard.py:36 with panels/within_calibration.py:636 | The arity change is invisible to the staleness guard, as the guard's own contract admits (field NAMES only). Measured: output/t2star_q1_070423_57fb5e_20260808_124131 (pre-P5) still carries 4-tuples in `pooled_xi_per_threshold`, `__setstate__` accepts it without complaint, and the 5-unpack then fails at DRAW time with "not enough values to unpack (expected 5, got 4)" - reached by `compare_t2star_0704_vs_1004 --reuse-deps`. It raises rather than lying, so no wrong number ships, but the guard's stated purpose ("fail loudly at the pickle boundary") is defeated for any value-shape change. | Out of this increment's scope to fix; it is ledger:29 item 2 again, now with a concrete instance to cite.

IMPORTANT | analyzers/checks/c3_serial_copula.py:100 (`--vanilla`) with check_ledger.py:416 | C3 CANNOT SUCCEED IN THIS ENVIRONMENT, and the P5 widening is what hides it. `copula` is installed in the USER library `/home/sera/R/library`; `--vanilla` implies `--no-environ --no-init-file`, so `.libPaths()` drops to the two system dirs and `requireNamespace("copula")` is FALSE. Measured end to end: `c3.run([Segment(x=rng.exponential(size=30), tau=...)], seed=0)` raises `RuntimeError: Rscript exited 1 ... Error: the 'copula' package is required for C3`, while a plain `Rscript -e 'requireNamespace("copula")'` returns TRUE. Before P5 this killed the ledger job, which is loud; after P5 every C3 row becomes `declined: Rscript exited 1 ...` / verdict `not computed` and the check silently never runs. The widening is right; landing it without first running the bridge once means the first real R invocation in this repo's history fails and nobody is told. | Drop `--vanilla` for `--no-save --no-restore` (keeps R_LIBS_USER), or pass `env={"R_LIBS_USER": ...}`; then run C3 once for real before shipping.

IMPORTANT | analyzers/checks/c3_serial_copula.py:13-18, :85-88, c3_serial_copula.R:9-12 | Three docstrings assert a fact about the environment that is now false: "R is absent on this machine, so C3 is UNASSESSED", "none of the code paths past `_invoke_rscript` have ever executed", "UNEXERCISED: R is absent on the machine this was written on". Measured: `Rscript` 4.5.3 is on PATH at /usr/bin/Rscript and `_invoke_rscript` now executes on every ledger run. check_ledger.py:407-415 already says "R is now installed" - the two modules contradict each other in the same tree. Under this repo's claims rule a docstring must match the state it ships in. | Restate as "R may be absent; when it is, ..." and record the one real invocation once the `--vanilla` problem above is fixed.

GREEN | analyzers/check_ledger.py:415-429 with _verdict:215-216 | A `declined:` row CANNOT be mistaken for a pass. `p_value=None` is the first precedence branch, so the row is `not computed` with the exception text in `notes`, and it never reaches the `p <= alpha` or the underpowered branches. Verified on the shipped ledger output/check_ledger_q1_7174d1_20260812_104552: all 12 C3 rows read `not computed` / "R unavailable". One caveat worth knowing: `pd.DataFrame` coerces `p_value=None` to NaN in the float column, so downstream the None-ness survives only in `verdict`/`notes`, not in `p_value`.

IMPORTANT | analyzers/checks/c3_serial_copula.py:143 (`timeout_s: float = 120.0`) | The 120 s budget is not adequate at the sizes this ledger reaches. Measured on this machine with the user library forced onto the path: `serialIndepTestSim(n=355, lag.max=5, N=1000)` + `serialIndepTest` takes 97.1 s - 81% of the budget, on an idle machine. The cost grows superlinearly in n, and the ledger calls C3 once per threshold per clock (up to 20 invocations, so a full run is ~30 min of R even when nothing times out). Any load spike, or a threshold with more events than 355, converts a valid check into `TimeoutExpired` -> `declined:` -> `not computed`. The widened except makes that outcome quiet. | Raise the default well above the measured 97 s (600 s is the same order as the other bench costs), and put the measured 97 s at n=355 in the docstring so the next reader can scale it.

MINOR (sharpens the OPEN entry at this ledger:220) | analyzers/check_ledger.py:416 | Confirmed: `RuntimeError` is the base of both `RecursionError` and `NotImplementedError` (checked), so a genuine bug under `c3.run` degrades to a `declined:` row. Two things sharpen it. (a) The over-catch is not new: `ValueError` was already in the tuple and `c3.run:149` calls `validate_segment`, whose ValueError means the CARVE produced an invalid segment - a data-contract violation, silently downgraded to `declined:` since before P5. (b) The only RuntimeErrors that are genuinely the bridge's are the five in `_invoke_rscript` (c3:92,118,123,130,135); nothing else in `analyzers/checks/` raises one. So a dedicated `RBridgeError` around those five, caught alone, costs one class and removes the whole over-catch. | Define `RBridgeError(RuntimeError)` in c3, raise it at those five sites, and narrow the except to `(RBridgeError, subprocess.TimeoutExpired)` - keeping `ValueError`/`KeyError` only if the carve contract is deliberately tolerated here.

GREEN | analyzers/checks/_multiprocess.py:54,116 (default change) | Claim re-verified independently and repo-wide. `gamma_hat`/`gamma_hat_batch` are called at exactly six sites - c1:83,110; c2:171,191; cvm:146,162 - and every one passes the estimator positionally from a `gamma_estimator` parameter that itself defaults to `GAMMA_COMPLETE` (c1:73,94,121; c2:157,178,201; cvm:132,153,172; battery:86). Tests pass it explicitly at every call (test_checks_published_values.py:104,118,134,171,184; test_checks_statistics.py:170,207,210,220,222). `bench/` never names `gamma_hat` at all, and neither does `monoliths/`. The default was unreachable before and after. | none

IMPORTANT | analyzers/shape_stats.py:86-88 and :189-190 | The docstring's measured count is not in any artifact. "0 of 279 windows had a tie on either axis" - the shipped artifact output/t2star_q1_070423_57fb5e_20260813_105641 has 234 windows in the shape tables (2/231/1 at 2/3/4 us) and the 100423 artifact has 75, so neither 279 nor any pairing of them reproduces it. The CLAIM is correct - recomputed from the read table, max tie fraction is exactly 0.0 on BOTH axes over all 234 eligible windows and over all four non-degenerate pooled samples - only the number is unsourced. This is the exact defect CLAUDE.md's second claims rule names. | Recompute the count into the docstring (234 on 0704, 309 across both datasets) or cite the artifact and drop the figure.

MINOR | analyzers/shape_stats.py:11 and :30 | "the median window here has ~7 reads" names a single cell as if it were the ladder. Measured: 7.0 is the median over COMPLETE windows at the 3 us threshold ALONE. Over the 234 windows that actually reach these statistics the median is 11.0; over all 1212 complete windows on the ladder it is 1.0, and 978 of them have four reads or fewer. The number chosen matters, because :30 uses it to argue the asymptotics are marginal. | Say which threshold and which population, e.g. "median 11 reads over the 234 eligible windows; 1 read over all complete windows".

IMPORTANT | analyzers/permutation.py:49-50 and :93-94 | "a three-read window is the modal case in this project, so this is the common path, not a corner" and "which is the common case here" are both false for the only consumer. `xi_p_value` is called from `window_stats` (via `for_windows`, which receives only windows already filtered to `n_reads >= shape_min_reads`, shipped value 5 in both jobs) and from `pooled_xi` (thousands of reads). Measured on the shipped artifact: 0 of 234 windows have n <= 4, minimum 5. So the exact-enumeration regime the `exact` field and `resolution` exist for is UNREACHABLE from the shipped pipeline, not the common path. The modal complete window does have 1 read - but those never reach xi at all. | Reword to "unreachable at the shipped `shape_min_reads=5`; the field exists for callers that lower it", and keep the tests, which are the only exercise of that path.

GREEN | analyzers/shape_stats.py:74-103, 151-156, 159-168 | Every quoted claim checked against the reference PDF: eq (8) is transcribed exactly as printed in 10.2 (numerator over i=1..n-1, denominator 2*sum over i=1..n, r = max-rank, l = reverse max-rank), the tie-free reduction `1 - 3 sum|dr|/(n^2-1)` matches, the XI_TIE_CUTOFF quote is verbatim from caveat 1, and "roughly valid even for n as small as 20" is verbatim from caveat 2. The declared deviation (deterministic stable tie-break where Chatterjee breaks ties "uniformly at random") is stated in the PDF in those words and is honestly flagged as a deviation. The tied-ceiling numbers verified by exhaustive search: n=12 two distinct y -> 0.8333 against a tie-free ceiling of 0.7692. | none

IMPORTANT (CRITICAL the day CvM is promoted) | analyzers/checks/cvm_cramer_von_mises.py:73-76, :186 | The limiting CDF is truncated at 12 terms and the series does NOT converge in the upper tail, so the asymptotic p-value is NON-MONOTONE in the statistic and eventually rises back toward 1. Measured: p is minimised at z = 7.66 (p = 1.0e-15) and thereafter INCREASES - p(20) = 1.2e-8, p(100) = 3.8e-3, p(500) = 0.100, p(1e5) = 0.705. A larger statistic gets a larger p-value. Constructible verdict flip: N = 682 near-constant durations with a step-change trend (gamma_hat ~ 0.005, exactly the loose-threshold regime this project has - 682 is the complete-window count at the 4 us threshold, and the reference itself says carved durations "are integer multiples of the read spacing") gives statistic 794.4 and p = 0.156, i.e. NOT REJECTED for an overwhelming trend. Nothing ships it today because CvM is deliberately unregistered in `battery.ROW_KEYS`, so this is latent, not live - but promotion is described as "one line plus a bench re-run". The four pinned critical values are all z <= 0.75 and cannot see this. C2's `adinf` was checked for the same class and is clean (monotone, saturates at p = 0). | Guard the tail: return `p = 0.0` above the z where the series stops converging (z ~ 8 is already p < 1e-15), or raise _CDF_TERMS and assert monotonicity. Add a test that `1 - cvm_limiting_cdf(z)` is non-increasing over z in [0.05, 1000].

MINOR | analyzers/checks/cvm_cramer_von_mises.py:72-74 | "It converges fast - the j = 3 term is already below 1e-12 across the range that matters - so this is generous rather than tuned." Measured: true only for z <~ 0.8. The j = 3 term is 3.5e-6 at z = 2, 2.0e-3 at z = 5 and 4.3e-2 at z = 20. "The range that matters" is doing unstated work, and it is what makes the finding above invisible. | State the range (z <= 1, the published-critical-value band) and say what happens outside it.

MINOR | analyzers/checks/cvm_cramer_von_mises.py:1-40 | No source equation number, against CLAUDE.md's "every transcribed formula cites its source to equation number". The docstring cites "the reference document Section 5.2" and "its eq (7)", but 5.2's own title is "Cramer-von Mises, eq. (6)" - eq (6) of Kvaloy & Lindqvist (arXiv:1802.08339), the same paper c2 cites by arXiv id and equation. Worse, `c2_anderson_darling._eq7` already means K-L eq (7), which is the ANDERSON-DARLING statistic, so "eq (7)" now names two different functionals in one package. | Cite "Kvaloy & Lindqvist, arXiv:1802.08339 eq (6) (printed as eq (7) of the reference document)".

MINOR | analyzers/checks/cvm_cramer_von_mises.py:8-14 | The m = 1 side of the paper's verdict is omitted. The reference says plainly "For a single process the paper drops it, since this test had less power than the Anderson-Darling test", and `run`'s DEFAULT calibration is the m = 1 asymptotic one. As written the docstring reads as an unqualified endorsement. | Add the m = 1 sentence beside the m > 1 one.

SHARPENED | analyzers/checks/c3_serial_copula.py:143 | The n = 682 timing measurement did not finish inside a 580 s ceiling, so C3 at the 4 us threshold (682 complete windows on the shipped 0704 record) costs at least 8 minutes against a 120 s budget. Combined with the measured 97 s at n = 355, the default guarantees a `TimeoutExpired` -> `declined:` row on the loosest thresholds - which is where the tie problem is worst and the check is most wanted.

MINOR | analyzers/distinguish_band.py:158-162 | The comment still asserts two things the code does not do: "a constructor field rather than a default" (the line below it is `xi_seed: int = 0`, a default) and "it reaches the provenance label like every other step kwarg" (it reaches no label - see the first finding of this pass). The previous pass flagged the first half; the second half was not corrected. | Say what is true: defaulted at every level, and not yet declared by any job.

MINOR | docs/iid_checks/C3_serial_copula.md:3,31,47, LIMITATIONS.md:42, README.md:90 | Same false environment claim as the c3 module, in four more places: "R is absent on this machine", "every row", and a status row reading "C3 | UNASSESSED". Rscript 4.5.3 is on PATH. README.md:90 is also a status table in an agent-facing doc, which CLAUDE.md forbids for exactly this reason - it went stale in one day. | Restate conditionally and drop the status row.

MINOR | docs/iid_checks/ | CvM shipped as a new instrument with no doc, in the one directory that carries a page for every other check (C1, C2, C3, C5, C6 + LIMITATIONS + README). Not a request to write one - CLAUDE.md says do not create long .md docs unprompted - but the asymmetry should be a deliberate choice, and README.md's own table does not mention CvM exists. | Note CvM in the README's list, or record deliberately that it is undocumented until promoted.

MINOR | panels/within_calibration.py | 1039 lines. The renderer now carries eight axes plus the heatmap, timeline, survival and summary builders. `_within_calibration_render.py` exists precisely as the functions-of-axes half; the per-axis builders are the natural split. | Watch it; the repo rule says flag files that grow unwieldy.

GREEN | baseline reproduced | `PYTHONPATH=. python -m pytest tests/ -q` = 249 passed, 2 skipped. `ruff check .` = the one pre-existing F841 (`raw_meta`, plots/interpolation_stage_plot.py:63) and nothing else. No source file was modified by this review; the only write is this ledger.

MINOR | jobs/active/t2star_q1_070423.py:74-88 (and its 100423 twin), jobs/common.py:174-184 | `xi_seed` is not the only parameter stranded on a default. `k` is declared on the WINDOWS step (`k=1.0`) but the panel adapters never receive it, so `make_panel_data`'s own `k: float = 1.0` decides the unresolved-band half-width that the figure draws. Today both are 1.0 and nothing is wrong; the moment a job carves at `k=2.0` the panel draws a k=1.0 band over a k=2.0 carve and says nothing. `use_uncertainty` IS threaded from the same result, which is what makes the omission visible. `windows.py:525` already puts `k` in `WindowsResult.meta`, so the fix is one line in each adapter, exactly as `use_uncertainty` is read today. | Read `k` from `window_result.meta` alongside `use_uncertainty`, or declare it as a step kwarg on the panel step too.

GREEN | analyzers/shape_stats.py:200-212, :362-373 | The `p_value=None` rule is met without a None. A p that was not computed always carries `xi_p_method == "none"` beside a NaN, and both branches that CAN produce a number set `asymptotic` or `permutation`; there is no path where a missing p is indistinguishable from a large one. Verified on the shipped artifact: 234/234 rows read `asymptotic` with a finite p, and the three degenerate pooled cells (1 us, 8-10 us) read `none` with NaN.

MINOR | analyzers/distinguish_band.py:96-104 | `DistinguishBand` records `shape_min_reads`, `k` and `use_uncertainty` as result fields but NOT `xi_seed`. So even once a job declares the seed, the artifact that carries the permutation p-values will not say which seed produced them; a reader would have to reconstruct it from the Mermaid label of the run that wrote the pickle. The other three settings that shape these numbers are all carried. | Add `xi_seed: int = 0` to the band alongside them (note this changes the field-name set, which IS what `StaleArtifactGuard` checks, so old artifacts will be caught properly for once).

GREEN | panels/_within_calibration_compute.py:400-466 | The seed threading through the compute layer itself is complete and drops nothing: `build_within_calibration_panel_data(xi_seed=...)` -> `distinguish_band.make_inputs_from_windows(xi_seed=...)` -> `DistinguishBandInputs.xi_seed` -> both `pooled_xi` and `for_windows`. The break is entirely at the job boundary. | none

---

## Increment B - fixes applied after the COLD-READ pass

FIXED | panels/within_calibration.py:676 | The leaked `label`. `for col, (...) in enumerate(notes)`
read the loop variable left over from the build loop at :626, so every column tested the LAST
threshold. Measured consequence on the shipped artifact: 4-9 us are thin and 10 us is not, so
`thin_pooling` came out EMPTY and the figure printed no thin-pooling caveat at all - six of ten
pooled cells are not within-excursion statistics and the figure said nothing. Now
`enumerate(zip(labels, notes))`, with a comment naming the failure so it is not re-introduced.

FIXED | analyzers/checks/cvm_cramer_von_mises.py | The limiting CDF diverged outside the range
anything tested. `w = (4j+1)^2/(16z)` goes to zero as z grows, `K_{1/4}` diverges, and the
truncated 12-term sum turns around: p bottomed at z = 7.66 then CLIMBED, giving p(100) = 3.8e-3,
p(500) = 0.100, p(1e5) = 0.705. The reviewer's constructed case - 682 near-constant durations
with a step trend, statistic 794.4 - returned p = 0.156 and FAILED TO REJECT. All four pinned
critical values sit in [0.34, 0.75], which is exactly why 16 tests missed it.
Delegating to scipy does NOT fix it: `scipy.stats._hypotests._cdf_cvm_inf` breaks the same way,
its p rising after z = 5 (4.87e-11 at z=5, 1.81e-9 at z=10, 3.29e-6 at z=1e5).
Fix: evaluate the series only for z <= `_SERIES_Z_MAX` = 5.0 and saturate at F = 1 above it.
The cutoff is measured, not guessed - three independent lines: the published criticals all lie
below 0.75; an INDEPENDENT Karhunen-Loeve Monte Carlo (`W^2 = sum_k Z_k^2/(k pi)^2`, 4e6 draws)
agrees to 4e-5 absolute through z = 2 and produced no draw above 2.904; and the dominant
eigenvalue bounds the tail by `exp(-pi^2 z/2)` = 2e-11 at z = 5. Four tests added, including
monotonicity over `z` in [0.02, 1e6] and the reviewer's verdict-flip case, which now gives p = 0.

FIXED | analyzers/checks/c3_serial_copula.py | `--vanilla` implies `--no-environ`, dropping
`R_LIBS_USER` and with it `/home/sera/R/library` from `.libPaths()` - measured, plain `Rscript`
sees it and `Rscript --vanilla` does not - so `copula` was invisible and EVERY C3 call raised.
Post-B4 that no longer killed the job; it silently became a `declined:` row, which is the worse
failure. `--vanilla` is kept (a reproducibility tool should refuse the user profile) and the
search path is now passed explicitly as `R_LIBS`, asked of R itself by a new `r_library_paths()`
rather than hard-coded to this machine.

C3 FIRST CONTACT | 2026-08-13, Rscript 4.5.3 | The check has now RUN, for the first time since it
was written. On iid exponential input: n=50 -> statistic 0.00579, p 0.958, 3.9 s; n=150 ->
0.00713, p 0.904, 14.7 s; n=355 -> 0.00763, p 0.866, 130.2 s. Failing to reject data that
satisfies the null is the expected outcome and is a SMOKE TEST, not calibration - C3 still has no
bench cell and therefore no size or power evidence. Five docs/modules asserting "R is absent on
this machine" corrected; `docs/iid_checks/README.md` now reads RUNS, UNCALIBRATED.

FIXED | analyzers/checks/c3_serial_copula.py:182 | Timeout 120 -> 900 s. The reviewer's 97.1 s at
n=355 is confirmed and exceeded here (130.2 s), so the old default was ALREADY overrun by a size
the ladder produces. Cost grows about as n^2.8; the docstring records the three measured points
and states plainly that n = 682 is still not covered (extrapolates to ~800 s, measured unfinished
at 580 s) and becomes `not computed` with the timeout recorded.

FIXED | jobs/active/t2star_q1_070423.py, t2star_q1_100423.py, jobs/common.py | `xi_seed` reached
the analyzers but no job declared it, so it was 0 at every level and - because `runner.py` builds
the Mermaid label from `node.kwargs` alone - a defaulted argument could never appear in
provenance. The ledger's earlier FIXED was true of the analyzer layer only; the rule binds at the
job. Now declared on both t2star panel steps and on `configure_ramsey_job`. VERIFIED in the
shipped artifact: `step_t2star_panel_data["t2star_panel_data(shape_min_reads=5,
use_uncertainty=True, xi_seed=20260813)"]` in q1_27h_0704_dataset_t2star.prov.md.

FIXED | analyzers/shape_stats.py:86,189 | "0 of 279 windows" was in no artifact. Recomputed from
the two shipped panel pickles: 234 window-rows on 0704 (d611af) and 75 on 1004 (731c02), 309 in
total, `xi_p_method` = `asymptotic` on every one and no tie on either axis. The CLAIM was right
and the NUMBER was invented; both datasets are now named separately, since pooling two into one
figure is what produced the wrong total.

FIXED | analyzers/permutation.py:49,93 | "a three-read window is the modal case ... the common
path" is false for the only consumer: `for_windows` admits only `n_reads >= shape_min_reads` (5),
and 0 of the 234 windows on 0704 have n <= 4. The exact-enumeration regime is UNREACHABLE from
the pipeline. Reworded to say so, and kept documented because a direct caller can still land
there and must not read a floor of 1/36 as though it were 1/1000.

STATE | 253 passed, 2 skipped. ruff clean across `analyzers/` and `jobs/` (the one known
pre-existing F841 is in a panel module, untouched). Both t2star jobs re-run; identities moved
(57fb5e -> d611af, c3ab94 -> 731c02) because the job files changed, which is the identity
signal the earlier analyzer-only edits could not produce.

NOT FIXED, carried to Increment C | the reviewer's four MINOR seed findings: one seed serves every
window (windows of equal n draw a bit-identical permutation sequence, so their Monte Carlo error
does not average down in `medians["xi_p_value"]`); `distinguish_band.py:158` still claims the
field reaches the label from the analyzer layer; `DistinguishBand` does not carry `xi_seed` as a
field; and `k` is declared on the windows step but never reaches the panel adapter, which uses
its own `k=1.0`. The last is a pre-existing defect this pass surfaced rather than caused.

---

## Increment B - AUDIT of the seven post-cold-read fixes (fresh context, 2026-08-13)

SCOPE: the seven FIXED entries above only. COMMIT: 2f1bd95.
Manifest (checked off as each is audited, findings appended at the moment of discovery):
- [ ] 1 panels/within_calibration.py leaked `label`
- [ ] 2 analyzers/checks/cvm_cramer_von_mises.py `_SERIES_Z_MAX`
- [ ] 3 analyzers/checks/c3_serial_copula.py `r_library_paths()` / R_LIBS
- [ ] 4 C3 timeout 120 -> 900 and the n^2.8 claim
- [ ] 5 xi_seed at the job layer (2 jobs + jobs/common.py)
- [ ] 6 analyzers/shape_stats.py "234 + 75 = 309"
- [ ] 7 the "RUNS, UNCALIBRATED" doc edits (5 places)

### 1 - leaked `label` (panels/within_calibration.py:676)  VERIFIED
GREEN | panels/within_calibration.py:673-681 | Fix confirmed end to end on the SHIPPED artifact.
`output/t2star_q1_070423_d611af_20260813_153158/t2star_panel_data.pkl` has
`pooled_is_thin_per_threshold` True at exactly 4-9 us (1,2,3,10 us False), and
`pdftotext` on the static PDF of the same run prints
"pooled over windows averaging too few reads to be a within-excursion statistic: 4 us, 5 us,
6 us, 7 us, 8 us, 9 us" - the right six thresholds, named once. | none
GREEN | panels/, plots/ (whole class) | AST scan for any name bound by a `for` target and read
after the loop body ends, comprehension scopes excluded, over every function in `panels/*.py`
and `plots/*.py`: ZERO hits. The only two candidates (`non_repairable.py:553,579`) are
comprehension-local rebinds, not leaks. The class is closed, not just the instance. | none
MINOR | panels/within_calibration.py:676-678 | `zip(labels, notes)` without `strict=True`. The two
lists are appended in lockstep in one loop so they cannot differ today, but a future edit that
`continue`s the build loop would silently truncate the caveat again - the same silence the fix
just removed. | `zip(labels, notes, strict=True)`.

### 2 - CvM `_SERIES_Z_MAX = 5.0`  ATTACKED, mostly holds
GREEN | analyzers/checks/cvm_cramer_von_mises.py:88-131 | The cutoff discards NO resolution
below it and the divergence claim reproduces. Measured: the 12-term sum is bit-comparable to a
40- and an 80-term sum through z = 5 (identical to all 15 printed digits at z = 0.05 ... 5.0),
so nothing in [2, 5] is lost - the series IS evaluated there (F(2) = 0.999987219, p = 1.278e-05;
F(5) = 0.999999999996944, p = 3.06e-12). With the cutoff removed the raw series bottoms at
z = 7.60 (p = 1.0e-15) and climbs: p(20) = 1.19e-08, p(100) = 3.76e-03, p(500) = 0.100,
p(1e5) = 0.705 - the ledger's numbers, confirmed independently. The function is monotone
non-increasing in p over 25000 points spanning [1e-3, 1e8], the discontinuity at the cutoff is
3.1e-12, and vectorised output is BIT-IDENTICAL to the scalar loop (max|diff| = 0) including an
array that straddles the cutoff. `np.where(inside, z, 1.0)` leaks nothing: with
`warnings.simplefilter("error")` no warning is raised at any z from 1e-300 to 1e300. | none
GREEN | tests/test_checks_cvm.py:151-190 | The new tests DO fail when the guard is defeated.
Runtime-patched `_SERIES_Z_MAX` (no source edit): at 1e12 both
`test_the_p_value_is_monotone_...` and `test_the_reviewers_verdict_flip_case_now_rejects` fail;
at 50 and at 20 the monotonicity test still fails. | none
MINOR | analyzers/checks/cvm_cramer_von_mises.py:214 (`run`) | A SATURATED p is reported as
`p_value = 0.0` with `notes = "gamma=... limiting_CvM"` - indistinguishable in the result from a
p that was computed. The truth is a bound (`p < 3e-12`), not a number, and this repo's own rule
is that a p which was not computed must be distinguishable in the result. Latent only because
CvM is unregistered in `battery.ROW_KEYS`; the day it is promoted a ledger row will read a flat
0. | When `observed > _SERIES_Z_MAX`, append e.g. `" p<3e-12 (series saturated)"` to `notes`.
MINOR | tests/test_checks_cvm.py:163 | The monotonicity test certifies "no verdict-flipping
divergence", NOT the value 5.0. Measured: with `_SERIES_Z_MAX` raised to 8, 10 or 12 the whole
file still passes 20/20, because the rise between z = 7.6 and z = 12 is ~1e-14, under the test's
own `<= 1e-12` slack. The band (5, ~15] is uncertified; only the comment's three lines of
evidence hold the constant at 5. | Either assert the constant directly, or say in the test that
it pins the divergence and not the cutoff.
MINOR | analyzers/checks/cvm_cramer_von_mises.py:71-72 | Un-fixed carry-over from the cold-read
pass (ledger:384), now WORSE: "the j = 3 term is already below 1e-12 across the range that
matters" sits four lines above the constant that DEFINES the range that matters as z <= 5, where
the j = 3 term is 1.949e-03 - nine orders out. (Convergence at z = 5 is fine on the real
evidence: the j = 11 term is 4.1e-24. The sentence, not the code, is wrong.) | Restate as "at the
cutoff z = 5 the last kept term is 4e-24; the j = 3 term is below 1e-12 only for z <~ 1".

### 3 - C3 `r_library_paths()` / `R_LIBS`  WORKS, with three caveats
GREEN | analyzers/checks/c3_serial_copula.py:70-92, :133-134 | The mechanism is correct and
measured. `r_library_paths()` returns
`('/home/sera/R/library','/usr/lib64/R/library','/usr/share/R/library')`; under `--vanilla`
`.libPaths()` is the last two and `requireNamespace('copula')` is FALSE, with `R_LIBS` set to the
joined tuple it is all three and TRUE. `R_LIBS` is the right variable (it is read from the
process environment, which `--no-environ` does not suppress - only `.Renviron` files are; and it
takes a path LIST, which `R_LIBS_USER` semantically does not). `os.pathsep` matches R's
separator on both platforms. C3 then runs end to end here: n=50 -> statistic 0.00579 in 1.8 s.
| none
MINOR | analyzers/checks/c3_serial_copula.py:80-92 | One extra `Rscript` spawn PER CALL, measured
at 0.28-0.31 s. Negligible against a 60-130 s R run, and a ledger pass adds ~6 s over 20 calls -
but it is a repeated probe of an environment that cannot change inside a run. | `functools.cache`
on `r_library_paths`, or hoist it to the caller.
MINOR | analyzers/checks/c3_serial_copula.py:134 | The empty-tuple case sets `R_LIBS=""`. Measured
harmless (an empty `R_LIBS` behaves exactly as unset: same `.libPaths()`, `copula` FALSE), and
unreachable anyway because `_invoke_rscript` raises when `rscript_path()` is None. It does mean
that if R ever printed nothing the fix silently reverts to the broken state rather than saying
so. | Skip the assignment when the tuple is empty, so the variable is absent rather than blank.
MINOR | analyzers/checks/c3_serial_copula.py:14, :123 and docs/iid_checks/C3_serial_copula.md:4 |
`/home/sera/R/library` is hard-coded in PROSE in three places - the exact machine-binding
`r_library_paths()` was written to avoid, now in the docstring instead of the code. Nothing leaks
into `output/`: the success-path `notes` is `lag.max=... N=... seed=...` and `R_LIBS` is never
recorded anywhere (see the next finding). The one real leak route is a FAILURE: `check_ledger`
writes `f"declined: {exc}"[:160]`, and that exception carries R's stdout/stderr, which can carry
absolute paths into the ledger artifact. | Say "the user library" and drop the literal path.
MINOR | analyzers/checks/c3_serial_copula.py:125-131 (docstring) | "The path is then a recorded
input instead of an ambient one, which is the same reason seeds are explicit here" is FALSE as
written: the path is passed explicitly to the subprocess but RECORDED nowhere - not in
`CheckResult.notes` (`lag.max=... N=... seed=...`), not in the ledger columns, not in any prov
record. Grepping `output/` for `R/library` finds nothing. It is explicit, not recorded. | Either
put the library paths (and the R version) in `notes`, or drop the "recorded" claim.

### 4 - timeout 120 -> 900 and the n^2.8 claim
GREEN | analyzers/checks/c3_serial_copula.py:182 with check_ledger.py:408 | The new default is
the one that binds: `check_ledger` calls `c3.run(...)` without `timeout_s`, so 900 s applies.
Timing re-measured here from scratch (idle machine): 1.8 s at n=50, 6.0 s at n=150, 60.3 s at
n=355 - about 2.2x faster than the docstring's machine, same shape. | none
IMPORTANT | analyzers/checks/c3_serial_copula.py:186-187 | "The cost grows roughly as n^2.8" is
NOT supported by the three points the same sentence cites. From (50, 3.9), (150, 14.7),
(355, 130.2): pairwise exponents are 1.208 (50->150), 2.532 (150->355) and 1.790 (50->355), and
the OLS log-log slope over all three is 1.764. My own three points give the same picture (1.10 /
2.68 / 1.79). Nothing in the cited data yields 2.8; the only evidence pointing that steep is the
UNFINISHED 682 run, which bounds the local exponent below at 2.29 and is not a measurement. The
"~800 s at n = 682" extrapolation two lines down is 2.8's output - at the fitted 1.76 it is 411 s
and at the top-end local 2.53 it is 679 s. This is the docstring-number rule at :186 exactly. |
State "superlinear; locally ~2.5 between n = 150 and 355, 1.8 fitted across the measured range",
and give the 682 extrapolation as a range with its exponent named.
IMPORTANT | analyzers/checks/c3_serial_copula.py:13-18 (the FIRST CONTACT numbers) | Two of the
three quoted p-values do not reproduce, and the docstring never says at which seed. Re-run with
the module's own default `seed=0` on the same inputs (confirmed same inputs: all three
STATISTICS reproduce to 5 digits - 0.00579, 0.00713, 0.00763 - once the generator stream is
continued rather than reseeded): p = 0.9476 vs the quoted 0.958 at n=50, p = 0.9116 vs 0.904 at
n=150, p = 0.8656 vs 0.866 at n=355. The statistic is seed-INVARIANT and the p is not: at n=50,
seeds 0/1/7/20260813 give 0.9476/0.9575/0.9535/0.9505. So the quoted p-values came from other
seeds, and the C3 p carries ~0.01 of Monte-Carlo noise at N=1000. | Quote the seed beside the
numbers (the repo's own rule: a seed that affects a reported number is a declared parameter), or
quote the statistics only, which do reproduce.
MINOR | analyzers/checks/c3_serial_copula.py:182 with check_ledger.py:407 | 900 s x up to 20 C3
invocations is a 5-hour worst case before a ledger job gives up, each ending in a `declined:` row
that reads `not computed`. The budget is right for one call and unbounded for the pass. | Note
the per-pass worst case in the docstring, or give the ledger its own smaller budget.

### 5 - `xi_seed` declared at the job layer
GREEN | jobs/active/t2star_q1_070423.py:102-117, twin, jobs/common.py:258-262 | Verified end to
end, not by reading. Both shipped prov.md files carry
`step_t2star_panel_data["t2star_panel_data(shape_min_reads=5, use_uncertainty=True,
xi_seed=20260813)"]`, and `python main.py inspect jobs/active/ramsey_q1_100423.py` shows
`fidelity_panel_data: _fidelity_panel_data <- [fidelity_raw, fidelity_windows]
{'xi_seed': 20260813}`, so the fidelity branch will label it too. Consumer coverage is complete:
`build_within_calibration_panel_data` has exactly two callers (`t2star.make_panel_data`,
`fidelity.make_panel_data`) and both now receive the seed from a job; `mtbf_q1` builds a
`AcrossCalibrationPanelData`, which has no xi. | none
MINOR | jobs/active/t2star_q1_070423.py:116, t2star_q1_100423.py:116, jobs/common.py:196 | The
literal `20260813` is written in three places with nothing tying them together. Nothing is wrong
today; the drift mode is that one job is re-seeded and the composite
`compare_t2star_0704_vs_1004` then compares a permutation-calibrated number against another
seed without saying so. | One module-level constant imported by all three, or read it from
`jobs/common`.
MINOR | jobs/active/t2star_q1_070423.py:116 with t2star_q1_100423.py:116 | The two independent
datasets now share a seed, so on tied data windows of equal `n` in the two records would draw a
BIT-IDENTICAL permutation sequence and their Monte-Carlo errors would be common - the same defect
already logged for windows WITHIN a record (this ledger:352), now across the two records the
composite job differences. Dormant today and verified so: 234/234 and 75/75 rows read
`xi_p_method = asymptotic`, so the seed is never consulted on this data. | Same fix as :352 -
derive the per-window seed - or say in the composite that the two share it.
IMPORTANT | jobs/common.py:258-262 | The fix is applied to ONE of the parameters that shape the
fidelity panel's numbers. The `fidelity_panel_data` step declares `xi_seed` and NOTHING else, so
`shape_min_reads` (5), `k` (1.0) and `use_uncertainty` all still ride the builder defaults and
are absent from the Mermaid label - confirmed by `inspect`, whose kwargs dict is
`{'xi_seed': 20260813}` alone. The t2star jobs two files over declare `shape_min_reads` and
`use_uncertainty` for exactly this reason, and the comment added here points AT that file. This
is the "fix every site of a class" rule, half applied inside the function being fixed. | Declare
`shape_min_reads` (and `use_uncertainty`) on the fidelity step too.
MINOR | jobs/common.py:180 | An unannounced behaviour change rode along with the seed fix:
`use_uncertainty=bool(window_result.meta.get("use_uncertainty", False))` is new and is in none of
the seven fix entries. It is a no-op today (the fidelity carve never passes `use_uncertainty`, so
the meta value is False), but `.get(key, False)` is a silent fallback on a key `windows.py:526`
writes unconditionally - if it ever went missing the panel would quietly draw the certain-state
figure over an uncertain carve. | `window_result.meta["use_uncertainty"]`, and record the change.

### 6 - "0 of 279" -> 234 + 75 = 309  VERIFIED IN THE ARTIFACTS
GREEN | analyzers/shape_stats.py:84-91, :193-194 | Both counts come from the artifacts that ship.
`output/t2star_q1_070423_d611af_20260813_153158/t2star_panel_data.pkl` has exactly 234 rows
across `shape_stats_per_threshold`, the 1004 twin (731c02) has exactly 75; 309 total. The tie
claim is confirmed by TWO independent routes in the artifact: `xi_tie_frac` (the x axis) is 0.0
on all 309, and `xi_p_method` is `asymptotic` on all 309 - which, since the branch is
`max(tie_fraction(x), tie_fraction(y)) > 0.0`, is a recorded proof that the Y axis is tie-free on
every one of them too. Naming the two datasets separately is the right correction. | none
MINOR | analyzers/shape_stats.py:11 and :30 | Left un-fixed, in the SAME docstring whose other
number was corrected, and it is the same defect class: "the median window here has ~7 reads",
twice, and it carries the argument that the asymptotics are marginal. Measured on the two shipped
artifacts: median `n_reads` over the rows that actually reach these statistics is 11.0 (0704) and
14.0 (1004), minimum 5 on both. 7 is the median at the 3 us threshold alone (the cold-read pass
said so at this ledger:376); it appears in neither the "fixed" nor the "carried to Increment C"
list. | Same treatment as the 309: name the population, "median 11 reads over the 234 eligible
windows on 0704, 14 over the 75 on 1004".

### 7 - "R is absent" -> "RUNS, UNCALIBRATED"  INCOMPLETE AND SELF-CONTRADICTORY
IMPORTANT | bench/results/promotion_report.md:5 | A SIXTH site, uncorrected, and it is the one
TRACKED doc of the set: "C3 (`copula::serialIndepTest`) needs R, and `Rscript` is absent on this
machine ... no code path past `_invoke_rscript` has ever executed." Both clauses are false as of
2026-08-13 (Rscript 4.5.3 at /usr/bin/Rscript; C3 ran here at n = 50/150/355 during this audit).
Its CONCLUSION - "C3 carries no evidence here. Its silence is not a pass." - is still exactly
right, which is why this is a doc defect and not a wrong verdict. The fix entry claims five
sites; the class has six. | Restate the environment clause; keep the conclusion verbatim.
IMPORTANT | docs/iid_checks/C3_serial_copula.md:35-41 vs :3-8 | Contradictory statements in one
short file, which is the specific thing this pass was asked to check. The header says C3 has run;
the "Limitations" section still says, in the present tense, "It cannot pin the numeric path. The
first machine with R installed gets a code path that has never run, including the CSV round-trip
and the result parsing." A reader who starts at "## Limitations" - which is where anyone
assessing the check starts - gets the pre-2026-08-13 state as current. :55 compounds it: "report
`not computed` when R is absent - which is every row in every ledger produced so far". | Move
those two paragraphs under the same "historic" framing the header paragraph already uses.
MINOR | docs/iid_checks/C3_serial_copula.md:10-11 | The edit left the markdown broken: "...had
ever executed. Its silence is not a pass.**" has a closing `**` with no opener, so every
subsequent bold marker in the rendered file is inverted, and the orphaned sentence no longer has
a subject. | Delete the stray `**`, or restore the pair.
MINOR | docs/iid_checks/C3_serial_copula.md:59-60 | "If R is installed later:
`test_r_is_genuinely_absent_here` skips rather than fails" is written as a future contingency for
something that has happened. Verified: `pytest tests/test_checks_c3_bridge.py` = 5 passed, 1
skipped, with exactly that skip message. | Present tense.
MINOR | docs/iid_checks/C3_serial_copula.md:3-6 and LIMITATIONS.md:44-46 | The unreproducible
smoke-test p-values (0.958 at n=50, 0.904 at n=150) and the unsupported `n^2.8` are each
replicated into a second doc, so the two findings under fixes 3-4 above have three sites apiece,
not one. | Fix the module docstring and propagate.
MINOR | docs/iid_checks/README.md:90 | The cold-read pass asked for the status ROW to be dropped
(CLAUDE.md: no status tables in agent-facing docs, "it went stale in one day"); the fix updated
the row instead. The content is honest - "no bench cell, no size or power evidence" - but
"first contact 2026-08-13 (Rscript 4.5.3)" is environment state inside a table whose other four
rows are bench VERDICTS, and it is the part that will go stale next. | Keep the verdict, move the
date to the C3 page.
MINOR | docs/iid_checks/LIMITATIONS.md:40 | The heading still reads "## 4. C3 is unassessed"
while its own first line says C3 executes. Defensible (unassessed = uncalibrated) but it is the
one line a skimmer reads. | "C3 runs but is uncalibrated".
GREEN | analyzers/permutation.py:49-54, :93-100 | The "modal case" reword is now TRUE and is the
right claim. Verified against both shipped artifacts: minimum `n_reads` is 5 on each (234 rows on
0704, 75 on 1004), so 0 rows can reach the enumerated regime, and `(n!)^2` = 36 / 576 / 518400 at
n = 3 / 4 / 6 as stated. The docstring keeps the field and says why a direct caller still needs
it. | none
GREEN | no doc implies C3 carries calibration evidence | Checked every site: README.md:90
("no bench cell, no size or power evidence"), LIMITATIONS.md:44-48 ("What remains missing is
CALIBRATION ... No conclusion anywhere rests on C3"), C3_serial_copula.md:3-8 ("a smoke test, NOT
calibration"), the module docstring, and promotion_report.md:5 ("C3 carries no evidence here").
The smoke test is never described as evidence of size or power anywhere. | none
GREEN | baseline reproduced | `PYTHONPATH=. python -m pytest tests/ -q` = 253 passed, 2 skipped.
`ruff check .` = the single known pre-existing F841 (`raw_meta`) and nothing else. No source file
was modified by this audit; the only write is this ledger. | none

MANIFEST CLOSED: all seven audited. 1 verified clean, 2 holds with 3 minors, 3 works with
4 minors, 4 has an unsupported exponent and unreproducible p-values, 5 is half-applied in
jobs/common.py, 6 verified in both artifacts, 7 is incomplete (a sixth site) and
self-contradictory inside one file.

---

## Increment B - fixes applied after the AUDIT of the seven fixes

The audit's own summary: five of seven fixes verified correct by measurement; the defects it
found were almost all in the PROSE describing them, which is the failure mode CLAUDE.md's claims
discipline names. Fixed:

FIXED | analyzers/checks/c3_serial_copula.py | "the cost grows roughly as n^2.8" was INVENTED.
Refit from the three cited points: OLS log-log slope 1.764, with pairwise slopes that disagree
with each other (1.208 from 50->150, 2.532 from 150->355, 1.790 end to end). Three points do not
determine a power law, and the separate n=682-unfinished-at-580s observation is not predicted by
any fit through them (slope 1.76 extrapolates to 412 s). No exponent is claimed now; the three
measured points are given, the disagreement is stated, and the reader is told to measure the n
they have. This is the third time this pass that a number was asserted rather than computed.

FIXED | analyzers/checks/c3_serial_copula.py, docs/iid_checks/C3_serial_copula.md | The quoted
C3 p-values (0.958 / 0.904 / 0.866) were produced at `seed=1`, and quoted without it; at the
module default `seed=0` the same inputs give 0.948 and 0.912. The STATISTIC is seed-invariant
and reproduces exactly - the R side simulates its own null, so only the p moves. Both sites now
quote the seed and say which half depends on it.

FIXED | bench/results/promotion_report.md:5 | The SIXTH "R is absent on this machine" site, and
the only TRACKED one - the ledger's pass rule cites this file, so it was the one that mattered
most. Now states that C3 has executed, that the smoke test changes nothing in the report because
the bench never ran C3 and `ROW_KEYS` has no C3 row, and that failing to reject iid data is not
calibration.

FIXED | docs/iid_checks/C3_serial_copula.md | Said C3 had run at line 3 and that the numeric path
"has never run" under `## Limitations`, and my edit left an unmatched `**` that bolded a whole
paragraph. Both repaired; marker count now even. The historic note is kept but labelled as
history rather than left contradicting the header.

FIXED | analyzers/checks/cvm_cramer_von_mises.py:71 | Carried-over comment "the j = 3 term is
already below 1e-12 across the range that matters". Measured: 8.4e-28 at z=0.35, 9.2e-11 at z=1,
but 1.9e-03 at z=5 - nine orders out at the top of the retained range. 12 terms is still right
(the audit confirmed 12-, 40- and 80-term sums agree to every printed digit through z=5), but the
margin comes from the later terms, and the comment now says so.

FIXED | analyzers/checks/cvm_cramer_von_mises.py | A saturated `p_value = 0.0` reached
`CheckResult` indistinguishable from a computed one. The verdict is right and the magnitude is
not a measurement, so `notes` now carries `p_saturated(z>5)` and a reader cannot quote the zero
as a precision claim.

FIXED | analyzers/shape_stats.py:11,30 | "the median window here has ~7 reads", twice. Measured
over the eligible rows of the shipped artifacts: 11.0 on 0704 and 14.0 on 1004. The 7 is the 3 us
cell - a pooled number labelled as though it were the whole, which is the FIRST rule in CLAUDE.md's
claims discipline and the fourth instance this pass.

FIXED | jobs/common.py + both t2star jobs | The literal `20260813` was in three files. Now one
`XI_SEED` in `jobs/common.py`, imported. The constant's comment carries the open finding it does
NOT fix: one seed serves every window, so two windows of equal n draw an identical permutation
sequence and their Monte Carlo error does not average down under the median.

FIXED | jobs/common.py:181 | `use_uncertainty=bool(window_result.meta.get("use_uncertainty",
False))` - a silent fallback that rode along with the seed fix and would redraw the panel in the
other mode if the key were ever missing. `windows.run` always records it, so absence is a broken
artifact. Now indexes and raises.

FIXED | panels/within_calibration.py | `zip(labels, notes, strict=True)`.

VERIFIED AFTER THE FIXES | Re-ran the 0704 job (identity 1e0202). The thin-pooling caveat prints
"4 us, 5 us, 6 us, 7 us, 8 us, 9 us" on the static PDF - exactly the six thresholds the artifact
marks thin, where before the leak it printed nothing. Label carries `xi_seed=20260813`.
253 passed, 2 skipped; ruff at the one known pre-existing F841.

NOT FIXED, carried to Increment C, with the audit's reasons:
- The new CvM tests pin the DIVERGENCE, not the value 5.0: raising `_SERIES_Z_MAX` to 8, 10 or 12
  still passes all 20. That is arguably correct (the cutoff is a judgement, the monotonicity is
  not), but it means the constant can drift without a test objecting.
- `r_library_paths()` spawns an extra Rscript per call (0.29 s) and its result is written to no
  provenance artifact, so two machines with different library sets are indistinguishable after
  the fact.
- `jobs/common.py`'s fidelity step declares only `xi_seed`; `shape_min_reads`, `k` and
  `use_uncertainty` remain on builder defaults and off the Mermaid label - the same class as the
  fix, in the function the fix touched.
- `k` is declared on the windows step and never reaches the panel adapter, which uses its own
  `k=1.0`. Pre-existing.
- `distinguish_band.py:158` still claims the field reaches the provenance label from the analyzer
  layer; `DistinguishBand` does not carry `xi_seed` as a field.

UNREVIEWED LAYER | the fixes made in response to the AUDIT | Recorded so it is not later assumed
covered. The review chain is three deep and only two links are reviewed: Increment B (cold read +
mutation pass), then the seven fixes (the audit), then THESE, which no reviewer has seen. Six are
prose corrections written directly against the audit's measured objections; four are code -
`p_saturated` in CvM notes, `zip(strict=True)`, the `XI_SEED` extraction, and `use_uncertainty`
going from `.get(..., False)` to indexing.
Exercised since: 253 passed; both t2star jobs re-run; `ramsey_q1_100423` re-run, which is the ONLY
caller of `_fidelity_panel_data` and therefore the only exercise of the raise - it completed and
its label reads `fidelity_panel_data(xi_seed=20260813)`. The "windows.run always records
use_uncertainty" claim was VERIFIED rather than left asserted: `WindowsResult` has exactly one
construction site, analyzers/windows.py:519-529, and it always sets the key.
To fold into the Increment C gate. Worth a specific look: whether these corrections now UNDERstate
in the other direction - three consecutive audits pushing on overclaiming can hedge prose into
uselessness, which is its own failure.

---

## Increment C - Tier 3 (permutation exactness and asymptotic size)

NEW | tests/test_tier3_calibration.py | 12 tests. Two claims held to two standards on purpose:
C5/C6 are permutation-calibrated, which is EXACT under exchangeability, so their level is a
combinatorial identity and is ASSERTED; C1/C2/CvM are asymptotic and divided by an estimated
gamma_hat, are known to miss at small n (bench: 0.069 and 0.0757 at n=20 vs 0.05), and are
MEASURED with only the direction asserted. Asserting a tight band on the latter would encode
the miss as correct.
Not a KS test, per the plan: at B=199 a permutation p lives on a 200-point grid and differs
from the continuous uniform by 1/(2B) BY CONSTRUCTION, so KS would test the grid. The exact
statement `P(p <= k/(B+1)) = k/(B+1)` is used instead, at alphas chosen to LAND on the grid
(0.01=2/200, 0.05=10/200, 0.10=20/200).
Aggregation and multiplicity stated before the verdict: 2 checks x 3 layouts x 3 alphas = 18
comparisons against one band of `bonferroni_z_crit(18)` null SEs, reusing
`calibration_summary.null_se` and `bonferroni_z_crit` so this file and the bench keep ONE
definition of calibrated. Resolution stated rather than hidden: +/-0.020 at alpha=0.10 and
+/-0.0067 at alpha=0.01, so the 0.01 cell catches only a gross error.

FOUND BY MUTATION, IN MY OWN NEW TEST | The first version of this file could not catch two
defects in `permutation_p_value`. Both mutants survived all 11 tests:
  - dropping the `+1` tie correction: at the grid alphas `k/199 <= 0.05` and `(1+k)/200 <= 0.05`
    BOTH reduce to `k <= 9`. The rejection rates are IDENTICAL at 0.01, 0.05 and 0.10 - an
    arithmetic coincidence, not a weak assertion. The term is visible only at the FLOOR, where
    the correct minimum is 1/(B+1) = 0.005 and the mutant returns exactly 0.
  - `>` instead of `>=`: on exponential gaps no permuted statistic ever exactly equals the
    observed one, so the substitution is a no-op across every replicate.
Two tests added that look where the terms actually live (the observed floor over 2000
replicates, and a direct unit test with exact ties in the null). All three mutants - including
`divide by B not B+1` - are now CAUGHT. This is the same lesson as the 2/5 null variance in
Increment B: a calibration test can pass while the constant it depends on is unpinned.

---

## Increment C - Tier 4 (R cross-implementation)

NEW | rscripts/reference_values.R + tests/fixtures/r_reference_{inputs,values}.csv +
tests/test_r_cross_implementation.py | 18 tests, and the suite still never requires R: the
script writes committed fixtures, the test reads them. CSV rather than the planned JSON because
`jsonlite` is not installed and long-format CSV diffs cleanly under review. The fixture carries
the INPUT DATA as well as the answers - matching R's RNG stream from Python would be fragile and
a generator mismatch would surface as a fake statistical disagreement.
Agreement at 1e-10 or better on: xi tie-free vs `XICOR::xicor`, xi with y-ties-only vs the same,
`energy::dcor` on three cases, Spearman on four, and the lag-1 rank autocorrelation C5 is built
on. R 4.5, XICOR 0.4, energy 1.7, randtests 1.0, copula 1.1, all recorded in the fixture.

THE FINDING | `XICOR::xicor` is RANDOM on tied-x data, so equality is the WRONG test | The
headline tied case failed at 0.4649 (ours) against 0.4976 (R), which looks exactly like a
transcription error. It is not. Eq (8) breaks x-ties uniformly AT RANDOM: measured, 7 distinct
values in 8 calls on identical data, and over 2000 draws mean 0.4825, sd 0.0429, range
[0.357, 0.628]. A single R draw is not a reference constant and pinning it would pin R's RNG
state. Our deterministic stable-sort value sits at 0.4649 - inside the 0.1-99.9 percentile band
and within 3 sd of the mean.
The test now asserts MEMBERSHIP in the tie-break distribution rather than equality, which is a
weaker claim than the one first written and the strongest claim the estimator supports. The
mechanism is localised, not guessed: the y-ties-only case has continuous x, `xicor` is
deterministic there (50 draws, 1 distinct value), and our value matches it to 1e-10. So the
disagreement is X-tie-BREAKING, not eq (8).
This is also the concrete motivation for the tie experiment: what the deterministic break COSTS
is now a measurable question with a known reference distribution, not a caveat.

BARTELS, deliberately not used as a target | `randtests::bartels.rank.test` is the rank von
Neumann RATIO; our C5 is a studentized MAXIMUM over lags. Cross-checking one against the other
would be apples to oranges. What they genuinely share is the lag-1 rank autocorrelation, so that
is what is pinned; the Bartels values are in the fixture as context and are asserted only to
exist. Recorded so a later reader does not "fix" the missing comparison.

---

## Increment C - the xi tie experiment and the instrument report

NEW | bench/xi_ties.py -> bench/results/xi_tie_experiment.csv | Three questions on one
generator: where the closed form stops agreeing with the permutation, what the deterministic
x-tie break costs against a randomised one, and whether the asymptotic null survives ties.
A study, not a pipeline layer - nothing outside bench/ imports it.

METHOD DEFECT FOUND AND FIXED BEFORE THE RUN | The deliverable was specified as "the tie
fraction where the two p-values diverge by more than 0.02", read off `mean |p_closed -
p_perm|`. That statistic cannot answer it: at B = 999 the permutation p-value carries Monte
Carlo error of about 0.0158, which is MOST of a 0.02 threshold, so the absolute difference
measures mostly its own resampling noise. Confirmed on the tie-free control cell, where the
true difference is ~0 and |dp| still reads 0.0120. The experiment now records the SIGNED
mean as well - noise averages out of it, systematic disagreement does not - and the
deliverable is read off the signed quantity with the MC floor stated beside it.

SECOND METHOD DEFECT, found by reading the first four cells | Q2 asks what the deterministic
X-tie break costs, and reported a spread of exactly 0.0000 in every cell. The generator only
quantised y; x stayed continuous, so there were never any x-ties for a tie break to act on.
A column of zeros would have read as "the deterministic choice costs nothing". Fixed: x is
quantised in the Q2 block only (Q1/Q3 keep x continuous, which is the shipped situation -
x is the read time). Now measures a real effect: at n=35 with 20 levels, x tie fraction 0.80,
tie-break sd 0.0456, and our deterministic value at the 82nd percentile of the admissible
ones; at 5 levels, sd 0.1719.

EARLY RESULT, full grid still running | Across n=35 the signed difference stays within
-0.0026 to -0.0011 at tie fractions from 0.000 to 0.994 - the closed form and the permutation
do NOT systematically disagree even at 99% ties. What DOES move is the closed form's type-I
error: 0.027 (tie-free) -> 0.043 -> 0.057 -> 0.063 (tie_y 0.994) against a nominal 0.05. So
the cost of ties shows up as level, not as p-value disagreement. If that holds across the
grid it argues XI_TIE_CUTOFF = 0.0 is far more conservative than it needs to be - but the
grid is not finished and this is written as the provisional reading it is.

NEW | analyzers/instrument_validation.py, plots/instrument_validation_plot.py,
jobs/active/instrument_validation.py, bench/instrument_report.py, tests (11) | The report.
Four figures from one typed artifact: the tier matrix (the index), published values (Tier 2),
cross-implementation (Tier 4), and the tie experiment. Pure-compute builder, pure renderer,
every input declared as a Dataset so the figure's dependence runs through provenance. The
`instrument | tier | verdict` table is GENERATED markdown, not drawn into a PNG - a PNG goes
stale as silently as a doc table and cannot be diffed.

STRUCTURAL | reference/ is new and TRACKED | The Tier 4 fixture was written to
tests/fixtures/, and `tests/` is gitignored - so the "committed fixture" the plan requires
would not have survived a clone, and the suite would have silently started requiring R to
regenerate it. The published load-haul-dump record had the same problem and is now also a
tracked CSV, read by BOTH the suite and the figure so the two cannot drift. CLAUDE.md's
Layout section updated.

NEW | jobs/active/check_ledger_q1_070423.py | The "our data" counterpart: the validated
instruments run on the real 912-day record, same carve as the T2* panel so the two are
comparable. No job wired the ledger before this.

OPEN, and a real one | C3 may make the ledger impractical. Its cost grows steeply with n and
the job runs it per threshold, so a 10-rung ladder can spend a long time in R before every
row either lands or times out at 900 s. `not computed` is the honest outcome and cannot be
misread as a pass, but if most C3 rows time out then paying the wall-clock buys nothing and
the ledger should either take a smaller timeout at the job level or skip C3 above some n.
Measure before deciding - this is written as the open question it is.

---

## Increment C - RESULTS (both studies finished)

THIRD METHOD DEFECT, caught by reading the printed output | bench/xi_ties.py main() | The
signed-mean rewrite of the DELIVERABLE block never applied - the formatter had reflowed it and
the string replace failed silently, the same way three earlier edits in this pass did. The run
therefore printed the deliverable off `|dp|`, the statistic already established as unusable.
Recomputed from the CSV, which carries both columns, and the two answers DIFFER: `|dp|` puts
the crossing at 3 levels for n=35, the signed mean at 2. The tie-free control settles which is
right - its true difference is ~0 and `|dp|` still reads 0.0095-0.0120, so `|dp|` was reporting
its own noise. Code fixed; no re-run needed.

DELIVERABLE | The closed-form and permutation p-values agree until the response is nearly
binary. Systematic divergence beyond 0.02 (signed mean) appears ONLY at 2 distinct response
values, at every n: -0.0552 (n=35), -0.0359 (n=75), -0.0261 (n=150), -0.0203 (n=355). Reported
in LEVELS rather than tie fraction because tie fraction saturates - 20 levels already ties
83-99% of a sample, so "diverges at tie fraction 1.000" is true of several cells at once.

THE MORE USEFUL RESULT | The cost of ties is LEVEL, not p-value disagreement. Type-I of the
closed form at nominal 0.05, by distinct response values:
    levels     20     10      5      3      2
    n=35    0.043  0.057  0.063  0.103  0.163
    n=75    0.033  0.047  0.063  0.087  0.147
    n=150   0.040  0.047  0.073  0.077  0.173
    n=355   0.053  0.063  0.087  0.087  0.140
The permutation reference holds 0.023-0.063 in EVERY cell. So the closed form is sound down to
about 5 distinct values and inflates to 3x nominal at 2-3. This is direct evidence that
`XI_TIE_CUTOFF = 0.0` - permute on ANY tie - is far more conservative than the data requires,
and it costs 760x per panel render. A cutoff keyed on DISTINCT VALUES rather than tie fraction
would be the principled form. NOT changed in this pass: it is a calibration decision, the
measurement is one generator on simulated data, and the estimator's real ladder is tie-free
anyway so nothing ships differently today.

Q2, the deterministic x-tie break | Spread of xi over random tie breaks: sd 0.019 to 0.172,
largest at coarse quantisation and small n, exactly 0 when x is continuous. Our deterministic
choice lands between the 2nd and 90th percentile across cells with no systematic bias - it is
an arbitrary admissible member, which is what the Tier 4 membership test asserts.

C3 CONCERN RESOLVED | The open worry that C3 would make the ledger impractical does NOT hold.
The real run completed and C3 returned p-values on every threshold that had usable windows
(.004, <.001, <.001, <.001, .016 in-spec; .004, .371, .648, .460, .480 calendar). No row timed
out at 900 s. The concern is withdrawn.

THE REAL-DATA RESULT | 104 ledger rows: 31 fail, 29 underpowered, 26 not computed, 12 pass,
6 not interpretable (ties). The iid assumption is REJECTED on the in-spec clock at 3-6 us by
every check that had power there, while the CALENDAR clock passes at 4-5 us. The two clocks
disagreeing is the finding the ledger exists to surface, and it is visible at a glance.

STATE AT THE C GATE | 298 passed, 2 skipped. ruff at the one known pre-existing F841. Style
ratchet 17 (the new plot module drove it to 28 and was refactored back - all colour and
typography now in plots/theme.py).

---

## Increment C + unreviewed-B-fix-layer - reviewer pass (fresh context, 2026-08-13)

SCOPE: Part 1 the unreviewed B fix layer (cvm p_saturated, zip strict, XI_SEED, use_uncertainty,
six prose corrections); Part 2 Increment C (tier3 tests, Tier 4 R cross-impl, bench/xi_ties.py,
instrument_validation.*, check_ledger_q1_070423.py, reference/, CLAUDE.md Layout);
Part 3 sweep for a fourth silently-failed edit.
COMMIT: 2f1bd95 (working tree, most files untracked)

MANIFEST (checked off as reviewed)
- [ ] analyzers/checks/cvm_cramer_von_mises.py (p_saturated)
- [ ] panels/within_calibration.py (zip strict), jobs/common.py (XI_SEED, use_uncertainty)
- [ ] prose: c3_serial_copula.py, docs/iid_checks/C3_serial_copula.md, promotion_report.md, shape_stats.py
- [ ] tests/test_tier3_calibration.py
- [ ] rscripts/reference_values.R + reference/*.csv + tests/test_r_cross_implementation.py
- [ ] bench/xi_ties.py + bench/results/xi_tie_experiment.csv
- [ ] analyzers/instrument_validation.py + plot + job + bench/instrument_report.py + tests
- [ ] jobs/active/check_ledger_q1_070423.py
- [ ] reference/ + CLAUDE.md Layout

FINDINGS (appended at the moment of discovery)

### Part 1 - the unreviewed B fix layer

GREEN | jobs/common.py:172-198 | `XI_SEED = 20260813` is a single definition imported by both
t2star jobs (no literal left anywhere: `grep -rn 20260813` finds only jobs/common.py). It is
passed as a step kwarg (`xi_seed=xi_seed` at :276) so it reaches the Mermaid label. The
`use_uncertainty` change indexes `window_result.meta["use_uncertainty"]` and the "windows.run
always records it" premise is TRUE: `WindowsResult(` has exactly one construction site
repo-wide (analyzers/windows.py:519) and it always sets the key. | none
GREEN | analyzers/shape_stats.py:11-14,32-34 | The corrected "median window is 11 reads on 0704
and 14 on 1004" is EXACT against the shipped artifacts: median `n_reads` over the concatenated
`shape_stats_per_threshold` rows is 11.0 (n=234) and 14.0 (n=75). Not an understatement - it is
the number the artifact carries. | none
GREEN | panels/within_calibration.py:681 | `zip(labels, notes, strict=True)`; the only other zips in
the file are over a value unpacked from one list (:513) and a `zip(*survival)` transpose (:830),
neither of which strict= applies to. | none

MINOR | analyzers/checks/cvm_cramer_von_mises.py:224 | `p_saturated(z>5)` is appended to the free
text `CheckResult.notes`. That is the right place TODAY (CvM is not in the ledger), but
`check_ledger.py:466` builds its `notes` column from `_verdict`'s reason plus the battery note
and DISCARDS `result.notes` except for a `variant=` token scan. If CvM is ever promoted into
`battery.ROW_KEYS` the saturation marker silently stops reaching the artifact, and a saturated
p=0.0 becomes indistinguishable from a computed one - the exact defect this fix was written to
close. | On promotion, add a structured flag (or scan for the token as `variant=` is scanned).
MINOR | analyzers/checks/c3_serial_copula.py:13 | The line is 130 chars where every neighbour is
<=91, and it states the same fact twice: "**C3 RUNS, and is still UNCALIBRATED.** R IS NOW
INSTALLED AND C3 HAS RUN." Signature of text inserted without the surrounding paragraph being
reflowed - the same edit-hygiene class as the three failed replaces this pass. Content is
correct, not understated. | Reflow and drop the duplicate sentence.
MINOR | docs/iid_checks/C3_serial_copula.md:44-45 | "What remains untested is ... behaviour on
data that is NOT iid" is now stale in the mild direction: C3 has since run on the real 912-day
record and returned rejections at 5 thresholds (ledger:993). Still uncalibrated, so the verdict
holds; the sentence just no longer describes the state. | Say "unCALIBRATED on non-iid data";
it has now been exercised there.

### Part 2/3 - Tier 3 (tests/test_tier3_calibration.py)

IMPORTANT | tests/test_tier3_calibration.py:15,168-172,194-195 | THE FOURTH FAILED EDIT, and it
is a claim not a formatter artifact. Three places say the instrument report/figure imports
`measure_asymptotic_size` "so the figure and the test measure the SAME thing by construction".
NOTHING imports it: `grep -rn "measure_asymptotic_size" --include=*.py .` matches only this file,
and `analyzers/instrument_validation.py` has no size field, no import of any check module, and
`plots/instrument_validation_plot.py` draws only the tie experiment's type-I columns. So the
function is not public-for-the-report, and the report's three tier-3 "asymptotic size measured"
verdicts rest on NO number in the artifact. | Delete the three sentences, or have the builder
actually call it and store the sizes.
IMPORTANT | tests/test_tier3_calibration.py:13,189 | "the bench measures it at 0.069 (C1) and
0.0757 (C2) at n = 20" is a POOLED MEAN over the two Weibull shapes, labelled as a measurement.
Verified against bench/results/size_table.csv: at n=20, arm A, continuous, no extra censoring,
C1 asymptotic is 0.064 (shape 0.75) and 0.074 (shape 1.5) -> mean 0.069; C2 is 0.0650 and 0.0865
-> mean 0.07575. This is verbatim the instance CLAUDE.md's FIRST claims-discipline rule records
("At n=20 the two Weibull shapes give 0.0650 and 0.0865"), reintroduced in new prose. |
Quote the two shapes, or say "mean over the two Weibull shapes, spread 0.065-0.087".
MINOR | tests/test_tier3_calibration.py:199 | The asymptotic band `0.005 <= size <= 0.20` is 4x
nominal at the top. Measured actual sizes at n=30, seed 777: it passes with enormous margin (see
the measurement below). The docstring is honest that it catches only a broken limit - but the
instrument report converts this same test into a tier-3 "pass", which is where the width starts
to matter. | State the measured value in the failure message so a drift is visible.

GREEN | tests/test_tier3_calibration.py | Bonferroni family is right: `N_COMPARISONS = 2 x 3 x 3
= 18` is exactly the number of assertions in the exactness test (c5, c6 x 3 layouts x 3 alphas)
and no other assertion shares the band. The alphas DO land on the B=199 grid: p = (1+k)/200, and
0.01=2/200, 0.05=10/200, 0.10=20/200 are exactly representable and exactly equal to the literals
in IEEE double, so `p <= alpha` counts the intended grid points. | none
GREEN | positive control, measured by the reviewer | Monkeypatched three mutants of
`permutation_p_value` into c6 and re-ran the whole family at [30], 2000 replicates: dropping the
numerator +1 gives rates 0.0145/0.0590/0.1115 - INSIDE the Bonferroni band, exactness passes;
`divide by B` and `strict >` also pass exactness. The floor test catches the first two (min p
0.000000 and 0.005025 vs the exact 0.005) and the tie unit test catches `>`. So the ledger's
"all three mutants are now CAUGHT" is TRUE, and its statement that the exactness test alone
cannot see them is also true and now independently confirmed. | none
GREEN | tests/test_tier3_calibration.py:167-181 vs the ledger path | `measure_asymptotic_size`
calls `module.run([segment], calibration=CALIB_ASYMPTOTIC)` with no gamma override, and
`c1.run`/`c2.run`/`cvm.run` all default to `GAMMA_COMPLETE`, which is what `run_battery` passes.
Same code path, m=1. (The ledger's real records are m>1 and the in-spec clock drops C1/C2
entirely, so the measurement is of the instrument, not of the shipped configuration - worth
saying, but it is not a different code path.) | none

IMPORTANT | tests/test_tier3_calibration.py:14, 186-192 | Direction claim contradicted by this
test's own generator. The docstring says the asymptotic checks "miss nominal at small n and miss
upward" and that only "the direction" is asserted. Measured by the reviewer with the file's own
`measure_asymptotic_size` (1200 replicates, seed 777, iid exponential, m=1):
    n=20  C1 0.0342  C2 0.0292  CvM 0.0383     n=30  C1 0.0525  C2 0.0475  CvM 0.0475
i.e. CONSERVATIVE at n=20, the opposite direction from the bench's Weibull cells. Two separate
problems: (a) no direction is asserted anywhere - the only assertion is `0.005 <= size <= 0.20`;
(b) the bench numbers are quoted as if they described this measurement, but they come from a
different generator (Weibull shape 0.75/1.5, bench carve and censoring). | Say which generator
each number came from, and drop "only the direction asserted" or assert one.
IMPORTANT | analyzers/instrument_validation.py:353-358 | The C1 tier-3 row is
`TIER_PASS, "asymptotic size measured, anti-conservative at small n as the source reports"`.
Neither half is supported by evidence in this repo at the place it points: the only tier-3
measurement of C1 (the file the row's own docstring family cites) is CONSERVATIVE at n=20
(0.0342), and "pass" is read off an assertion band four times nominal at the top. A tier whose
question is "does its p-value hold its nominal level" cannot be `pass` and "anti-conservative"
in the same cell. Compare `Chatterjee xi` tier 3, which is correctly `partial` for a weaker
defect. | `partial`, with the measured number and its generator in the detail.

### Part 2 - Tier 4 (rscripts/reference_values.R, reference/*.csv, test_r_cross_implementation.py)

IMPORTANT | tests/test_r_cross_implementation.py:83-113, :20-24 | THE BAND IS TOO WIDE TO BE
EVIDENCE, and the docstring points the reader at it as "the ONLY external evidence that the
[eq (8)] change was made correctly". Attacked as instructed by constructing deliberately wrong
xi estimators on the shipped `xi_tied` fixture (n=60) and testing them against the band
[0.35652, 0.59912] with the 3sd gate [0.3537, 0.6113]:
    tie-free reduction (the PRE-Increment-B code)   0.4815  INSIDE - passes
    ell uses min ranks instead of max               0.4210  INSIDE - passes
    r uses average ranks (the tie-free habit)       0.4744  INSIDE - passes
    r uses min ranks                                0.4838  INSIDE - passes
    ell built from +y instead of -y                 0.4047  INSIDE - passes
    n -> n-1 in the numerator                       0.4738  INSIDE - passes
    factor 2 dropped from the denominator          -0.0702  caught
    unsorted (forgot to order by x)                -0.0478  caught
Only gross errors are caught. Note also that `xicor_q001` EQUALS `xicor_min` in the fixture, so
the lower edge is the whole observed support of 2000 draws, not a percentile. | Keep the test as
the consistency check it is, and move the "only external evidence" sentence to the case that
carries it (below).
GREEN | tests/test_r_cross_implementation.py:136-145 | The evidence the eq (8) change actually
rests on is `xi_tied_y_only`: continuous x, 40 of 45 y-values tied, XICOR deterministic
(`xicor_distinct_draws == 1`, pinned), equality to 1e-10. Verified by the reviewer that this
test CATCHES every mutant the membership test lets through: tie-free reduction 3.6e-02, ell min
ranks 3.1e-02, r average ranks 2.2e-02, r min ranks 4.3e-02, ell from +y 6.5e-02, n->n-1
2.2e-02, against our 2.3e-16. So Tier 4 does discharge the claim - just not where the docstring
says. A revert to the tie-free form is separately caught by :162-170. | none
MINOR | tests/test_r_cross_implementation.py:88 and rscripts/reference_values.R:85-87 | "7
distinct values in 8 calls on identical data, spanning 0.425 to 0.563" is a scratchpad
measurement that appears in no shipped artifact - the fixture records 2000 draws with min 0.3565
and max 0.6284. CLAIMS DISCIPLINE: a measured number in a docstring must come from the artifact
it cites, in the state it ships. | Quote `xicor_sd`/`xicor_min`/`xicor_max` from the fixture, or
drop the 8-call anecdote.
MINOR | tests/test_r_cross_implementation.py:64-69 | `test_the_fixture_records_which_r_produced_it`
asserts `>= 0` on every package major and minor, which no non-negative integer can fail. It pins
that the KEYS exist, not the versions. | Assert the versions the fixture was actually built with
(XICOR 0.4, energy 1.7), so a regeneration under a different version is a visible failure.
GREEN | rscripts/reference_values.R | Reads correctly end to end: every `add_input` case is
consumed by a test, `ties = TRUE` is XICOR's eq (8) path, the tie-free case records BOTH
`ties=TRUE` and `ties=FALSE` and they are bit-identical (0.591553209224785), the C3 reference is
pinned with `set.seed(707)`/N=1000/lag.max=5 and the module docstring's statistic-invariant vs
p-value-varies distinction is respected, and `write.csv(quote=FALSE)` is safe (no field contains
a comma). 18 tests pass with no R present. | none

### Part 2 - bench/xi_ties.py and the tie experiment CSV

GREEN | bench/results/xi_tie_experiment.csv vs the ledger's DELIVERABLE | Every deliverable
number re-derived by the reviewer from the CSV: signed-mean crossings of 0.02 occur ONLY at
y_levels=2, at -0.055185 (n=35), -0.035895 (n=75), -0.026123 (n=150), -0.020296 (n=355) - the
ledger's four figures exactly, and no other cell exceeds 0.02 (next largest |signed| is 0.0116).
The type-I table reproduces cell for cell (0.043/0.057/0.063/0.103/0.163 at n=35, etc.) and the
permutation column spans 0.0233-0.0633, matching "0.023-0.063 in EVERY cell". Q2 spreads span
0.0192-0.1719 as claimed. | none
GREEN | bench/xi_ties.py:147-162 | `_xi_random_tie_break` IS eq (8) with a uniform random x-tie
break: `np.lexsort((rng.random(n), x))` sorts by x with a fresh uniform key breaking ties, `r =
rankdata(y,"max")[order]`, `ell = rankdata(-y,"max")` NOT reordered, denominator
`2*sum(ell*(n-ell))`. Term for term the same expression as `shape_stats.chatterjee_xi`, differing
only in the tie-break, which is what it is for. | none
GREEN | bench/xi_ties.py:205-218 | The Q2 sub-experiment DOES quantise x now
(`_make_pair(..., x_levels=y_levels)`) and only there; Q1/Q3 call `_make_pair` without
`x_levels`, so `tie_fraction_x` is 0.000 in every row while `tie_fraction_x_q2` runs 0.80-1.00.
The column of zeros the ledger describes is gone and the effect is real. | none
GREEN | bench/xi_ties.py main() | The DELIVERABLE block that silently failed to apply HAS landed:
:253-271 reads `p_signed_diff_mean`, states the MC floor, and falls back to reporting the worst
cell when nothing crosses. | none

MINOR | bench/xi_ties.py:10-11 | Module docstring still defines the deliverable as "the tie
fraction at which the two p-values first differ by more than 0.02", which is the form the results
section rejected as unreadable (tie fraction saturates at 1.000 across three cells at once). The
report and `_divergence_levels` both report LEVELS. | Say levels in the docstring too.
MINOR | bench/xi_ties.py:226 | `seed=hash((n, y_levels)) % (1 << 31)` - a seed that determines
every number in a shipped CSV, derived from a hash rather than declared. Int-tuple hashes are
stable across processes so the study IS reproducible, but the seed appears in no column of the
CSV and a reader cannot regenerate one cell. | Put the seed in the row.
MINOR | ledger:989 "no systematic bias" | The 20 tied cells' `xi_deterministic_percentile` has
mean 62.6 and median 77.8 against the 50 an unbiased arbitrary member would give; with SE ~6.5
that is about 2 SE high. The claim is asserted, not measured, and each cell is ONE pair (Q2 uses
a single representative dependent pair per cell, not an average over pairs). | Either measure it
or say "between the 2nd and 90th percentile, on one pair per cell".
MINOR | bench/xi_ties.py:218 | On the tie-free control the "percentile" is 100.0 because every
draw equals ours and the convention is `mean(draws <= ours)`. A point mass has no percentile; a
reader scanning that column sees 100 next to a spread of 1e-16. | Emit NaN when
`xi_tie_break_sd == 0`.
CORRECTION to the entry above (my own arithmetic, recomputed): the 20 tied cells' percentile has
mean 62.78, median 75.25, SE 6.21. The 2-SE-high reading stands; the median figure I first wrote
(77.8) was wrong.

### Part 2 - the instrument report (the tier verdicts)

IMPORTANT | analyzers/instrument_validation.py:369-374 | C2 tier 4 = `pass`, "gamma=1 path
equals the textbook AD form to float precision". The report's own header defines tier 4 as "does
it agree with an INDEPENDENT implementation of the same statistic". The thing it agrees with is
`_classical_ad` at tests/test_checks_statistics.py:63 - a five-line formula hand-written in this
repo, in the same language, by the same author. That is a second transcription, i.e. tier 1
evidence, and it is exactly the failure mode the module docstring says tier 4 exists to catch
("a routine that is SELF-CONSISTENTLY WRONG"). Contrast CvM's tier 4, which uses
`scipy.stats.cramervonmises` and IS independent. `scipy.stats.anderson` exists and was not used.
| Downgrade to `partial` ("second transcription, not an independent implementation"), or compare
against scipy.
IMPORTANT | analyzers/instrument_validation.py:384-389 | C3 tier 4 = `pass`, "it IS the R
implementation, over a bridge". Circular: the tier asks whether OUR number agrees with an
independent one, and no comparison exists. Everything tier 4 would catch here lives in the
bridge - CSV write, decimal separator, column order, result parsing - and
`docs/iid_checks/C3_serial_copula.md:39-41` says the numeric path is pinned by nothing. Worse,
the comparison IS available and was declined: `reference/r_reference_values.csv` carries
`durations_iid/serial_indep_global_statistic = 0.00739025142047825` with its seed, N and lag.max,
and test_r_cross_implementation.py:228-242 pins only that those fields exist. | `absent` with
"bridge unvalidated; reference value in hand, comparison needs R at test time" - or run the
comparison behind a `rscript_path() is None` skip.
IMPORTANT | analyzers/instrument_validation.py:414-421 vs 210-217 of cvm_cramer_von_mises.py |
CvM's three tier rows are all `pass` with no row recording that the m > 1 path - the one the
gapped records here actually take - has NO asymptotic calibration (it raises) and NO external
validation of any kind (the unweighted sum is an extension beyond the source; this ledger:268-272
says so). The tier-4 detail is scoped to the gamma=1, m=1 path, but the table cell reads `pass`
for the instrument. | Add the m>1 caveat to the tier-4 detail, as C5's tier 4 already does for
its max-over-lags aggregation.
MINOR | tests/test_instrument_validation.py:211 | `assert "2 levels" in render_tier_table_markdown(data) or True` is a tautology - it can never
fail, and the trailing comment admits the table uses a different phrasing. A dead assertion in a
file whose whole subject is not overstating evidence. | Delete it or assert the real string.
MINOR | tests/test_instrument_validation.py | No test pins the C1 tier-3 verdict, which is the
one this pass got wrong (see the C1 entry above). `test_c3_is_not_credited_...` and
`test_xi_tier_3_is_partial_...` show the pattern; C1 is the missing case. | Add one.
MINOR | bench/results/instrument_report.md, generated | C5 and C6 tier 2 and dcor tiers 2 and 3
render as a bare `absent` with no detail while every other cell reads "verdict - detail", because
`render_tier_table_markdown:504` falls back to the bare constant when no `TierRow` exists. The
absent-with-a-reason rows and the absent-by-omission rows are indistinguishable. | Emit "absent -
not assessed" for the fallback.
MINOR | analyzers/instrument_validation.py:481-486 | The header table documents four tiers; the
matrix renders only 2, 3 and 4. A reader sees tier 1 defined and then never scored. | Say tier 1
is code review and is not tabulated.
GREEN | analyzers/instrument_validation.py:204-210 | Real positive control: the builder RAISES if
a row marked `agrees=True` differs by more than 1e-3, and tests/test_instrument_validation.py:92
proves it fires on a corrupted published value. Verified in the generated report - the three
divisor rows carry `NO` and the reconciling factor 1.0142. | none
GREEN | jobs/active/instrument_validation.py | Contract-clean: every input is a `Dataset` loaded
with `job.load_df` (so each CSV's hash reaches the run identity), the builder is a pure step with
`divergence_threshold` and `n_perm_in_tie_study` declared as step kwargs, no pipeline module
imports `bench/` or `tests/`, and `bench/instrument_report.py` imports the pipeline (legal
direction). `_divergence_levels` picks the FINEST crossing and its ordering is right (0 -> 1e9,
descending), pinned by test:214. | none

### Part 2 - check_ledger_q1_070423.py, reference/, CLAUDE.md

GREEN | jobs/active/check_ledger_q1_070423.py vs jobs/active/t2star_q1_070423.py | The carve IS
identical, verified on the artifacts rather than by reading: same dataset path, same
`_filter_step(RAMSEY_CONFIG)` -> `_final_stage` -> `t2star.run` chain, byte-identical
`_T2STAR_THRESHOLDS`, byte-identical `_windows_run` body, same step kwargs (gap_mult=10.0, k=1.0,
use_uncertainty=True). Window counts per threshold in the shipped ledger match the shipped panel
windows table EXACTLY: 1/4/356/682/130/30/11/2/1 at 1-9 us. The docstring's comparability claim
holds. | none
GREEN | ledger:992-1000 real-data claims, re-derived from the artifact | 104 rows; verdicts
31 fail / 29 underpowered / 26 not computed / 12 pass / 6 not interpretable - exact. C3 in-spec
p-values 0.004496, 0.0005, 0.0005, 0.0005, 0.016484 and calendar 0.004496, 0.3711, 0.6479,
0.4600, 0.4800 - exact. No timeout row (the two `not computed` C3 rows read "n=3 too short for
lag.max=5"). In-spec 3-6 us: every check that returned a p rejected; calendar 4-5 us: 7 pass /1
underpowered and 5 pass /3 underpowered. All accurate. | none
MINOR | jobs/active/check_ledger_q1_070423.py:58 | `extra={"run_name": PREFIX}` makes the ledger
artifact's `dataset_id` "q1_27h_0704_ledger" while the panel's is "q1_27h_0704_dataset" - the same
physical record under two ids, in the two artifacts the docstring says are to be read side by
side. A join on `dataset_id` between them finds nothing. | Use the panel's run_name, or add a
column that carries it.
MINOR | CLAUDE.md:80 | "C3 copula-via-R (needs Rscript, ABSENT HERE)" - Rscript 4.5.3 is
installed and C3 has run on the real record. This is a SEVENTH site of the stale
"R is absent" claim (the fix layer corrected five, and docs/iid_checks/C3_serial_copula.md:63
still carries an eighth in "which is every row"). The agent guide is the one a fresh session
reads first. | Update the line.
MINOR | CLAUDE.md Layout | Stale in three more ways after this pass: `checks/` does not list
`cvm_cramer_von_mises.py`; `analyzers/` does not list `permutation.py`, `check_ledger.py` or
`instrument_validation.py`; `jobs/active/` does not list `instrument_validation.py` or
`check_ledger_q1_070423.py`. Also the doc-hygiene section still says the tracked .md files are
"README.md, docs/**, and bench/results/promotion_report.md", but `bench/results/instrument_report.md`
is now a tracked generated .md too. | Refresh the four lines.
MINOR | reference/load_haul_dump.csv vs tests/fixtures/load_haul_dump.py | The ledger says the
record is "read by BOTH the suite and the figure so the two cannot drift". It is actually
DUPLICATED - the CSV for the figure, a hardcoded numpy array for `test_checks_published_values.py`
- and kept in step by `test_instrument_validation.py:85-89`, which does compare them. So the
protection is real but it is a test, not a single source; the claim as written is stronger than
the arrangement. | Restate, or have the fixture module read the CSV.

### Part 3 - the sweep for a fourth silently-failed edit

FOUND, ONE | tests/test_tier3_calibration.py | See the IMPORTANT entry above: three sentences
say the instrument report/figure imports `measure_asymptotic_size`; nothing does. This is the
fourth instance of the class the brief asked me to look for - a described edit that never landed
(or a claim written for an edit that was then not made), and unlike the first three it is not
visible in the printed output because nothing prints it.
SWEPT, CLEAN | Everything else in the Increment C sections was checked against the code rather
than assumed: the signed-mean DELIVERABLE block in `bench/xi_ties.py:253-271` HAS landed; the Q2
x-quantisation HAS landed (`x_levels=y_levels` at :209, and `tie_fraction_x` is 0.000 in all 24
rows while `tie_fraction_x_q2` is 0.80-1.00); `_divergence_levels` really does take the finest
crossing; `XI_TIE_CUTOFF` is still 0.0 as the results section says it deliberately left it;
`bonferroni_z_crit`/`null_se` are genuinely imported from `calibration_summary` rather than
re-defined; the stated resolutions (+/-0.0201 at alpha=0.10, +/-0.0067 at 0.01) reproduce; the
style ratchet is 17 with zero hex/fontsize literals in the new plot module; `tests/` = 298
passed, 2 skipped, ruff at the one known F841. No further doubled sentences or unreflowed
insertions in the new files (only analyzers/checks/c3_serial_copula.py:13, logged above).

MINOR | analyzers/instrument_validation.py | 564 lines carrying four dataclasses, three builders,
two divergence readers and a markdown renderer. `render_tier_table_markdown` is 100 lines of
string assembly living in `analyzers/`. It is pure (the file writing is in bench/), so no rule is
broken, but the file is at the unwieldy line on arrival. | The markdown renderer is the natural
split.
MINOR | plots/instrument_validation_plot.py:227 | Caption says "{n} of {n} quantities reproduce
exactly" while `agrees` is a 1e-3 RELATIVE tolerance and mu_hat is 54.7222 against a printed
54.72. "Exactly" is the wrong word on a comparison against rounded published values. | "to the
precision the paper prints".
MINOR | analyzers/shape_stats.py:35 | A stray blank line splits item 5 from item 6 of the
"SIX DIFFERENCES" list - left by the median-window prose correction. Cosmetic, but it is the same
edit-hygiene signature. | Remove.

### Part 1 answer - does the corrected prose now UNDERSTATE?

Mostly no. The six corrections were checked against the artifacts they cite and each is either
exact (shape_stats' 11/14 median windows; the 1/N divisor consequence - sqrt(5/4) = 1.118, so
"about 12% on a five-event segment" is right) or correctly refuses a claim it cannot support
(the C3 cost, where no exponent is now asserted). Two places have drifted into understatement
since, both because the world moved after the prose was written:

MINOR | analyzers/checks/c3_serial_copula.py:206 | "A separate run had n = 682 unfinished at
580 s" is now the WEAKEST thing known about the cost: the shipped ledger computed C3 at
n_events = 682 on the in-spec clock inside the 900 s timeout (statistic 1.511, p 0.0005), and no
row timed out. A reader sizing `timeout_s` is being shown only the discouraging measurement. |
Add the completed n=682 point.
MINOR | docs/iid_checks/C3_serial_copula.md:44-45 and bench/results/promotion_report.md:5 | Both
still describe C3 as exercised on iid input only. It has since run on the real 912-day record at
ten thresholds on two clocks and rejected on five of them. Uncalibrated is still right;
"smoke-tested on iid input only" is no longer the whole of what has been run. | One sentence.

### VERDICT (reviewer, Increment C + the unreviewed B fix layer)

DO NOT SHIP as it stands. Nothing here produces a WRONG NUMBER - every deliverable figure in the
ledger's Increment C sections was re-derived from the CSVs and artifacts and every one is
correct. The defects are all of one kind, and it is the kind this pass exists to prevent: a
verdict or a docstring that claims more evidence than exists.

Blocking (four IMPORTANT, all one-line prose or one-word verdict changes):
1. tests/test_tier3_calibration.py - the instrument report does NOT import
   `measure_asymptotic_size`; three sentences say it does; the tier-3 "size measured" verdicts
   have no number behind them anywhere.
2. tests/test_tier3_calibration.py:13,189 - 0.069 and 0.0757 are pooled means over two Weibull
   shapes (0.064/0.074 and 0.065/0.0865), labelled as cells. CLAUDE.md's first claims-discipline
   rule, fourth instance.
3. tests/test_tier3_calibration.py:14 - the asserted "direction" is not asserted and runs the
   other way on this file's own generator (0.0342 / 0.0292 / 0.0383 at n=20, conservative).
   analyzers/instrument_validation.py:353-358 then prints "anti-conservative" as a `pass`.
4. analyzers/instrument_validation.py - C2 tier 4 `pass` rests on a hand-written formula in the
   test file, not an independent implementation; C3 tier 4 `pass` is circular and declines a
   comparison whose reference value is already in `reference/r_reference_values.csv`.
Plus the Tier 4 membership band, which accepts the pre-Increment-B estimator and five other
wrong ones - keep it, but stop calling it the evidence for eq (8) (the y-only case is).

---

## Increment C - fixes after the COLD-READ audit

FIXED | THE FOURTH FAILED EDIT, exactly where the audit was asked to sweep |
`measure_asymptotic_size` lived in `tests/test_tier3_calibration.py` while three of its
docstrings and the report's three tier-3 verdicts claimed the report imported it. It did not -
`grep -rn` matched that one file - and the pipeline may not import `tests/`, so "asymptotic
size measured" was a verdict resting on no number in the artifact. The function now lives in
`analyzers/instrument_validation.py`, the TEST imports it, and `build_instrument_validation`
calls `measure_all_asymptotic_sizes()` so each tier-3 row quotes a number that run produced.
Pinned by `test_the_tier_3_rows_quote_a_number_this_run_produced`.

FIXED | pooled means presented as cells | "the bench measures 0.069 (C1) and 0.0757 (C2) at
n=20" are POOLED MEANS over the two Weibull shapes. The table's actual cells, verified:
C1 0.0640 (shape 0.75) and 0.0740 (1.50); C2 0.0650 and 0.0865. This is verbatim the first
instance CLAUDE.md's claims-discipline section records - `report.size_by_n` - reintroduced in
new prose. All four cells are now named with their shapes and mc_se.

FIXED | the direction claim was INVERTED, and the reason is interesting | The prose said
"anti-conservative at small n as the source reports". Measured with the file's own function at
n=20: C1 0.0342, C2 0.0292, CvM 0.0383 - CONSERVATIVE. Not a contradiction of the bench: the
bench generates WEIBULL gaps (shapes 0.75, 1.50) and this measurement generates EXPONENTIAL
ones. Both are legitimate iid nulls, since these check trend against renewal rather than
exponentiality, so the finding is that the size of an asymptotic check here DEPENDS ON THE GAP
DISTRIBUTION through the estimated gamma_hat - and therefore no single direction can be
asserted. Both numbers now appear side by side and no direction is claimed anywhere.

FIXED | two tier-4 `pass` cells with nothing independent behind them |
  - C2: its "reference" is `_classical_ad`, five hand-written lines in our own test file -
    same language, same author. That is tier-1 evidence wearing a tier-4 label. -> partial.
  - C3: "it IS the R implementation, over a bridge" compares R to itself. -> absent, with the
    comparison that WOULD settle it named (our bridge against the fixture's
    `serial_indep_global_statistic` at seed 707), and why it is not done: it needs R at test
    time, which the suite refuses to require.
Both pinned by `test_no_tier_verdict_claims_evidence_that_does_not_exist`.

FIXED, and NOT found by the audit | tests/test_tier3_calibration.py | The exactness test seeded
itself with `hash((check_name, layout_name))`. Python randomises string hashing per process, so
the seed differed on every run - measured 90936 / 90550 / 90044 across three interpreters - and
a test whose entire claim is that a rate lands inside a band was silently FLAKY. It failed once
during this fix round, which is how it surfaced. Replaced with an explicit `SEEDS` table;
verified 12 passed on three consecutive runs. Same defect class `block_permutations` raises
over when a caller omits an rng.

NOTE ON THE TIE-BREAK BAND | The audit is right that `[q001, q999]` is wide: it accepts the
pre-Increment-B tie-free reduction and four other wrong estimators, and `xicor_q001` equals
`xicor_min`, so the lower edge is the whole observed support. The eq (8) claim is nonetheless
discharged - by `xi_tied_y_only`, which is deterministic, agrees to 2.3e-16, and catches every
one of those mutants. The membership test is a weak SUPPLEMENT, not the evidence. Docstring
should say so; recorded rather than silently relied on.

STATE | 300 passed, 2 skipped. ruff at the one known pre-existing F841. Ratchet 17.

STRENGTHENED | tests/test_r_cross_implementation.py, xi tier 4 | Prompted by the question
"if it was published why not just use it": `scipy.stats.chatterjeexi` EXISTS as of scipy 1.17
and is installed here. Measured against ours on all four fixture cases: agreement to 1e-10,
including `xi_tied`, where the R comparison cannot pin equality because XICOR breaks x-ties at
random and scipy (like us) breaks them deterministically. So the tied path - the only behaviour
Increment B changed - now has an EXACT external check for the first time; the membership band
was the weak supplement the audit correctly called out.
This is stronger tier-4 evidence than the R fixture for a reason unrelated to authority: it
runs unconditionally in the suite, whereas the R comparison reads a frozen file that only
regenerates on a machine with R. 5 tests added, 305 passing.
OPEN, a genuine scope question for the human: `chatterjee_xi` could now simply CALL scipy's,
with zero numerical effect (proven identical on four cases). Kept as ours for now - it is
validated, it is ten lines, and swapping an implementation during a review pass is not a
review-pass change. Recorded so the option is not forgotten.

---

## Increment C addendum - the cross-dataset independence survey

NEW | analyzers/independence_survey.py, plots/independence_survey_plot.py,
jobs/composite/independence_survey.py, tests/test_independence_survey.py (20 tests) |
Seven figures - one per `battery.ROW_KEYS` entry - each a grid of all 34 6D2S datasets by the
10-rung T2* ladder, both clocks stacked. Answers a question the per-dataset ledger cannot:
whether iid fails on THIS record or on the device.
Coloured by VERDICT, not p-value. A p-value heatmap is the obvious design and is wrong: on a
short window "did not reject" carries no information, and a pale cell would read as evidence
of independence when it is evidence of nothing. The ledger's three-way verdict already
encodes that against the bench, so the survey reuses it and prints p inside the cell.

REMOVED | jobs/active/check_ledger_q1_070423.py | Redundant, and redundant in the way its own
neighbour warns against. `jobs/composite/check_ledger_q1.py` already ledgers both q1 datasets
and gets its windows by `include` + `.ref` from the T2* jobs, so there is ONE carve wiring;
the job I added in this pass re-derived the carve, which that file's docstring explicitly
calls out as "fifty lines that must stay byte-identical to those jobs forever". Deleted. Its
output directory stays - output/ is append-only - so the figure already produced is intact.

NEW | analyzers/check_ledger.py `include_c3` | The survey needs C3 off: it is out of process,
costs 130 s at n=355 and grows steeply, and has no bench cell so it cannot be scored on the
grid anyway. Rows are OMITTED rather than written `not computed`, because a blank row would
claim the check was attempted. Threaded through `make_inputs_from_windows` so it is reachable
from a job and lands on the provenance label - the defect class the reviewer caught with
`xi_seed` and which I nearly repeated: the first version added the field to the dataclass only.
Also caught before it shipped: the first guard was `if not inputs.include_c3: return results`,
which returns the WRONG TYPE - the function goes on to build row dicts from `results` and
returns those. Fixed to a positive guard around the block.

FOUND, and PRE-EXISTING | the threshold ladder was not bit-identical between the survey and
the panels | The composites build the ladder as `k * 1e-6`; the T2* jobs write the literals
`1e-6 ... 10e-6`. These differ: 1e-6 is not exactly representable, so `5 * 1e-6` is
4.9999999999999996e-06 and `10 * 1e-6` is 9.999999999999999e-06 - two of the ten rungs land on
a different double from the panel's. `k / 1e6` reproduces all ten literals exactly.
`jobs/composite/check_ledger_q1.py` has had this since it was written, so its ledger has been
scoring a marginally different ladder than the panel it describes.
IMPACT IS NIL IN PRACTICE and this says so rather than dressing it up: the gap is about 4e-22
and no measured T2* value will fall inside it, so no window has ever changed. It is fixed
because the survey CLAIMS to score the same ladder, and a claim true only to 15 significant
figures is not the claim being made. Both composites now use `k / 1e6`, and
`test_the_survey_scores_the_same_threshold_ladder` asserts exact float equality against the
T2* job's literals - which is how it was found.

THE RESULT | 34 datasets x 10 thresholds x 2 clocks, C3 excluded. Rejection share of DECIDED
cells (pass + fail as the denominator, not all cells - an underpowered grid must not look
reassuring):
    instrument                        in_spec   calendar
    C1 LR asymptotic                  8/8 = 1.000    31/67 = 0.463
    C1 LR permutation                 8/22 = 0.364   25/118 = 0.212
    C2 AD asymptotic                  9/18 = 0.500   33/51 = 0.647
    C2 AD permutation                 9/22 = 0.409   32/118 = 0.271
    C5 rank studentized               37/168 = 0.220 16/167 = 0.096
    C5 rank raw                       36/168 = 0.214 15/167 = 0.090
    C6 exchangeability                49/168 = 0.292 18/167 = 0.108
Two readings worth carrying, both provisional: the IN-SPEC clock rejects at roughly twice the
calendar rate on every rank check, which is the same clock disagreement the single-dataset
ledger showed, now across 34 records; and C1/C2 have almost no usable cells on the in-spec
clock at all (179 of 208 `not computed`), because `tau == T_N` there makes eq (7) singular -
exactly what `include_tau_checks` documents. The asymptotic C1 in-spec cell reads 8/8 = 1.000
and MUST NOT be read as "C1 always rejects": it is 8 decided cells out of 208.

---

## Increment C addendum - REVIEWER PASS (independent, fresh context, 2026-08-14)

SCOPE: the cross-dataset independence survey + the unreviewed Increment C audit fixes.
COMMIT: 2f1bd95 (working tree; nearly all files in scope are untracked)

### Manifest
- [ ] analyzers/independence_survey.py (278)
- [ ] plots/independence_survey_plot.py (289)
- [ ] jobs/composite/independence_survey.py (261)
- [ ] tests/test_independence_survey.py (254)
- [ ] analyzers/check_ledger.py include_c3 (503)
- [ ] analyzers/instrument_validation.py tier verdicts (635)
- [ ] tests/test_tier3_calibration.py SEEDS (226)
- [ ] tests/test_r_cross_implementation.py scipy (288)
- [ ] ladder k/1e6 sweep
- [ ] claim sweep for a fifth failed edit

### Reviewed
- [x] src/quebra/core/job.py (_load_dataset, _load_dataframe_raw)
- [x] src/quebra/core/dataset.py
- [x] src/quebra/schemas/ramsey_series.py
- [x] src/quebra/schemas/null.py
- [x] tests/test_load_dataset_contract.py
- [x] docs/WRITING_A_SCHEMA.md
- [x] G1 .gitignore / Makefile / pytest.ini  (R0.1, R0.2 acceptance: all 5 criteria PASS)
- [x] G2 jobs/{reference,rscripts,bench} move
- [x] G3 spec/ledger/ (R0.3)
- [x] G6 .claude/ tracking + repo weight
- [x] G4 rename (R0.4)
- [x] G7 tests/ correctness spot-checks
- [x] G5 project identity + em dash sweep (R0.5)

### Findings (this pass)

IMPORTANT | analyzers/independence_survey.py:117-131 (`counts`) and the ledger's THE RESULT
table | The census silently drops every ledger row the survey cannot key. Measured on the
shipped artifact
(output/independence_survey_340722_20260814_030436/independence_survey.pkl): every grid is
34x10 = 340 cells but `sum(counts.values())` is 208 (in_spec) / 207 (calendar) - 132/133
cells are NaN and land in NO verdict bucket. Cause: `check_ledger._blank_row` writes
`check_id="(all)"`, which matches no `ROW_KEYS` entry, so a rung the carve declined
entirely vanishes instead of counting as `not computed`. It is not scattered: the 1 µs and
10 µs columns are 34/34 NaN in EVERY grid, i.e. two of the ten ladder rungs are wholly
absent from all seven figures and from every denominator. The ledger's prose "(179 of 208
`not computed`)" and "8 decided cells out of 208" therefore quote a denominator over the
subset that produced keyed rows; the honest statement is 311 of 340. `rejection_share_of_
decided` itself is unaffected (its denominator is pass+fail), but the "out of 208" framing
is not. Minimal fix: map `(all)` blank rows onto every ROW_KEYS entry for that
(dataset, threshold, clock), or record the count in the (currently always-empty) `dropped`
field and quote 340 as the grid size.

IMPORTANT | analyzers/independence_survey.py:225-226 | A second, differently-caused silent
blank: `run_battery` drops the C2 asymptotic row when m > 1 segments (Kvaloy-Lindqvist
4.2). Measured: the C2-asymptotic/calendar grid has 35 cells that are NaN while the C2-
permutation/calendar grid has a verdict at the same (dataset, threshold) - 168 NaN vs 133.
A reader comparing the two C2 figures sees cells disappear with no marking and no note. Same
class as above: absence is drawn and counted as nothing rather than as a stated reason.

MINOR | analyzers/independence_survey.py:142,244 | `dropped: dict[str, int]` is constructed
as `{}` unconditionally and never written - the one field that would have carried the two
findings above is dead. Either populate it or remove it.

CRITICAL | tests/test_independence_survey.py:98-113 | The ladder guard does not guard the
survey. `test_the_survey_scores_the_same_threshold_ladder` RE-TYPES the survey's ladder as a
literal in the test (`survey_ladder = [(f"{k} µs", k / 1e6, True) for k in range(1, 11)]`)
instead of reading `THRESHOLDS` out of `jobs/composite/independence_survey.py`; it cannot
read it, because `_module_constants` uses `ast.literal_eval`, which raises on the ListComp
and silently skips it (`"THRESHOLDS" not in SURVEY`). So the assertion compares the T2* job
to a copy of the reference. MUTATION TESTED in a scratch mirror (no source touched), 20 tests
each:
  - survey ladder `k / 1e6` -> `k * 1e-6` (the exact drift this pass was written to catch):
    20 passed, NOTHING FAILED.
  - survey ladder `range(1, 11)` -> `range(1, 9)` (drops two rungs): 20 passed, NOTHING FAILED.
  - T2* job `5e-6` -> `5.5e-6`: 1 failed (so the guard is real in ONE direction only).
The ledger's claim that this test "asserts exact float equality against the T2* job's
literals - which is how it was found" is therefore half true: it pins the panel side, not the
survey side, and would not have caught the defect had it been introduced in the survey.
This is CLAUDE.md's recorded "positive control must fail when the thing it guards is broken /
assert against the REAL output, not a copy of the reference". Minimal fix: import THRESHOLDS
from the job module (or `ast.literal_eval` the elements after unrolling the comprehension)
and compare THAT to the T2* literals.

VERIFIED | the ladder fix itself | `k / 1e6` reproduces all ten T2* literals to exact float
equality (checked element-wise against the AST-read literals); `k * 1e-6` differs at k=5
(4.9999999999999996e-06) and k=10 (9.999999999999999e-06), as claimed. `grep -rn "\* 1e-6"`
over the repo finds only the two explanatory comments - no construction site remains. Both
composites use `k / 1e6`.

VERIFIED by mutation | the other survey guards DO bite: GAP_MULT (survey side and T2* side),
MIN_EVENTS_PASS, INCLUDE_C3 each fail exactly one test when mutated. `_module_constants`
handles AnnAssign, so `DATASET_FILES` is really read.

IMPORTANT | jobs/composite/independence_survey.py:73-80 | False comment, and the one constant
in the block that is NOT pinned by a test. The block is headed "Verdict parameters ... Equal
to jobs/composite/check_ledger_q1.py so the two ledgers are comparable" and `SEED = 20260814`
sits inside it, but check_ledger_q1 uses `SEED = 20260812`. The seed selects the permutation
draws, hence the permutation p-values, hence the verdicts - so the two ledgers are NOT
comparable cell-for-cell on the one dataset they share (q1 070423), which is what the comment
asserts. The parametrized equality test lists ALPHA/MIN_EVENTS_PASS/TIE_CUTOFF_DISTINCT/
LAG_MAX/N_PERMUTATIONS and omits SEED, so nothing catches it. Minimal fix: either use the
same seed and add SEED to the parametrize list, or say plainly that the seed differs and the
permutation p-values are therefore not cell-comparable.

VERIFIED | plots/independence_survey_plot.py | The overview's labelling is lookup-based, not
positional: `grid = pd_.grid(key, clock)` and the row label comes from `grid.label`, the
column title from the same `clock` used in the lookup, so the off-by-one class asked about
cannot occur. `_draw_transposed` uses `grid.verdicts.to_numpy().T` with y ticks from
`.columns` (thresholds) and x ticks from `.index` (datasets) - genuinely the same data,
correctly relabelled. Dropping p-values in the overview is stated in the docstring AND in the
caption ("Read a p-value off the per-instrument figures, not this one"). `theme.verdict_color`
raises on an unknown verdict, so no silent colour fallback.

IMPORTANT | plots/independence_survey_plot.py:112-118,272-276 vs docs/FIGURE_STANDARD.md:84-91
| "Every panel that drops data says how much it dropped, in the panel." These panels drop 132
of 340 cells per grid (the unkeyable `(all)` rows - the whole 1 µs and 10 µs columns) and, for
C2 asymptotic, 35 more for m > 1 segments, and paint all of them with the `not computed`
colour without saying anywhere in the panel that they were dropped rather than computed-and-
declined. The caption's counts ("N of M decided cells reject") do not include them either. An
annotation of the form `no rows: 132 of 340 cells` is what the standard asks for.

MINOR | plots/independence_survey_plot.py:93-94, 251-252 | Caption points at the wrong colour.
Both captions say "Grey cells carry no information - a non-rejection on too few events is not
evidence of independence", but the class that sentence describes is `underpowered`, which
`theme.VERDICT_COLORS` renders #B9A87A (tan). The greys are #9A9A9A (`not interpretable
(ties)`) and #D8D8D8 (`not computed`). A reader following the caption will read the wrong
cells. Name the verdict, not the colour.

MINOR | plots/independence_survey_plot.py:140-143, 284-285 vs FIGURE_STANDARD.md:59-62 |
"Units go in the axis label, in parentheses. Never in the tick labels." The threshold ticks
are "1 µs" ... "10 µs" under an axis labelled "Threshold" (and in the overview, under no axis
label at all). Should be `Threshold (µs)` with bare numeric ticks.

MINOR | plots/independence_survey_plot.py:26,133 | Two small couplings: the plot imports the
private `_fmt_p` from the analyzer, and the text-colour test compares against the string
literals `("pass", "fail")` rather than `VERDICT_PASS`/`VERDICT_FAIL`, so renaming a verdict
constant silently changes label contrast instead of failing.

IMPORTANT | bench/results/instrument_report.md:35 | THE FIFTH STALE ARTEFACT, and it is the
one the pass was written to fix. The shipped report's xi tier-4 cell still reads
"pass - matches XICOR exactly tie-free; inside its tie-break distribution when tied" - the
weak tie-break-membership claim the audit called out. `analyzers/instrument_validation.py:501`
now says "matches `scipy.stats.chatterjeexi` to 1e-10 ... INCLUDING the tied one", but
`bench/instrument_report.py` was never re-run, so the generated file on disk does not carry
the fix. Verified by regenerating into a scratch copy and diffing: exactly that one line
changes; the file was restored byte-identical (mtime included) and NOT left modified. Minimal
fix: re-run `python bench/instrument_report.py`.
VERIFIED alongside it: the three tier-3 numbers in the shipped .md (0.0342 / 0.0292 / 0.0383)
are exactly what `measure_all_asymptotic_sizes()` returns on this checkout, so that edit did
land and the numbers are this run's.

IMPORTANT | analyzers/instrument_validation.py:413-416,427-429 | The bench cells are named by
shape only, and shape is not the factor that moves them. "the bench measures 0.0640 and
0.0740 on Weibull shapes 0.75 and 1.50" holds `arm`, `quantised`, `censoring_target` and
`clock` silently fixed at (A_iid_weibull, False, 0.00, in_spec). Measured: at n=20, C1
asymptotic, shape 0.75 there are TEN table rows spanning 0.0630 to 0.1762 - the
censoring_target=0.25 sibling is 0.1415, more than double the quoted cell. Same for C2
(0.0000 to 0.4000 at shape 0.75). The quoted values are correct as cells; the sentence
identifies them by the one factor that varies least. This is the recorded recurrence
("never call a mean the cell" / name the factor): fixed once for the shape pooling, now
under-specified on the remaining three factors. Minimal fix: say "primary null cell
(A_iid_weibull, uncensored, unquantised, in-spec)".

IMPORTANT | analyzers/instrument_validation.py:117-119,397 | A seed that decides a REPORTED
number is a module default, not a declared parameter. `ASYMPTOTIC_SIZE_SEED = 777` and
`ASYMPTOTIC_SIZE_REPLICATES = 1200` are defaults; `build_instrument_validation` calls
`measure_all_asymptotic_sizes()` with no arguments, and neither the seed nor the replicate
count reaches `meta` or the rendered table. The tier-3 verdicts (0.0342 / 0.0292 / 0.0383)
are functions of that seed. This is CLAUDE.md's rule verbatim and the same defect class the
previous reviewer caught as `xi_seed`. Minimal fix: make them arguments of
`build_instrument_validation` and put them in `meta`.

MINOR | analyzers/instrument_validation.py:413 etc. | The tier-3 rows quote four decimals with
no Monte-Carlo error. At 1200 replicates the MC SE is ~0.005, so "0.0342" against nominal
0.05 is ~3 SE - real, but the row does not let a reader see that. Carry the SE.

MINOR | analyzers/instrument_validation.py:151 | `rejected += int(p is not None and p <= alpha)`
folds a `p_value=None` into the denominator as a non-rejection, so a check that silently
declined would report a LOW size rather than a problem. Measured 0 of 300 Nones for each of
C1/C2/CvM at n=20, so the defect is latent, not active. Minimal fix: count Nones and raise or
report them.

IMPORTANT | tests/test_instrument_validation.py:246-261 | The pin that is supposed to prove
the tier-3 rows quote a number THIS RUN produced only checks that the sentence contains a
four-decimal number. `re.search(r"size measured at n=\d+: 0\.\d{4}", row.detail)` matches
`"size measured at n=20: 0.9999"` just as happily (demonstrated). If the f-string were
replaced by a hardcoded literal - which is exactly the defect the docstring names - the test
passes. CLAUDE.md: "assert against the REAL output". Minimal fix: call
`measure_all_asymptotic_sizes()` in the test and assert the formatted value appears in the row.

MINOR | tests/test_instrument_validation.py:241-243 | The direction guard is a literal-string
guard: it asserts only that the exact old sentence "anti-conservative at small n as the source
reports" is absent. Any newly written direction claim ("conservative at small n, as the theory
predicts") passes untouched. Pin the property, not the sentence that failed.

VERIFIED | tests/test_tier3_calibration.py:15-28 | Here the four bench cells ARE fully
specified - n, alpha, clock, arm A_iid_weibull, both shapes, and mc_se - and every number
checks out against bench/results/size_table.csv (0.0640/0.005473, 0.0740/0.005853,
0.0650/0.005512, 0.0865/0.006286), as does "anti-conservative in all four". The exponential
figures 0.0342 / 0.0292 / 0.0383 reproduce exactly. So the under-specification finding above
applies to the REPORT's rows, not to this docstring.

VERIFIED | tests/test_tier3_calibration.py:83-88 | The `hash()` flakiness is genuinely gone:
`SEEDS` is deterministic across processes and the file passes 12/12 on three runs with
PYTHONHASHSEED=random. (Nit: the comment says "written out rather than derived" while the
table is in fact derived from `enumerate`, so inserting a layout at the front silently
renumbers every seed. Deterministic, but not what the comment says.)

VERIFIED by mutation | tests/test_r_cross_implementation.py:248-288 | The scipy cross-check
really would fail on a wrong estimator. scipy 1.17.1 is installed, `chatterjeexi` is present,
and neither of the 5 tests is among the suite's 2 skips. Ours vs scipy agrees to 0.0e+00 on
all four cases; two plausible wrong estimators (the pre-P5 tie-free reduction, and
`rankdata(method="min")`) differ from scipy by 1.7e-2 to 4.3e-2 on `xi_tied` and
`xi_tied_y_only`, i.e. 8 orders of magnitude above TOL=1e-10. The tied path does now have an
exact external check, as claimed. (The tie-free cases cannot discriminate - all estimators
agree there - so the discrimination rests entirely on the two tied cases; that is what the
docstring says.)

MINOR | analyzers/shape_stats.py:78-110 | `chatterjee_xi` gives the source (Chatterjee 2021,
JASA 116(536):2009-2022) and writes the formula out, but cites no EQUATION NUMBER, which
CLAUDE.md requires of a transcribed formula. The ledger's own prose refers to "eq (8)".

MINOR | analyzers/independence_survey.py:254-271 | `survey_summary` is never called by the
job - nothing materializes it - so the seven-row table quoted in the ledger is not a run
product; it has to be recomputed by hand from the pickle. It does reproduce exactly (all 14
numbers checked against the shipped artifact), but a `job.materialize` of the summary would
make the quoted table an artifact rather than a scratch computation.

MINOR | analyzers/independence_survey.py:245-250 | `meta` is asserted, not derived:
`"c3_excluded": True` is hardcoded regardless of what the ledgers actually ran, and `alpha`
is a step kwarg that is only recorded - the verdicts came from each ledger's own alpha. Run
the survey over ledgers built with `include_c3=True`, or with a different alpha, and the
artifact still claims otherwise. (`CheckLedger` carries no `include_c3` field to derive it
from, which is the underlying gap.) Every figure caption repeats the C3 sentence
unconditionally for the same reason.

MINOR | analyzers/instrument_validation.py (635 lines) | Growing unwieldy, and mixed-purpose:
a 20-row hand-maintained tier table, a Monte-Carlo size measurement, three artifact builders
and a markdown renderer in one module. The tier table in particular is prose-in-code that a
reviewer must read line by line. Candidate split: the measurement and the tier table.

VERIFIED | provenance and removals | `include_c3=False` and `seed=20260814` both appear on
the step labels in
output/independence_survey_340722_20260814_030436/provenance/*.prov.{json,md}, so the C3 flag
really is threaded to the label and not just onto the dataclass. The two
output/check_ledger_q1_070423_* directories from the deleted job are intact (output/ not
touched). Every source file in scope predates the shipped run (latest source 03:04:29, run
03:06:13), so the shipped figures do reflect this code - with the single exception of
bench/results/instrument_report.md noted above.

### Reviewed (this pass)
- [x] analyzers/independence_survey.py
- [x] plots/independence_survey_plot.py
- [x] jobs/composite/independence_survey.py
- [x] tests/test_independence_survey.py (mutation tested, 7 mutants)
- [x] analyzers/check_ledger.py include_c3
- [x] analyzers/instrument_validation.py tier verdicts
- [x] tests/test_tier3_calibration.py SEEDS
- [x] tests/test_r_cross_implementation.py scipy (mutation tested, 2 mutants)
- [x] ladder k/1e6 sweep
- [x] claim sweep - one stale artefact found (instrument_report.md)

VERDICT: DO NOT SHIP until the ladder guard actually reads the survey's THRESHOLDS and
bench/results/instrument_report.md is regenerated. Baseline reproduced: 324 passed, 2 skipped;
ruff at the one known pre-existing F841.

---

## Survey review - fixes

FIXED, CRITICAL | tests/test_independence_survey.py | The ladder guard compared the T2* job to
a copy of the reference RETYPED INSIDE THE TEST, so it could not see the survey at all.
`_module_constants` uses `literal_eval`, which raises on the ListComp, so `THRESHOLDS` was
never in the dict and the test quietly built its own. Reviewer's mutation table: survey ladder
`k / 1e6` -> `k * 1e-6` and `range(1, 11)` -> `range(1, 9)` BOTH left 20/20 green. It would not
have caught the very defect the ledger says it found. This is CLAUDE.md's positive-control rule
verbatim - "assert against the REAL output, not a copy of the reference".
Fixed with `_evaluated_constant`, which unparses the assignment and evaluates it. Re-mutated
against the real code line (the first attempt patched the COMMENT, which is why one mutant
still looked to survive): `k*1e-6` CAUGHT, 8 rungs CAUGHT, `k/2e6` CAUGHT.

FIXED | analyzers/independence_survey.py | 132 of 340 cells per grid were silently blank.
`check_ledger._blank_row` writes `check_id="(all)"` for a rung that produced no windows or was
declined at segmentation - one row standing for all seven instruments - so matching on
`check_id` dropped them and the cell rendered as "no row". Measured: the 1 us and 10 us columns
were 34/34 absent in EVERY one of the seven figures. Blanket rows are now folded into each
instrument's grid, and any remaining hole is filled with `not computed` (35 of them are
C2-asymptotic, which `run_battery` legitimately drops for m > 1 segments). Every grid now sums
to 340 of 340 with zero blanks.
The consequence for the numbers already reported: the ledger's "179 of 208 not computed" quoted
a denominator over the keyed subset. The honest figure is 311 of 340 for C1 in-spec. The
rejection SHARES are unchanged, because they always divided by pass+fail.

FIXED | bench/results/instrument_report.md | The fifth stale artifact of this pass. The shipped
xi tier-4 cell still read "inside its tie-break distribution when tied" - the weak claim the
previous audit rejected - because the code changed and the generator was never re-run.
Regenerated; it now reads the scipy claim.

FIXED | analyzers/instrument_validation.py | Bench cells named by SHAPE only. Verified: ten
rows share n=20 / C1 asymptotic / shape=0.75 and span 0.0630 to 0.1762, so "the bench measures
0.0640" silently fixed arm, clock, quantised and censoring as well. Both tier-3 rows now name
the full cell (arm=A_iid_weibull, clock=in_spec, quantised=False, censoring=0.00) and state the
range the other rows cover. Same rule, third instance this pass.

FIXED | analyzers/instrument_validation.py, jobs/active/instrument_validation.py |
`ASYMPTOTIC_SIZE_SEED` decided the three reported tier-3 numbers from a bare default, reaching
neither `meta` nor the provenance label. Now a builder parameter, declared in the job, and both
it and `n` are recorded in `meta`. Same class as the `xi_seed` defect.

FIXED | tests/test_instrument_validation.py | The pin only regex-matched four decimals, so
"size measured at n=20: 0.9999" would have passed. It now re-measures and compares.

FIXED | jobs/composite/independence_survey.py | `SEED` sat under a comment claiming equality
with `check_ledger_q1.py` while differing from it. The difference is CORRECT and now says so:
a shared permutation seed would make two jobs' Monte Carlo error identical rather than
independent, so a rung near alpha would land the same way in both and read as corroboration.
New `test_the_two_ledgers_use_different_seeds` pins the difference; the five genuine
comparability parameters keep their equality test.

FIXED | plots/independence_survey_plot.py | FIGURE_STANDARD requires a panel that drops data to
say how much IN the panel. Each per-instrument caption now carries `N of 340 not computed`
alongside the decided count.

NEW | plots/independence_survey_plot.IndependenceSurveyOverviewPlot | One image, all seven
instruments: 7 rows of instruments x 2 columns of clocks, transposed so thresholds are on y and
datasets on x. p-values are dropped at this density and the caption says to read them off the
per-instrument figures. Reviewer verified the labelling is lookup-based (no off-by-one) and the
transpose is the same data.

STATE | 325 passed, 2 skipped. ruff at the one known pre-existing F841. Ratchet 17.

---

# Phase 0 review (2026-08-23)

SCOPE: complete Phase 0 change set (staged + untracked), whole repo
COMMIT: aff894e (HEAD, nothing committed)
AUTHORITY: spec/spec01hygiene.md, AGENTS.md

## Manifest

## Reviewed
- [x] G1 .gitignore / Makefile / pytest.ini  (R0.1, R0.2 acceptance: all 5 criteria PASS)
- [x] G2 jobs/{reference,rscripts,bench} move
- [x] G3 spec/ledger/ (R0.3)
- [x] G6 .claude/ tracking + repo weight
- [x] G4 rename (R0.4)
- [x] G7 tests/ correctness spot-checks
- [x] G5 project identity + em dash sweep (R0.5)

## Findings

### G1 - ignore rules, Makefile, pytest.ini

VERIFIED PASS | .gitignore | all five R0.1 acceptance checks pass: `git check-ignore -v` returns nothing for `tests/`, `README.md`, `.github/workflows/ci.yml`; `git ls-files | grep -c '\.pyc$'` = 0; R0.2 pattern count = 0 in both `git ls-files` and the staged set; no deletions in `git status --porcelain`. | none

VERIFIED PASS | pytest.ini:14 | `pythonpath = .` is confirmed to be the fix. Re-running the same suite with that one line stripped gives `Interrupted: 24 errors during collection`; with it, 330 passed / 2 skipped. Claim in the file's own comment is accurate. | none

IMPORTANT | Makefile:12 (`check: lint types arch test`) | `make check` exits 2 today. `ruff format --check .` reports 21 files, 10 of which are `tests/*` that THIS commit is what makes tracked - they have never been formatted because `tests/` was gitignored. Committing a phase named "Hygiene" with its own checkpoint gate red, and newly tracking 10 unformatted files, is the defect the phase exists to remove. (The other 11 are pre-existing: verified DIRTY at HEAD for the 4 sampled, so the change set introduces no NEW non-test violations.) | `ruff format tests/` before commit; the 11 pre-existing paths can stay for a follow-up.

MINOR | Makefile:16-27 | `types` and `arch` `exit 0` when mypy / lint-imports are absent, and both ARE absent here, so `make check` reports two gates green that never ran. It echoes SKIPPED, so it is not silent, but the exit code a CI job reads cannot tell "passed" from "not installed". Once SPEC 0002 adds CI this becomes a false-green. | Have the skip branch exit a distinct non-zero, or gate on a `SKIP_OPTIONAL=1` env var so CI cannot skip by accident.

MINOR | Makefile:8 | `.PHONY` lists `check lint types arch deps test test-all test-r docs clean` but omits `test-real`, which is a real target at line 45. | Add `test-real` to `.PHONY`.

MINOR | pytest.ini:14 | `pythonpath = .` puts the repo root on `sys.path` unconditionally. After SPEC 0002 adds `pyproject.toml` and `pip install -e .`, the suite will still import the source tree rather than the installed distribution, so the install itself is never exercised by any test. Documented as a stopgap but nothing records that it must be removed. | Add a one-line `# remove in SPEC 0002` to the comment, or note it as a SPEC 0002 requirement.

MINOR | .gitignore:36-41 | R0.1.3 says use Appendix A verbatim and, on a conflict with something already tracked, "stop and report the conflict rather than resolving it". `output/`, `output_backup/`, `output_backup2/` were added (correctly - Appendix A only has `outputs/`, and using it verbatim would have un-ignored 361 MB) but that is a resolution, not a report. Outcome is right, procedure was not followed. | Mention the deviation in the checkpoint banner so it is on record.

### G2 - the bench/reference/rscripts move under jobs/

VERIFIED PASS | jobs/bench/* | all six modules import cleanly as `jobs.bench.*`; `parents[2]` in `instrument_report.py:26,33` and `xi_ties.py:46` is correct for `jobs/bench/<name>.py`; `RESULTS_DIR = Path(__file__).parent / "results"` in `runner.py:59`, `report.py:43`, `xi_ties.py:55` is move-invariant; all five `Dataset(path=...)` sites updated (`jobs/active/check_calibration.py:43,44`, `jobs/composite/check_ledger_q1.py:52`, `jobs/composite/independence_survey.py:146`, `jobs/active/instrument_validation.py:48,50,52,53,54`). `main.py:119,126` globs only `jobs/active` and `jobs/archived`, so `run --all` does not sweep `jobs/bench/`. | none

IMPORTANT | jobs/bench/probe_unresolved.py:44 | `OUT_CSV = repo_root() / "bench" / "results" / "probe_unresolved_out.csv"` was MISSED by the move sweep. It is the one hardcoded absolute-from-root path in `jobs/bench/`; every sibling uses `Path(__file__).parent / "results"`. Running the script writes to a `bench/` that no longer exists, so it either raises or resurrects a stray top-level `bench/results/` next to the real one. | `Path(__file__).resolve().parent / "results" / "probe_unresolved_out.csv"`, matching runner.py:59.

MINOR | jobs/bench/probe_unresolved.py:20-21 | Docstring `Usage: PYTHONPATH=. python bench/probe_unresolved.py` / `Writes: bench/results/...` - both stale after the move, and `PYTHONPATH=.` is now unnecessary given pytest.ini/`jobs` being a package. | Update to `jobs/bench/`.

MINOR | analyzers/windows.py:22 | Points a reader at `scripts/probe_unresolved.py`. That file is now `jobs/bench/probe_unresolved.py`, and `scripts/` no longer exists on disk nor in `.gitignore`. A dangling pointer in a load-bearing analyzer docstring. | Repoint to `jobs/bench/probe_unresolved.py`.

MINOR | jobs/active/instrument_validation.py:17 | `bench/results/promotion_report.md` missing the `jobs/` prefix; the same file gets it right at lines 44-54. | Add `jobs/`.

MINOR | jobs/bench/instrument_report.py:3-4 | Claims `jobs/bench/results/*.md` is tracked because of "the `!jobs/bench/results/*.md` rule in .gitignore". The new .gitignore has exactly three `!` rules (lines 28, 32, 33) and none of them is that one - `*.md` is no longer ignored at all. The stated reason for the file's location is now false. | Reword: markdown is tracked by default now.

MINOR | jobs/bench/results/promotion_report.md:2 | The generated report says "Generated by `bench/report.py`", from `jobs/bench/report.py:529`. Stale path baked into a TRACKED artifact, so it ships wrong until the bench is re-run. | Fix report.py:529 and regenerate, or edit the one line.

MINOR (scope) | jobs/bench/probe_unresolved.py + jobs/bench/results/probe_unresolved_out.csv | Neither existed at HEAD (`git ls-tree -r HEAD` has 14 `bench/` files, not these two). 225 lines of new study script plus a 1021-row generated CSV enter git under a commit whose spec is R0.1-R0.5 hygiene. Its own docstring says "Wired into nothing, imported by nothing." | Either commit it separately with an honest message, or leave it untracked until it has a consumer.

IMPORTANT | CLAUDE.md:98-104, 113-114, 133-135 | CLAUDE.md is now TRACKED for the first time (the old `*.md` rule hid it) and its Layout section is stale on five counts, against its own rule "Every claim in a doc must match the code": (a) `reference/` and `rscripts/` are documented at top level, they are under `jobs/`; (b) ":100 It exists because tests/ is gitignored" - tests/ is no longer gitignored, which is this very phase; (c) ":113 UNTRACKED (gitignored) tests/" - false; (d) ":114 scripts/, monoliths/" - absent from disk AND from the new .gitignore; (e) ":133-135 "The tracked .md files are README.md, docs/**, and jobs/bench/results/promotion_report.md ... because `*.md` is ignored by default" - `*.md` is not ignored any more, and AGENTS.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, spec/** and every tests/*.md are now tracked too. | Rewrite the Layout and Docs sections, or the em-dash sweep will have shipped a doc that contradicts the commit it rides in.

MINOR | CLAUDE.md:6-11 | The Commands block still carries three `<FILL: confirm...>` placeholders and does not mention `make check` / `make test`, which AGENTS.md 6 makes the canonical entry points. Now tracked, so the placeholder ships. | Fill them from the Makefile.

MINOR | CLAUDE.md vs AGENTS.md | Two agent guides are now tracked side by side and disagree: project name "QRE tool" vs "QUEBRA"; layout `core/ analyzers/ panels/` vs a table whose package row is `src/quebra/`; `output/` vs `outputs/`. AGENTS.md 2 describes a tree that does not exist yet. A new contributor cannot tell which is normative. | State in one line at the top of each which is authoritative and for what.

### G3 - spec/ledger (R0.3)

VERIFIED PASS | spec/ledger/INDEX.md | R0.3 acceptance holds: 1 `.jsonl`, 1 index row. All 503 records parse as JSON after redaction (checked, not assumed - the README's own claim). All six redaction counts in the README table are exact: `<repo>` 671, `<workspace>` 7, `<home>` 20, `<dataset>.pickle` 70, `<dataset>_freq_log` 16, and `<dataset>` totals 646 = 70+560+16. The `Commit` column is right: `git log --diff-filter=A` puts all five named files' first add at `aff894e`. No API key, bearer token, private-key block, `sk-ant`, `ghp_`, or email address in the file. | none

IMPORTANT | spec/ledger/7c6ea3af-...jsonl (5 occurrences) + spec/ledger/README.md:31-46 | The redaction MISSED the dash-mangled scratchpad path. `/tmp/claude-1000/-home-sera-Desktop-polimi-thesis-code-912days-qre-tool/...` survives 5 times, and it encodes the username and the entire directory chain the README says was replaced 671 + 7 + 20 times. `912days` appears 6 times, `polimi` 5, `qre_tool` 2. The substitutions matched only the slash-separated spelling. The README's "Audited before copying, and clean" and its `<home>` row are therefore claims the artifact does not support - the exact defect class CLAUDE.md's "Claims discipline" and AGENTS.md 8 forbid. | Redact `-home-sera-Desktop-polimi-thesis-code-912days-qre-tool` too, then re-verify JSON parse; or drop the sentence.

IMPORTANT | spec/ledger/*.jsonl | 10.54 MB for ONE 1-hour session, and git history is append-only: this cannot be undone later without a rewrite of every downstream clone. 9.97 MB of it is `user` records (n=153, ~65 kB each) - tool results echoed back. 5.10 MB of THAT is the `toolUseResult` field, which duplicates the `tool_result` block already present in the same record's `message.content`. So roughly half the payload is literal intra-record duplication. gzip -9 gets it to 6.0 MB, which is about what the packfile will carry, permanently. At this rate the ledger grows ~10 MB per working session. | Either strip the redundant `toolUseResult` field before committing (halves it at zero information loss), or keep the ledger in a separate repo / release asset and reference it. Do not let the first commit set an unbounded-growth precedent.

MINOR | spec/ledger/README.md:23-29 | Explains that the second, still-open transcript is deferred because "copying a live file would capture a mid-sentence snapshot". Reasonable, but nothing schedules the copy, and the same retention sweep R0.3.1 warns about applies to it. | Add it to INDEX.md's "Not yet indexed" as a dated TODO, or note the deadline.

MINOR | spec/ledger/README.md | 3.2 kB of prose for a 3-file directory, with a "Reading a transcript" section that re-explains newline-delimited JSON. R0.3.2 asks for three things: what the files are, why retained, and that they are the JOSS/thesis evidence base. Sections "What survived, and what did not" and "Redaction" earn their place; "Reading a transcript" (last 5 lines) does not. | Cut the "Reading a transcript" section.

### G6 - .claude/ now tracked

CRITICAL | .claude/.claude/** (11 files staged) | A nested duplicate of the agent configuration, mtime 2026-06-29, is staged for commit. `.claude/.claude/settings.json` is an obsolete copy whose permission set is WEAKER than the live one: it allows `Bash(git add:*)` and `Bash(git commit:*)`, which AGENTS.md 1 makes a hard prohibition ("Never run `git add`, `git commit`..."), and it lacks the current `Edit(data/**)` / `Edit(outputs/**)` denials. `.claude/.claude/agents/code-reviewer.md` (2362 B) and `plan-critic.md` (1659 B) are likewise stale, shorter forks of the live 4009 B / 1394 B files. Committing this publishes a second, contradictory, permissive agent config that someone can copy back over the real one. | `git rm --cached -r .claude/.claude` and delete the directory. It is a copy accident, not configuration.

IMPORTANT | .claude/review-findings.md (180 kB, 1824 lines before this section) | AGENTS.md 2, added in this same change set: "Prose belongs in `spec/`, never in `.claude/`, which holds configuration only." This file is 1800 lines of review prose - the largest single non-transcript addition, bigger than any source file in the repo. It is a working ledger for a review that is already finished, and its content (P5 findings on shape_stats, check_ledger, permutation nulls) is not configuration by any reading. | Move to `spec/` if the findings still matter, or leave it untracked. Add `.claude/review-findings.md` to `.gitignore`.

IMPORTANT | .claude/qre_checks_reference.tex (70 kB) | Two AGENTS.md 2 rules at once: it is prose in `.claude/`, and "Write specs and docs in Markdown, not LaTeX. What makes a spec work is numbered requirements ... not the markup." AGENTS.md also says thesis and paper LaTeX live outside this repository. It is cited by `.claude/review-findings.md` as "Authority for what it should be", so it IS load-bearing reference material - which is an argument for `spec/`, not for `.claude/`. | Move to `spec/` (as .md, or as-is if converting is too costly), or keep it out and cite the PDF the review already names.

MINOR | .claude/agents/*, .claude/commands/*, .claude/hooks/* | These 11 files are genuine configuration and belong under version control by AGENTS.md 2's own reading. No objection - listed so the CRITICAL above is not read as covering them. | none

MINOR | .gitignore:24 | Only `.claude/settings.local.json` is excluded. That is correct today (verified: it is the one `.claude` file absent from the staged set), but nothing stops the next `review-findings.md`-shaped file from being auto-staged. | Consider `.claude/*.md` and `.claude/*.tex` exclusions, or an allowlist of `agents/ commands/ hooks/ settings.json`.

### G4 - the vocabulary rename (R0.4)

VERIFIED | R0.4.5 acceptance | `grep -rn "repairable" --include="*.py" . | wc -l` returns **11**, not 0 and not 14. Sites: `panels/across_calibration.py` 1,4,8,11; `panels/within_calibration.py` 47; `jobs/active/mtbc_q6.py` 3; `jobs/active/mtbf_q1.py` 3; `tests/test_artifact_guard.py` 240,242,243,269. R0.4.4 PASSES outright: zero `availability` in `analyzers/ panels/ plots/ core/ jobs/`.

VERIFIED PASS | rename mechanics | All 8 file moves register as `R`/`RM` in porcelain, history preserved. All panel modules import and expose the new symbols; `panels/comparison.py` -> `CompareSeriesData`/`CompareSeriesPanel` with its only consumer (`jobs/composite/compare_t2star_0704_vs_1004.py:25,29,49,68`) updated; `python main.py inspect` on that job resolves the DAG. `tests/test_within_calibration_builder.py` + `test_across_calibration_builder.py` + `test_artifact_guard.py`: 22 passed. Full suite 330 passed / 2 skipped, unchanged from the pre-rename baseline as R0.4 requires.

JUSTIFIED (7 of 11) | panels/across_calibration.py:1-14, panels/within_calibration.py:47, jobs/active/mtbc_q6.py:3, jobs/active/mtbf_q1.py:3 | Decision D2b holds for these. The mapping note is real, argues the distinction (calibration boundary vs restoration-after-failure), cites Ascher and Feingold / Rigdon and Basu, and the three other sites cross-reference it. Same for `README.md:5`, `AGENTS.md:4`, `CITATION.cff:7` ("repairable-systems statistics", the field's name) and `docs/iid_checks/README.md:116` (a paper TITLE - renaming that would falsify a citation). | none

IMPORTANT | AGENTS.md:87 vs panels/across_calibration.py:11-14 | AGENTS.md 4, "Locked vocabulary", says flatly: "Do **not** use `repairable` / `non_repairable`. They are being removed." D2b says the term survives in prose that cites the field. Both files are tracked in THIS commit and they contradict each other on the one rule AGENTS.md marks as a scientific error to violate. A contributor reading AGENTS.md would delete the mapping note. | Add the D2b carve-out to AGENTS.md 4 in one line: kept only in prose naming the literature, nowhere in identifiers.

IMPORTANT | docs/PANEL_CONTRACT.md:274 | "the standard **non-repairable** degradation analysis surface" - this is describing OUR panel's coverage, three lines below `WithinCalibrationPanel` and inside the normative panel contract, with no mapping note. Unlike the 11 code sites it does not cite the field; it just uses the retired name for our own tier. The rename sweep touched this file (three `+/-` pairs) and missed this line because it is hyphenated prose, not the `non_repairable` identifier. This is the laziness case, not a D2b case. | Change to "within-calibration degradation analysis surface".

IMPORTANT | docs/PANEL_CONTRACT.md (same paragraph region) | The doc says "`panels/within_calibration.py` is ~650 lines, exceeding the project's 200-line ..." - the rename updated the PATH on that line and left the NUMBER. Measured: **1051 lines**, 5x the stated budget and 60% above the figure the doc quotes. CLAUDE.md's own rule: a measured number in a doc must come from the artifact in the state it ships. | Update to 1051, and treat the file as the flagged-unwieldy one (`panels/_within_calibration_compute.py` is a further 492).

MINOR | tests/test_artifact_guard.py:243 | Quotes the spec ("R0.4.5 of SPEC 0001 forbids the word `repairable` remaining in the source tree") and in doing so is itself one of the 11 hits that make R0.4.5 fail. Lines 240 and 269 are forced - the pickle stream literally contains `panels.non_repairable...` and the assertion must match it - but 243 is avoidable prose. | Say "the rename spec" without the word.

MINOR | panels/comparison.py | `CompareNonRepairableData/Panel` became `CompareSeriesData/Panel`, not `CompareWithinCalibration*`. R0.4.2 gives one mapping and says to flag any site that does not fit rather than renaming it. Choosing a third name is defensible (the panel really is generic) but it is an unrecorded deviation from the table. | Note it in the checkpoint banner.

MINOR | R0.4.5, non-.py scope | R0.4.5 says "no occurrence ... outside `spec/`, `docs/adr/`, and `spec/ledger/`" - not "no occurrence in .py". Only the acceptance LINE is .py-scoped. 6 non-.py occurrences remain (README.md:5, AGENTS.md:4,87, CITATION.cff:7, docs/iid_checks/README.md:116, docs/PANEL_CONTRACT.md:274). Five are justified; PANEL_CONTRACT.md:274 is not. Worth stating so the deviation is scoped honestly. | Report the non-.py set in the banner too.

### G7 - correctness spot-checks

IMPORTANT | tests/test_artifact_guard.py:231-274 | The widened guard is not merely looser, it is now **vacuous for its stated purpose**. Measured over the 72 real candidates the test globs (`output/*/subjobs_output/*/t2star_panel_data.pkl` + `output_backup2`): **72/72 raise ModuleNotFoundError, 0 raise ValueError.** The `ValueError` branch - the only one that exercises `StaleArtifactGuard` on a real artifact - is unreachable and will stay unreachable, because any pickle written from here on is post-split by construction. The docstring says "TWO failure modes now" as if both fire; only one does. The test would pass with `StaleArtifactGuard.__setstate__` deleted. (Not CRITICAL: lines 92-205 give the guard synthetic coverage including `_StalePickle` through the real `pickle.load` path, so the guard itself is still tested.) | Either assert that at least one ValueError was seen and regenerate one pre-split artifact under the new module name, or rename the test to what it now checks and stop calling it a guard test.

IMPORTANT | tests/test_bench_isolation.py:55-97 and 174 | Mutation-tested, three planted files, each removed after. (A) `import jobs.bench.runner` in `panels/` -> FAILS `test_pipeline_packages_do_not_import_the_bench[panels]`. Correct. (B) `importlib.import_module("jobs.bench.runner")` in `jobs/active/` -> FAILS `[jobs]`. Correct. (C) **`from ..bench import runner` in `jobs/active/` -> 19 passed. The guard MISSES it.** `_imported_roots` discards `node.level`, so it yields the bare string `"bench"`, and `_imports_bench` compares against `"jobs.bench"` - no match. That import resolves at runtime to `jobs.bench.runner`: a real, working bench import the guard admits. This is a REGRESSION introduced by this diff: under the old top-level-name matching, `"bench"` would have matched. Worse, line 174 of the positive control lists exactly this form, `("from ..bench import runner\n", "bench")`, and passes - because the control asserts on `_imported_roots`, not on `_imports_bench`, so it certifies a form the predicate does not catch. This is the CLAUDE.md instance "the AST walk missed importlib/relative imports its own docstring named" recurring in the same file. | Resolve `node.level` against the file's package before adding, or add `name == "bench" or name.startswith("bench.")` to `_imports_bench`; and re-point the positive control at `_imports_bench`.

VERIFIED PASS | pytest.ini:14 | Confirmed by measurement, not assertion: stripping `pythonpath = .` and re-running gives `Interrupted: 24 errors during collection`; restoring it gives 330 passed / 2 skipped. It does not mask a packaging defect that exists today, because no `pyproject.toml` exists and SPEC 0001 explicitly forbids adding one. See the G1 MINOR for the SPEC 0002 hazard it creates.

MINOR | tests/test_bench_isolation.py:113-115 | `_python_files` drops any path with `"bench"` as a path component. Correct for `jobs/bench/`, but it would also silently exclude a future `analyzers/bench/` or `plots/bench/` from every scan. | Anchor on the relative prefix `jobs/bench` rather than the component name.

### G5 - project identity files and the em dash sweep (R0.5)

VERIFIED PASS | em dash sweep | `grep -rlP '\x{2014}'` over the whole tree (excluding .git and output*) returns exactly ONE file: `spec/ledger/*.jsonl`, 79 hits, which must not be edited because it is a verbatim record. Every source file, doc and new prose file is clean. Also clean of every banned word in AGENTS.md 8 (surfacing / brings into view / data-driven / delve / leverage / firstly / excellent) - the only hits are AGENTS.md quoting its own rule.

VERIFIED PASS | the non-em-dash half of the unstaged diff | Isolated it mechanically: every remaining `+/-` pair outside the em-dash swap is ruff line-wrapping forced by the longer names (`WithinCalibration` > `NonRepairable`), e.g. `panels/across_calibration.py` `_draw_scatter/_draw_rolling/_draw_histogram` signatures and `jobs/active/mtbf_q1.py` import block. No semantic change.

VERIFIED PASS | CODE_OF_CONDUCT.md | Verbatim Contributor Covenant 2.1 with correct attribution and the `[INSERT CONTACT METHOD]` placeholder properly resolved to `CITATION.cff`. 106 lines is the standard's own length. NOT AI bloat - this is the right artifact to copy rather than write. Nothing to cut. | none

VERIFIED PASS | CITATION.cff | 21 lines, valid CFF 1.2, parses as YAML, has all four required keys. Correctly omits `version`/`date-released`/`doi` because R0.5.4 forbids tagging. Minimal, not padded. | none

IMPORTANT | README.md:56 | "Requires Python 3.11 or newer, plus numpy, scipy, pandas, matplotlib, plotly and pandera." **Four dependencies are missing.** The pipeline also imports `allantools` (`analyzers/allan.py:6`), `sklearn` (`analyzers/tlf.py:5`), `yaml` (`loaders/registry.py:7`) and `joblib` (`jobs/bench/runner.py:33`). Anyone following the install block on a clean environment hits ImportError. Installability is the first thing a JOSS reviewer checks, and it is the whole point of R0.5. | Add allantools, scikit-learn, PyYAML, joblib to the list.

IMPORTANT | README.md:16-17 and AGENTS.md:80 | "the loss measured here is roughly 25 to 45 per cent of real crossings at working thresholds". "Measured here" asserts the repo contains the measurement. `grep -rn "25 to 45|25-45|25 and 45"` over the whole tree returns exactly two lines: this one and AGENTS.md's. There is no artifact, no table, no test, no locator. It is the headline number of the Statement of Need - the paragraph a JOSS reviewer reads first - and it cites itself. AGENTS.md 8: "Never invent a section number, equation number, figure number, or citation. If you do not know the locator, write 'no source located'." | Either point at the artifact that measured it, or reword to what the code enforces ("QUEBRA never resamples, because resampling destroys and invents crossings") and drop the number.

IMPORTANT | CONTRIBUTING.md:47-48 | "Tests in `tests/statistical/` and `tests/jobs/` must name their oracle." Neither directory exists. `tests/` is flat: `tests/test_*.py` plus `tests/fixtures/`. AGENTS.md 5's six-tier table describes the same non-existent layout. A contributor following CONTRIBUTING.md would create directories nothing collects. | Say "statistical and end-to-end tests" until the tiers exist, or label the tier table as the target layout.

MINOR | CONTRIBUTING.md:16 | "the run directory name under `outputs/`" - this repo writes `output/` (singular). `.gitignore:36-39` says so explicitly: "`outputs/` is the name SPEC 0002 moves to; `output/` ... is what this repository writes today". A bug reporter is sent to a directory that does not exist. | `output/`.

MINOR | CONTRIBUTING.md:36 | Tells contributors "Run the gates before you push: `make lint`". `make lint` exits 1 at this commit (21 files fail `ruff format --check`). The first contributor who follows the instruction fails on code they did not write. Same root cause as the G1 IMPORTANT. | Format `tests/` at minimum.

MINOR | README.md:12 | "Doing that correctly is harder than it looks, for three reasons this toolkit addresses directly." Pure announcer sentence; the three paragraphs that follow each open with their own thesis and need no herald. It is also the one line in the file that reads generated. | Cut the sentence.

MINOR | AGENTS.md:4-6 | "applies repairable-systems statistics (Kaplan-Meier, Nelson-Aalen, log-rank, RMST, MCF) to them". `grep -rli "nelson|log_rank|logrank|rmst|mean_cumulative" --include="*.py" analyzers/` returns NOTHING. README.md:40 gets this right ("Nelson-Aalen, log-rank, RMST and MCF are **not** implemented yet"); AGENTS.md, tracked in the same commit, states the opposite. | Match the README's wording.

MINOR | README.md:1 vs repository-code | The project is named QUEBRA throughout but `git remote -v` and every URL in README/CITATION/CONTRIBUTING say `github.com/seraconti/qretool`. Precondition P2 records the repository as renamed; it is not, or not to this name. The README's clone command is at least CORRECT (it matches the remote), so this is cosmetic, but a reader meets two names for one project in the first 50 lines. | Rename the GitHub repo, or say once in the README that the historical slug is `qretool`.

MINOR | CITATION.cff:14 | A bare public email address in a machine-readable, indexed file. Sera's call, but it is the one irreversible personal-data item in this commit and there is no ORCID to substitute. | Consider ORCID plus the GitHub handle instead.

IMPORTANT | panels/within_calibration.py:6-9 | The mechanical rename rewrote a sentence whose entire subject was the OLD name, and inverted it into a falsehood: "That re-export is load-bearing and must not be removed: artifacts materialized before the split name `panels.within_calibration.WithinCalibrationPanelData` in their pickle stream". They do not. They name `panels.non_repairable.NonRepairablePanelData` - measured, 72/72 pickles under `output/` and `output_backup2/` raise ModuleNotFoundError on exactly that module. The docstring now claims a re-export protects artifacts that in fact cannot load at all, which is the opposite of what `tests/test_artifact_guard.py:239-247` records. Searched for siblings of this class (`pre-split`, `written before`, `used to be`, `formerly`); this is the only one. | Restore the old dotted name in that sentence and state that the re-export no longer covers pre-rename artifacts.

MINOR | R0.5 acceptance "No file contains an em dash" | Technically fails: `spec/ledger/*.jsonl` has 79. Editing a verbatim transcript to satisfy a style rule would be worse than the violation. | Scope the criterion to source and prose in the banner.

BLOCKING-BY-SPEC | "Done when" | `git ls-files` must show `.github/` tracked, and `.github/` does not exist. The same section says "Explicitly not in this phase: ... no CI." The spec contradicts itself: `.github/` has no non-CI content to hold. The R0.1 acceptance line only requires that `.github/workflows/ci.yml` NOT be ignored, which passes. | Sera's call to amend "Done when" to the acceptance line's weaker form; do not create `.github/` just to satisfy it.

---

# Phase 1 / SPEC 0002 review (installability)

SCOPE: whole repo, Phase 1 / SPEC 0002 (staged + untracked)
COMMIT: 9057803 (nothing committed; phase is staged/untracked)

## Manifest
- [x] src/quebra/core/paths.py
- [x] src/quebra/cli.py
- [x] pyproject.toml + quebra.toml
- [x] scripts/acceptance.sh + .github/workflows/ci.yml
- [x] docs/WRITING_A_JOB.md + README.md
- [x] conftest.py + tests/ deltas
- [x] src/quebra/recipes.py + __init__.py files
- [x] jobs/ import rewrites
- [x] baselines reproduction

## Reviewed
- jobs/ import rewrites
- baselines reproduction
- src/quebra/recipes.py + __init__.py files
- conftest.py + tests/ deltas
- docs/WRITING_A_JOB.md + README.md
- scripts/acceptance.sh + .github/workflows/ci.yml
- pyproject.toml + quebra.toml
- src/quebra/cli.py
- src/quebra/core/paths.py

## Findings

### src/quebra/core/paths.py

IMPORTANT | src/quebra/core/paths.py:3-7 | The module docstring, the first thing a reader meets, still says the repo root is "anchored off this file's location, the same pattern as provenance.get_git_commit". That is exactly what `repo_root` (:44-48) stopped doing in this phase - it walks up from `Path.cwd()`. The header also still calls the project `qre_tool/` and asserts the dataset root is "one level above" the repo, which is now only true because `quebra.toml` happens to say `data_root = ".."`. Header and function docstrings contradict each other on the single largest behaviour change in the phase. | Rewrite lines 3-7 to describe cwd-anchored marker discovery and the four-mechanism data root.

IMPORTANT | src/quebra/core/paths.py:150-156 | An explicit root that does not exist SILENTLY falls through to the environment, then `quebra.toml`, then platformdirs. In this checkout `quebra.toml` always resolves, so `--data-root /tpyo` yields `912days/` with no warning, and the run then hashes a different dataset tree than the operator asked for. AGENTS.md 3 makes fall-through the wrong direction ("errors are raised, not swallowed"); R1.3.4 only requires a raise when NOTHING resolves, it does not ask for this. `tests/test_data_root_resolution.py:96-107` pins the fall-through as intended behaviour, so the test locks the defect in. | Raise when `explicit is not None and not root.is_dir()`; keep the fall-through for the three non-explicit mechanisms.

IMPORTANT | src/quebra/core/runner.py:390 and src/quebra/cli.py:130-132 vs paths.py:139 | R1.3.5 says the `--data-root` flag maps to mechanism 1. It does not: the CLI resolves it itself and `run_job` does `Path(data_root).resolve() if data_root else default_dataset_root()`. `resolve_data_root(explicit=...)` therefore has NO production caller - mechanism 1 exists only for the test that exercises it. The two routes also disagree: the runner accepts a nonexistent root verbatim (and fails later at dataset resolution), the tested route falls through. | `run_job` should call `resolve_data_root(data_root)` so one chain governs.

MINOR | src/quebra/core/paths.py:22 | `PROJECT_MARKERS` includes `pyproject.toml` and `.git`, so ANY python project or git repository above the cwd is accepted as the QUEBRA project root - a git-tracked `$HOME`, a sibling project, a vendored subrepo. Measured: `cd /tmp && repo_root()` returns `/tmp`; `cd / ` returns `/`, after which `resolve_dataset_path`'s second candidate is `/<relative path>`. No live defect (the dataset fallback then simply misses and raises), but the marker set makes "some other project" indistinguishable from "this project". | Prefer `quebra.toml` as the sole positive marker, or document that the other two are heuristics.

MINOR | src/quebra/core/paths.py:65-92 | `resolve_dataset_path` is now cwd-dependent through its `repo_root()` fallback candidate, so which file gets content-hashed into the run identity depends on where the process was launched. Inside the checkout this is stable; outside it the candidate silently changes. The docstring argues the fallback (D4) but does not say it moved from `__file__` to the cwd. | One sentence in the docstring stating the fallback now follows the caller's project.

MINOR | R1.3.2 | `src/quebra/_fixtures/` was not created and nothing anywhere uses `importlib.resources` (`grep -rn "importlib.resources" src/` is empty). The requirement's first mechanism, packaged resources, is simply unimplemented. Defensible - there are no packaged resources yet - but it is an undeclared deviation, and the phase claims R1.3 complete. | Say so in the checkpoint banner, or add the empty package with a README.

### src/quebra/cli.py (and the death of main.py)

VERIFIED PASS | R1.1.4 | `grep -rn "sys.path" src/ tests/ | wc -l` = 0. The only hit anywhere in the tree is the word appearing in `conftest.py:16`'s prose. No `jobs.*` import in `jobs/active/` or `jobs/composite/` (only stdlib + `quebra.*`). `main.py -> src/quebra/cli.py` and `jobs/common.py -> src/quebra/recipes.py` both register as `RM` renames, so R1.1.2 holds.

VERIFIED PASS | src/quebra/cli.py:31-36 | The output root cannot land in site-packages: `_output_root` is `Path.cwd()/"output"` (or an explicit flag) and `_jobs_dir` is `Path.cwd()/"jobs"`. Nothing in the module touches `Path(__file__)`.

IMPORTANT | AGENTS.md:45-47 and AGENTS.md:200 | This change set DELETES `main.py` (renamed to `src/quebra/cli.py`) and, in the same uncommitted working tree, ADDS a Commands block telling every agent to run `python main.py run jobs/active/<job>.py`, `python main.py run --all` and `python main.py inspect`. All three now fail with "can't open file". Line 200's layout block still lists `main.py   CLI` while the block directly above it already gained the new `src/quebra/recipes.py` entry - a half-applied edit, the exact failure class this review was asked to sweep for. | Replace with `quebra run ...` / `quebra inspect ...`, and change line 200 to `src/quebra/cli.py`.

IMPORTANT | AGENTS.md:180-205 | The whole "Layout (real)" block still describes the pre-phase top-level layout (`core/`, `loaders/`, `transforms/`, `analyzers/`, `plots/`, `panels/`, `schemas/` at the repository root). After R1.1.1 every one of those lives under `src/quebra/`. The block is labelled "(real)", which is now false for eight of its ten entries. | Prefix the tree with `src/quebra/`.

IMPORTANT | jobs/composite/compare_t2star_0704_vs_1004.py:3,7,8 and jobs/composite/independence_survey.py:12,33 | Both files were edited in this phase (import rewrites) and both still document `PYTHONPATH=. python main.py run jobs/composite/<job>.py` as the way to run them. `main.py` no longer exists and `PYTHONPATH=.` is no longer needed. A composite is the ONE job family a reader cannot discover by `run --all`, so its docstring is the only instruction that exists. | `quebra run jobs/composite/<job>.py`.

IMPORTANT | src/quebra/__init__.py (empty) vs SPEC 0002 R1.3 acceptance | The spec's acceptance line is `QUEBRA_DATA_ROOT=/tmp/qd python -c "import quebra; print(quebra.__version__)"`. Measured from `/tmp`: `AttributeError: module 'quebra' has no attribute '__version__'`. `scripts/acceptance.sh:50-51` prints `quebra.__file__` instead, so the script passes while the stated criterion does not hold. | Add `__version__ = importlib.metadata.version("quebra")` to `src/quebra/__init__.py`, or amend the criterion.

MINOR | src/quebra/cli.py:119 | `--data-root` help still says "(default: the repo's parent directory)". After R1.3 the default is the four-mechanism chain; the repo's parent is merely what `quebra.toml` happens to declare. | "default: QUEBRA_DATA_ROOT, then [tool.quebra] data_root, then the user data dir".

MINOR | src/quebra/cli.py:134-139 | `quebra run --all` from a directory with no `jobs/active/` glob-matches nothing, prints nothing and exits 0. Silent success for a command that did no work, and this is now reachable because the CLI is anchored on an arbitrary cwd rather than on the repo. | Raise if `_jobs_dir("active")` does not exist, or if `job_files` is empty.

MINOR | src/quebra/cli.py:16-19, 190 | `h5py` is wrapped in `try/except ImportError: h5py = None`, but `pyproject.toml:37` makes `h5py>=3.11` a mandatory dependency and `loaders/registry.py` imports it unguarded. The guard can no longer fire, and if it somehow did, `schema-wizard` on an `.h5` file falls silently through to `load(file_path)` rather than saying h5py is missing. | Drop the try/except now that the dependency is declared.

### pyproject.toml + quebra.toml + Makefile

VERIFIED PASS | pyproject.toml:28-40 vs R1.2.2 | Derived independently with an AST walk over all 76 files under `src/quebra/`. The third-party import set is exactly {allantools, h5py, matplotlib, numpy, pandas, pandera, platformdirs, plotly, scipy, sklearn, yaml} - 11 names, and all 11 are declared (sklearn -> scikit-learn, yaml -> PyYAML). Nothing declared is unimported. `joblib` really is absent from `src/` (it appears only in `jobs/bench/runner.py:33`), so the comment at :25-27 is accurate. `make deps` (deptry over src/quebra) exits 0, 76 files scanned, no issues.

VERIFIED PASS | pyproject.toml:81-90 | `select = ["E4","E7","E9","F"]` is ruff's documented default, so this phase changes no lint outcome. Confirmed the claim at :84-85 is in the right ballpark and in the right direction: `ruff check .` under the shipped selection reports exactly 1 finding (the pre-existing F841 at `src/quebra/plots/interpolation_stage_plot.py:63`), and widening would land a reformat nobody reviewed. Correct call for an installability phase.

VERIFIED PASS | pyproject.toml:66-72, 92-103, 105-125 | R1.2.4 satisfied: `[tool.ruff]`, `[tool.pytest.ini_options]` with `addopts = "--strict-markers"` and all four markers, `[tool.hatch.build.targets.wheel] packages = ["src/quebra"]`. R1.2.6 satisfied: no `[tool.importlinter]`, and `make arch` correctly SKIPS with that reason (exit 0). R1.2.3 satisfied (`dev` has all seven named tools plus `build`; `r = []`).

VERIFIED PASS | LICENSE vs pyproject.toml:11 | `license = "GPL-3.0-or-later"` matches the GPLv3 text actually in `LICENSE`.

IMPORTANT | .github/workflows/ci.yml:33-34 | CI runs `ruff check .` as its second step. Measured at this commit: `ruff check .` exits **1** on the pre-existing `F841` in `src/quebra/plots/interpolation_stage_plot.py:63`. The workflow therefore CANNOT be green on the first push, which is R1.4.2's own acceptance criterion ("The CI workflow passes on a push"). The spec asks CI to run the fast selector; the lint step is an addition that fails. | Fix the F841 (it is one dead assignment) or drop the lint step to match the spec.

IMPORTANT | Makefile:18-20 | The skip-guard on `types` was DELETED, so `make types` now hard-fails (measured: 11 mypy errors, exit 2), and `make check` (`lint types arch test`) fails with it. AGENTS.md:50-52, edited in this same working tree, still tells agents `make types` and `make arch` "do not pass yet" and that a failure "tells you which phase you are in" - but a hard failure in `check` no longer distinguishes "wrong phase" from "you broke the build". Same for `lint`: `ruff check .` exits 1 and `ruff format --check .` reports 11 files. `make check`, the documented pre-checkpoint gate, cannot pass at this commit. | Restore the guard (or gate `types` on a spec marker the way `arch` now is), and say in AGENTS.md which of the four are expected red.

MINOR | Makefile:9 | `.PHONY` lists `check lint types arch deps test test-all test-r docs clean` but not `test-real`, which is a real target at :45. A file named `test-real` would shadow it. | Add it.

MINOR | Makefile:46 | `pytest -m "real or regression"` names a `regression` marker that `[tool.pytest.ini_options] markers` does not define. `--strict-markers` does not validate `-m` expressions, so this silently selects nothing rather than erroring. | Drop `or regression`, or register the marker.

MINOR | pyproject.toml:69-72 vs R1.2.5 | R1.2.5 says "Exclude from the wheel: spec/, docs/adr/, tests/, data/, outputs/". No wheel `exclude` is written; the exclusion is implicit in `packages = ["src/quebra"]`. That is stronger in practice, but the sdist `exclude` at :72 is explicit while the wheel one is not, so a reader checking R1.2.5 finds nothing where they look. | One comment saying the wheel excludes by construction.

MINOR | quebra.toml (untracked) | The file is the sole reason mechanism 3 resolves in this checkout and is currently UNTRACKED. If it is not staged with the rest of the phase, a fresh clone has no data root at all and every dataset job dies with `DataRootNotFound`. | Confirm it is added before the commit.

### scripts/acceptance.sh + .github/workflows/ci.yml

VERIFIED PASS | scripts/acceptance.sh | Ran it: exit 0, seven steps, all 0. The venv IS outside the repo (`$(mktemp -d)/venv`) and the wheel IS what is under test - verified independently by running `env -C <repo> <venv>/bin/python -c "import quebra; print(quebra.__file__)"`, which prints `/tmp/tmp.*/venv/lib64/python3.13/site-packages/quebra/__init__.py`, not `src/`. So the pytest step, despite running with the repo as cwd, exercises the installed distribution. The wheel itself is clean: 82 members, top level exactly `quebra/` and `quebra-0.1.0.dev0.dist-info/`, zero entries under `spec/ data/ outputs/ tests/ jobs/ output/`. R1.2 acceptance holds.

IMPORTANT | scripts/acceptance.sh:57-58 and .github/workflows/ci.yml:36-39 | **The fast selector deselects nothing.** Measured: `pytest -m "slow or heavy or real or r"` collects 0 tests and deselects all 339; `grep` finds no `@pytest.mark.{slow,heavy,real,r}` anywhere in `tests/`. The acceptance step and CI both report 337 passed / 2 skipped, identical to the full suite. So ci.yml:36-37's stated mechanism - "The `real` marker is what keeps those tests out; CI never sees the tree they need" - is not a mechanism at all. R1.4.3 passes today only because `data/real_private/` does not yet exist and no test happens to read a private tree; nothing enforces it. | Say the marker set is declared but unused, or mark the tests that need `tool/datasets/` (`tests/test_paths_dataset_fallback.py` is the closest) before SPEC 0003 creates the private tree.

IMPORTANT | pyproject.toml:69-72 (sdist exclude) | The sdist ships `.claude/` - all of it, including `review-findings.md` (2000+ lines of internal review notes on unreleased statistics) and `qre_checks_reference.tex`, plus `settings.json`, the hooks and the agent definitions. Verified against the built `dist/quebra-0.1.0.dev0.tar.gz`. `spec/ledger/*.jsonl` was correctly excluded; `.claude/` was not considered. | Add `.claude/` to `[tool.hatch.build.targets.sdist] exclude`.

IMPORTANT | .github/workflows/ci.yml | CI does not run `scripts/acceptance.sh`, does not run `python -m build`, and installs from the source tree with the repository present. The single claim this phase exists to make - a wheel installs and works with no checkout - is therefore verified only by a script a human has to remember to run. R1.4 acceptance lists the two as separate criteria so this is not a spec violation, but "CI is green" will not catch a packaging regression. | Add one step running `bash scripts/acceptance.sh`, or say in the banner that CI does not cover packaging.

MINOR | scripts/acceptance.sh:37 | `WHEEL="$(ls -t "${REPO}"/dist/*.whl | head -1)"` picks the newest wheel in a directory that ACCUMULATES. If the build step fails, the script keeps going and installs a stale wheel from a previous run; every later step then passes and only `STATUS=1` from the failed build makes the overall exit nonzero. The steps after a failed build prove nothing about the current tree while printing "exit 0". | `rm -rf "${REPO}/dist"` before building, or exit immediately when the build step fails.

MINOR | scripts/acceptance.sh:44-46 | The venv is created but never removed, and neither is the `mktemp -d` parent. Each run leaks a full venv (numpy, scipy, matplotlib, plotly) into `/tmp`. | `trap 'rm -rf "$(dirname "${VENV}")"' EXIT`.

MINOR | scripts/acceptance.sh:15 | `set -u` without `set -o pipefail`. The one pipeline (`ls -t ... | head -1`) is guarded by the emptiness check at :38, so nothing is masked today. | Note only.

MINOR | .github/workflows/ci.yml:6-8 | No `concurrency` group and no `permissions:` block. Every push to every branch starts a full 2-interpreter matrix, and the job runs with the default (write) token. | `permissions: contents: read` and a concurrency group.

### docs/WRITING_A_JOB.md + README.md

VERIFIED PASS | docs/WRITING_A_JOB.md:13-40 | The example job is real, not illustrative. Wrote it verbatim to a scratch directory outside the repo and ran `quebra inspect my_first_job.py`: exit 0, two nodes printed. Every API it names exists with the signature shown - `Dataset(path, schema, qubit, device)` (core/dataset.py:9-15), `Job("name")` positional (core/job.py:279), `track912Schema` (schemas/track912.py:9), `t2star.run` / `t2star.make_inputs_from_norm` (analyzers/t2star.py:46,72), `job.load` / `job.step` / `job.materialize` / `job.figure` / `job.include(..., alias=)` / `.ref`. The run-directory format at :87 matches `runner.py:428` exactly (`<job>_<identity6>_<timestamp>`). The data-root order at :63-69 matches `resolve_data_root`. 124 lines, single-purpose: not doc bloat.

IMPORTANT | docs/WRITING_A_JOB.md:8 | "`pip install quebra`, put a `.py` file anywhere, and run it by path." Measured: `pip index versions quebra` -> "No matching distribution found"; `https://pypi.org/pypi/quebra/json` -> 404. The distribution is unpublished (`version = "0.1.0.dev0"`, and SPEC 0001 R0.5.4 forbids tagging). The first instruction in the new doc is a command that cannot succeed, and it is the one a JOSS reviewer would try first. | "`pip install .` from a checkout, or `pip install <wheel>`" until the name is claimed on PyPI.

IMPORTANT | README.md:105-106 vs scripts/acceptance.sh:35-58 | R1.4.4's acceptance is that the README install commands and the script "agree line for line", and README:107-109 asserts flatly "Nothing is documented here that the script does not do". They differ on four points: (a) the script builds a wheel with `python -m build` and installs THAT, the README says `pip install .`; (b) the script runs `pip install pytest` as its own step, the README omits it; (c) the script runs `pytest -m "not slow and not heavy and not real and not r" -q tests/`, the README says `pytest tests/`; (d) the script's venv is outside the repo, the README's `.venv` is inside it. (b) is the one that bites: after a plain `pip install .` pytest is NOT installed (it lives only in the `dev` extra), so a reviewer following the README literally gets "command not found" on the next line. | Add `pip install pytest` (or `pip install ".[dev]"`) to the README block, and soften the "line for line" claim to what is actually shared.

IMPORTANT | README.md:97-98 | The clone command changed from `https://github.com/seraconti/quebra.git` to `git@github.com:seraconti/qretool.git`. The SSH form requires a key registered with GitHub; a reviewer on a machine that has never seen this repository - the governing constraint of the whole spec - cannot run it. The repository-name mismatch (quebra vs qretool) was already logged in the Phase 0 section; this change fixes the name and breaks the protocol. | `git clone https://github.com/seraconti/qretool.git`.

MINOR | README.md:87-91 | The "Feedback is welcome, particularly from anyone who runs long characterization campaigns..." sentence appears twice: once inside the Status paragraph at :87 and again as its own paragraph at :89-91. Pre-existing (untouched by this diff), but the README is in R1.4.4's scope and this is in the section a reviewer reads. | Delete one.

MINOR | README.md:141-142 | The Documentation section lists "time and clock semantics, the panel contract, and the figure standard" and does not mention `docs/WRITING_A_JOB.md`, the doc this phase added and the only entry point for someone writing their own job. | Add it.

MINOR | docs/WRITING_A_JOB.md:31 | The showcase example wires its step as a `lambda`, nine lines after the doc explains that "anything that changes the answer belongs in a kwarg rather than a closure" (:50-52). It works (verified), but the first job a reader writes is now a closure, and `quebra inspect` renders the node as `<lambda>` with no kwargs, which is exactly the opaque graph the doc sells inspect against. | Use a named `def`.

MINOR | docs/WRITING_A_JOB.md:24 | `path="tool/datasets/6D2S/070423_6D2S_qubit1.pickle"` hard-codes this researcher's private tree into the generic getting-started doc, and SPEC 0003 replaces `tool/datasets/` with the three-way `data/` split. A reader without those files gets a FileNotFoundError from step one. | Use an obviously-placeholder path, e.g. `my_device/run_001.pickle`.

### conftest.py + tests/ deltas

VERIFIED PASS | baselines | Reproduced all of them. `pytest -q` -> **337 passed, 2 skipped**. `pytest --collect-only -q | tail -1` -> **339 collected**; 339 - 7 (the new `tests/test_data_root_resolution.py`) = **332**, the P2 baseline, so D6(b)'s collect-count condition holds. `ruff check .` -> exactly 1 finding, the pre-existing F841 at `src/quebra/plots/interpolation_stage_plot.py:63`. `bash scripts/acceptance.sh` -> exit 0, seven steps, all 0. `mypy src/quebra/core` -> 11 errors in 2 files (out of phase). `make arch` -> SKIPPED, exit 0, correct under R1.2.6. `make deps` -> exit 0.

VERIFIED PASS | tests/test_bench_isolation.py:80-96, 105-116 | The relative-import hole logged in the Phase 0 section is genuinely FIXED, confirmed by mutation against `_imports_bench` on planted files: `from ..bench import runner`, `from .bench import runner` and `from ..bench.carve import carve_windows` all now return True, while `from quebra.recipes import ...` and `import jobs` return False. `node.level` is recorded and matched.

IMPORTANT | tests/test_bench_isolation.py:76-79 | The SAME class of hole remains one line away: for a non-relative `ImportFrom` only `node.module` is recorded, never `module + "." + alias`. Measured: `from jobs import bench` yields `{'jobs'}` and `_imports_bench` returns **False**. That is an ordinary, working absolute import of the bench that the guard admits. AGENTS.md 4: "Fix every site of a class, not the one that failed" - the relative half was fixed and the absolute half was not. | `roots.update(f"{node.module}.{a.name}" for a in node.names)` for the `node.level == 0` branch, and add `from jobs import bench` to the control table.

IMPORTANT | tests/test_bench_isolation.py:41-50 | `PIPELINE_PACKAGES` names the seven `src/quebra/` subpackages but not the package's TOP-LEVEL modules. `cli.py` gets its own assertion at :148-149; `src/quebra/recipes.py` and `src/quebra/provenance.py` get none. `recipes.py` is the file this phase moved INTO the distributed package, so it is precisely the new module that must not depend on the study, and it is now the one that is unscanned. | Replace the seven entries with `"src/quebra"`; rglob covers all of them and the top-level modules too.

IMPORTANT | tests/test_artifact_guard.py:277-290 | The ModuleNotFoundError assertion was WIDENED from `"non_repairable" in exc or "repairable" in exc` to a five-token any() including the bare strings `"panels"`, `"analyzers"` and `"core"`. D6(b) says no assertion may change; this one did, and in the direction that weakens it. Concretely: if the wheel ever fails to ship `quebra/panels/`, unpickling raises `No module named 'quebra.panels'`, the token `"panels"` matches, and the test passes - the packaging break that this whole phase exists to prevent is now indistinguishable from the accepted rename loss. The comment two lines above claims the opposite ("this clause cannot swallow an unrelated packaging break"). | Match on the REMOVED module names only: `panels.non_repairable`, `panels.repairable`, or a bare `panels.`/`analyzers.`/`core.` prefix that cannot appear under `quebra.`.

MINOR | tests/test_bench_isolation.py:180-208 | The positive control still asserts `expected in _imported_roots(...)` rather than `_imports_bench(...)`, so it certifies the collector, not the predicate. This was already logged in the Phase 0 section and carried forward unchanged. It is why the `from jobs import bench` miss above is invisible: the control would happily accept `"jobs"`. | Assert `_imports_bench(planted)` as well.

MINOR | tests/test_path_resolution.py:62-66 | `test_resolve_repo_path_is_cwd_independent` is now a TAUTOLOGY. `resolve_repo_path(p)` is `(repo_root()/p).resolve()` and the assertion's right-hand side is `repo_root()/"jobs"/"active"`; both sides read the same cwd-derived value, so it holds for every cwd including the `tmp_path` it chdirs to. Under the old `__file__` implementation it was a real assertion. The name and the change it was written to guard are now opposites of the shipped behaviour. | Rename to what it checks, or pin against an absolute path captured before the chdir.

MINOR | tests/test_path_resolution.py:31-39, tests/test_data_root_resolution.py:110-116 | Three tests now depend on the process cwd being inside this checkout: `repo_root()` must find a marker, and `default_dataset_root()` must resolve through the repo's `quebra.toml`. Run the suite from anywhere else and they fail with `DataRootNotFound`. `scripts/acceptance.sh:57` avoids this only because it passes `env -C "${REPO}"`, which is also what stops the "clean environment" step from being as clean as its comment claims. | Note the cwd requirement in the module docstring so a future runner does not chase it.

MINOR | tests/test_data_root_resolution.py:63,78 | Raw `os.chdir(deep)` inside two tests instead of `monkeypatch.chdir`. Safe today only because the `isolated` fixture already called `monkeypatch.chdir`, whose undo restores the pre-test cwd; drop the fixture from either test and the suite leaks a cwd into every test that follows. | Use `monkeypatch.chdir`.

MINOR | conftest.py | Docstring-only, no code, which is the whole trick (pytest's prepend import mode puts the rootdir on `sys.path`). It works - verified, `jobs.*` and `tests.fixtures` both import - but the mechanism is entirely implicit and one `--import-mode=importlib` away from silently breaking. | Consider `sys.path` being explicit here instead; R1.1.4 scopes its ban to `src/` and `tests/`, and this file is neither.

### src/quebra/recipes.py + __init__.py files + jobs/ import rewrites

VERIFIED PASS | R1.1.1 / R1.1.2 / R1.1.3 | `git status --porcelain` = 136 entries: 71 `R`/`RM` renames, 0 `A`, 1 unstaged `D` (pytest.ini). No file appears as add-plus-delete. All 9 directories under `src/quebra/` carry an `__init__.py` (9 of 9, matching the acceptance criterion), plus `jobs/`, `jobs/active/`, `jobs/composite/`, `jobs/bench/`. Every module under `quebra.` imports cleanly (`pkgutil.walk_packages` over all 76: zero failures), and every file in `jobs/active/`, `jobs/composite/` and `jobs/bench/` imports cleanly.

VERIFIED PASS | jobs/bench/instrument_report.py, jobs/bench/xi_ties.py | The two `sys.path.insert(0, ...parents[2])` lines were REMOVED, not preserved, as R1.1.4 demands. Both documented invocations still work after the removal: `python jobs/bench/instrument_report.py` regenerates `jobs/bench/results/instrument_report.md` byte-identically (checked - `git status` on that path stays empty), and `python jobs/bench/xi_ties.py` starts its Monte Carlo. Zero un-rewritten imports anywhere: `grep` for a top-level `from|import (analyzers|core|panels|plots|loaders|schemas|transforms|provenance)` over every `.py` in the tree returns nothing.

IMPORTANT | src/quebra/provenance.py:23, :46 | `get_git_commit` and `is_tree_clean` still anchor on `Path(__file__).resolve().parent`. Before this phase that was the repository root; now it is `<...>/site-packages/quebra/`. So the two roots in one run disagree by construction: `paths.repo_root()` follows the caller's cwd while provenance asks git about wherever the LIBRARY is installed. Installed from a wheel this yields `"nogit"` and `is_tree_clean() == False` (reuse permanently disabled, silently); installed editable inside some other checkout it records THAT repository's commit into `.prov.json`. Provenance is a hard rule in AGENTS.md 1 and this is the one field a reader uses to reproduce a figure. | Anchor both on `paths.repo_root()`, and record explicitly when no repository was found rather than the string "nogit".

MINOR | src/quebra/recipes.py:55-77 | `run_start_unix_s_from_hdf5` opens an HDF5 file. It is called at job-build time rather than inside a step, so it does not violate "a step never reads disk" - but this phase moved the function INTO the distributed package on the grounds that it is reusable library code, and AGENTS.md 3 puts disk access in `loaders/`. The package now has a second I/O site outside the loader registry. | Either move it behind the loader registry or say in the docstring why it is exempt.

MINOR | src/quebra/analyzers/reliability_band.py:111, distinguish_band.py:143, check_ledger.py:133 | Three user-facing error messages instruct the reader to "construct via `analyzers.reliability_band.run()`" (and siblings). Those dotted paths no longer import after R1.1.1; the working form is `quebra.analyzers.*`. An actionable error message that gives an unimportable path is worse than none. About a dozen more docstring references carry the old prefix, but these three are the ones a user is told to type. | Prefix the three with `quebra.`.

MINOR | tests/test_checks_cvm.py:163, jobs/bench/probe_unresolved.py:20 | Two more run instructions that do not run: `python jobs/bench/runner.py` fails with `ModuleNotFoundError: No module named 'jobs'` (its `from jobs.bench.arms import ...` needs the repo root on the path; `python -m jobs.bench.runner` works), and probe_unresolved's usage line still says `PYTHONPATH=. python bench/probe_unresolved.py` from before the bench moved under `jobs/`. Both pre-date this phase, but both files are in this change set. | `python -m jobs.bench.runner`, `python jobs/bench/probe_unresolved.py`.

MINOR | the index vs the working tree | 48 files are `RM`: staged as renames, with the import rewrite left UNSTAGED. The staged tree alone does not import - `git show :src/quebra/recipes.py` still says `import analyzers.fidelity`. `pytest.ini`'s deletion is also unstaged (` D`), and `quebra.toml`, `conftest.py`, `pyproject.toml`, `.github/`, `scripts/`, `docs/WRITING_A_JOB.md`, `tests/test_data_root_resolution.py` and six `__init__.py` files are untracked. A `git commit` without `git add -A` produces a broken commit. | `git add -A` before committing; the phase is one commit, not two.

### baselines reproduction and the Done-when clause

CRITICAL | SPEC 0002 "Done when" vs scripts/acceptance.sh:57 | **The fast test suite does NOT pass from an unrelated working directory.** The Done-when clause is: "`pip install .` succeeds in a fresh virtualenv outside the repository, `import quebra` works from an unrelated working directory, the fast test suite passes THERE, and CI is green." Measured, using the very venv the acceptance script built:

```
cd /tmp && <venv>/bin/python -m pytest -q -m "not slow and not heavy and not real and not r" <repo>/tests
6 failed, 331 passed, 2 skipped
```

The six: `test_data_root_resolution.py::test_the_repository_resolves_through_its_own_quebra_toml`, `test_path_resolution.py::test_repo_root_is_the_tool_repo`, `::test_default_dataset_root_is_repo_parent`, `test_paths_dataset_fallback.py::test_a_tracked_in_repo_table_resolves`, `::test_without_the_fallback_that_path_would_not_exist`, `::test_an_absolute_path_is_still_existence_checked`. All six die on `DataRootNotFound` or a missing marker, because `repo_root()` and `resolve_data_root()` now both read `Path.cwd()`.

`scripts/acceptance.sh:57` runs that step with `env -C "${REPO}"`, so the one cwd under which these six pass is the one the script chooses. The script's own header claims it "is the only thing that can falsify" the installability claim; on this point it does the opposite. This is not a packaging bug - the wheel is correct - it is the phase's headline claim being checked under the single condition that makes it true. | Either fix the six tests to be cwd-independent (capture an anchor from `Path(__file__)` in the TEST, which is legitimate there), or amend Done-when to say the suite runs from the checkout because `tests/` is not shipped. Do not leave the current wording and the current script together.

VERIFIED PASS | baselines | `pytest -q` -> 337 passed, 2 skipped. `pytest --collect-only -q | tail -1` -> 339; minus the 7 new tests in `tests/test_data_root_resolution.py` = 332, the P2 baseline, so D6(b) holds on the count. `ruff check .` -> 1 pre-existing F841. `bash scripts/acceptance.sh` -> exit 0, seven steps. `mypy src/quebra/core` -> 11 errors. `lint-imports` -> skipped, no contract. `make deps` -> exit 0. Wheel: 82 members, `quebra/` + dist-info only.

VERIFIED PASS | src/quebra/core/paths.py:31 | "the four jobs that declare `jobs/bench/results/*.csv` as a Dataset" - exactly four: `jobs/active/check_calibration.py`, `jobs/active/instrument_validation.py`, `jobs/composite/check_ledger_q1.py`, `jobs/composite/independence_survey.py`. Accurate.

VERIFIED PASS | tests/test_artifact_guard.py:246-250 | "77 pickles under `output/` and `output_backup*/` are affected, plus 5 naming `panels.repairable`" - measured over all 1012 pickles in the three output trees: exactly 77 contain `panels.non_repairable` and exactly 5 contain `panels.repairable` without it. Accurate. (0 contain `quebra.panels`, which confirms the `ValueError` branch of that test is still unreachable - already logged in the Phase 0 section.)

VERIFIED PASS | .github/workflows/ci.yml:16-18 | The 3.11 claim checks out: `ast.parse(..., feature_version=(3,11))` over every `.py` in `src/`, `jobs/` and `tests/` reports zero syntax failures, so the nested f-string it cites is genuinely gone and the 3.11 matrix leg will not die on import.

MINOR | pyproject.toml:84-85 | "Measured on this tree, `select = ["E","F","I","UP","B"]` reports 1193 findings, 1116 of them line-too-long." Measured now: **1212 findings, 1138 E501**. The numbers were taken before the phase finished adding files. AGENTS.md 4 names this exact defect class ("a measured number in a docstring must come from the artifact it cites, in the state it ships"). The argument is unaffected; the numbers are wrong. | 1212 / 1138, or drop the counts and keep the reasoning.

MINOR | AGENTS.md:213 | "`monoliths/`, `scripts/` and `jobs_old/` were deleted and no longer exist." This phase CREATED `scripts/`, and `scripts/acceptance.sh` is R1.4.1's deliverable. Same half-applied-edit class as the `main.py` lines. The layout section also never gained `pyproject.toml`, `quebra.toml`, `conftest.py`, `scripts/` or `.github/`. | Drop `scripts/` from that sentence and add the five new root files to the layout.

---

## db61799 slice review - generic loading path / schema dispatch

SCOPE: src/quebra/core/job.py (_load_dataset + _load_dataframe_raw only), src/quebra/core/dataset.py, src/quebra/schemas/ramsey_series.py, src/quebra/schemas/null.py, tests/test_load_dataset_contract.py, docs/WRITING_A_SCHEMA.md
COMMIT: db61799 (reviewed at HEAD b14bbc7)

NOTE: a second reviewer was appending to this ledger concurrently, so this slice's
entries sit at the file tail interleaved with theirs rather than under the heading
below. Every entry of mine names one of the six scoped paths above; grep those.
STATUS: complete, all six files reviewed.

### Manifest
(empty - all reviewed)

### Reviewed

### Findings

---

## b14bbc7 slice review - DataUnavailable / packaged fixtures / data manifest

SCOPE: src/quebra/core/paths.py (new parts only: DataUnavailable, _is_manifested,
_MANIFEST_RELATIVE, hoisted tomllib, changed raise in resolve_dataset_path),
src/quebra/_fixtures/__init__.py, scripts/make_fixtures.py, scripts/make_data_manifest.py,
tests/test_data_unavailable.py, tests/test_packaged_fixtures.py, tests/test_data_manifest.py
COMMIT: b14bbc7

### Manifest
(reviewed) src/quebra/core/paths.py
(reviewed) src/quebra/_fixtures/__init__.py
(reviewed) scripts/make_fixtures.py
(reviewed) scripts/make_data_manifest.py
(reviewed) tests/test_data_unavailable.py
(reviewed) tests/test_packaged_fixtures.py
(reviewed) tests/test_data_manifest.py

### Reviewed

### Findings

IMPORTANT | src/quebra/core/paths.py:86 | `text.endswith(str(record.get("path","\0")))` is a raw STRING suffix match, so it matches across a path component boundary. Measured: with record `path = "6D2S/x.pickle"`, `_is_manifested` returns True for `data/other/evil_6D2S/x.pickle` AND for `/tmp/zzz6D2S/x.pickle`. Both are wrong paths that the new message will call "an EMBARGOED record rather than a wrong path" - the exact inversion the class exists to prevent. | Anchor on a separator: `text == p or text.endswith("/" + p)`.

IMPORTANT | src/quebra/core/paths.py:79-86 | The docstring promises the manifest read "must degrade to 'not manifested' rather than replace a missing-dataset message with a manifest-parsing one", but `except (OSError, tomllib.TOMLDecodeError)` does not cover the shapes that actually occur. Measured, all RAISING out of the error path: `[record]` written as a table instead of `[[record]]` (a one-bracket typo) -> AttributeError 'str' has no attribute 'get'; `record = "hello"` or `record = [1,2]` -> AttributeError; a manifest containing a non-ASCII filename read under `LC_ALL=C` -> UnicodeDecodeError (a ValueError, not OSError). Any of these replaces the useful FileNotFoundError with a traceback from the diagnostic helper. | `records = ...` then `if not isinstance(records, list): return False`, keep only `isinstance(r, dict) and isinstance(r.get("path"), str)`, and read with `manifest.read_bytes()` + `tomllib.loads(... .decode("utf-8"))` or `tomllib.load(open(...,"rb"))`.

MINOR | src/quebra/core/paths.py:86 | The `"\0"` sentinel does work (no POSIX path can contain NUL, so a record with no `path` never matches) but it is load-bearing obscurity, and `str()` around it silently accepts a non-string `path`: measured, `path = 5` makes `_is_manifested(Path("foo5"))` return True. | Drop the sentinel in favour of the isinstance filter above.

MINOR | src/quebra/core/paths.py:127-171 | `DataUnavailable.__init__` takes four required positional args but calls `super().__init__(one_string)`, so `self.args == (msg,)`. OSError's `__reduce__` reconstructs as `type(self)(*self.args)`, which raises TypeError - the exception cannot be pickled or copied, and multiprocessing/joblib propagation would surface a TypeError instead of the real error. | `self.args = (raw, candidates, dataset_root, manifested)` is wrong for str(); simplest is to accept defaults for the last three params.

MINOR | src/quebra/core/paths.py:69 | `_is_manifested` reads the manifest from `repo_root()`, not from `dataset_root`, so a reviewer running with `--data-root` pointed at a private tree that carries its own MANIFEST.toml gets "not in data/real_private/MANIFEST.toml" for a record that is in one. Defensible (the manifest is committed repo metadata) but undocumented. | One sentence in the docstring saying the manifest is always the checkout's.

IMPORTANT | tests/test_packaged_fixtures.py:29-36 | `test_the_fixture_path_is_not_computed_from_the_source_tree` compares `fixture_path(name).parent` with `module.fixture_path(name).parent` - the SAME function object called twice, second call served from `_RESOLVED`. It asserts `x == x` and cannot fail for any implementation, including one written as `Path(__file__).parent / name`. The claim in its own docstring ("it must come from the imported package") is unguarded, and this is the bug class `repo_root()` was already burned by. | Assert the path is under `resources.files("quebra._fixtures")`, or that it survives with `quebra` imported from a copied install tree.

MINOR | src/quebra/_fixtures/__init__.py:3-5 | "point a `Dataset` at `fixture_path(...)` and the whole pipeline runs" is not true as shipped: `ramsey_synthetic.csv` carries no `DDMMYY_` prefix and its timestamps start at 0, so `RamseySeriesSchema.to_norm` reaches level 3 of the run-start resolution and RAISES `ValueError: Cannot determine run start time`. All four tests in tests/test_packaged_fixtures.py pass `extra={"run_start_unix_s": 1.7e9}`; the docstring does not mention it. | Add the required `extra` to the docstring recipe (renaming the fixture to a DDMMYY_ prefix would instead buy the midnight UserWarning).

MINOR | src/quebra/_fixtures/__init__.py:41-44 | The `_RESOLVED` cache returns the path unconditionally on a hit, and the temp file's lifetime is `_STACK`'s. The leak itself is fine and documented (a wheel install is a directory, so `as_file` is a no-op), but the cache has no guard if anything ever closes the stack, and two threads racing the first call each `enter_context`, leaking one extraction. | `if name not in _RESOLVED or not _RESOLVED[name].is_file():` costs one stat on the error-free path.

MINOR | scripts/make_fixtures.py:26-27, 72 | "A rerun must reproduce the committed bytes" is TRUE here - regenerated into a clean tree, the CSV is byte-identical to the committed one (numpy 2.4.4, pandas 2.3.3, `cmp` clean) - but nothing enforces it and one dependency default breaks it off-platform: `DataFrame.to_csv` defaults `lineterminator` to `os.linesep`, so the same script on Windows writes CRLF and every byte after the first line differs. | Pass `lineterminator="\n"`, and add a test that regenerates into tmp_path and compares.

MINOR | scripts/make_fixtures.py:70-71 | "`%.9g` keeps ... the round-trip exact enough for a fixture" is correctly hedged - 9 significant digits is NOT a lossless float64 round-trip (17 are needed) - but the module docstring one screen above says the script exists "so the committed files are reproducible", which reads as value-exact. Measured, the loss is immaterial: 1 Hz quantisation against a 5 kHz noise sigma, and ~1e-13 s against a 4 us sigma. | Say "byte-reproducible; values are stored to 9 significant digits" once, at the top.

GREEN | scripts/make_fixtures.py:27-31 | Seed is a written-out constant, not derived from a clock or a hash, and every physical constant carries its unit suffix (`CADENCE_S`, `QUBIT_FREQUENCY_HZ`, `T2STAR_MEAN_S`, `t_s`, `drift_hz`, `t2star_error_s`). The unsuffixed CSV column names (`timestamp`, `frequency`, `T2star`) are imposed by `RamseySeriesSchema`, not chosen here.
GREEN | pyproject.toml:72-73 + .gitignore | The fixture really does ship: hatchling's wheel target takes all of `src/quebra`, and `git check-ignore` does not match `src/quebra/_fixtures/ramsey_synthetic.csv`, so the "inside the wheel" claim holds.

IMPORTANT | src/quebra/schemas/null.py:6-8 | Docstring: "`Dataset.schema=None` runs `RamseySeriesSchema`, which ten in-repo jobs depend on; `NullSchema` has to be asked for by name." The ten is real but it counts the wrong thing. There are exactly ten `schema=None` Datasets in `jobs/` (check_calibration 2, instrument_validation 5, ramsey_q1_100423 1, check_ledger_q1 1, independence_survey 1) and exactly ten `job.load_df()` calls, 1:1 - every one of those ten is a raw-DataFrame load, and `load_df` never consults `dataset.schema`. NOT ONE in-repo `job.load()` call site passes `schema=None`: all 8 pass `track912Schema` or `CalibrationLogSchema`. So changing the default tomorrow would alter the behaviour of zero jobs, not ten. What 7 job files actually depend on is `RamseySeriesSchema` running as the FALLTHROUGH after a `validate` schema (the track912 path), which is a different guarantee and the one worth stating. | Replace with the true statement: "seven in-repo jobs reach it as the fallthrough after `track912Schema.validate`; no in-repo caller relies on `schema=None`."

IMPORTANT | src/quebra/schemas/null.py:45-47 | Duplicate column labels silently produce a 2-D array. `frame[column]` on a duplicated label returns a DataFrame, so `.to_numpy()` is 2-D, and the loop then assigns the same key twice. Measured: `pd.DataFrame([[1,2,3],[4,5,6]], columns=["a","a","b"])` -> `norm["a"]` has shape `(2, 2)`, no error, no warning. Every step downstream expects 1-D under a Norm key. The `meta` collision two lines up proves the author was thinking about key collisions; this is the same class, unguarded. | Raise on `frame.columns.duplicated().any()` alongside the `meta` check.

MINOR | src/quebra/schemas/null.py:46 | `str(column)` can map two distinct labels onto one key. Measured: `pd.DataFrame({0: [1,2], "0": [3,4]})` -> a single key `"0"` holding `[3 4]`; the integer-labelled column is gone with no error. | Fold into the duplicate-label guard: check for collisions after `str()`, not before.

MINOR | src/quebra/schemas/null.py:37-44 | The `meta` it builds is `dataset_id` plus `**dataset.extra`, in that order, so a caller's `extra={"dataset_id": ...}` silently overrides the computed value. `RamseySeriesSchema` has the opposite precedence (`dict(extra)` then `.update({...})`, computed wins). Two schemas in one package disagreeing on who wins is a trap. Also absent here: `run_name`, `qubit`, `device`, `duration_h`, `n_points` - so a NullSchema Norm cannot say which qubit it came from even though the Dataset declared one. | Match RamseySeriesSchema's precedence, and carry qubit/device/n_points into meta.

MINOR | src/quebra/schemas/null.py:1 | "Every column of the file" is not what it returns. `_load_dataset` injects `qubit_id` and `device` into the frame before dispatch, so a NullSchema Norm carries up to two keys that are not columns of the file. | "Every column of the frame handed to it, including the qubit_id/device columns job.load injects."

MINOR | src/quebra/schemas/ramsey_series.py:103 | `stacklevel=2` was correct one frame out; the move added a frame and it was not re-counted. Measured: the DDMMYY warning is now attributed to `src/quebra/core/job.py:183` - the `return RamseySeriesSchema.to_norm(...)` line inside the library - where before it pointed at `_load_dataset`'s caller. Every such warning now blames the same library line regardless of which job triggered it. | `stacklevel=3`.

VERIFIED PASS | src/quebra/schemas/ramsey_series.py:50-145 vs 9057803:core/job.py:161-258 | The move is behaviour-preserving. Textual diff of the two bodies (indentation normalised) shows ONLY black re-wrapping of two `pd.to_numeric(...)` calls plus the relocated `timestamp`/`frequency` KeyError. The `[valid][order]` index chain is intact and identical on all three passthrough columns (`normalised chi-square`, `T2star`, `T2star error`), the meta dict construction order is unchanged, and the three-level run-start resolution including the no-`t_raw[0]`-fallback comment is verbatim. Live check on a synthetic `010423_demo.csv` gives `run_start_resolution='date_only_midnight'`, `run_start_unix_s=1680307200.0`, keys `t_rel_s/delta_hz/raw_frequency_hz/meta`.

VERIFIED PASS | src/quebra/core/job.py:140-190 | Dispatch is correct and total: `to_norm` before `validate` (same precedence as before), and the third branch is a raised `TypeError` naming both required methods and the doc - no silent passthrough. `import warnings`, `import numpy as np` and `check_unix_s` were removed from job.py and nothing there still references them. No import cycle: `transforms/lookup_prior.py` imports only numpy/pandas/typing.

VERIFIED PASS | src/quebra/core/job.py:150-155 | The conditional `qubit_id`/`device` injection is a real behaviour change but not a silent one. Old: `int(dataset.qubit)` on `qubit=None` raised `int() argument must be...`, naming neither field. New: the column is simply absent, and `BaseQubitSchema` declares `qubit_id` required, so the track912 path still fails - now with a pandera SchemaError that names the column. All 8 in-repo `job.load` datasets declare both fields, so nothing in-repo changes.

VERIFIED PASS | src/quebra/core/dataset.py:12-30 + loaders/registry.py | The `loader_kwargs`/`extra` split is complete. All four registered loaders audited: `_load_csv` does `pd.read_csv(path, **meta)`, `_load_hdf` reads `meta.get("key")`, `_load_yaml` and `_load_pickle` both `del meta`. Both `_load_dataset` and `_load_dataframe_raw` now pass `dict(dataset.loader_kwargs)`; `git grep` finds no remaining site that forwards `extra` to a reader. Every in-repo `extra=` is `{"run_name": ...}` on a `.pickle`, whose loader discarded it, so the split is a no-op for existing jobs - the docstring's account of why it was a defect is accurate.

IMPORTANT | tests/test_load_dataset_contract.py:128 | Same false claim as null.py, restated in a test docstring that presents it as the reason the test exists: "it is the behaviour ten in-repo call sites rely on". Zero in-repo `job.load` call sites pass `schema=None`. The ten `schema=None` Datasets are all `load_df` inputs and never touch a schema. | Same correction as the null.py entry.

IMPORTANT | tests/test_load_dataset_contract.py (whole file) | The contract file never tests the `validate` branch, which is the one every real job takes. All 8 in-repo `job.load` sites pass `track912Schema` (validate-shaped, 6 sites) or `CalibrationLogSchema` (to_norm-shaped, 2). The file tests `to_norm`, `schema=None`, and the neither-method TypeError - but the docstring's own middle claim, "a schema with `validate` cleans a frame and then the default normaliser runs on the result", has no test here and none anywhere else (`git grep` for `track912|_load_dataset|CalibrationLogSchema` over `tests/` returns only this file and `test_reference_model.py`). Also untested: a schema carrying BOTH methods, where the code silently prefers `to_norm`. | Add a two-line fake `validate` schema that renames a column, and assert the resulting Norm has `t_rel_s` - that pins the fallthrough the 6 track912 jobs live on.

MINOR | tests/test_load_dataset_contract.py:86-94 | `test_loader_kwargs_do_reach_the_file_reader` asserts only the NEGATIVE: that omitting `sep` raises KeyError. It never asserts anything about a run that supplies `loader_kwargs`, so the name overstates it, and a `KeyError` raised for any unrelated reason would satisfy it. The positive half exists but is in a different test. | `pytest.raises(KeyError, match="day")`, or assert the frame width with `sep` supplied.

MINOR | tests/test_load_dataset_contract.py:17-19 | "checked separately on four real 6D2S records (three `Norm` shapes, 7 keys each, arrays compared elementwise)". Three distinct shapes that all have exactly 7 keys is at best odd phrasing, and the harness is not in the repo, so no reader can re-derive the claim or re-run it after the next edit to `RamseySeriesSchema`. A number nobody can check is the class of claim AGENTS.md 4 exists to stop. | Either commit the comparison as a `@pytest.mark.real` test, or drop the parenthetical and say only that it was checked out of band.

VERIFIED PASS | tests/test_load_dataset_contract.py | 11 passed locally. No `filterwarnings = error` in `[tool.pytest.ini_options]`, so the two unasserted DDMMYY UserWarnings do not fail the gate - and their pytest output independently confirms the stacklevel finding above, printing `src/quebra/core/job.py:183` as the warning site.

IMPORTANT | tests/test_data_manifest.py:89-105 | `test_a_corrupted_record_would_be_caught` is declared "a positive control on the check above", but it never touches the check above, or any project code: it hashes a literal with `hashlib` and asserts the digest changes when a byte is appended. It is a test of `hashlib.sha256`, and it would still pass if `test_every_manifest_entry_matches_the_file_on_disk` were deleted, or if its assertion were inverted. The repo's own standard is that a positive control must FAIL when the thing it guards is broken. | Build a synthetic private root + manifest under `tmp_path`, run the SAME comparison (extract it into a helper), and assert it raises when the digest is wrong.

MINOR | scripts/make_data_manifest.py:67-68 | `_quote` escapes only `\` and `"`, but TOML basic strings forbid raw control characters. Measured through `tomllib`: a filename containing a newline or `\x07` produces a manifest that FAILS to parse (`Illegal character`), and since `_is_manifested` then degrades to False, the affected record silently stops being recognised as embargoed. Non-ASCII and tab are fine. | Escape the control range (`\n` -> `\\n`, else `\\u%04X`), or use `tomli_w`.

MINOR | scripts/make_data_manifest.py:99, 111 | `str(rel)` writes the OS separator, so a manifest generated on Windows records `2x2\030723_....pickle` while `paths._is_manifested` compares against `raw.as_posix()` - no record would ever match. `MANIFEST.write_text(...)` also uses the locale encoding, and TOML is defined as UTF-8. | `rel.as_posix()` and `write_text(..., encoding="utf-8")`.

MINOR | scripts/make_data_manifest.py:90 | `generated = date.today()` makes the output non-reproducible: rerunning on any later day produces a diff even when not one record changed, which is exactly what erodes trust in a "do not hand-edit" generated file. There is also no `--check` mode, so nothing detects a manifest that has drifted from `build()`. | Drop the date (git already dates the commit), or add `--check` comparing `build()` to the committed text.

MINOR | tests/test_data_manifest.py:7-9 + :26-39 | "These tests skip rather than fail when `data/real_private/` is absent" - the skips are correct where they exist (`_records`, `_present_files`, the `checked == 0` guard, and the conditional-expression `pytest.skip` at :80-85, which does work because `skip()` raises before the assignment). But the premise is wrong for a checkout: `MANIFEST.toml` is COMMITTED inside `data/real_private/`, so the directory always exists and the guards fire only for a wheel install. Verified in a synthetic checkout carrying only MANIFEST.toml: 4 passed, 1 skipped (`no manifested file is present to verify`) - nothing fails, which is the requirement. | Restate as "skip when the RECORDS are absent"; nothing to change in the code.

MINOR | tests/test_data_manifest.py | Nothing checks `manifest.total_bytes`, nothing checks the sha256 fields are 64 hex chars (`:46` only tests truthiness), and nothing checks the committed manifest still equals `scripts/make_data_manifest.build()`. The last is the one that would catch a hand-edit of a file whose header forbids hand-editing. | Add a skip-guarded regeneration test.

MINOR | src/quebra/core/paths.py:106 + quebra.toml:16 | SPEC 0003 set `data_root = "."`, so `dataset_root == repo_root()` for every in-checkout run and `candidates` holds the same resolved path twice. Every message now reads `Tried '/…/x.pickle' or '/…/x.pickle'` (measured, verbatim). `test_the_error_names_every_location_it_tried` passes trivially on the duplicate. | Dedupe candidates while preserving order before constructing the message.

MINOR | tests/test_data_unavailable.py | The suite covers absent, unparseable, manifested and unmanifested, but not the two shapes that actually break `_is_manifested`: a `[record]` table instead of `[[record]]` (raises AttributeError) and a path that matches only as a mid-component suffix (`/elsewhere/mine2x2/030723_2x2_qubit1.pickle` is reported True against the REAL manifest). Both are one-line additions to `fake_repo`. | Add the two cases alongside the fixes to paths.py.

GREEN | src/quebra/core/paths.py:110 + tests/test_data_unavailable.py | The intended distinction works end to end on the real manifest: a job's declared `data/real_private/6D2S/070423_6D2S_qubit1.pickle` is recognised as manifested, a sibling typo is not, `DataUnavailable` is still a `FileNotFoundError`, and the embargoed branch names the fixtures as the way forward. Nothing is swallowed - the raise is unconditional and only the WORDING depends on the manifest.
GREEN | tests/test_data_manifest.py:49-77 | The two checks that matter both run and are correctly directional: an unmanifested file present on disk fails, and a manifested file present on disk must match digest AND byte count, skipping per-entry only for records that are genuinely absent.

---

# SPEC 0003 Phase 1B review

SCOPE: scripts/promote_run.py, tests/test_promote_run.py, Makefile (promote target),
tests/test_data_root_resolution.py, tests/test_path_resolution.py,
tests/test_paths_dataset_fallback.py, tests/test_windows_not_interpolated.py,
quebra.toml, .gitignore, the nine jobs/ dataset repoints
COMMIT: b14bbc7

## Reviewed
- quebra.toml, .gitignore, Makefile, jobs/ (9 files), scripts/promote_run.py,
  tests/test_promote_run.py, and the four modified tests. Manifest empty.

## Findings

IMPORTANT | scripts/promote_run.py:29 | `_quote` escapes only `\` and `"`. A --note containing a newline or any control character writes a PROMOTED.toml that is not valid TOML; measured: note="line one\nline two" produces `note = "line one\nline two"` with a raw newline and `tomllib.loads` fails with "Illegal character '\n'". The script exits 0, so the committed audit record is silently unparseable. | Escape the TOML basic-string set (\b \t \n \f \r plus \uXXXX for other control chars), or refuse a note with control characters.

IMPORTANT | scripts/promote_run.py:69-71 | Destination is `published/{job_stem}_{identity[:6]}` with `mkdir(exist_ok=True)` and `shutil.copy2` on top. Measured: two DIFFERENT runs (identities abcdef1111 and abcdef2222) of the same job write into one directory - run A's `node_0.prov.json` is OVERWRITTEN, run A's other records survive alongside run B's, and PROMOTED.toml then says identity=abcdef2222, record_count=1 while six files sit in provenance/. A committed provenance record is destroyed and the manifest misdescribes what is there, silently. | Refuse to write into an existing destination unless the manifest's identity matches exactly, or use the full identity in the directory name.

IMPORTANT | scripts/promote_run.py:67 | `records[0][1].get("identity", "")[:6] or "unknown"` raises `TypeError: 'NoneType' object is not subscriptable` when the record has `"identity": null`, which `build_prov_record` (src/quebra/provenance.py:78) produces by default and which 142 of 400 sampled records under output/ actually carry. The `or "unknown"` branch is dead for the representation that occurs. Not reachable on a clean run in this checkout today (all clean runs have an identity), but reachable via --allow-dirty. | `(records[0][1].get("identity") or "")[:6] or "unknown"`.

MINOR | .gitignore:34-36 | The new comment says the two backups "are what this repository already holds (305M, 33M and 23M)". Measured today: `output_backup/` and `output_backup2/` do not exist, and `output/` is 309M, not 305M. A measured claim in a comment that is false as shipped. | State that the backup names are kept as a guard against re-creation, and drop or refresh the sizes.

MINOR | .gitignore:22-25 | The private-data comment still reads "These two trees do not exist yet - the dataset root is currently one level ABOVE the repository" and cites SPEC 0002. This commit is precisely what made both sentences false: data/real_private/ exists and data_root is ".". | Update the comment to SPEC 0003 and the present tense.

MINOR | tests/test_data_root_resolution.py:70 | Docstring of `test_a_relative_data_root_anchors_on_the_file_that_declares_it` still says "This repository's own `quebra.toml` says `data_root = \"..\"`". It now says ".". The test body is synthetic and unaffected, but the stated motivation is false. | Update the sentence.

MINOR | tests/test_data_root_resolution.py:111-126 and tests/test_path_resolution.py:38-50 | Both rewrites are honest re-expressions, not weakenings - but with declared `data_root = "."` the assertion collapses to `resolve_data_root() == repo_root()`, so a resolver that ignored quebra.toml entirely and returned the repo root would still pass. The docstring claim "through mechanism 3 rather than `__file__`" is not what the assertion demonstrates. Mechanism 3 itself is still properly covered by the synthetic-toml tests at lines 55-77. | Also assert the resolver reacts to a CHANGED declared value (write a temp quebra.toml with a different root), or soften the docstring claim to what is asserted.

MINOR | Makefile:54 | `python scripts/promote_run.py` uses bare `python`; the `arch` target three rules above uses `python3`. On a distro without the unversioned alias (this is Fedora) `make promote` fails with "python: command not found". | Use `python3`, or a `PYTHON ?= python3` variable.

MINOR | Makefile:54 | `"$(NOTE)"` is inside double quotes, so a note containing a backtick, `$(...)` or a `"` is interpreted by the shell rather than passed through; `$(PROMOTE_FLAGS)` is unquoted and reaches the shell whole. Self-inflicted only, but the guard rails above suggest care was intended. | Single-quote the expansions, or document PROMOTE_FLAGS as trusted input.

MINOR | scripts/promote_run.py:50 | `root: Path = Path(".")` makes the published tree cwd-relative, so running the script from a subdirectory silently creates a second `published/` there. The Makefile always runs from the repo root, so this only bites direct invocation. | Default to the repo root, or refuse when `root/PUBLISHED` is not under the checkout.

GREEN | scripts/promote_run.py:73-77 | `path.with_suffix("").with_suffix(".prov.md")` traced for `node_0.prov.json`, and for node names containing dots (`filter_0.5`, `a.1.5`, `a.prov`), a trailing dot, and multi-dot stems: it yields the matching `.prov.md` in every case and can never name a file outside `provenance/*.prov.md`. Copying is restricted to the `*.prov.json` glob plus that sibling, so no artifact can travel. | none

GREEN | scripts/promote_run.py:57 | `r.get("tree_clean", False)` (missing key = dirty) is the right default and matches src/quebra/core/runner.py:147, which uses the identical expression for reuse eligibility. 198 of 400 sampled legacy records lack the key and are correctly refused. | none

GREEN | tests/test_paths_dataset_fallback.py:33-46 | `test_without_the_fallback_that_path_would_not_exist` is STRONGER than what it replaced. The old form asserted only that a file was absent from this checkout's dataset root and never called the resolver; the new form drives an empty tmp_path root and asserts the resolver returns the repo-root path. Not tautological - it fails if the fallback is removed. | none

GREEN | jobs/ (9 files, 10 path lines) | All ten repoints resolve: every path exists under data/real_private/, and all 34 filenames in independence_survey.DATASET_FILES are present under data/real_private/6D2S/. `grep -rn "tool/datasets\|FOR ZENODO" jobs/ src/` returns 0. The survey's carve parameters were untouched, so tests/test_independence_survey.py's equality with the active T2* jobs is unaffected. Stale references remain only in AGENTS.md, docs/TIME_SEMANTICS.md and docs/WRITING_A_JOB.md - outside this slice. | none

GREEN | tests/ (all five) | `pytest` on the five files: 45 passed. No test was deleted and no assertion count dropped. | none

IMPORTANT | docs/WRITING_A_SCHEMA.md:77-78 | "It is also the schema `job.load` uses when `Dataset.schema` is `None`, which is why the jobs in `jobs/active/` that load Ramsey records do not name a schema at all." The second half is flatly false and a reader will act on it. EVERY Ramsey-record job in `jobs/active/` names a schema explicitly: `ramsey_2x2_q1_030723.py:24`, `ramsey_q1_100423.py:25`, `t2star_q1_070423.py:32`, `t2star_q1_100423.py:32` and `km_poster_6d2s.py` all pass `schema=track912Schema`; `mtbf_q1.py:32` and `mtbc_q6.py:35` pass `CalibrationLogSchema`. They reach `RamseySeriesSchema` as the fallthrough AFTER `track912Schema.validate`, which is the interesting mechanism and the one the doc should show. This is the third restatement of one wrong belief (see null.py and the test docstring). | Delete the clause, or replace with: "the six track912 jobs reach it as the fallthrough after their `validate` schema returns."

MINOR | docs/WRITING_A_SCHEMA.md:14-18 | The first code block does not run: it imports `NullSchema` and then uses `Dataset`, which is never imported. Measured - `exec` of the block verbatim raises `NameError: name 'Dataset' is not defined`. It is the first thing a new user copies. | Add `from quebra.core.dataset import Dataset`.

MINOR | docs/WRITING_A_SCHEMA.md:89 | "`duration_h=None,  # optional; run length, copied into meta`" is presented as a property of `Dataset`, but only `RamseySeriesSchema` and `CalibrationLogSchema` copy it; `NullSchema` - the schema the same document tells you to start with - drops it, along with `qubit` and `device`. A reader who follows the page top to bottom loses all three without notice. | Say "copied into meta by the shipped schemas; your own `to_norm` must do it itself."

VERIFIED PASS | docs/WRITING_A_SCHEMA.md | Every other runnable or measurable claim checks out. The `ReadingsSchema` block executes as written through `_load_dataset` and yields `{'t_rel_s': ..., 'value': ..., 'meta': {'dataset_id': 'r'}}` - `dataset.path.stem` works because `__post_init__` coerces `path` to `Path`. The `Dataset(...)` field list matches the dataclass in order and defaults, all seven fields. "Longest schema in the repo": ramsey_series 144 lines vs track912 83, null 48, calibration_log 46, base 11 - true. `t2star.make_inputs_from_norm` exists at `analyzers/t2star.py:46` (and in fidelity/mtbf/windows, so "and friends" holds). `calibration_log.py` does build `CalibrationEvent` objects. `pd.read_csv(path, **loader_kwargs)` and "an HDF5 key is loader_kwargs" both match `loaders/registry.py`. "Runs in about a second": measured 1.19 s for the 11 tests. The doc is 129 lines for a new public extension point - proportionate, not a dumped essay.

---

SCOPE: SPEC 0004 Phase 2 "Boundaries" - pyproject.toml, Makefile, .github/workflows/ci.yml,
src/quebra/core/job.py, src/quebra/core/runner.py, src/quebra/core/_artifact_guard.py (untracked),
src/quebra/panels/_artifact_guard.py (deleted), 7 repointed import files, spec/specboundaries04.md (untracked)
COMMIT: 1f58d37

## Manifest
- [ ] pyproject.toml (+71/-?)
- [ ] Makefile (+/-10)
- [ ] .github/workflows/ci.yml (+/-18)
- [ ] src/quebra/core/job.py (+17)
- [ ] src/quebra/core/runner.py (+47)
- [ ] src/quebra/core/_artifact_guard.py (untracked)
- [ ] src/quebra/panels/_artifact_guard.py (deleted)
- [ ] 7 repointed import files
- [ ] spec/specboundaries04.md (untracked)

## Reviewed
- [x] pyproject.toml
- [x] Makefile
- [x] .github/workflows/ci.yml
- [x] src/quebra/core/job.py
- [x] src/quebra/core/runner.py
- [x] src/quebra/core/_artifact_guard.py
- [x] src/quebra/panels/_artifact_guard.py (deleted)
- [x] 7 repointed import files

## Findings

IMPORTANT | pyproject.toml:178-181 | The comment justifying `follow_imports = "silent"` states a measurement that does not reproduce: "At the default (normal), mypy reports errors in followed modules too - plots/base.py, loaders/registry.py, schemas/ramsey_series.py, provenance.py". Measured today with a fresh cache and `--no-incremental` on three configs (shipped, `normal`, and a minimal `[tool.mypy]` with only python_version+normal+ignore_missing_imports): `mypy src/quebra/core` reports **0 errors / 9 source files in every case**, and `-v` shows **zero `followed=True` sources**. The real mechanism scoping errors to core is mypy's DEFAULT silencing of site-packages: `quebra` is an editable install (`_editable_impl_quebra.pth`) with no `py.typed`, so followed `quebra.*` modules are silenced regardless of `follow_imports`. Proof: adding `--no-silence-site-packages` turns the same run into "Found 628 errors in 36 files". So `follow_imports = "silent"` is a no-op for the shipped gate, and it is a global setting that will suppress real errors the moment `py.typed` is added or the scope widens. | Correct the comment to the measured behaviour, or drop `follow_imports` and state that site-packages silencing is what scopes the gate.

IMPORTANT | src/quebra/core/job.py:252-256 | The new comment says "a load node carrying a non-Dataset here would be a real defect worth failing on" - but the code `if not isinstance(ds, Dataset): continue` SKIPS it, silently omitting that dataset's content hash from `build_identity`'s `data` tuple. Before the change a non-Dataset reached `ds.path` and raised AttributeError. runner.py's `_dataset_of` (same condition, same phase) correctly RAISES. Comment contradicts code, and the direction is loud->silent in the identity computation. | Raise (reuse `_dataset_of`-style TypeError), or change the comment to say it is skipped.

MINOR | src/quebra/core/runner.py:44 | `_dataset_of(node: object)` uses `getattr(node, "kwargs", {})` - a silent `{}` fallback for a node with no `kwargs` - when `_DAGNode` is already imported in this module and the two call sites both pass a `_DAGNode`. | Type the parameter `_DAGNode` and use `node.kwargs.get("dataset")`.

MINOR | src/quebra/core/runner.py:216-221 | The comment says "they are always populated (run_job sets all three)" but FOUR fields are read here; `job_out_dir` is deliberately left un-`_require`d. If it were None the `job_out_dir not in d.parents` self-read guard silently disables (None is a legal `in` operand) - the one case where a None would produce a wrong reuse rather than a crash, and it is the one not guarded. | `_require` `job_out_dir` too, or say in the comment why it alone is exempt.

MINOR | pyproject.toml:189-190 | `[tool.deptry]`'s comment still opens "Scope the scan to the distributed package." With `deptry .` in the Makefile the scan is now repo-wide (107 files, was `src/quebra`); `known_first_party` declares first-party-ness, it does not scope. | Reword to "declare `quebra` first-party; the scan is repo-wide".

MINOR | pyproject.toml:129-133 | The layer comment says `cli`, `recipes` and `provenance` "are listed explicitly. Omitted, they sit outside every layer and are unconstrained in both directions" - but `quebra._fixtures` is a fourth top-level module and IS omitted, so it is unconstrained in exactly the way the comment warns against. (Harmless today: it imports nothing from quebra.) | Add `quebra._fixtures` at the bottom of `layers`, or say why it is exempt.

MINOR | .github/workflows/ci.yml:38-39 | "The `real` marker is what keeps those tests out; CI never sees the tree they need." Measured: `grep @pytest.mark` over tests/ yields only `parametrize` - ZERO tests carry `real`, `slow`, `heavy` or `r`, so `FAST` excludes nothing and the marker keeps nothing out. What actually keeps CI green without the private tree is per-test `pytest.skip` in `tests/test_data_manifest.py` (4 sites) and `tests/test_artifact_guard.py:305`. The claim is inherited from the deleted step, but it is now the sole stated safety argument for a step that runs the WHOLE suite. | Say that the guard is the per-test `pytest.skip` on an absent `data/real_private/`, and that the markers are currently unused.

VERIFIED | pyproject.toml [tool.importlinter] | `lint-imports` exits 0 (79 files, 159 deps, 1 contract kept). Exactly 10 `ignore_imports`. Ratchet is load-bearing both ways, measured on copies via `--config` (pyproject.toml left untouched, `git diff --stat` still 70 insertions): deleting `quebra.core.job -> quebra.loaders.registry` gives "Layered architecture BROKEN ... quebra.core.job -> quebra.loaders.registry (l.20)"; adding a fabricated `quebra.core.job -> quebra.loaders.fabricated` exits 1 with "No matches for ignored import". `unmatched_ignore_imports_alerting = "error"` is stated explicitly as claimed. All 10 entries match real imports (implied by the unmatched=error pass).

VERIFIED | src/quebra/core/job.py TYPE_CHECKING | `import quebra.core.job` loads no matplotlib/plotly/pylab module (measured over `sys.modules`). `_FigureSink` is still a dataclass with fields `plot_class, input, targets, name`; nothing calls `typing.get_type_hints` on it (`grep get_type_hints src/` is empty), so the string annotation `type[BasePlot]` is never resolved at runtime. `@dataclass(slots=True)` is unaffected - slots are built from `__annotations__` keys, not resolved types.

VERIFIED | src/quebra/core/runner.py `_require`/`_dataset_of` | Not a converted working path. `ResolutionContext(` is constructed at exactly ONE site repo-wide (runner.py:480, `grep` over src/ jobs/ tests/ scripts/), and it sets `subjobs_dir`, `job_out_dir`, `pool_root` and `dataset_root` unconditionally; `dataset_root = Path(data_root).resolve() if data_root else default_dataset_root()` can never be None. Both `load()` and `load_df()` always put a `Dataset` in `kwargs["dataset"]`. The `kwargs["dataset"]` -> `_dataset_of(node)` substitution at line 503 is equivalent: `kwargs` is still `node.kwargs` at that point.

VERIFIED | src/quebra/core/_artifact_guard.py | Move is byte-identical apart from the TYPE_CHECKING import and the cast. `from _typeshed import DataclassInstance` is under `if TYPE_CHECKING` and the cast target is a STRING literal, so nothing resolves at runtime. The cast is honest: all 10 concrete subclasses (SizeVsN, PowerVsDependence, ValidationCurve, ReadDependence, CheckLedger, SignalBand, ReliabilityBand, DistinguishBand, WithinCalibrationPanelData, AcrossCalibrationPanelData) are `dataclasses.is_dataclass() == True` and non-slots. No stale reference to `quebra.panels._artifact_guard` anywhere in src/, jobs/, tests/, docs/, AGENTS.md or spec/. 666 `.pkl` files under `output/`: 0 contain the string `_artifact_guard`, so the guard is never named in stored state (pickle records the concrete class's module).

VERIFIED | Makefile | `PKGROOT` has no remaining reference in the repo (only two prose mentions in spec/specboundaries04.md). `deptry .` exits 0, "Scanning 107 files... Success!".

VERIFIED | test suite | `pytest -m "not slow and not heavy and not real and not r"` = 378 passed, 2 skipped in 25s. The 4 tests that would flip without `data/real_private/` are all `pytest.skip` sites in `tests/test_data_manifest.py`, none ERROR: 378/2 -> 374/6 is arithmetically the reported figure. `testpaths = ["tests"]` so the pathless `pytest $(FAST)` in `make test` collects the same set the old CI line did.


--- SECOND PASS (fix layer + spec/specboundaries04.md), appended 2026-08-30 ---

## Reviewed (second pass)
- [x] spec/specboundaries04.md (untracked, 324 lines) - NEVER REVIEWED before this pass
- [x] pyproject.toml (fix layer: follow_imports dropped, deptry comment, _fixtures layer)
- [x] src/quebra/core/job.py (fix layer: isinstance -> raise)
- [x] src/quebra/core/runner.py (fix layer: _dataset_of typed, job_out_dir _require)
- [x] .github/workflows/ci.yml (fix layer: real-marker comment rewritten)

## Findings (second pass)

IMPORTANT | Makefile:22 (`arch:` -> `lint-imports`) | `.import_linter_cache/` can serve a STALE dependency graph across exactly the kind of file move R4.2.1 performed, and `make arch` reads it. Reproduced: `lint-imports --config <copy>` reports "Analyzed 80 files, 160 dependencies" and five violations naming `quebra.analyzers.* -> quebra.panels._artifact_guard` - a module deleted in this diff, at pre-move line numbers - while `--no-cache` on the identical config reports "79 files, 161 dependencies" and none of them. The stale entry (`.import_linter_cache/fa73d0*.data.json`, mtime 2026-08-30 00:32) is NEWER than the sources it misdescribes (`analyzers/reliability_band.py`, mtime 2026-08-29 15:31), so it survived both the edits and a rewrite; repeat cached runs keep returning it. The shipped contract is currently correct (79/159/KEPT with AND without the cache) and CI is unaffected (fresh checkout, and grimp self-ignores the dir via its own `.gitignore`), so this is a local-gate reliability defect, not a wrong result today. But the phase's whole claim is that direction is a build failure, and a build failure computed from a graph containing a deleted module is not one. | `arch: lint-imports --no-cache`, or add `rm -rf .import_linter_cache` to `make clean`.

MINOR | pyproject.toml:167 | Measured number in a shipped comment is wrong: "a mixin appearing in zero of 400 archived .pkl files". There are 666 `.pkl` files under `output/`, which is the figure `spec/specboundaries04.md` R4.2.1 uses. Zero is right (`find output -name '*.pkl' -print0 | xargs -0 grep -l _artifact_guard` = 0 of 666); 400 is not. Note `grep -rl --include='*.pkl' output` silently returns nothing here - it also reports 0 for `panels`, which 151 files do contain - so anyone re-measuring must use find|xargs. | s/400/666/.

MINOR | .github/workflows/ci.yml:44-47 | The rewritten comment fixes the marker claim but misattributes one of its two guards. `tests/test_artifact_guard.py:305` does NOT skip on an absent `data/real_private/`; it globs `output/*/subjobs_output/*/t2star_panel_data.pkl` and skips "no pre-split artifact present on this machine" - an absent `output/`, which is gitignored and therefore always absent in CI. The four `data/real_private/` skips are all in `tests/test_data_manifest.py`. Relatedly, "378 passed / 2 skipped becomes 374 passed / 6 skipped" is the local rename experiment, not what CI will print: a fresh runner also has no `output/` (one more skip) and no Rscript, which makes `tests/test_checks_c3_bridge.py:63` RUN rather than skip (it skips locally *because* Rscript is present). | Say `test_data_manifest.py` guards the private tree and `test_artifact_guard.py` guards an absent `output/`; label 374/6 as the local measurement, not the expected CI line.

MINOR | spec/specboundaries04.md:125 | "The move is a file move plus import-line edits in ten modules." Measured: seven modules carry the import (`analyzers/{calibration_summary,check_ledger,distinguish_band,reliability_band,signal_band}.py`, `panels/{_within_calibration_data,across_calibration}.py`), which is also what the first-pass reviewer scoped as "7 repointed import files". Nine files change in total if you count the added and deleted module. | s/ten modules/seven modules/.

MINOR | spec/specboundaries04.md:216-219 (R4.3.4) | The `.prov.json` re-run comparison is called "the only thing protecting the phase's behaviour-neutrality claim", yet R4.3 is marked **DONE 2026-08-29** and neither the requirement, the Acceptance block nor the Review outcome records that it was performed. Every other load-bearing claim in this document carries "MEASURED", "Verified before writing this requirement" or a re-measurable command. Behaviour neutrality does hold by inspection (`kwargs["dataset"]` -> `_dataset_of(node)` is value-identical, and `_require` only narrows a field that is unconditionally set), but the doc's own acceptance criterion is unrecorded. | Record the comparison, or downgrade R4.3.4 to "argued by inspection" and say so.

MINOR | spec/specboundaries04.md:275 | "The reviewer covered 8 of 9 scoped files before its session ended; the ninth was this spec, checked separately." Written by the document's own author before any independent check of it existed. As of this pass the statement is true; when committed it was an assertion about a review that had not happened. | Attribute the check ("second review pass, 2026-08-30") rather than asserting it in the passive.

MINOR | spec/specboundaries04.md:106, 185, 217 | Line citations are anchored to three different revisions. `job.py:35`/`job.py:385` and `runner.py:65`/`runner.py:365` are correct at `1f58d37`; `job.py:249` is correct in the CURRENT file; `job.py:254 narrows by isinstance` is now `job.py:261` (the fix layer inserted a 7-line comment) and `runner.py:362-366` is now `_emit_prov`'s signature, not the `fn.__name__` test. | State the revision each citation is against, or cite symbols instead of lines.

VERIFIED | spec/specboundaries04.md R4.0 "16 illegal imports in 6 rule violations" + the per-pair table | Reconstructed from `1f58d37` source, not from the tool: analyzers->panels 10 (5 `_artifact_guard` in calibration_summary/check_ledger/distinguish_band/reliability_band/signal_band, 4 `_within_calibration_compute` in fidelity/reliability_band/signal_band/t2star, 1 `within_calibration` in t2star), analyzers->plots 1 (fidelity->plots.theme), core->plots 2 (job->plots.base, runner->plots.targets), core->loaders 1, core->schemas 1, schemas->transforms 1. Sum 16 across 6 ordered pairs, and 16 - 1 (R4.1.4) - 5 (R4.2.1) = the 10 frozen entries. Table is exact.

VERIFIED | spec/specboundaries04.md:96 "813 modules against 648" | Exact, both figures. `python -c "import sys, quebra.core.job; print(len(sys.modules))"` = 648 with `matplotlib`/`plotly` both absent; adding `quebra.plots.base` = 813 with both present.

VERIFIED | spec/specboundaries04.md:123 "all 666 archived .pkl files, zero contain the string _artifact_guard" | 666 `.pkl` under `output/`; 0 match `_artifact_guard` (find|xargs, since `grep -r --include` is unreliable on this tree). Corroborated by what the archive DOES contain: 151 files name a `panels.*` module, and the recorded module paths are pre-src-layout (`analyzers.fidelity`, `panels.non_repairable`), so pickle really does record the concrete class's module and never the mixin.

VERIFIED | spec/specboundaries04.md:49-53 "242 errors in 51 files" at 1f58d37 vs "208 errors in 41 files" now | BOTH figures re-measured without checking out the old commit: `git archive HEAD src/quebra | tar -x -C <scratch>` then `mypy --config-file <bare> <scratch>/src/quebra` gives exactly "Found 242 errors in 51 files (checked 79 source files)"; `mypy src/quebra` on the working tree gives exactly "208 errors in 41 files". Presenting both is honest AND the stated reason for the drift is exact, checked file by file: under a bare config the working tree is 232/49, i.e. HEAD minus 7 errors in `core/runner.py`, 2 in `core/job.py` and 1 in `panels/_artifact_guard.py` (10 errors, 2 files - `job.py` stays on the list because its pandas `import-untyped` survives a bare config); the `[tool.mypy]` pandas override then removes exactly 24 `import-untyped` errors, one per module that imports pandas, of which 8 modules had no other error. 232-24 = 208, 49-8 = 41. R4.0's category breakdown for the 10 core errors is also exact: 4 arg-type, 2 attr-defined, 2 union-attr, 1 type-var, 1 import-untyped.

VERIFIED | spec/specboundaries04.md:128 "MEASURED: 10 entries" | Exactly 10 `ignore_imports`; `lint-imports` KEPT with and without `--no-cache` (79 files, 159 dependencies).

VERIFIED | spec/specboundaries04.md:55-65, the three tool behaviours | All three reproduced. (1) Moving `exclude_type_checking_imports` into the contract block makes the TYPE_CHECKING `job.py -> plots.base` import a violation again (161 deps vs 159), so it is top-level-only; a deliberately bogus `totally_bogus_option = "banana"` in the same block drew no complaint - unknown contract options ARE silently accepted. (2) `"quebra.core : quebra.provenance"` KEPT, `"quebra.core | quebra.provenance"` BROKEN naming `quebra.core.identity -> quebra.provenance (l.32)` - exactly the stated example. (3) With `unmatched_ignore_imports_alerting` deleted, a fabricated entry still fails: "No matches for ignored import ...", exit 1. R4.2.3's explicitness is belt-and-braces, as the text claims.

VERIFIED | spec/specboundaries04.md:141-146 (R4.2.4) | `panels/_within_calibration_data.py:36` does define `WithinCalibrationPanelData`, and 2 of the 666 archived pickles contain `quebra.panels._within_calibration_data`, `within_calibration` and the class name - so the move really would break them, unlike `_artifact_guard` (0 of 666). The four frozen `_within_calibration_compute` imports point at a module that appears in 0 pickles, but that module imports `_within_calibration_data` at its top level (and imports three analyzers back), so the argument transfers rather than failing. The rejected alternative reason is correctly labelled false: `Identity.code` is `hash_string(job_file.read_text())`, job file only.

VERIFIED | spec/specboundaries04.md "Not in this phase" | Honest on all four. No `jobs/validation|survey|comparison` exists (`jobs/` is active, bench, composite, reference, rscripts), so `acyclic_siblings` really would assert over absent packages. `grep @pytest.mark tests/` yields only `parametrize` and there is no `pytestmark` anywhere - zero tests carry slow/heavy/real/r. `tests/test_bench_isolation.py` is genuinely not subsumed: its `PIPELINE_PACKAGES` includes `"jobs"`, which `root_package = "quebra"` cannot see. The quote of quebraplan 2.1 is verbatim (quebraplan.md:140) and 2.3 does condition `acyclic_siblings` on the jobs/ split.

VERIFIED | spec/specboundaries04.md "Review outcome" vs the fixes actually present | Accurate. It reports 2 IMPORTANT + 5 MINOR, which is exactly what the first pass recorded, and all seven fixes are in the tree: `follow_imports` gone with a comment stating the measured no-op; `build_identity` raises `TypeError`; `_dataset_of(node: _DAGNode)` with no `getattr` fallback; `job_out_dir` inside `_require`; the deptry comment now says "the scan itself is repo-wide"; `quebra._fixtures` in `layers`; the CI marker comment rewritten (with the residual misattribution above). Its "verified and unchanged" list also still holds: one `ResolutionContext(` construction site (runner.py:483) setting all four fields.

VERIFIED | src/quebra/core/job.py:249-266 | The skip->raise change adds no failure mode any legitimate DAG can reach. A load node exists only via `Job.load`/`Job.load_df`, both annotated `dataset: Dataset` and both the only writers of `kwargs["dataset"]`; `Job.step` refuses any fn named `_load_dataset`/`_load_dataframe_raw`, so a user cannot forge one. `if ds is None: continue` is correctly restored AHEAD of the isinstance, and it agrees with `runner._dataset_load_nodes`, which filters `kwargs.get("dataset") is not None` - so the two modules treat a None-dataset load node identically (ignored) and a wrong-typed one identically (raise). Pre-change the same input raised `AttributeError` on `ds.path`, so this is loud->loud with a better message.

VERIFIED | src/quebra/core/runner.py:213-232, 443, 507 | `_require(context.job_out_dir, ...)` breaks no path that previously tolerated None. `ResolutionContext(` is constructed at exactly one site repo-wide (runner.py:483) and `job_out_dir` is already dereferenced two lines earlier (`job_out_dir.relative_to(out_dir)` at line 470), so it cannot be None there; `_locate_artifact` has exactly one caller, the `locate=` injection at that same site. `_dataset_of(node: _DAGNode)` is only ever called on members of `_dataset_load_nodes(job)` (line 443) or on a node whose id is in `resolved_datasets` (line 507), both of which already exclude a missing/None dataset, so its `TypeError` is unreachable from a valid DAG - it is a type narrowing, not a new gate.

VERIFIED | pyproject.toml layers - `quebra._fixtures` at the bottom | Correct for the stated purpose. `_fixtures` is a data package (`FIXTURES`, `fixture_path`, one CSV) importing nothing from `quebra`; bottom placement is what forbids that changing, which is exactly what the comment claims and what R4.1.3 exists to close. Worth knowing that it constrains one direction only: nothing now stops a production module importing packaged fixtures, since everything sits above it. Today only `tests/test_packaged_fixtures.py` imports it, and tests are outside `root_package` either way.

VERIFIED | gates | `make lint`, `make types`, `make arch`, `make deps` and `make check` each exit 0; `pytest -q` = 378 passed, 2 skipped (380 collected), matching P2 and "Done when". `mypy src/quebra/core` = "Success: no issues found in 9 source files". The `dev` extra carries ruff, mypy, import-linter>=2.13 and deptry, so CI's `make check` + `make deps` are installable; `requires-python = ">=3.11"` matches the 3.11/3.12 matrix and `[tool.mypy] python_version = "3.11"`.

---

# SPEC 0005 / Phase 3 review (identity closure)

SCOPE: src/quebra/core/closure.py, src/quebra/core/job.py (Job.code_hash only),
src/quebra/recipes.py (T2STAR_THRESHOLDS + configure_t2star_job only),
jobs/active/t2star_q1_070423.py, jobs/active/t2star_q1_100423.py,
src/quebra/analyzers/within_calibration_data.py,
src/quebra/analyzers/within_calibration_compute.py,
tests/test_identity_closure.py, tests/test_independence_survey.py
COMMIT: 1f58d37 (working tree, uncommitted)

## Manifest

- [ ] src/quebra/core/job.py (+75/-?)
- [ ] src/quebra/recipes.py (+113)
- [ ] jobs/active/t2star_q1_070423.py (-132)
- [ ] jobs/active/t2star_q1_100423.py (-132)
- [ ] src/quebra/analyzers/within_calibration_data.py (moved, 70)
- [ ] src/quebra/analyzers/within_calibration_compute.py (moved, 492)
- [ ] tests/test_identity_closure.py (new, 207)
- [ ] tests/test_independence_survey.py (+46/-?)

## Reviewed
- [x] src/quebra/core/closure.py

## Findings

---

## SPEC 0005 / Phase 3 review (identity + discovery slice)

SCOPE: src/quebra/core/discovery.py, src/quebra/core/job.py (Job.include only),
src/quebra/cli.py, JOB_ID/JOB_FAMILY in 12 jobs/active+jobs/composite files,
scripts/make_job_manifest.py, docs/JOBS.md, tests/test_job_discovery.py,
tests/test_job_manifest.py, spec/specidentity05.md
COMMIT: 1f58d37 (working tree, uncommitted)

### Manifest
- [ ] src/quebra/core/discovery.py (new, 125)
- [ ] src/quebra/core/job.py (Job.include only)
- [ ] src/quebra/cli.py (+33/-?)
- [ ] jobs/active/*.py x9 + jobs/composite/*.py x3 (JOB_ID/JOB_FAMILY)
- [ ] scripts/make_job_manifest.py (new, 134)
- [ ] docs/JOBS.md (new, 52)
- [ ] tests/test_job_discovery.py (new, 115)
- [ ] tests/test_job_manifest.py (new, 71)
- [ ] spec/specidentity05.md (new, 486)

### Reviewed

### Findings

### src/quebra/core/closure.py

CRITICAL | src/quebra/core/closure.py:1-25 (docstring) + effect on every job | The closure MISSES the pandera schema class that actually validates and cleans the loaded frame. `_load_dataset` (core/job.py:148) dispatches on `dataset.schema`, a class object carried on the `Dataset` at runtime; `Dataset` kwargs are skipped by `parameter_row` and grimp never sees the edge. Measured in an isolated copy of the tree: appending a line to `src/quebra/schemas/track912.py` left `t2star_q1_070423`'s code_hash byte-identical at `320f903b...` (whereas the same mutation to `analyzers/t2star.py` moved it). `track912Schema.validate` filters and coerces the frame, so this is code that changes the numbers while the identity asserts nothing changed - the exact defect the module was written to fix, one layer down. | Seed the traversal with `type(value).__module__` for every `Dataset` kwarg's `schema` (and, generally, for any kwarg whose value is a class or instance defined in `quebra.*`).

IMPORTANT | src/quebra/core/closure.py:6-11 ("keeps the radius narrow") and pyproject/spec claim R5.0.4 | The claim that the closure excludes render modules is FALSE as shipped. Measured closure of `t2star_q1_070423` (35 modules) contains `quebra.panels._within_calibration_render`, `quebra.plots.base`, `quebra.plots.theme`, `quebra.plots.allan_plot`, `quebra.plots.tlf_plot`, `quebra.plots.fidelity_helpers`. Mutation-verified: appending a line to `plots/theme.py` moves the digest (`b4192242...`), and to `panels/_within_calibration_render.py` moves it (`fe3e3996...`). Cause: the step functions now live in `quebra.recipes`, which function-locally imports `quebra.panels.within_calibration`, which imports the render module. So the recipe collapse (R5.3) re-created precisely the blast radius the docstring says was avoided. | Either drop the "narrow radius" claim from the docstring and the spec, or exclude `quebra.plots.*` / `*_render` from `_reachable`.

IMPORTANT | src/quebra/core/closure.py:120-127 `_reachable` seeded per-module | Seeding at MODULE granularity, not function granularity, means the whole of `quebra.recipes` seeds every t2star job. The measured closure therefore also contains `analyzers.allan`, `analyzers.tlf`, `transforms.interpolate`, `transforms.lookup_prior` - modules the T2* graph provably never executes (the docstring itself says it "adds NO interpolate node"). Editing the Ramsey/Allan path moves the T2* identity. Over-claiming is safer than under-claiming, but the docstring's "keeps the radius narrow" is not what the code does. | Say what it is (module-level, coarse), or seed from `fn.__code__.co_names`.

IMPORTANT | src/quebra/core/closure.py:178-184 `parameter_row` repr guard | A `set` kwarg breaks the cross-process determinism claim outright. Measured, three separate processes: `a(labels={'qq','y','ab','x','zz'})`, `a(labels={'y','zz','ab','x','qq'})`, `a(labels={'y','ab','zz','qq','x'})` - three different rows, three different digests, same job. String hashing is randomised per process and no ` at 0x` appears, so the guard never fires. | Render containers canonically: `sorted(repr(v) for v in value)` for `set`/`frozenset`, and reject anything else that is not a scalar/str/tuple/list/dict of scalars.

IMPORTANT | src/quebra/core/closure.py:178-184 | A `pathlib.Path` kwarg renders as `PosixPath('/home/sera/x/y.csv')` - an ABSOLUTE path with no ` at 0x` - so it enters the identity and breaks install-independence exactly as this module's own docstring (hazard 4) forbids. Realistic today: any future `rscript_path=` / sidecar-file kwarg. | Reject `Path` kwargs, or store them repo-relative.

IMPORTANT | src/quebra/core/closure.py:178-184 | A numpy array kwarg longer than the print threshold renders truncated: measured `array([   0,    1,    2, ..., 1997, 1998, 1999], shape=(2000,))`. Two arrays differing only in the elided middle produce an identical row and an identical identity - a silent collision, which is the failure `parameter_row` was added to close. | Hash array bytes rather than repr, or reject `ndarray`.

MINOR | src/quebra/core/closure.py:180 | `if "0x" in rendered and " at 0x" in rendered` - the first conjunct is subsumed by the second and can never change the outcome. | Drop it.

MINOR | src/quebra/core/closure.py:180 | The guard catches only the CPython default `<... at 0x...>` form. `functools.partial(len)` renders `functools.partial(<built-in function len>)` and passes; any custom `__repr__` embedding `id()`, a timestamp or a hostname without the literal " at 0x" also passes. The guard is a heuristic presented as a contract. | Allowlist accepted types instead of denylisting one repr shape.

GREEN | src/quebra/core/closure.py | Headline claim VERIFIED by mutation in an isolated tree copy: `analyzers/t2star.py` +1 line moves the digest 320f903b -> 2b8d8ab5 and restores exactly; `analyzers/kaplan_meier.py` (unreached) +1 line leaves it byte-identical. Repo left untouched (`git status` unchanged).
GREEN | src/quebra/loaders/registry.py | The runtime loader dispatch is NOT a closure hole: `_LOADER_REGISTRY` is populated by decorators inside `registry.py` itself, no `importlib`/entry points, and `registry` is in the measured closure.

### src/quebra/core/closure.py (second pass: `_graph()` and grimp)

CRITICAL | src/quebra/core/closure.py:51-59 `_graph()` | `grimp.build_graph(PACKAGE)` uses grimp's DEFAULT `cache_dir`, i.e. `.grimp_cache/` in the process CWD, and that cache is keyed on MTIME, not content. Measured in an isolated tree copy: append `import quebra.analyzers.kaplan_meier` to `analyzers/t2star.py` and restore its mtime (size changed 6894 -> 6940) and the closure stays at 35 modules with kaplan_meier ABSENT; the identical run with `cache_dir=None` gives 36 modules with kaplan_meier PRESENT. So any workflow that preserves mtime while changing content (`cp -p`, `rsync --times`, `tar -x`, a container layer restore, some `git` operations) yields a wrong import graph and therefore an identity that silently stops covering a module. That is the exact failure this module exists to prevent, reintroduced by a default argument. | `grimp.build_graph(PACKAGE, cache_dir=None)`.

IMPORTANT | src/quebra/core/closure.py:51-59 | Computing an identity now has a filesystem SIDE EFFECT and a hard failure mode. Measured: running `Job.code_hash()` from an empty scratch directory creates `.grimp_cache/` there; running it from a read-only CWD dies with `PermissionError: Permission denied (os error 13)` out of `grimp/adaptors/caching.py:229`, with no quebra-level message. Identity computation writing to CWD is I/O in the graph runtime, and read-only CWDs are normal in CI containers. | Same fix: `cache_dir=None`.

IMPORTANT | src/quebra/core/closure.py:61-75 `_quebra_imports_of_file` | `except (OSError, SyntaxError): return set()` SWALLOWS the error and returns an EMPTY seed set, which makes the closure empty and silently restores the pre-SPEC-0005 behaviour (job file text only). Project rule is errors raised, not swallowed - and this module's own `_seed_modules` raises for the analogous "cannot resolve a module" case two functions below, so the file is internally inconsistent about it. | Re-raise with the job path named.

IMPORTANT | src/quebra/core/closure.py:122-124 `_reachable` | `stack = [s for s in seeds if s in known]` silently discards any seed grimp does not know. It is needed because `_quebra_imports_of_file` deliberately emits attribute names (`quebra.recipes.RAMSEY_CONFIG`) alongside real modules, but the filter cannot tell "that was an attribute" from "that module is missing from the graph". A stale cache or a package-layout change therefore drops coverage with no signal. | Resolve `from X import y` candidates against `graph.modules` explicitly and raise if NEITHER the module nor the attribute parent is known.

MEASURED | cost | `import grimp` 27 ms, `build_graph("quebra")` 3 ms warm / 81 modules; per-job `code_hash()` 1.4-4 ms for simple jobs. Not a hot path. `instrument_validation` 545 ms and `independence_survey` 141 ms are dominated by job import, not by the closure. Cost is not a finding.

VERIFIED | determinism | Claim 3 parts 1 and 3 hold. Twelve jobs hashed all-in-one-process twice: byte-identical. The same twelve hashed one-per-subprocess: byte-identical to the all-in-one-process run, so `run --all` does not contaminate. Running from a copied tree at a different absolute path reproduced `320f903b...` exactly, which is the install-independence claim for the tree location.

IMPORTANT | src/quebra/core/discovery.py:72-75 | `read_declaration` swallows `OSError` and `SyntaxError` and returns None, so a job file that does not parse becomes INVISIBLE to discovery. Measured: a dir with `good.py` and a syntactically broken `broken.py` both declaring `JOB_ID = "dup"` returns `{'dup': good.py}` with NO `DuplicateJobId`. Consequence for `run --all`: the old code globbed `jobs/active/*.py` and let the import raise into the `failures` list (exit 1); the new code drops the file before anything can raise, so a broken job is skipped with exit 0. Loudness regression. | Re-raise (or collect) parse/read errors instead of returning None; at minimum let `discover` fail on a `*.py` under `jobs/active|composite` that will not parse.
IMPORTANT | src/quebra/core/discovery.py:87-88 + tests/test_job_discovery.py:100 | A job file that simply forgets `JOB_ID` is silently excluded from `run --all` forever, and no test catches it: `test_every_in_repo_job_declares_an_id_and_a_family` iterates over what discovery already FOUND, so a file with no `JOB_ID` cannot fail it. | Add a test asserting every non-`__init__` `.py` under `jobs/active/` and `jobs/composite/` yields a declaration.
MINOR | src/quebra/core/discovery.py:50-67 | `_string_constant` silently ignores a non-literal `JOB_ID` (`JOB_ID = "pre"+"fix"` -> job vanishes). Documented and tested as intended, but the failure mode is invisibility, not a message. | Raise when the name is assigned but not a plain string literal.
GREEN | src/quebra/core/discovery.py | No-import rule holds: `ast.parse` only, no `import`/`importlib`/`exec` anywhere in the module, and a file whose body is `raise RuntimeError(...)` is discovered fine (measured). | none
GREEN | src/quebra/core/discovery.py:97-104 | Duplicate `JOB_ID` raises `DuplicateJobId` and the message names BOTH paths (measured on two well-formed files). | none

IMPORTANT | src/quebra/cli.py:105-106 | `--family` help says "see `quebra jobs`". There is no `jobs` subcommand: `quebra --help` lists `{run,inspect,schema-wizard}`. Shipped help text pointing at a command that does not exist. | Point at `docs/JOBS.md`.
IMPORTANT | src/quebra/cli.py:136-154 | `--all` silently changed meaning. Old: `jobs/active/*.py` = 9 jobs. New (measured with `run_job` mocked): 12 jobs, newly including the three composites `check_ledger_q1`, `compare_t2star_0704_vs_1004`, `independence_survey`. Composites re-run their own sub-jobs, so `run --all` now executes the two t2star jobs three times over. Neither the spec's R5.4 section nor the CLI comment mentions the widening. | Either keep composites out of a bare `--all` (e.g. require `--family composite`) or state the widening in the spec and the help.
IMPORTANT | src/quebra/cli.py:103-107,136 | `--family` is accepted and silently ignored when `--all` is absent. Measured: `quebra run jobs/active/mtbf_q1.py --family totally-bogus` runs the job and exits 0. A mistyped selector silently does the wrong thing. | `parser.error` when `--family` is given without `--all`.
MINOR | src/quebra/cli.py:142-143 | `declared = discovery.discover(jobs_root) if jobs_root.is_dir() else {}` -> from a cwd with no `jobs/`, `quebra run --all` prints nothing, runs nothing and exits 0 (measured, RC=0). Same shape as the old dead glob, but `--all` is now the only selection route. | Error when `--all` selects zero jobs.
MINOR | src/quebra/cli.py:142 vs src/quebra/core/job.py:324 | Two different roots for the same tree: the CLI uses `Path.cwd()/"jobs"`, `Job.include` uses `repo_root()/"jobs"`. From a subdirectory the CLI finds nothing while `include` still resolves. | Use `repo_root()` in both.
GREEN | src/quebra/cli.py | `--include-archived` removal is clean: `jobs/archived/` does not exist, and no reference to the flag survives in tests, Makefile, CI, README, AGENTS.md or docs (grepped). `--all --family t2star` -> exactly the 2 t2star jobs; `--family composite` -> exactly the 3 composites; an unknown family calls `parser.error` and lists the declared families. | none

GREEN | src/quebra/core/job.py:312-333 | ID-first/path-second dispatch verified end to end: with `t2star_q1_070423.py` COPIED to `jobs/some/deep/place/renamed_file.py` in a throwaway project root, `quebra inspect jobs/cmp.py` still wires `t2star_q1_070423:t2star_panel_data`. (Done in a sandbox; the tracked tree was never moved.) Edge cases all loud: `''` -> ValueError listing declared IDs; `bare.py` -> path branch, resolves; `jobs\a\b.py` -> FileNotFoundError naming the resolved path; `/abs/x.py` -> FileNotFoundError; an ID containing a dot (`sub.dotted`) resolves as an ID. | none
MINOR | src/quebra/core/job.py:322-326 | When `jobs/` is absent, an argument that was meant as an ID falls through to `resolve_repo_path` and reports a path-not-found error naming a path the caller never wrote. | Mention "no jobs/ directory found" in that branch.

IMPORTANT | scripts/make_job_manifest.py:26-37 | `INTERESTING` omits parameters that decide what a run means, including two seeds: `VALIDATION_SEED=20260811`/`VALIDATION_REPLICATES=4000`/`VALIDATION_N` (check_calibration), `ASYMPTOTIC_SIZE_SEED=777`/`N_PERM_IN_TIE_STUDY=999`/`DIVERGENCE_THRESHOLD=0.02` (instrument_validation), `TIE_CUTOFF_DISTINCT=5` (check_ledger_q1, independence_survey), `C3_N_NULL_SIM=200`. Measured: editing `VALIDATION_SEED` leaves `build()` byte-identical, so the manifest and its staleness gate are both blind to it. The docstring claims the list is "the ones that decide what a run MEANS". | Surface every UPPER_CASE module-level literal, or subtract an explicit `BORING` set so a new constant is included by default.
IMPORTANT | tests/test_job_manifest.py:60-70 | `test_regenerating_is_idempotent` SHELLS OUT to the generator, whose `main()` writes `docs/JOBS.md`. Measured: `pytest tests/test_job_manifest.py` changes the file's mtime. The staleness gate therefore self-heals - the run that reports "JOBS.md is stale" also rewrites it, so the next run is green with nothing fixed. | Have the test call `build()` twice, or run the generator against a tmp copy; never let the suite write a committed artifact.
IMPORTANT | tests/test_job_manifest.py:40-52 | `test_the_generator_does_not_import_the_jobs` does not test the generator. It writes an explosive job into `tmp_path`, then asserts `discover(tmp_path)` (the wrong function) and `assert gen.build` (truthiness of a function object). `gen.build()` is never called, and cannot be pointed at `tmp_path` because `JOBS` is a module constant. A test asserting coverage it does not have. | Make `build(jobs_root=JOBS)` take the root and call it on `tmp_path`.
MINOR | scripts/make_job_manifest.py:53-56 | `except (ValueError, TypeError): pass` drops a non-literal INTERESTING constant from the row with no marker, so the reader sees an absent parameter rather than "computed". | Render `<computed>`.
MINOR | tests/test_job_manifest.py:20 | Docstring "Fails when a job changed without regeneration" overclaims: measured, appending a module-level constant or changing `VALIDATION_SEED` leaves `build()` identical. It fails only when JOB_ID/JOB_FAMILY/Dataset literals/include literals/an INTERESTING constant change. | Say what it actually covers.
MINOR | tests/test_job_discovery.py:24-26 | `pytest.importorskip("pathlib")` to obtain `Path` - stdlib, cannot be missing; if it ever were, the whole module would skip silently. | `from pathlib import Path`.

IMPORTANT | jobs/composite/independence_survey.py:60 | `JOB_FAMILY = "composite"` on a job that contains NO `job.include` at all - its own docstring (line 14) says "this one loads its datasets directly rather than through `job.include`". The family was copied from the directory, which is precisely what R5.4 claims to have stopped. | Give it a subject family (e.g. `validation` or `independence`), or drop "composite" as a family.
MINOR | jobs/ (all 12) | "composite" is a mechanism, not a subject; the other five families (t2star, ramsey, survival, interval, validation) are subjects. A reader cannot predict where a new job goes - `check_ledger_q1` is as much "validation" as `check_calibration` is. | Either make family purely subject-matter and expose "has includes" from the manifest, or document the rule in docs/JOBS.md.
MINOR | jobs/active/ramsey_q1_100423.py, jobs/active/t2star_q1_100423.py | Both declare `PREFIX = 'q1_13h_1004_dataset'` (visible in docs/JOBS.md rows). Distinct JOB_IDs now, but the shared PREFIX is what names node/artifact labels. | Confirm the two cannot collide in `output/`.

### Reviewed
- [x] src/quebra/core/discovery.py
- [x] src/quebra/core/job.py (Job.include)
- [x] src/quebra/cli.py
- [x] jobs/active + jobs/composite JOB_ID/JOB_FAMILY (12 files)
- [x] scripts/make_job_manifest.py
- [x] docs/JOBS.md
- [x] tests/test_job_discovery.py
- [x] tests/test_job_manifest.py

CRITICAL | src/quebra/cli.py:136-154 vs docs/WRITING_A_JOB.md:229 and AGENTS.md:200 | The committed docs state the invariant this change breaks. WRITING_A_JOB.md:229: "`quebra run --all` sweeps `jobs/active` and would otherwise re-run every sub-job" - given as the REASON composites live in `jobs/composite/`. AGENTS.md:200: "`jobs/composite/` ... NOT swept by `run --all`". Measured, `run --all` now selects all 12 including the composites, so it re-runs every sub-job and additionally launches `independence_survey`, which this spec's own budget section calls "~6.5 h wall-clock at INCLUDE_C3=True over 415 cells". Neither doc was updated and the spec never mentions the widening. | Exclude family `composite` from a bare `--all`, or update both docs and say so in R5.4.
IMPORTANT | docs/WRITING_A_JOB.md:210-232 | The job-authoring guide never mentions `JOB_ID` or `JOB_FAMILY`, and still teaches `job.include("other_job.py")`. A job written by following the guide declares no `JOB_ID` and is therefore silently invisible to `run --all` forever. | Add the two constants to the guide and switch the include example to an ID.
IMPORTANT | docs/WRITING_A_JOB.md:173,185 | R5.1.6 required a `docs/` sweep and it did not happen. Line 173 still says the identity is "a content hash of the job file's source, the datasets it loaded, and the identities of any sub-jobs" - R5.1 added the step-source closure and the parameter row. Line 185's example run directory is `output/t2star_q1_070423_43e8d4_...`, the exact stale prefix R5.1.6 named; the spec's own R5.3 outcome says that digest is now `ffba1a`. | Sweep both.
MINOR | src/quebra/cli.py:145 | `quebra run --all --family ""` - empty string is falsy, so the guard is skipped and all 12 jobs run instead of erroring. | Test `args.family is not None`.

IMPORTANT | spec/specidentity05.md:346 | "the two **133-line** files were byte-identical". Measured at HEAD: both `jobs/active/t2star_q1_0{7,10}0423.py` are **128** lines, which is also what this same spec says at R5.0.2 line ~80 ("128 lines each"). The document contradicts itself and the artifact. | Say 128.
IMPORTANT | spec/specidentity05.md:347 | "They are 34 lines each now — **198 lines removed**". Measured: 34 lines each is correct; the removal count is not. `git diff --numstat` gives 113 removed + 19 added per file = 226 removed / 38 added, net 188 fewer lines in the two job files, against 113 lines ADDED to `recipes.py` (net -75 repo-wide). 198 corresponds to no measurement. | Quote 188 (net, two files) or 226/38 and the +113 in recipes.
IMPORTANT | spec/specidentity05.md:150-152 (R5.0.4 acceptance) vs pyproject.toml:163,166-177 | Acceptance says "no entry names a phase that will not remove it". All five surviving `ignore_imports` entries name SPEC 0005, and the spec's own "Not in this phase" section defers them. The comment above the list also still reads "The frozen baseline: **10** imports" over a list of 5, and an orphaned comment block about `panels/_within_calibration_data.py` survives with a dangling "# SPEC 0005." and no entry. Measured numbers in a shipped comment that are false. | Fix the comment and retarget the five entries at the spec that will remove them.
MINOR | spec/specidentity05.md:296-299 (R5.2 acceptance) / :338-348 | R5.2 has no `**Outcome.**` section; the paragraph that opens R5.3's Outcome ("`core/discovery.py` reads `JOB_ID` and `JOB_FAMILY` statically ... the acceptance holds") is R5.2's outcome pasted under R5.3. Same shift puts R5.4's outcome inside R5.5. A reader checking R5.2 or R5.4 finds no record. | Move each Outcome under its own requirement.
MINOR | spec/specidentity05.md:290-294 (R5.2.4) vs src/quebra/core/job.py:322-333 | R5.2.4 says "No deprecation window ... If an external caller ever appears, add the compatibility path then, against a real case." The shipped `include` keeps the path branch permanently and the `FileNotFoundError` text advertises it ("a repo-root-relative path still works"). Reasonable engineering, but the spec asserts the opposite of what was built. | Reword R5.2.4 to state that the path form is retained as a fallback, and why.
MINOR | spec/specidentity05.md:411 (R5.5 acceptance) | "its test fails when a job changes without regeneration" is false in general. Measured against a copy of `jobs/`: changing `ALPHA` moves `build()`; changing `VALIDATION_SEED` or adding a module-level constant does not. The gate covers JOB_ID, JOB_FAMILY, `Dataset(path=...)` literals, `include` literals and the ten `INTERESTING` names only. | State the covered surface.
MINOR | spec/specidentity05.md:430-435 ("Done when") | "The collect count is recorded with its delta explained." R5.1's outcome records 380 -> 393; the tree as shipped collects **408** (`406 passed, 2 skipped`) and no line of the spec records that number or its delta. | Record 408 and the +15 from R5.4/R5.5's tests.
MINOR | spec/specidentity05.md:382-384 (R5.4 acceptance) | "A job with no `JOB_FAMILY` is reported, not silently skipped" is satisfied by a test over the repo, not by the tool: at runtime a family-less job is silently omitted from every `--family` selection and nothing prints. | Have `--family` (or a `quebra jobs` listing) name the uncategorised jobs.
GREEN | spec/specidentity05.md:75-79 (R5.0.2) | "20 non-`__init__` files — 9 active, 3 composite, 8 bench" - counted, exact. The "byte-identical once the date and the run duration were normalised" claim also holds: normalising `070423`/`100423`, `27h`/`13h`, `duration_h`, `0704`/`1004` makes the two HEAD files `diff`-clean. | none
GREEN | spec/specidentity05.md:140-144 (R5.0.4 outcome) | "`analyzers.t2star`'s transitive closure went from 14 quebra modules with 4 render to **9 with 0**" - re-measured with `grimp.build_graph("quebra").find_upstream_modules("quebra.analyzers.t2star")`: 9 modules, zero `plots.*` or `*_render`. | none
GREEN | spec/specidentity05.md:296 | "All 4 in-repo `include` sites use `JOB_ID`" - grepped: exactly 4, in `check_ledger_q1.py` and `compare_t2star_0704_vs_1004.py`, all IDs. The remaining `.include(` calls are tests passing tmp_path absolutes. | none
NOT VERIFIED | spec/specidentity05.md:326-335, 349-353 | The digests `5c35194470316077`, `43e8d4 -> ffba1a`, the "byte-identical `q1_27h_0704_dataset_windows.pkl`" and the "2 bytes" `t2star_panel_data.pkl` delta all require running the T2* jobs over `data/real_private/`, which this review is forbidden to touch. Unchecked, and they are the spec's load-bearing numbers. | Another reviewer with data access must confirm.

- [x] spec/specidentity05.md

---

SCOPE: src/quebra/recipes.py (T2* family section only), jobs/active/t2star_q1_070423.py,
jobs/active/t2star_q1_100423.py, tests/test_independence_survey.py (diff vs HEAD).
COMMIT: 1f58d37

## Manifest
- [ ] src/quebra/recipes.py (T2* section)
- [ ] jobs/active/t2star_q1_070423.py (+19/-113)
- [ ] jobs/active/t2star_q1_100423.py (+19/-113)
- [ ] tests/test_independence_survey.py (+34/-12)

## Reviewed

## Findings

### Verified by measurement (behaviour preservation, claim 1)

GREEN | recipes.py + both jobs | DAG is byte-for-byte the same shape as HEAD. Built HEAD's two job files (from `git show`) and the new two in-process and dumped `dag`: identical node ids in identical order (`load`, `t2star_filter`, `t2star_final_filter_stage`, `t2star`, `windows`, `t2star_panel_data`), identical `inputs` edges (`t2star_panel_data <- [t2star, windows]`), identical sinks in identical order (`_MaterializeSink q1_..._windows` then `_FigureSink q1_..._t2star` with `targets=['static','academic']`, `WithinCalibrationPanel`). `quebra inspect` agrees. | none

GREEN | claim 2, provenance visibility | All five land in `node.kwargs`, measured not read: `windows` -> `{'gap_mult': 10.0, 'k': 1.0, 'use_uncertainty': True}`; `t2star_panel_data` -> `{'shape_min_reads': 5, 'use_uncertainty': True, 'xi_seed': 20260813}`. Identical dicts at HEAD. `runner._label` builds from `node.kwargs`, so the label is unchanged. | none

GREEN | claim 3, threshold ladder | `[(f"{k} µs", k / 1e6, True) for k in range(1, 11)]` reproduces the ten old literals EXACTLY, compared by IEEE-754 bit pattern (`struct.pack('>d')`) on all ten rungs, labels included. `k * 1e-6` would have differed at k=5 (`4.9999999999999996e-06`) and k=10 (`9.999999999999999e-06`); the shipped form does not. | none

GREEN | claim 4, the two jobs still differ | They differ in exactly path / PREFIX / duration_h and nothing else; the two DAGs differ only in those three places, and `Job(name)` differs, so identities differ. | none

### Findings

IMPORTANT | tests/test_independence_survey.py:88-105 | The rewritten `_effective_t2star_carve` is NOT strictly stronger; it is weaker on one axis and the weakening is silent. It pre-seeds `effective` with the recipe defaults and then overwrites from the job file inside `try: ... except (ValueError, SyntaxError): pass`. A job that overrides with anything non-literal keeps the swallowed exception AND keeps the recipe default, so the test compares the survey against a value the job does not use. MEASURED: injecting `gap_mult=MY_GAP` into the job file yields `{'GAP_MULT': 10.0, ...}` and the test PASSES while the job carves with `MY_GAP`; `k=2.0 * 1.5` likewise yields `K: 1.0` and passes. At HEAD the same mutation left `found` without the key and `assert name in found` fired loudly. That is precisely the "survey and panel describe different windows" defect the module docstring says this file exists to catch. | Re-raise instead of `pass`: on `ast.literal_eval` failure, fail the test naming the kwarg, e.g. `pytest.fail(f"{kw.arg} is overridden with a non-literal; the control cannot read it")`.

IMPORTANT | src/quebra/recipes.py:297-302 vs src/quebra/analyzers/t2star.py:117-128 | The new comment claims "One ladder, one place". False as shipped: `analyzers/t2star.py` still holds `T2STAR_DEFAULT_LADDER`, the same ten rungs as explicit literals. The count went from 3 copies to 2, not to 1, and nothing pins the two equal - no test compares `recipes.T2STAR_THRESHOLDS` to `T2STAR_DEFAULT_LADDER` (grepped). Project rule: a claim in a shipped comment must be true as shipped. | Either import the analyzer ladder, or say "two ladders" and add an equality assertion.

IMPORTANT | src/quebra/recipes.py:319, jobs/active/t2star_q1_070423.py:5, jobs/active/t2star_q1_100423.py:5 | "two 133-line job files" / "these two files were 133 lines each". MEASURED: `git show HEAD:jobs/active/t2star_q1_070423.py | wc -l` = 128, same for 100423. The same wrong number is already logged against spec/specidentity05.md:346 and has now been copied into three shipped source files. | Say 128.

IMPORTANT | src/quebra/recipes.py:311, 338 | `thresholds` is the one parameter of `configure_t2star_job` that does NOT reach provenance: `ladder` is a closure capture of `_windows_run`/`_t2star_panel_data`, never a step kwarg. The function's own docstring states the rule it breaks - "an argument left to its default would be invisible to provenance" - and applies it to the other five. The ladder is the most meaning-bearing parameter in the graph (it defines every rung of the panel); a job that passes `thresholds=` gets no record of it on the node label. | Forward `thresholds=ladder` as a step kwarg on `windows` and `t2star_panel_data`, as the other five are.

MINOR | src/quebra/recipes.py:338 | `thresholds=[]` is accepted silently: `[] is not None`, so the empty ladder is used, the panel scores zero rungs and nothing raises. Repo rule is errors raised, not silent degradation. | `if thresholds is not None and not thresholds: raise ValueError(...)`.

MINOR | src/quebra/recipes.py:311 vs :271 | `gap_mult: float = 10.0` hardcodes a number that is already imported into this module as `DEFAULT_GAP_MULT` (line 16) and used by `configure_ramsey_job` at line 271. Equal today (`windows.DEFAULT_GAP_MULT = 10.0`, checked); if the constant moves, ramsey follows and t2star silently does not. | `gap_mult: float = DEFAULT_GAP_MULT`.

MINOR | src/quebra/recipes.py:334-336 | The three function-body imports are cargo-cult, not cycle-breaking. MEASURED: `import quebra.analyzers.t2star` does not pull in `quebra.recipes` (no cycle); `WithinCalibrationPanel` is ALREADY imported at module scope (recipes.py:19-22), so that line is dead; and `recipes` sits above `panels`/`analyzers` in the import-linter layer list (pyproject.toml:147-152), so a module-level import is permitted. Function-level imports are also visible to grimp, so they buy nothing from the contract either. | Move all three to module scope alongside the existing `windows`/`WithinCalibrationPanel` imports.

MINOR | src/quebra/recipes.py:305-311 vs :204-215 | Inconsistent with `configure_ramsey_job` directly above: ramsey takes `dataset` POSITIONALLY and annotates `job: Job` bare; t2star makes `dataset` keyword-only and quotes `"Job"` / `"Dataset"` even though both are module-level imports and `from __future__ import annotations` is in force. Two sibling recipes with two conventions. | Match the neighbour.

MINOR | src/quebra/recipes.py:300 | `T2STAR_THRESHOLDS` holds SI seconds and carries no unit suffix, against the project's unit-suffix rule; the comment carries the unit instead. (Same defect in `T2STAR_DEFAULT_LADDER`, pre-existing.) | `T2STAR_THRESHOLDS_S`.

MINOR | tests/test_independence_survey.py:71 | `T2STAR_JOB = _module_constants(...)` is now dead - its only consumer was the `_T2STAR_THRESHOLDS` lookup this diff removed (grepped: one occurrence, the assignment). | Delete it.

MINOR | tests/test_independence_survey.py:166-176 | The ladder control lost its anchor. At HEAD it compared the survey's `k / 1e6` comprehension against the job's ten explicit LITERALS - a genuine cross-form check. It now compares the survey comprehension against `recipes.T2STAR_THRESHOLDS`, which is the character-for-character identical expression, so the surviving comment "`k * 1e-6` fails this at k = 5 and k = 10 ... `k / 1e6` reproduces the literals exactly" describes a comparison the test no longer performs. The only remaining explicit-literal ladder, `T2STAR_DEFAULT_LADDER`, is now pinned by nothing. | Compare the survey ladder against `analyzers.t2star.T2STAR_DEFAULT_LADDER` (the literals) as well, or drop the claim.

MINOR | tests/test_independence_survey.py:96 | The override scan reads only `jobs/active/t2star_q1_070423.py`. There are now two declared members of the `t2star` family and the recipe makes per-job overrides a first-class feature, so an override in `t2star_q1_100423.py` alone is invisible to every carve control. (Pre-existing narrowness, newly load-bearing.) | Loop over both `jobs/active/t2star_*.py`.

MINOR | jobs/composite/independence_survey.py:70-76 | Stale as shipped after this diff: "the literal `5e-6` the T2* jobs write". The T2* jobs write no literal any more; the ladder lives in `recipes.T2STAR_THRESHOLDS` as the same comprehension. | Retarget the comment at `recipes.T2STAR_THRESHOLDS` / `T2STAR_DEFAULT_LADDER`.

MINOR | jobs/bench/probe_unresolved.py:17 | "Every job file declares a ladder byte-identical to T2STAR_DEFAULT_LADDER" is false after the collapse - no job file declares a ladder. | Reword.

## Reviewed
- [x] src/quebra/recipes.py (T2* section)
- [x] jobs/active/t2star_q1_070423.py
- [x] jobs/active/t2star_q1_100423.py
- [x] tests/test_independence_survey.py
