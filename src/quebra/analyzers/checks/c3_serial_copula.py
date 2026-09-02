"""C3 - copula-based serial independence test, over a file bridge to R.

Wraps `copula::serialIndepTest` (Genest & Remillard's empirical-copula test based on the
Mobius decomposition of the serial independence hypothesis). It is here because it tests a
strictly stronger null than C5/C6 - full serial independence at all lags jointly, not just
zero rank autocorrelation - and no maintained Python implementation exists.

**Bridge, not bindings.** CSV out, `Rscript`, CSV back. No `rpy2`: rpy2 pins an ABI against
a specific R build and turns "R is missing" into an import-time failure of the whole
package, whereas a subprocess turns it into a per-call `None`. The pipeline must import
cleanly on a machine without R.

**C3 runs and is UNCALIBRATED.** Exercised under Rscript 4.5.3, Rscript 4.5.3 with
`copula` from the user library, on iid exponential input AT `seed=1`: n=50 gives statistic
0.00579 / p 0.958 in 3.9 s, n=150 gives 0.00713 / p 0.904 in 14.7 s, n=355 gives 0.00763 /
p 0.866 in 130.2 s. The SEED IS PART OF THE NUMBER: the R side simulates its own null, so
the statistic is seed-invariant and reproduces exactly, while the p-value does not - at the
module default `seed=0` the same inputs give 0.948 and 0.912. Quoting a p without its seed
is the defect this line exists to avoid.

Failing to reject data that satisfies the null is the expected outcome and is a SMOKE TEST,
NOT calibration: C3 still has no size or power evidence, because the bench never ran it and
`battery.ROW_KEYS` has no C3 row.

When R is missing, every entry point below returns `p_value=None` with
`notes="R unavailable"` rather than raising - a missing optional interpreter is a fact about
the environment, not a defect in the data, and the other five checks must still run. The
promotion report scores five checks, not six. Do not read a `not computed` row as a pass.

**No multi-process form.** `serialIndepTest` takes one series. Concatenating segments would
manufacture lag pairs across read gaps - the exact relation the carve refuses to assert -
and combining per-segment p-values needs a dependence-free combination rule that is not
established for this statistic. So `m > 1` returns `None` with that reason recorded rather
than a number whose meaning nobody can defend.
"""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from quebra.analyzers.checks._rank_serial import MAX_LAG_CAP
from quebra.analyzers.checks.result import (
    CALIB_R_COPULA,
    CLOCK_IN_SPEC,
    CheckResult,
    Segment,
    concatenated_gaps,
    segment_sizes,
    validate_segment,
)

CHECK_NAME = "c3_serial_copula"

R_SCRIPT = Path(__file__).with_name("c3_serial_copula.R")

# The R side simulates its own null distribution; this is how many draws it uses. Kept
# here rather than in the R file so the Python result can record it.
#
# It is the DOMINANT cost: the simulation is what makes C3 grow steeply with n, so a survey
# over hundreds of cells can trade it down. `run` takes it as a parameter for that reason -
# at N = 200 the p-value resolution is 1/201 = 0.005, still far below any alpha this project
# reads, while the run is several times cheaper. The value used is recorded in `notes` on
# every result, because a C3 p-value means something different at a different N.
N_NULL_SIM = 1000

_UNAVAILABLE = "R unavailable"


def rscript_path() -> str | None:
    """Absolute path to `Rscript`, or None. The only environment probe in the module."""
    return shutil.which("Rscript")


