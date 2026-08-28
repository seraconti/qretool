"""T2* within-calibration job for 070423_6D2S_qubit1 - carved from observed reads only.

Deliberately does NOT call configure_ramsey_job and has NO interpolate node. Windows
are carved from the filtered reads: the gap policy is meaningless on a uniform grid,
and an interpolated point is not an observation, so a window must never be built from
one. tests/test_windows_not_interpolated.py pins that as a property of the DAG.

gap_mult, k and use_uncertainty are step kwargs, not closure captures, so they appear
on the provenance label - the `allan` pattern, not the `filter` pattern.
"""

from __future__ import annotations

import quebra.analyzers.t2star as t2star
import quebra.analyzers.windows as windows
from quebra.analyzers.t2star import T2StarResult
from quebra.analyzers.windows import WindowsResult
from quebra.core.dataset import Dataset
from quebra.core.job import Job
from quebra.recipes import RAMSEY_CONFIG, XI_SEED, _filter_step, _final_stage
from quebra.panels.within_calibration import (
    WithinCalibrationPanel,
    WithinCalibrationPanelData,
)
from quebra.schemas.track912 import track912Schema

PREFIX = "q1_27h_0704_dataset"

job = Job("t2star_q1_070423")
main_ds = Dataset(
    path="tool/datasets/6D2S/070423_6D2S_qubit1.pickle",
    schema=track912Schema,
    qubit=1,
    device="6D2S",
    duration_h=27,
    extra={"run_name": PREFIX},
)

# T2* thresholds for this dataset, in SI seconds. Declared here so the ladder is
# visible at job level; devices outside the 1–10 µs range need their own.
_T2STAR_THRESHOLDS: list[tuple[str, float, bool]] = [
    ("1 µs", 1e-6, True),
    ("2 µs", 2e-6, True),
    ("3 µs", 3e-6, True),
    ("4 µs", 4e-6, True),
    ("5 µs", 5e-6, True),
    ("6 µs", 6e-6, True),
    ("7 µs", 7e-6, True),
    ("8 µs", 8e-6, True),
    ("9 µs", 9e-6, True),
    ("10 µs", 10e-6, True),
]


def _t2star_run(norm: object) -> T2StarResult:
    return t2star.run(t2star.make_inputs_from_norm(norm))  # type: ignore[arg-type]


def _windows_run(
    result: T2StarResult, gap_mult: float, k: float, use_uncertainty: bool
) -> WindowsResult:
    return windows.run(
        windows.make_inputs_from_frame(
            result.frame,
            time_col="t_rel_s",
            value_col="t2star_s",
            sigma_col="t2star_error_s" if use_uncertainty else None,
            thresholds=_T2STAR_THRESHOLDS,
            dataset_id=str(result.meta.get("dataset_id", "")),
            gap_mult=gap_mult,
            k=k,
            use_uncertainty=use_uncertainty,
        )
    )


def _t2star_panel_data(
    result: T2StarResult,
    window_result: WindowsResult,
    shape_min_reads: int,
    use_uncertainty: bool,
    xi_seed: int,
) -> WithinCalibrationPanelData:
    return t2star.make_panel_data(
        result,
        windows=window_result.windows,
        reads=window_result.reads,
        gap_spans_s=window_result.diagnostics.get("gap_spans_s"),
        thresholds=_T2STAR_THRESHOLDS,
        shape_min_reads=shape_min_reads,
        use_uncertainty=use_uncertainty,
        xi_seed=xi_seed,
    )


main_node = job.load(main_ds)
_filtered = job.step(_filter_step(RAMSEY_CONFIG), main_node, name="t2star_filter")
_final = job.step(_final_stage, _filtered, name="t2star_final_filter_stage")
_result = job.step(_t2star_run, _final, name="t2star")
_windows = job.step(
    _windows_run,
    _result,
    name="windows",
    gap_mult=10.0,
    k=1.0,
    use_uncertainty=True,
)
_panel = job.step(
    _t2star_panel_data,
    _result,
    _windows,
    name="t2star_panel_data",
    # Declared here, not defaulted in the builder, so both reach the provenance label.
    shape_min_reads=5,
    use_uncertainty=True,
    # The xi permutation null is only reproducible if its seed is an input, and it only
    # reaches the Mermaid label if it is declared HERE: runner.py builds that label from
    # node.kwargs, so an argument left to its default is invisible to provenance.
    xi_seed=XI_SEED,
)

job.materialize(_windows, name=f"{PREFIX}_windows")
job.figure(
    WithinCalibrationPanel,
    _panel,
    targets=["static", "academic"],
    title=f"{PREFIX}_t2star",
)
