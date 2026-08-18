# Limitations that cut across all five checks

Per-check limitations live on the per-check pages. These are the ones that would mislead a
reader who took any single ledger row at face value.

## 1. A non-rejection is usually not evidence

This is the binding one. At the dependence this instrument actually shows (duration lag-1
0.12-0.15), C5 and C6 have:

| n | 20 | 35 | 50 | 75 | 100 | 355 |
|---|---|---|---|---|---|---|
| C5 studentized | 0.070 | 0.101 | 0.135 | 0.192 | 0.292 | 0.849 |
| C6 | 0.060 | 0.092 | 0.117 | 0.168 | 0.249 | 0.782 |

Below n = 75 a non-rejection is the expected outcome whether the durations are dependent or
not. A REJECTION is meaningful, because the checks are correctly calibrated. It is the
silence that carries no information.

`analyzers/check_ledger.py` enforces this: a `pass` requires the p-value AND a sufficient
event count AND that the bench found the check calibrated at that count. On the 0704
record, 31 of 68 non-rejections would have printed `pass` under a p-value-only rule.

## 2. Multiplicity across the ladder is not corrected

A ledger runs 5 checks x 2 calibrations x 2 clocks over up to 10 thresholds. Nothing
corrects for that. The thresholds are nested (a window in spec at 3 µs is in spec at 4 µs),
so the tests are strongly positively dependent and a Bonferroni correction would be far too
conservative - but "far too conservative" is not "unnecessary". **Read the ladder as a
pattern, not as ~200 independent decisions.** A single isolated rejection at one threshold
is much weaker evidence than a monotone trend down the ladder.

## 3. The two clocks can disagree, and neither is wrong

On the 0704 record at 4 µs, the calendar clock passes every check and the in-spec clock
cannot compute C1 or C2 at all. That is not a contradiction: they ask different questions
(see the README), and the in-spec clock's `tau == T_N` collapse is structural for a record
that ends out of spec.

## 4. C3 is unassessed

R is present since 2026-08-13 and C3 executes; where R is absent the bridge still degrades to
`p_value=None` and the row reads `not computed`. What remains missing is CALIBRATION, not the
interpreter: C3 has no bench cell, so its size and power are unmeasured. Two operational limits
found on first contact: `--vanilla` implies `--no-environ` and so needs `R_LIBS` passed
explicitly or `copula` is invisible, and the run cost grows about as n^2.8 (130 s at n = 355),
so large windows can exhaust the timeout and report `not computed` for that reason alone.
The promotion report scores four checks. No conclusion anywhere rests on C3.

## 5. The bench's censoring arm never reached its label

The grid asked for censoring 0.25. The generator caps the segment count so each segment
expects at least a few events, and that cap binds at every n, so the realised value is
0.1675-0.1685 throughout. The out-of-envelope findings (notably C1 asymptotic at 0.699) are
real, but they happened at c ≈ 0.17. `bench/report.py` now prints the realised value.

## 6. The tie cutoff is weakly determined

`bench/grid.py` sweeps quantisation as a BOOLEAN, not as a distinct-duration count, so the
evidence brackets the cutoff between roughly 5 and 20 distinct values and no more finely.
The ledger declares 5 and says so. On the T2* ladder it never binds - durations are
wall-clock seconds and effectively continuous. It will bind on a quantised metric, and
there the number is a placeholder rather than a calibrated threshold.

## 7. What the provenance record cannot hold

The record has a closed schema. `alpha`, the ladder, the seed and every step kwarg reach
the Mermaid label, and the bench table's sha256 enters `dataset_hashes` and the run
identity. The **R version cannot**: it is discovered at runtime, so it lives in
`CheckLedger.r_version` on the materialized artifact and nowhere else.

## 8. Bench numbers describe synthetic records

Every size and power figure comes from generated data. Arms B and C carve their reads with
the real `analyzers/windows.py` primitives, so the carve policy is not idealised - but the
underlying processes are Weibull and Gaussian, not this instrument. The bench answers "what
would this check do on a record of this shape and size", not "what is this record".

The one place that gap is visible: after segments began splitting at read gaps, the real
record moved into an m > 1 regime that the bench measured only OUTSIDE its censoring
envelope. That regime has no in-envelope bench support.
