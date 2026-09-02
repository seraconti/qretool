# C5 - studentized rank autocorrelation

## What it computes

The rank autocorrelation of the durations at lags 1..H, studentized by the permutation
ensemble's own spread, with the MAXIMUM over lags calibrated by permutation:

```
r_h = sum_{pairs at lag h} (R_i - Rbar)(R_{i+h} - Rbar) / sum_i (R_i - Rbar)^2
statistic = max_h |r_h - mean_perm(r_h)| / sd_perm(r_h)
```

Pairs never cross a segment boundary: a lag-1 pair spanning a read gap would relate two
windows separated by unobserved hours.

Studentizing by the ensemble's own moments follows the Chung-Romano / Romano-Tirlea
argument for studentized permutation tests. The moments are computed from the observed
value TOGETHER WITH the permutations, which makes the scaling a symmetric function of the
augmented sample and keeps the test exactly valid at finite `B` rather than valid to
O(1/B).

## Where it lives

`analyzers/checks/c5_rank_autocorr.py`; the shared rank machinery is in
`analyzers/checks/_rank_serial.py`.

## Limitations

**Studentization does much less than expected, and the reason is measurable.** Every lag
shares one denominator (the full centred sum of squares) while its numerator sums only the
within-segment pairs at that lag, so the null spread of `r_h` GROWS with the pair count -
the opposite of the usual intuition. Measured:

| configuration | lags, pairs | null SD | ratio |
|---|---|---|---|
| one segment of 60 | 1-5, 59..55 | 0.1269..0.1224 | 1.04 |
| 10 segments of 5 | 1-4, 40..10 | 0.0985..0.0600 | 1.64 |

So on an ungapped record the two variants are near-identical by construction, and only on
short, numerous segments does the unstudentized max concentrate on one lag (43% of
replicates on lag 1, against 21-29% once each lag is on its own scale). The unstudentized
variant ships so that this is a number rather than a claim.

**It is a rank statistic, so ties degrade it.** On a quantised metric where most windows are
one read long the ranks are mostly ties and the statistic loses meaning. The ledger's tie
rule applies. On the T2* ladder it never binds: durations are wall-clock seconds and 355
windows gave 355 distinct values.

**Underpowered where this instrument lives.** This is the binding limitation. At the
duration lag-1 the record actually shows (0.12-0.15), power is 0.070 at n = 20, 0.135 at
n = 50, 0.292 at n = 100, and only 0.849 at n = 355.

## What we do

Report it, and require more than its p-value before calling anything a pass. The bench put
C5 on HOLD - correctly calibrated (worst z = 2.36 against 3.45) but underpowered at the
operating point - so `analyzers/check_ledger.py` marks a non-rejection below
`min_events_pass` as `underpowered`, never `pass`.

C5 and C6 agree with each other to a mean absolute difference of 0.016 across 192 shared
cells. Running both buys very little; running one of them and C1/C2 buys a lot.
