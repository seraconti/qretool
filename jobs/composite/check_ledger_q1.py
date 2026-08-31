"""The check ledger for both q1 T2* datasets.

A composite, not a pair of standalone jobs, for one reason: the ledger must describe the
SAME carve the panel describes. `job.include` + `.ref` pulls the window table each t2star
job already materialises, so there is exactly one carve wiring in the repo and the
artifact's sha256 lands in this run's provenance. Re-deriving the carve here would mean
fifty lines that must stay byte-identical to those jobs forever, or the ledger and the
panel would silently describe different windows.

Every knob that turns a p-value into a verdict is declared HERE and passed as a step
kwarg, so it reaches the provenance label. An agent picking `MIN_EVENTS_PASS` is an agent
deciding what counts as evidence, which is not a decision that belongs in a default.
"""

from __future__ import annotations

import pandas as pd

from quebra.analyzers.check_ledger import CheckLedger, make_inputs_from_windows
from quebra.analyzers.check_ledger import run as run_ledger
from quebra.core.dataset import Dataset
from quebra.core.job import Job
from quebra.panels.check_ledger import CheckLedgerPanel

# SPEC 0005 R5.2/R5.4: the logical name and category. `include` resolves JOB_ID, so this
# file can move without breaking any composite; recategorising costs one string edit.
JOB_ID = "check_ledger_q1"
JOB_FAMILY = "independence"
# Not swept by a bare `run --all`: it re-runs sub-jobs and/or is long. Selectable
# with `--family independence` or by path. This is the declaration that replaced the old
# "jobs/composite/ is not swept" directory rule.
JOB_SWEEP = False

# The T2* ladder, repeated from the datasets' own jobs. Kept literal rather than imported
# so the ladder this ledger scored is visible in this file and lands on the label.
# `k / 1e6`, NOT `k * 1e-6`. The two differ: 1e-6 is not exactly representable, so
# `5 * 1e-6` is 4.9999999999999996e-06 while the literal `5e-6` the T2* jobs write is
# 5e-06 - two of the ten rungs (5 and 10) land on a different double. Dividing by the
# exactly-representable 1e6 reproduces the literal on all ten.
# The gap is about 4e-22 and no measured value will fall in it, so this has never changed
# a window. It is fixed because the survey CLAIMS to score the same ladder as the panel,
# and a claim that is true only to 15 significant figures is not the claim being made.
THRESHOLDS: list[tuple[str, float, bool]] = [
    (f"{k} µs", k / 1e6, True) for k in range(1, 11)
]

ALPHA = 0.05
# Below this many events a non-rejection is not evidence of anything. The bench measured
# C5/C6 power at 0.06-0.13 below n = 75 against the dependence this instrument shows, so
# 35 is already generous; it is the smallest grid point where any check had usable power.
MIN_EVENTS_PASS = 35
# Minimum distinct durations before a rank statistic is interpretable. Weakly determined:
# the bench swept quantisation as a boolean, so the evidence brackets this between ~5 and
# ~20 and no finer. On the T2* ladder it never binds - durations are wall-clock seconds
# and 355 windows gave 355 distinct values - but it will on a quantised metric.
TIE_CUTOFF_DISTINCT = 5
LAG_MAX = 5
N_PERMUTATIONS = 999
SEED = 20260812

BENCH_SIZE_TABLE = Dataset(path="jobs/bench/results/size_table.csv", schema=None)

job = Job("check_ledger_q1")

_bench = job.load_df(BENCH_SIZE_TABLE)
_d0704 = job.include("t2star_q1_070423", alias="d0704")
_d1004 = job.include("t2star_q1_100423", alias="d1004")


def _ledger(
    window_result: object,
    bench_size_table: pd.DataFrame,
    *,
    alpha: float,
    min_events_pass: int,
    tie_cutoff_distinct: int,
    lag_max: int,
    n_permutations: int,
    seed: int,
) -> CheckLedger:
    return run_ledger(
        make_inputs_from_windows(
            window_result,
            bench_size_table,
            thresholds=THRESHOLDS,
            alpha=alpha,
            min_events_pass=min_events_pass,
            tie_cutoff_distinct=tie_cutoff_distinct,
            lag_max=lag_max,
            n_permutations=n_permutations,
            seed=seed,
        )
    )


for alias, included, prefix in (
    ("d0704", _d0704, "q1_27h_0704_dataset"),
    ("d1004", _d1004, "q1_13h_1004_dataset"),
):
    node = job.step(
        _ledger,
        included.ref(f"{prefix}_windows"),
        _bench,
        name=f"check_ledger_{alias}",
        alpha=ALPHA,
        min_events_pass=MIN_EVENTS_PASS,
        tie_cutoff_distinct=TIE_CUTOFF_DISTINCT,
        lag_max=LAG_MAX,
        n_permutations=N_PERMUTATIONS,
        seed=SEED,
    )
    job.figure(
        CheckLedgerPanel,
        node,
        targets=["static", "academic"],
        title=f"{prefix} check ledger",
    )
    job.materialize(node, name=f"{prefix}_check_ledger")
