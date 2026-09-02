"""The instrument report: what licenses each statistical routine, as four figures.

P5's closing artifact. Every input is declared as a `Dataset` and loaded with
`job.load_df`, so each reference table's sha256 lands in `dataset_hashes` and in the run
identity - the same discipline `check_calibration.py` uses for the bench tables. A figure
here cannot silently be rebuilt against a regenerated fixture, and no pipeline module
imports `jobs/bench/` or `tests/`.

The four views answer four questions and are separate figures on purpose:

  tier matrix         which instrument has which evidence - the index for the other three
  published values    does our arithmetic reproduce the numbers the source PRINTS
  cross-implementation does it agree with an independent implementation of the same thing
  tie experiment      where does Chatterjee's xi stop being trustworthy under ties

WHAT IS NOT HERE. Power. None of these figures says an instrument can detect anything on a
short window; `bench/results/promotion_report.md` is where that lives, it scores four
checks and not five, and C3 and CvM have no bench cell at all.
"""

from __future__ import annotations

from quebra.analyzers.instrument_validation import build_instrument_validation
from quebra.core.dataset import Dataset
from quebra.core.job import Job
from quebra.plots.instrument_validation_plot import (
    CrossImplementationPlot,
    PublishedValuesPlot,
    TierMatrixPlot,
    TieExperimentPlot,
)

# SPEC 0005 R5.2/R5.4: the logical name and category. `include` resolves JOB_ID, so this
# file can move without breaking any composite; recategorising costs one string edit.
JOB_ID = "instrument_validation"
JOB_FAMILY = "validation"

PREFIX = "instrument_validation"

# Declared here, not defaulted in the builder, so both reach the provenance label.
DIVERGENCE_THRESHOLD = 0.02
# Must match `bench/xi_ties.N_PERM`. Passed explicitly rather than imported because nothing
# outside bench/ may import bench/ - see tests/test_bench_isolation.py.
N_PERM_IN_TIE_STUDY = 999
# Declared here, not defaulted in the builder: these two decide the three tier-3 numbers.
ASYMPTOTIC_SIZE_SEED = 777
ASYMPTOTIC_SIZE_TAU = 20.0

# Published source data and R reference values live in `jobs/reference/`, beside the
# jobs that declare them. They were in `tests/fixtures/` first, and `tests/` was
# gitignored, so a fixture there would not have survived a clone and this figure would
# have depended on a file no reviewer has.
LOAD_HAUL_DUMP = Dataset(path="jobs/reference/load_haul_dump.csv", schema=None)
LOAD_HAUL_DUMP_PUBLISHED = Dataset(
    path="jobs/reference/load_haul_dump_published.csv", schema=None
)
R_REFERENCE_INPUTS = Dataset(path="jobs/reference/r_reference_inputs.csv", schema=None)
R_REFERENCE_VALUES = Dataset(path="jobs/reference/r_reference_values.csv", schema=None)
TIE_EXPERIMENT = Dataset(path="jobs/bench/results/xi_tie_experiment.csv", schema=None)

job = Job(PREFIX)

_gaps = job.load_df(LOAD_HAUL_DUMP)
_published = job.load_df(LOAD_HAUL_DUMP_PUBLISHED)
_r_inputs = job.load_df(R_REFERENCE_INPUTS)
_r_values = job.load_df(R_REFERENCE_VALUES)
_ties = job.load_df(TIE_EXPERIMENT)

_report = job.step(
    build_instrument_validation,
    _gaps,
    _published,
    _r_inputs,
    _r_values,
    _ties,
    name="instrument_validation",
    divergence_threshold=DIVERGENCE_THRESHOLD,
    n_perm_in_tie_study=N_PERM_IN_TIE_STUDY,
    asymptotic_size_seed=ASYMPTOTIC_SIZE_SEED,
    asymptotic_size_tau=ASYMPTOTIC_SIZE_TAU,
)

job.materialize(_report, name=f"{PREFIX}_report")

job.figure(
    TierMatrixPlot,
    _report,
    targets=["static", "academic"],
    title=f"{PREFIX} tier matrix",
)
job.figure(
    PublishedValuesPlot,
    _report,
    targets=["static", "academic"],
    title=f"{PREFIX} published values",
)
job.figure(
    CrossImplementationPlot,
    _report,
    targets=["static", "academic"],
    title=f"{PREFIX} cross implementation",
)
job.figure(
    TieExperimentPlot,
    _report,
    targets=["static", "academic"],
    title=f"{PREFIX} tie experiment",
)
