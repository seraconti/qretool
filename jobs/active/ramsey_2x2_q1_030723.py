"""Archetype: 2x2-device Ramsey job.

Differs from the 6D2S Ramsey archetype in two ways, both deliberate:
  - No companion calibration file, so no lookup_prior: the 2x2 datasets carry no
    prior frequency/Rabi columns to enrich with.
  - configure_ramsey_job detects `device` starting with "2x2" and forces
    include_fidelity, include_tlf and allan_fractional off. Fidelity needs a Rabi
    drive frequency this device family does not supply. Passing include_fidelity=False
    here as well makes that explicit at the job level rather than implicit in common.
"""

from __future__ import annotations

from quebra.core.dataset import Dataset
from quebra.core.job import Job
from quebra.recipes import configure_ramsey_job
from quebra.schemas.track912 import track912Schema

PREFIX = "q1_2x2_16h_0307_dataset"

job = Job("ramsey_2x2_q1_030723")
main_ds = Dataset(
    path="data/real_private/2x2/030723_2x2_qubit1.pickle",
    schema=track912Schema,
    qubit=1,
    device="2x2",
    duration_h=16,
    extra={"run_name": PREFIX},
)

main_node = job.load(main_ds)

configure_ramsey_job(
    job,
    main_node,
    profile="overnight",
    include_fidelity=False,
    figure_prefix=PREFIX,
)
