# C3 - copula-based serial independence

**Runs, but uncalibrated.** R is installed and C3 has executed - first successful contact
2026-08-13, Rscript 4.5.3 with `copula` from the user library, on iid exponential input at
`seed=1`: n=50 gives statistic 0.00579 / p 0.958 in 3.9 s, n=150 gives 0.00713 / p 0.904 in
14.7 s, n=355 gives 0.00763 / p 0.866 in 130.2 s. The seed is part of the number - the R side
simulates its own null, so the statistic is seed-invariant while the p-value is not (at
`seed=0` the first two give 0.948 and 0.912).

Failing to reject data that satisfies the null is the expected outcome and is a SMOKE TEST,
NOT calibration. C3 still has no size or power evidence, because the bench never ran it and
`battery.ROW_KEYS` has no C3 row. **Its silence is not a pass.**

Historic note, kept because the rest of this file was written under it: R was absent, and no
code path past `_invoke_rscript` had ever executed.

## What it tests

Genest and Remillard's empirical-copula test of serial independence, based on the Mobius
decomposition of the independence hypothesis. Implemented in R as
`copula::serialIndepTest`, which needs a simulated null from `serialIndepTestSim(n, lag.max)`.

It is here because it tests a strictly STRONGER null than C5 or C6: full serial
independence at all lags jointly, not merely zero rank autocorrelation. Two duration
sequences can have zero rank autocorrelation at every lag and still be dependent; this
would see that and C5 would not.

## Where it lives

`analyzers/checks/c3_serial_copula.py` plus its sibling `c3_serial_copula.R`.

**A bridge, not bindings.** CSV out, `Rscript`, CSV back - no `rpy2`. rpy2 pins an ABI
against a specific R build and turns "R is missing" into an import-time failure of the whole
package; a subprocess turns it into a per-call `None`. The pipeline must import cleanly on
a machine without R, and here it must.

## Limitations

**Uncalibrated in the only sense that matters.** `tests/test_checks_c3_bridge.py` pins the
graceful-absence behaviour: missing R returns `p_value=None` with `notes="R unavailable"`,
nothing raises, and the ordinary data guards still fire. It cannot pin the numeric path.
That code path HAS now run (see the top of this file), so the paragraph below describes a
risk that has been partly discharged: the CSV round-trip, the exit-code handling and the
result parsing were all exercised on 2026-08-13. What remains untested is everything the
bench would have measured - size, power, and behaviour on data that is NOT iid. Historic
statement of the risk, kept because it is what the design defends against: the first machine
with R installed gets a code path that has never run, including the CSV
round-trip and the result parsing.

**No multi-process form.** `serialIndepTest` takes one series. Concatenating segments would
manufacture lag pairs across read gaps - exactly the relation the carve refuses to assert -
and combining per-segment p-values needs a dependence-free combination rule that is not
established for this statistic. So `m > 1` returns `None` with that reason recorded rather
than a number nobody can defend.

**The continuity assumption.** The distribution-free property is derived for continuous
observations. On a quantised metric the durations are integers times the read interval and
the empirical copula is not what the test assumes. The ledger's tie rule applies to C3 for
this reason, though it has never fired on the T2* ladder.

## What we do

Ship the bridge, call it, and report `not computed` when R is absent - which is every row
in every ledger produced so far. The promotion report scores four checks, not five, and
says so at the top.

If R is installed later: `tests/test_checks_c3_bridge.py::test_r_is_genuinely_absent_here`
skips rather than fails, and its skip message says the four-check scope needs revisiting.
