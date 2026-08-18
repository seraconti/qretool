"""The check ledger: every check, on every threshold, with what its answer is worth.

A p-value alone is not a result here. The same 0.4 means "no evidence of dependence" from
a calibrated check on 355 windows and "this test cannot see anything" from the same check
on 20. So every row carries three things beside the p-value, and a `pass` requires all
three to hold:

    n_events            enough events for the check to have power
    bench_size_at_n     the check was calibrated at that event count, per the bench
    tie_fraction        the durations are not so tied that a rank test is meaningless

If any fails, the verdict is NOT `pass`. That is the entire point of the ledger: a
non-rejection must never print as a pass on a p-value alone.

**Which clock.** Both are run. On the in-spec clock of a carved record, time stops
accruing the moment the record ends out of spec, so `tau == T_N` and eqs (4)/(7) are
singular - measured at ~73% of synthetic replicates. Those rows read `not computed` with
the reason, and the rank checks (which never touch `tau`) still run there.

**What the provenance record cannot hold.** Its schema is closed, so the R version is
discovered at runtime and lives in `CheckLedger.r_version` on the materialized artifact,
not in the `.prov.json`. `alpha`, the ladder, the seed and the thresholds DO reach the
label, because they are step kwargs.
"""

from __future__ import annotations

import subprocess
import zlib
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import analyzers.checks.c3_serial_copula as c3
from analyzers.calibration_summary import bench_acceptance_at_n, nearest_bracketing_n
from analyzers.checks._multiprocess import segments_from_windows
from analyzers.checks._permutation import block_permutations
from analyzers.checks._rank_serial import MAX_LAG_CAP
from analyzers.checks.battery import run_battery
from analyzers.checks.result import (
    CALIB_ASYMPTOTIC,
    CALIB_PERMUTATION,
    CALIB_R_COPULA,
    CLOCK_CALENDAR,
    CLOCK_IN_SPEC,
    CheckResult,
)
from panels._artifact_guard import StaleArtifactGuard

VERDICT_PASS = "pass"
VERDICT_FAIL = "fail"
VERDICT_UNDERPOWERED = "underpowered"
VERDICT_TIES = "not interpretable (ties)"
VERDICT_NOT_COMPUTED = "not computed"
VERDICTS = (
    VERDICT_PASS,
    VERDICT_FAIL,
    VERDICT_UNDERPOWERED,
    VERDICT_TIES,
    VERDICT_NOT_COMPUTED,
)

# HOW OFTEN THIS RULE BINDS, measured rather than assumed: on the T2* ladder it never does
# except where the event count already disqualifies the row. T2* durations are wall-clock
# seconds and effectively continuous - 355 windows gave 355 distinct values - so ties are a
# property of QUANTISED metrics (a fidelity threshold where most windows are one read long),
# not of this one. The rule earns its place on those ladders, not here.
#
# Checks whose validity rests on the durations being effectively continuous: C5 and C6 are
# rank statistics, C3's distribution-free property is derived for continuous observations.
# C1 and C2 use the durations directly and degrade differently (a fully tied vector makes
# gamma_hat zero, which raises rather than misleads), so the tie rule does not apply to
# them.
TIE_SENSITIVE_CHECKS = ("c3_serial_copula", "c5_rank_autocorr", "c6_exchangeability")

LEDGER_COLUMNS = [
    "dataset_id",
    "threshold_label",
    "clock",
    "check_id",
    "calibration",
    "variant",
    "statistic",
    "p_value",
    "verdict",
    "n_events",
    "n_windows_used",
    "n_censored_dropped",
    "n_segments",
    "n_distinct_durations",
    "tie_fraction",
    "bench_n_target",
    "bench_size_at_n",
    "bench_size_ci",
    "bench_size_cell",
    "bench_accepted",
    "notes",
]


@dataclass
class CheckLedger(StaleArtifactGuard):
    """One row per (threshold, clock, check, calibration), plus the settings that made it.

    The settings are ON the artifact rather than only in the job file because a ledger read
    six months from now has to be interpretable without opening the job that produced it -
    `alpha` and `min_events_pass` are what turn a p-value into a verdict.
    """

    rows: pd.DataFrame
    dataset_id: str = ""
    alpha: float = 0.05
    min_events_pass: int = 0
    tie_cutoff_distinct: int = 0
    lag_max: int = MAX_LAG_CAP
    n_permutations: int = 0
    seed: int = 0
    # Runtime-discovered, and the provenance schema has no free-form field to hold it.
    r_version: str = ""
    thresholds: list[tuple[str, float, bool]] = field(default_factory=list)

    def check_thresholds(self, labels: list[str]) -> None:
        """Every threshold on the ladder appears in the ledger, or the artifact is partial."""
        present = set(self.rows["threshold_label"]) if len(self.rows) else set()
        missing = sorted(set(labels) - present)
        if missing:
            raise ValueError(
                f"incomplete CheckLedger: no rows for threshold(s) {missing} - construct "
                "via analyzers.check_ledger.run()"
            )

    def passing(self) -> pd.DataFrame:
        return self.rows[self.rows["verdict"] == VERDICT_PASS]

    def naive_passes(self) -> pd.DataFrame:
        """Rows a p-value-only rule would have called `pass`, and this rule does not.

        This is the ledger's own demonstration that the extra two conditions do work.
        """
        naive = self.rows["p_value"].notna() & (self.rows["p_value"] > self.alpha)
        return self.rows[naive & (self.rows["verdict"] != VERDICT_PASS)]


