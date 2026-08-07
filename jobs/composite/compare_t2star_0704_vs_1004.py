"""Archetype: composite job — overlay two sub-jobs' T2* panel data in one figure.

Composites live in jobs/composite/, not jobs/active/: main.py globs jobs/active for
`run --all`, so a composite would otherwise re-run its sub-jobs on every sweep. Run it
by path instead:

    PYTHONPATH=. python main.py run jobs/composite/compare_t2star_0704_vs_1004.py
    PYTHONPATH=. python main.py run jobs/composite/compare_t2star_0704_vs_1004.py --reuse-deps

`include` pulls each sub-job in and runs it through the normal runner, so its datasets
and provenance resolve exactly as a standalone run. Every figure sink's input is always
persisted, so `ref("t2star_panel_data")` reads that artifact back with no edit to the
sub-jobs. The two references become a two-input step; the composite's own provenance
graph click-throughs to each sub-job's graph.

This compares one qubit across two dates rather than two qubits — the mechanism is the
same, and both sub-jobs already exist as archetypes.
"""

from __future__ import annotations

import numpy as np

from core.job import Job
from panels.comparison import CompareNonRepairableData, CompareNonRepairablePanel
from panels.non_repairable import NonRepairablePanelData


def _compare_t2star(*panels: NonRepairablePanelData) -> CompareNonRepairableData:
    """Overlay each sub-job's T2* panel data as a labeled (t_h, primary_series)."""
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
        title="T2* comparison: qubit 1, 070423 vs 100423",
    )


job = Job("compare_t2star_0704_vs_1004")
d0704 = job.include("jobs/active/t2star_q1_070423.py", alias="d0704")
d1004 = job.include("jobs/active/t2star_q1_100423.py", alias="d1004")

_cmp = job.step(
    _compare_t2star,
    d0704.ref("t2star_panel_data"),
    d1004.ref("t2star_panel_data"),
    name="t2star_compare",
)
job.figure(
    CompareNonRepairablePanel,
    _cmp,
    targets=["static", "academic"],
    title="t2star 0704 vs 1004",
)
