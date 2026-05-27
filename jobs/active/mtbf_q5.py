from __future__ import annotations

import analyzers.mtbf as mtbf
from analyzers.mtbf import MtbfResult
from core.dataset import Dataset
from core.job import Job
from core.types import Norm
from panels.repairable import RepairablePanel, RepairablePanelData, make_mtbf_panel_data
from schemas.calibration_log import CalibrationLogSchema

job = Job("mtbf_q5")

ds = Dataset(
    path="FOR ZENODO/Supplementary/Sup fig 1/6D2S/6D2S_qubit5_freq_log.pickle",
    schema=CalibrationLogSchema,
    qubit=5,
    device="6D2S",
    extra={"run_name": "mtbf_q5"},
)

norm = job.load(ds)


def _run_mtbf(n: Norm) -> MtbfResult:
    return mtbf.run(mtbf.make_inputs_from_norm(n))


def _make_panel_data(result: MtbfResult) -> RepairablePanelData:
    return make_mtbf_panel_data(result)


mtbf_result = job.step(_run_mtbf, norm, name="mtbf")
panel_data = job.step(_make_panel_data, mtbf_result, name="mtbf_panel_data")
job.figure(RepairablePanel, panel_data, targets=["static", "academic"], title="mtbf_q5")
