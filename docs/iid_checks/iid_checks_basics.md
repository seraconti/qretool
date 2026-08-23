# The iid checks - what they test, and what their answers are worth

Temporary working reference for the P4b cycle. It documents `analyzers/checks/` and the
calibration study in `jobs/bench/`. When the licence wiring is decided, the durable parts fold
into `docs/PANEL_CONTRACT.md` (how a check reaches a panel) and the rest is deleted.

This is the first directory in `docs/` to carry citations. That is deliberate: these are
implementations of published statistics and the equation numbers are load-bearing - a
reader checking the transcription needs to know which equation, in which paper.

---

## The question all five are asking

The panel carves a metric into in-spec **windows**. Reliability arithmetic on those windows
- occupancy, survival, mean time between failures - assumes the durations behave like a
renewal process: independent, identically distributed, no trend. If they do not, the
arithmetic still produces numbers, and the numbers are wrong in ways nothing else catches.

Five checks ask whether that assumption survives contact with the data.

| check | null it tests | rejects when |
|---|---|---|
| C1 Lewis-Robinson | renewal process, no trend | events crowd early or late |
| C2 Anderson-Darling | renewal process | event times are not uniform on `[0, tau]` |
| C3 copula serial independence | full serial independence at all lags | any lag shows dependence |
| C5 rank autocorrelation | zero rank autocorrelation | consecutive durations covary |
| C6 exchangeability | order carries no information | any departure from exchangeability |

They are not redundant, but two of them are close. Measured against C6 as the reference,
C5 agrees with it to a mean absolute difference of 0.014-0.016 in rejection rate over 192
shared power cells, while C1/C2 differ from it by 0.18-0.19 over the 156 they share. C5 and
C6 are largely measuring the same thing; C1/C2 measure a different one.

## Two clocks, because the mapping is not unique

A window table can become a renewal process two ways, and they ask different questions.

- **In-spec clock** (`CLOCK_IN_SPEC`): an event is a window dying by `down_crossing`, `x`
  is its duration, `tau` is the segment's total in-spec time. Asks whether successive
  in-spec lifetimes look renewal.
- **Calendar clock** (`CLOCK_CALENDAR`): an event is a window BIRTH, `x` is wall-clock time
  between births, `tau` is the observed length. Asks whether failures arrive as a renewal
  process in real time - the question a maintenance schedule poses.

Both are reported. Reporting one alone would hide that the answer depends on the choice,
and on the real record they DO disagree: at 4 µs the calendar clock passes every check
while the in-spec clock cannot compute C1 or C2 at all.

That last point is structural, not a bug. On the in-spec clock, time stops accruing the
moment the record ends out of spec, so `tau == T_N` and eq (7)'s `ln(tau/(tau - T_N))` is
`+inf`. Measured on synthetic iid reads: ~73% of replicates. Those rows read `not computed`
with the reason attached.

## Segments, because a read gap is not an interval

A gap in the reads means unobserved time. Treating the stretch across it as one inter-event
interval invents evidence. So a record is split at its gaps into independent time-censored
processes and combined by the multi-process forms (Kvaloy & Lindqvist eqs 13-16).

The split uses `WindowsResult.diagnostics["gap_spans_s"]`, not the birth taxonomy alone:
`analyzers/windows.carve` only emits `gap_resume` next to an in-spec read, so a gap flanked
by out-of-spec reads leaves NO trace in the window table. Reading births alone merged two
processes separated by 488 s of unobserved time and handed that 493 s span to eq (4) as a
renewal interval.

## Permutation, not asymptotics

Every check ships a permutation calibration and it is the one to use. Permutation is
**exactly** valid here rather than asymptotically: `tau`, `N` and `gamma_hat` are all
invariant to reordering gaps within a segment, so the conditional null is exact at finite
`B`. The p-value is tie-corrected, `p = (1 + #{null >= observed}) / (1 + B)`, because this
project's duration vectors are heavily tied on quantised metrics and `#/B` would count a
tie as a refutation.

Permutation requires an explicit seed. `block_permutations` raises on `rng=None`: it used
to default to OS entropy, which made three consecutive runs on identical input return
p = 0.3860 / 0.4040 / 0.3790 while the provenance record stayed identical.

## What the bench establishes, and what it does not

`jobs/bench/` measures empirical size and power at the event counts this project actually has,
over 336 cells and 480,000 replicates. Its verdicts:

| | verdict | why |
|---|---|---|
| C1, C2 permutation | PROMOTE | size holds across 80 null cells; mean power 0.60/0.61 at n = 100 |
| C1, C2 asymptotic | REJECT | oversized inside the envelope (worst z = 10.8 and 7.0) |
| C5, C6 | HOLD | correctly calibrated, but underpowered where it matters |
| C3 | RUNS, UNCALIBRATED | first contact 2026-08-13 (Rscript 4.5.3, `copula`); smoke-tested on iid input only - no bench cell, no size or power evidence |

**The number to read before trusting a non-rejection**: at the dependence this instrument
actually shows (duration lag-1 0.12-0.15), C5 and C6 have 6-13% power below n = 75 and
25-29% at n = 100, reaching 78-85% only at n = 355. A non-rejection at a threshold with 50
windows is close to uninformative. A rejection still means something; the silence does not.

That asymmetry is why `analyzers/check_ledger.py` requires three conditions for a `pass`
and not one. On the 0704 record, 31 of 68 non-rejections would have printed `pass` under a
p-value-only rule.

## Files

- `analyzers/checks/` - the five checks, the permutation harness, the segment mapping
- `analyzers/checks/battery.py` - runs the four permutation checks off ONE permutation set
- `analyzers/check_ledger.py` - scores each answer against event count, calibration, ties
- `jobs/bench/` - the calibration study; `jobs/bench/results/promotion_report.md` is its output
- `analyzers/calibration_summary.py` - the shared definition of "calibrated at this n"

## Per-check pages

[C1](C1_lewis_robinson.md) - [C2](C2_anderson_darling.md) - [C3](C3_serial_copula.md) -
[C5](C5_rank_autocorr.md) - [C6](C6_exchangeability.md) - [limitations](LIMITATIONS.md)

## Sources

- J. T. Kvaloy and B. H. Lindqvist, *Tests for trend in more than one repairable system*,
  arXiv:1802.08339. Equations (4), (7), (10), (11), (13)-(16); Sections 4.2 and 5.1.
- G. Marsaglia and J. Marsaglia, *Evaluating the Anderson-Darling Distribution*,
  Journal of Statistical Software 9(2), 2004. The `adinf` limiting function.
- C. Genest and B. Remillard, empirical-copula tests of serial independence; implemented in
  R as `copula::serialIndepTest`.
- S. Chatterjee, *A new coefficient of correlation*, JASA 116:2009-2022, 2021. Used by
  `analyzers/shape_stats.py`, not by these checks.
- B. H. Lindqvist, on trend-renewal processes - the model behind the bench's Arm D.
- D. R. Cox and P. A. W. Lewis, *The Statistical Analysis of Series of Events*, 1966, for
  the renewal-versus-trend framing.