def r_library_paths() -> tuple[str, ...]:
    """The library paths a NON-vanilla `Rscript` would search, asked of R itself.

    Hard-coding `~/R/library` would bind the tool to one machine. Asking R keeps the answer
    correct wherever it runs, and `--vanilla` below then searches exactly what an ordinary
    `Rscript` would - the isolation `--vanilla` buys is from the user PROFILE, not from the
    installed packages.
    """
    executable = rscript_path()
    if executable is None:
        return ()
    completed = subprocess.run(
        [executable, "-e", "cat(paste(.libPaths(), collapse='\\n'))"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"could not ask Rscript for .libPaths(): exited {completed.returncode}\n"
            f"stderr: {completed.stderr.strip()}"
        )
    return tuple(line.strip() for line in completed.stdout.splitlines() if line.strip())


def _unavailable_result(
    segments: list[Segment], clock: str, note: str, statistic: float = float("nan")
) -> CheckResult:
    return CheckResult(
        check=CHECK_NAME,
        statistic=statistic,
        p_value=None,
        calibration=CALIB_R_COPULA,
        clock=clock,
        n_events=int(sum(len(s.x) for s in segments)),
        n_segments=len(segments),
        n_censored_dropped=int(sum(s.n_censored_dropped for s in segments)),
        notes=note,
    )


def _invoke_rscript(
    x: np.ndarray, max_lag: int, seed: int, timeout_s: float, n_null_sim: int
) -> tuple[float, float]:
    """Run the R script on `x` and return `(statistic, p_value)`.

    It is written to fail loudly rather than plausibly - a non-zero exit, a missing output
    file or an unparseable row all raise, so a run either produces a real number or a
    traceback, never a silently wrong p-value.

    **`--vanilla` needs `R_LIBS` handed to it explicitly.** `--vanilla` implies
    `--no-environ`, which drops `R_LIBS_USER` and therefore the user library from
    `.libPaths()`: measured here, plain `Rscript` sees `/home/sera/R/library` and
    `Rscript --vanilla` does not, so `copula` was invisible and every call raised. Keeping
    `--vanilla` is right for a reproducibility tool - it refuses the user profile and any
    side effect hiding in it - so the fix is to pass the search path as an explicit
    environment variable rather than to drop the flag. NOTE what this does and does not buy:
    the path becomes explicit at the call, but it is NOT written to any provenance artifact,
    so a run on a machine with a different library set is not distinguishable after the
    fact. Recording it is open work, not a property of this fix.
    """
    executable = rscript_path()
    if executable is None:
        raise RuntimeError("_invoke_rscript called without Rscript on PATH")
    env = dict(os.environ)
    env["R_LIBS"] = os.pathsep.join(r_library_paths())
    with tempfile.TemporaryDirectory(prefix="qre_c3_") as workdir:
        work = Path(workdir)
        in_path = work / "durations.csv"
        out_path = work / "result.csv"
        with in_path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["duration_s"])
            writer.writerows([[repr(float(v))] for v in x])
        completed = subprocess.run(
            [
                executable,
                "--vanilla",
                str(R_SCRIPT),
                str(in_path),
                str(out_path),
                str(int(max_lag)),
                str(int(n_null_sim)),
                str(int(seed)),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
            env=env,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"Rscript exited {completed.returncode} for {CHECK_NAME}.\n"
                f"stdout: {completed.stdout.strip()}\nstderr: {completed.stderr.strip()}"
            )
        if not out_path.exists():
            raise RuntimeError(
                f"Rscript exited 0 but wrote no result file for {CHECK_NAME}. "
                f"stdout: {completed.stdout.strip()}"
            )
        with out_path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
    if len(rows) != 1:
        raise RuntimeError(f"expected exactly one result row, got {len(rows)}")
    row = rows[0]
    try:
        return float(row["statistic"]), float(row["p_value"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"unparseable result row from R: {row!r}") from exc


def run(
    segments: list[Segment],
    *,
    clock: str = CLOCK_IN_SPEC,
    max_lag: int = MAX_LAG_CAP,
    seed: int = 0,
    timeout_s: float = 900.0,
    n_null_sim: int = N_NULL_SIM,
) -> CheckResult:
    """Serial independence via `copula::serialIndepTest`, over the R file bridge.

    `timeout_s` was 120.0 and that was too small to be honest. Measured on this machine
    with `N_NULL_SIM = 1000`, iid exponential input, `seed=1`: 3.9 s at n = 50, 14.7 s at
    n = 150, 130.2 s at n = 355. n = 355 alone overran the old default, so every such row
    silently became `declined:` once the ledger stopped raising.

    NO GROWTH EXPONENT IS CLAIMED. An earlier draft of this docstring said "roughly n^2.8";
    that number is not in the data. The three points give an OLS log-log slope of 1.76, and
    the pairwise slopes disagree with each other (1.21 from 50->150, 2.53 from 150->355), so
    three points do not determine a power law here. A separate run had n = 682 unfinished at
    580 s, which no fit through these points predicts - the cost also depends on the machine
    and on `N_NULL_SIM`. Measure it for the n you actually have.

    900 s covers every n the T2* ladder has produced so far with margin, and still fails
    fast rather than hanging a job forever. A row that exceeds it becomes `not computed`
    with the timeout recorded, which is the correct outcome; raise `timeout_s` at the call
    site if that row is wanted.
    """
    if not segments:
        raise ValueError("C3 needs at least one segment")
    for segment in segments:
        validate_segment(segment, require_strict_tau=False)

    if rscript_path() is None:
        return _unavailable_result(segments, clock, _UNAVAILABLE)
    if len(segments) > 1:
        return _unavailable_result(
            segments,
            clock,
            f"skipped: serialIndepTest has no multi-process form (m={len(segments)})",
        )

    x = concatenated_gaps(segments)
    n = int(sum(segment_sizes(segments)))
    if n <= max_lag + 1:
        return _unavailable_result(
            segments, clock, f"skipped: n={n} too short for lag.max={max_lag}"
        )

    statistic, p_value = _invoke_rscript(x, max_lag, seed, timeout_s, n_null_sim)
    return CheckResult(
        check=CHECK_NAME,
        statistic=statistic,
        p_value=p_value,
        calibration=CALIB_R_COPULA,
        clock=clock,
        n_events=n,
        n_segments=1,
        n_censored_dropped=int(sum(s.n_censored_dropped for s in segments)),
        notes=f"lag.max={max_lag} N={n_null_sim} seed={seed}",
    )
