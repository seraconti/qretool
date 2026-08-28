"""Every column of the file, as an array, with no requirements at all.

The schema to reach for when you have not written one yet: it asks nothing of your data and
imposes no vocabulary on it, so a first job can be four lines and still go through `job.load`
and produce a `Norm` like every other job.

It is not the default. `Dataset.schema=None` runs `RamseySeriesSchema`, which ten in-repo
jobs depend on; `NullSchema` has to be asked for by name.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from quebra.core.dataset import Dataset
from quebra.core.types import Norm


class NullSchema:
    """`to_norm` that copies each column into the `Norm` under its own name.

    Column dtypes are left alone - a text column arrives as a text array. Steps that expect
    numbers should say so, rather than this guessing which columns are meant to be numeric.
    """

    @classmethod
    def to_norm(cls, frame: pd.DataFrame, dataset: Dataset) -> Norm:
        if "meta" in frame.columns:
            raise ValueError(
                "NullSchema cannot pass through a column named 'meta': the Norm reserves "
                "that key for run metadata. Rename the column, or write a schema that maps "
                "it explicitly (see docs/WRITING_A_SCHEMA.md)."
            )
        norm = Norm(
            {
                "meta": {
                    "dataset_id": str(
                        dataset.extra.get("run_name", Path(dataset.path).stem)
                    ),
                    **dataset.extra,
                }
            }
        )
        for column in frame.columns:
            norm[str(column)] = frame[column].to_numpy()
        return norm
