from __future__ import annotations

from core.dataset import Dataset
from core.job import Job
from jobs.common import configure_ramsey_job
from schemas.track912 import track912Schema

job = Job('ramsey_2x2_q1_200623')
configure_ramsey_job(
    job,
    Dataset(
        path='tool/datasets/2x2/200623_2x2_qubit1.pickle',
        schema=track912Schema,
        qubit=1,
        device='2x2',
        duration_h=14,
        extra={"run_name": 'q1_2x2_14h_2006_dataset'},
    ),
    profile='overnight',
    include_fidelity=False,
    figure_prefix='q1_2x2_14h_2006_dataset',
)