@dataclass(slots=True)
class CheckLedgerInputs:
    windows: pd.DataFrame
    bench_size_table: pd.DataFrame
    thresholds: list[tuple[str, float, bool]]
    dataset_id: str = ""
    gap_spans_s: list[tuple[float, float]] | None = None
    alpha: float = 0.05
    min_events_pass: int = 35
    tie_cutoff_distinct: int = 5
    lag_max: int = MAX_LAG_CAP
    n_permutations: int = 999
    seed: int = 0
    min_events_per_segment: int = 2
    # C3 is the only out-of-process check and by far the most expensive: measured 130 s at
    # n = 355, and the cost grows steeply. A survey across many datasets cannot afford it,
    # and does not lose calibrated evidence by skipping it - C3 has no bench cell, so its
    # rows are `not computed` or an uncalibrated p-value either way. When False the C3 rows
    # are OMITTED rather than written as `not computed`: a blank row would claim the check
    # was attempted and failed, when in fact it was never asked.
    include_c3: bool = True
    # See c3_serial_copula.N_NULL_SIM: the dominant cost, and part of what a C3
    # p-value means, so it is carried rather than left to a module default.
    c3_n_null_sim: int = c3.N_NULL_SIM


def make_inputs_from_windows(
    window_result: object,
    bench_size_table: pd.DataFrame,
    *,
    thresholds: list[tuple[str, float, bool]],
    alpha: float,
    min_events_pass: int,
    tie_cutoff_distinct: int,
    lag_max: int,
    n_permutations: int,
    seed: int,
    include_c3: bool = True,
    c3_n_null_sim: int = c3.N_NULL_SIM,
) -> CheckLedgerInputs:
    """Build inputs from a `WindowsResult`, taking the gap spans with it.

    `gap_spans_s` is not optional in spirit: without it `segments_from_windows` falls back
    to reading birth types alone, which cannot see a gap flanked by out-of-spec reads and
    silently merges two renewal processes separated by unobserved hours.
    """
    diagnostics = getattr(window_result, "diagnostics", {}) or {}
    return CheckLedgerInputs(
        windows=window_result.windows,
        bench_size_table=bench_size_table,
        thresholds=list(thresholds),
        dataset_id=str(getattr(window_result, "meta", {}).get("dataset_id", "")),
        gap_spans_s=diagnostics.get("gap_spans_s"),
        alpha=alpha,
        min_events_pass=min_events_pass,
        tie_cutoff_distinct=tie_cutoff_distinct,
        lag_max=lag_max,
        n_permutations=n_permutations,
        seed=seed,
        include_c3=include_c3,
        c3_n_null_sim=c3_n_null_sim,
    )


def _tie_stats(durations: np.ndarray) -> tuple[int, float]:
    """Distinct value count and the fraction of observations sharing a value."""
    if not len(durations):
        return 0, float("nan")
    _values, counts = np.unique(durations, return_counts=True)
    tied = float(counts[counts > 1].sum()) / float(len(durations))
    return int(len(_values)), tied


def _verdict(
    result: CheckResult,
    *,
    alpha: float,
    n_events: int,
    min_events_pass: int,
    n_distinct: int,
    tie_cutoff: int,
    bench_accepted: bool | None,
) -> tuple[str, str]:
    """The verdict and the reason it is not `pass`, in precedence order."""
    if result.p_value is None:
        return VERDICT_NOT_COMPUTED, result.notes
    if result.check in TIE_SENSITIVE_CHECKS and n_distinct < tie_cutoff:
        return (
            VERDICT_TIES,
            f"{n_distinct} distinct durations, below the cutoff of {tie_cutoff}",
        )
    if result.p_value <= alpha:
        # A rejection. Whether it is trustworthy still depends on the calibration, so the
        # note carries that even when the verdict does not.
        note = "rejected"
        if bench_accepted is False:
            note += "; but the bench found this check miscalibrated at this event count"
        return VERDICT_FAIL, note
    unmet = []
    if n_events < min_events_pass:
        unmet.append(f"n_events {n_events} < {min_events_pass}")
    if bench_accepted is False:
        unmet.append("bench found this check miscalibrated at this event count")
    if bench_accepted is None:
        unmet.append("no bench cell for this check at this event count")
    if unmet:
        # A non-rejection that cannot be read as evidence for the null.
        return VERDICT_UNDERPOWERED, "; ".join(unmet)
    return VERDICT_PASS, ""


