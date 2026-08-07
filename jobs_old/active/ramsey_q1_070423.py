from __future__ import annotations

from core.dataset import Dataset
from core.job import Job
from jobs.common import RAMSEY_CONFIG, _filter_step, _final_stage, configure_ramsey_job
from schemas.track912 import track912Schema
from transforms.lookup_prior import lookup_prior
import analyzers.t2star as t2star
from analyzers.t2star import T2StarResult
from panels.non_repairable import NonRepairablePanel, NonRepairablePanelData

job = Job('ramsey_q1_070423')
main_ds = Dataset(
    path='tool/datasets/6D2S/070423_6D2S_qubit1.pickle',
    schema=track912Schema,
    qubit=1,
    device='6D2S',
    duration_h=27,
    extra={"run_name": 'q1_27h_0704_dataset'},
)
comp_ds = Dataset(path='FOR ZENODO/Main/Fig 2/qubit1.pickle', schema=None)

main_node = job.load(main_ds)
comp_node = job.load_df(comp_ds)
enriched = job.step(
    lookup_prior,
    main_node,
    comp_node,
    fields=["frequency", "Rabi_frequency"],
    aliases={"frequency": "qubit_frequency_hz", "Rabi_frequency": "rabi_hz"},
    name="lookup_prior",
)

configure_ramsey_job(
    job,
    enriched,
    profile='overnight',
    include_fidelity=True,
    include_tlf=True,
    allan_fractional=True,
    allan_carrier_col='qubit_frequency_hz',
    figure_prefix='q1_27h_0704_dataset',
)

# T2* thresholds for this dataset.
# Values match T2STAR_DEFAULT_LADDER; declared here explicitly
# so the threshold choice is visible at the job level.
# For devices outside the 1–10 µs T2* range, supply different values.
_T2STAR_THRESHOLDS: list[tuple[str, float, bool]] = [
    ("1 µs",  1e-6,  True),
    ("2 µs",  2e-6,  True),
    ("3 µs",  3e-6,  True),
    ("4 µs",  4e-6,  True),
    ("5 µs",  5e-6,  True),
    ("6 µs",  6e-6,  True),
    ("7 µs",  7e-6,  True),
    ("8 µs",  8e-6,  True),
    ("9 µs",  9e-6,  True),
    ("10 µs", 10e-6, True),
]

_t2star_filtered = job.step(_filter_step(RAMSEY_CONFIG), main_node, name="t2star_filter")
_t2star_final = job.step(_final_stage, _t2star_filtered, name="t2star_final_filter_stage")


def _t2star_run(norm: object) -> T2StarResult:
    return t2star.run(t2star.make_inputs_from_norm(norm))  # type: ignore[arg-type]


def _t2star_panel_data(result: T2StarResult) -> NonRepairablePanelData:
    return t2star.make_panel_data(result, thresholds=_T2STAR_THRESHOLDS)


_t2star_result = job.step(_t2star_run, _t2star_final, name="t2star")
_t2star_panel = job.step(_t2star_panel_data, _t2star_result, name="t2star_panel_data")
job.figure(
    NonRepairablePanel,
    _t2star_panel,
    targets=["static", "academic"],
    title="q1_27h_0704_dataset_t2star",
)
