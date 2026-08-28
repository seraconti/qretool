"""Archetype: full Ramsey job - Allan, fidelity and TLF via configure_ramsey_job.

One of four representative jobs kept in jobs/active. The rest of the historical fleet
lives in jobs_old/ as reference only; those files predate the current contracts and do
not run. Iterate on this file, then fan it out.

Shape: load -> lookup_prior (enrich with calibration frequencies) -> configure_ramsey_job.
`configure_ramsey_job` owns the filter/interpolate/Allan/fidelity/TLF wiring; the
threshold ladder and window carving belong to the t2star archetype, not here.
"""

from __future__ import annotations

from quebra.core.dataset import Dataset
from quebra.core.job import Job
from quebra.recipes import configure_ramsey_job
from quebra.schemas.track912 import track912Schema
from quebra.transforms.lookup_prior import lookup_prior

PREFIX = "q1_13h_1004_dataset"

job = Job("ramsey_q1_100423")
main_ds = Dataset(
    path="tool/datasets/6D2S/100423_6D2S_qubit1.pickle",
    schema=track912Schema,
    qubit=1,
    device="6D2S",
    duration_h=13,
    extra={"run_name": PREFIX},
)
comp_ds = Dataset(path="FOR ZENODO/Main/Fig 2/qubit1.pickle", schema=None)

main_node = job.load(main_ds)
comp_node = job.load_df(comp_ds)

# Source columns keep their published names and map to the canonical unit-suffixed
# keys the analyzers expect.
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
    profile="overnight",
    include_fidelity=True,
    include_tlf=True,
    allan_fractional=True,
    allan_carrier_col="qubit_frequency_hz",
    figure_prefix=PREFIX,
)