def run(inputs: CheckLedgerInputs) -> CheckLedger:
    """Run every check on every threshold and score each answer."""
    acceptance = bench_acceptance_at_n(inputs.bench_size_table, alpha=inputs.alpha)
    grid = sorted({int(n) for n in acceptance["n_target"]})
    r_path = c3.rscript_path()

    rows: list[dict[str, object]] = []
    for label, _value, _big_good in inputs.thresholds:
        table = inputs.windows[inputs.windows["threshold_label"] == label]
        for clock in (CLOCK_IN_SPEC, CLOCK_CALENDAR):
            rows.extend(
                _rows_for(
                    table=table,
                    label=label,
                    clock=clock,
                    inputs=inputs,
                    acceptance=acceptance,
                    grid=grid,
                )
            )
    frame = pd.DataFrame(rows).reindex(columns=LEDGER_COLUMNS)
    ledger = CheckLedger(
        rows=frame,
        dataset_id=inputs.dataset_id,
        alpha=inputs.alpha,
        min_events_pass=inputs.min_events_pass,
        tie_cutoff_distinct=inputs.tie_cutoff_distinct,
        lag_max=inputs.lag_max,
        n_permutations=inputs.n_permutations,
        seed=inputs.seed,
        r_version="absent" if r_path is None else str(r_path),
        thresholds=list(inputs.thresholds),
    )
    ledger.check_thresholds([label for label, _v, _b in inputs.thresholds])
    return ledger


def _blank_row(
    label: str,
    clock: str,
    inputs: CheckLedgerInputs,
    note: str,
    n_windows: int = 0,
) -> dict:
    return {
        "dataset_id": inputs.dataset_id,
        "threshold_label": label,
        "clock": clock,
        "check_id": "(all)",
        "calibration": "",
        "variant": "",
        "statistic": float("nan"),
        "p_value": None,
        "verdict": VERDICT_NOT_COMPUTED,
        "n_events": 0,
        "n_windows_used": int(n_windows),
        "n_censored_dropped": 0,
        "n_segments": 0,
        "n_distinct_durations": 0,
        "tie_fraction": float("nan"),
        "bench_n_target": None,
        "bench_size_at_n": float("nan"),
        "bench_size_ci": "",
        "bench_size_cell": "",
        "bench_accepted": None,
        "notes": note,
    }


