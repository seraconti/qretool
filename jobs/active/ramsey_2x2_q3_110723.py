from __future__ import annotations

from core.dataset import Dataset
from core.job import Job
from jobs.common import configure_ramsey_job
from schemas.track912 import track912Schema

job = Job('ramsey_2x2_q3_110723')
configure_ramsey_job(
    job,
    Dataset(
        path='tool/datasets/2x2/110723_2x2_qubit3.pickle',
        schema=track912Schema,
        qubit=3,
        device='2x2',
        duration_h=17,
        extra={"run_name": 'q3_2x2_17h_1107_dataset'},
    ),
    profile='overnight',
    plot_mode='dedicated',
    include_fidelity=False,
    figure_prefix='q3_2x2_17h_1107_dataset',
)
