# C1 - Lewis-Robinson test for trend

## The equation

Kvaloy & Lindqvist (arXiv:1802.08339), eq (4), single process:

```
LR = (1/gamma_hat) * sqrt(12)/(tau*sqrt(N)) * [ sum_i T_i - (N/2)*tau ]
```

Multi-process, their eq (16), after substituting the optimal eq (15) weights:

```
LR_m = sqrt(12) / sqrt( sum_k gamma_hat_k^2 * tau_k^2 * N_k )
       * sum_j [ sum_i T_ij - (N_j/2) * tau_j ]
```

`sum_i T_i` is the total of the event times; `(N/2)*tau` is its expectation when events are
uniform on `[0, tau]`, which is the null of no trend. So LR is a centred, scaled "are the
events early or late" contrast - negative for a decreasing intensity, positive for an
increasing one, two-sided here.

The `1/gamma_hat` is what makes it a test of TREND rather than of the Poisson assumption:
dividing by the estimated coefficient of variation removes the renewal distribution's own
dispersion. That is the whole difference between Lewis-Robinson and the plain Laplace test.

## Where it lives

`analyzers/checks/c1_lewis_robinson.py`. Only eq (16) is implemented; setting `m = 1` in it
gives eq (4) exactly, so a separate single-process path would be a second copy of the same
formula, free to drift. `tests/test_checks_statistics.py::test_eq16_reduces_to_eq4_for_a_single_segment`
asserts the identity numerically rather than trusting the algebra (agreement to 1e-12).

## Limitations

**The asymptotic calibration is oversized at the event counts this project has.** It is
N(0,1) in the limit; measured on the primary null configuration it rejects at 0.069 at
n = 20 against a nominal 0.05, converging by n ≈ 75. Kvaloy & Lindqvist's own Section 5.1
predicts this ("all tests are a bit non-conservative for small samples in the underdispersed
case"), and their Figure 1 shows LR at ~0.08 at 10 expected events.

**The multi-process asymptotic collapses under segmentation.** With many short segments the
eq (16) normal approximation fails outright: at a realised censoring of 0.17 the bench
measured a rejection rate of **0.699** against a nominal 0.05 (z = 133). The permutation
form on the same cells stayed at 0.038.

**`gamma_hat` is undefined on a fully tied duration vector.** A quantised metric where every
window is one read long gives zero dispersion, and the statistic it scales has no meaning.
This raises rather than returning a number.

## What we do

Use the permutation calibration. It is exactly valid rather than asymptotically - `tau`,
`N` and `gamma_hat` are all invariant to reordering gaps within a segment, so the only
thing a permutation moves is `sum_i T_ij`. The bench PROMOTEd it: calibrated across 80 null
cells inside the censoring envelope (worst z = -2.05 against a Bonferroni threshold of
3.42), with mean power 0.596 at n = 100 across the trend grid (range 0.170-0.999 - the
spread is over trend strength, and mild trends are genuinely hard).

The asymptotic form is REJECTed by the bench and the ledger hatches any cell that uses it
at an event count where it was miscalibrated.
