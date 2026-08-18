"""Mean time between calibrations, 6D2S qubit 6 - the single-axes poster histogram.

The repairable archetype: a calibration-event log read through CalibrationLogSchema, with
inter-event intervals and nothing else. No thresholds, no window carving, no gap policy -
those belong to the non-repairable side.

This job differs from jobs/active/mtbf_q1.py in exactly two ways, both deliberate: it
renders ONE axes rather than the four-subplot RepairablePanel, and it renders to the
poster target (high-resolution PNG) rather than to static/academic PDF. The binning is not
a third difference - `analyzers.mtbf.log_interval_histogram` is the one definition the
panel's histogram subplot also uses.

Qubit 6 pairs this figure with 090623 qubit 6, one of the two datasets on the companion
Kaplan-Meier figure (jobs/active/km_poster_6d2s.py).
"""

from __future__ import annotations

import analyzers.mtbf as mtbf
from analyzers.mtbf import IntervalHistogramResult, MtbfResult
from core.dataset import Dataset
from core.job import Job
from core.types import Norm
from plots.mtbc_hist_plot import MTBCHistogramPlot
from schemas.calibration_log import CalibrationLogSchema

PREFIX = "mtbc_q6"

job = Job(PREFIX)

ds = Dataset(
    path="FOR ZENODO/Supplementary/Sup fig 1/6D2S/6D2S_qubit6_freq_log.pickle",
    schema=CalibrationLogSchema,
    qubit=6,
    device="6D2S",
    extra={"run_name": PREFIX},
)


def _run_mtbf(norm: Norm) -> MtbfResult:
    return mtbf.run(mtbf.make_inputs_from_norm(norm))


def _histogram(result: MtbfResult, label: str, n_bins: int) -> IntervalHistogramResult:
    return mtbf.make_interval_histogram(result, label=label, n_bins=n_bins)


_norm = job.load(ds)
_mtbf = job.step(_run_mtbf, _norm, name="mtbf")
_hist = job.step(
    _histogram,
    _mtbf,
    name="interval_histogram",
    # Declared here rather than left to the builder's default, so both reach the
    # provenance label: the bin count changes what the figure shows.
    label="qubit 6",
    n_bins=50,
)

job.materialize(_hist, name=f"{PREFIX}_interval_histogram")
job.figure(
    MTBCHistogramPlot,
    _hist,
    targets=["poster"],
    title=f"{PREFIX}_histogram",
)
