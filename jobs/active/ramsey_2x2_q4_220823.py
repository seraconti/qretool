from __future__ import annotations

from core.dataset import Dataset
from core.job import Job
from jobs.common import configure_ramsey_job
from schemas.track912 import track912Schema

job = Job('ramsey_2x2_q4_220823')
configure_ramsey_job(
    job,
    Dataset(
        path='tool/datasets/2x2/220823_2x2_qubit4.pickle',
        schema=track912Schema,
        qubit=4,
        device='2x2',
        duration_h=15,
        extra={"run_name": 'q4_2x2_15h_2208_dataset'},
    ),
    profile='overnight',
    include_fidelity=False,
    figure_prefix='q4_2x2_15h_2208_dataset',
)
