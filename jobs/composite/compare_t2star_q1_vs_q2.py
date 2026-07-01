"""Composite job: compare T2* across two qubits/datasets in one figure.

Includes two standalone ramsey jobs and references each one's t2star panel-data
node (`t2star_panel_data`). Because the sub-jobs run in figures-as-materialize
mode (default `figures=False`), that node is persisted as a .pkl and read back
here — no edits to the sub-jobs are needed. Run with:

    python main.py run jobs/composite/compare_t2star_q1_vs_q2.py
    python main.py run jobs/composite/compare_t2star_q1_vs_q2.py --reuse-deps
"""

from __future__ import annotations

import numpy as np

from core.job import Job
from panels.comparison import CompareNonRepairableData, CompareNonRepairablePanel
from panels.non_repairable import NonRepairablePanelData


def _compare_t2star(*panels: NonRepairablePanelData) -> CompareNonRepairableData:
    """Overlay each sub-job's T2* panel-data as a labeled (t_h, primary_series) series."""
    series: list[tuple[str, np.ndarray, np.ndarray]] = []
    for pd_ in panels:
        label = (
            str(pd_.meta.get("dataset", pd_.primary_label))
            if pd_.meta
            else pd_.primary_label
        )
        series.append(
            (
                label,
                np.asarray(pd_.t_h, dtype=float),
                np.asarray(pd_.primary_series, dtype=float),
            )
        )
    return CompareNonRepairableData(
        series=series,
        x_label="Elapsed time (h)",
        y_label="T2* (µs)",
        title="T2* comparison: q1 vs q2",
    )


job = Job("compare_t2star_q1_vs_q2")
q1 = job.include("jobs/active/ramsey_q1_100423.py", alias="q1")  # qubit 1, 100423
q2 = job.include("jobs/active/ramsey_q2_210423.py", alias="q2")  # qubit 2, 210423

_cmp = job.step(
    _compare_t2star,
    q1.ref(job, "t2star_panel_data"),
    q2.ref(job, "t2star_panel_data"),
    name="t2star_compare",
)
job.figure(
    CompareNonRepairablePanel,
    _cmp,
    targets=["static", "academic"],
    title="t2star q1 vs q2",
)