def _rows_for(
    *,
    table: pd.DataFrame,
    label: str,
    clock: str,
    inputs: CheckLedgerInputs,
    acceptance: pd.DataFrame,
    grid: list[int],
) -> list[dict[str, object]]:
    if not len(table):
        return [_blank_row(label, clock, inputs, "no windows at this threshold")]
    try:
        segments, n_dropped = segments_from_windows(
            table,
            clock=clock,
            min_events=inputs.min_events_per_segment,
            gap_spans_s=inputs.gap_spans_s,
        )
    except (ValueError, KeyError) as exc:
        return [
            _blank_row(
                label, clock, inputs, f"segmentation failed: {exc}"[:200], len(table)
            )
        ]
    if not segments:
        return [
            _blank_row(
                label,
                clock,
                inputs,
                f"no segment reached {inputs.min_events_per_segment} events "
                f"({n_dropped} dropped)",
                len(table),
            )
        ]

    durations = np.concatenate([s.x for s in segments])
    n_distinct, tie_fraction = _tie_stats(durations)
    n_events = int(len(durations))
    bench_n = nearest_bracketing_n(grid, n_events)

    # crc32, not hash(): Python randomises string hashing per process (PYTHONHASHSEED),
    # so `hash(label)` would have made every permutation p-value differ between runs while
    # the provenance record stayed identical - the exact defect the explicit-rng rule
    # exists to prevent. crc32 is stable across processes and versions.
    stream = zlib.crc32(f"{label}|{clock}".encode()) & 0x7FFFFFFF
    rng = np.random.default_rng([inputs.seed, stream])
    perm = block_permutations(
        [s.n_events for s in segments], inputs.n_permutations, rng
    )

    results: list[CheckResult] = []
    battery_note = ""
    try:
        results = run_battery(segments, clock=clock, perm=perm, max_lag=inputs.lag_max)
    except (ValueError, KeyError) as exc:
        battery_note = f"C1/C2 undefined here: {exc}"[:180]
        try:
            results = run_battery(
                segments,
                clock=clock,
                perm=perm,
                max_lag=inputs.lag_max,
                include_tau_checks=False,
            )
        except (ValueError, KeyError) as inner:
            return [
                _blank_row(
                    label, clock, inputs, f"battery failed: {inner}"[:200], len(table)
                )
            ]
        # The retry dropped C1 and C2. Say so with their own rows: without them the reader
        # sees a ladder where the trend checks simply vanish at the loose thresholds and
        # cannot tell whether they were attempted, declined, or forgotten. The reason
        # (usually tau == T_N on the in-spec clock) belongs on the row it applies to.
        for dropped, calibrations in (
            ("c1_lewis_robinson", (CALIB_ASYMPTOTIC, CALIB_PERMUTATION)),
            ("c2_anderson_darling", (CALIB_ASYMPTOTIC, CALIB_PERMUTATION)),
        ):
            for calibration in calibrations:
                results.append(
                    CheckResult(
                        check=dropped,
                        statistic=float("nan"),
                        p_value=None,
                        calibration=calibration,
                        clock=clock,
                        n_events=int(sum(s.n_events for s in segments)),
                        n_segments=len(segments),
                        notes=battery_note,
                    )
                )

    # C3 is out-of-process and shares nothing with the permutation set, so it is called
    # separately. With R absent it returns p_value=None and the row reads `not computed`.
    if inputs.include_c3:
        try:
            results.append(
                c3.run(
                    segments,
                    clock=clock,
                    max_lag=inputs.lag_max,
                    seed=inputs.seed,
                    n_null_sim=inputs.c3_n_null_sim,
                )
            )
        # RuntimeError and TimeoutExpired are the R bridge's own failure modes - a
        # non-zero Rscript exit, a missing or unparseable result file, or a simulation
        # that outran its timeout. They were NOT caught until P5, and it did not show
        # while R was absent because `rscript_path()` returned None and the bridge never
        # ran. With R installed the call executes for real, and an uncaught RuntimeError
        # kills the whole ledger job instead of writing the `not computed` row this
        # except clause exists to write.
        except (ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired) as exc:
            results.append(
                CheckResult(
                    check=c3.CHECK_NAME,
                    statistic=float("nan"),
                    p_value=None,
                    calibration=CALIB_R_COPULA,
                    clock=clock,
                    n_events=n_events,
                    n_segments=len(segments),
                    notes=f"declined: {exc}"[:160],
                )
            )

    out: list[dict[str, object]] = []
    for result in results:
        variant = ""
        for token in result.notes.split():
            if token.startswith("variant="):
                variant = token.split("=", 1)[1]
        match = acceptance[
            (acceptance["check"] == result.check)
            & (acceptance["calibration"] == result.calibration)
            & (acceptance["variant"].fillna("") == variant)
            & (acceptance["clock"] == clock)
            & (acceptance["n_target"] == bench_n)
        ]
        if len(match):
            entry = match.iloc[0]
            accepted = bool(entry["bench_accepted"])
            size = float(entry["bench_size_at_n"])
            half = 1.96 * float(entry["bench_size_se"])
            ci = f"[{size - half:.4f}, {size + half:.4f}]"
            cell = str(entry["bench_size_cell"])
        else:
            accepted, size, ci, cell = None, float("nan"), "", ""

        verdict, reason = _verdict(
            result,
            alpha=inputs.alpha,
            n_events=n_events,
            min_events_pass=inputs.min_events_pass,
            n_distinct=n_distinct,
            tie_cutoff=inputs.tie_cutoff_distinct,
            bench_accepted=accepted,
        )
        # The battery note explains why C1/C2 were dropped, so it belongs on THEIR rows.
        # Appending it to every row put "C1/C2 undefined here: tau ..." on a C3 row, which
        # is a different check with a different reason.
        relevant = battery_note if result.check.startswith(("c1_", "c2_")) else ""
        notes = "; ".join(part for part in (reason, relevant) if part)
        out.append(
            {
                "dataset_id": inputs.dataset_id,
                "threshold_label": label,
                "clock": clock,
                "check_id": result.check,
                "calibration": result.calibration,
                "variant": variant,
                "statistic": float(result.statistic),
                "p_value": result.p_value,
                "verdict": verdict,
                "n_events": n_events,
                "n_windows_used": int(len(table)),
                "n_censored_dropped": int(result.n_censored_dropped),
                "n_segments": int(result.n_segments),
                "n_distinct_durations": n_distinct,
                "tie_fraction": tie_fraction,
                "bench_n_target": bench_n,
                "bench_size_at_n": size,
                "bench_size_ci": ci,
                "bench_size_cell": cell,
                "bench_accepted": accepted,
                "notes": notes,
            }
        )
    return out
