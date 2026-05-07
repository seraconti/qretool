from __future__ import annotations

from core.dataset import Dataset
from core.job import Job
from jobs.common import configure_ramsey_job
from schemas.track912 import track912Schema
from transforms.lookup_prior import lookup_prior

job = Job('ramsey_q1_050423')
main_ds = Dataset(
    path='tool/datasets/6D2S/050423_6D2S_qubit1.pickle',
    schema=track912Schema,
    qubit=1,
    device='6D2S',
    duration_h=10,
    extra={"run_name": 'q1_10h_0504_dataset'},
)
comp_ds = Dataset(path='FOR ZENODO/Main/Fig 2/qubit1.pickle', schema=None)

main_node = job.load(main_ds)
comp_node = job.load_df(comp_ds)
enriched = job.step(
    lookup_prior,
    main_node,
    comp_node,
    fields=["frequency", "Rabi_frequency"],
    aliases={"frequency": "qubit_frequency"},
    name="lookup_prior",
)

configure_ramsey_job(
    job,
    enriched,
    profile='overnight',
    plot_mode='dedicated',
    include_fidelity=True,
    include_tlf=True,
    allan_fractional=True,
    allan_carrier_col='qubit_frequency',
    figure_prefix='q1_10h_0504_dataset',
)
