"""Mean time between calibrations, 6D2S qubit 6 - the single-axes poster histogram.

The across-calibration archetype (the literature's repairable-system tier; see
panels/across_calibration.py): a calibration-event log read through
CalibrationLogSchema, with
inter-event intervals and nothing else. No thresholds, no window carving, no gap policy -
those belong to the within-calibration side.

This job differs from jobs/active/mtbf_q1.py in exactly two ways, both deliberate: it
renders ONE axes rather than the four-subplot AcrossCalibrationPanel, and it renders to the
poster target (high-resolution PNG) rather than to static/academic PDF. The binning is not
a third difference - `analyzers.mtbf.log_interval_histogram` is the one definition the
panel's histogram subplot also uses.

Qubit 6 pairs this figure with 090623 qubit 6, one of the two datasets on the companion
Kaplan-Meier figure (jobs/active/km_poster_6d2s.py).
"""

from __future__ import annotations

import quebra.analyzers.mtbf as mtbf
from quebra.analyzers.mtbf import IntervalHistogramResult, MtbfResult
from quebra.core.dataset import Dataset
from quebra.core.job import Job
from quebra.core.types import Norm
from quebra.plots.mtbc_hist_plot import MTBCHistogramPlot
from quebra.schemas.calibration_log import CalibrationLogSchema

# SPEC 0005 R5.2/R5.4: the logical name and category. `include` resolves JOB_ID, so this
# file can move without breaking any composite; recategorising costs one string edit.
JOB_ID = "mtbc_q6"
JOB_FAMILY = "interval"

PREFIX = "mtbc_q6"

job = Job(PREFIX)

ds = Dataset(
    path="data/real_private/calibration_logs/6D2S_qubit6_freq_log.pickle",
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
