"""Every column of the file, as an array, with no requirements at all.

The schema to reach for when you have not written one yet: it asks nothing of your data and
imposes no vocabulary on it, so a first job can be four lines and still go through `job.load`
and produce a `Norm` like every other job.

It is not the default. `Dataset.schema=None` runs `RamseySeriesSchema`; `NullSchema` has to
be asked for by name.

An earlier version of this note claimed ten in-repo jobs depend on that default. They do not:
every `job.load` site in `jobs/` names `track912Schema` or `CalibrationLogSchema`, and only
`tests/test_windows_not_interpolated.py` reaches the default. What the job files actually
rely on is the FALLTHROUGH - a `validate` schema cleans the frame and `RamseySeriesSchema`
then produces the `Norm` - which is a different guarantee and the one worth not breaking.
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
        # Duplicate labels make `frame[column]` a DataFrame, so the "array" stored would be
        # 2-D and every downstream step would silently see the wrong shape. `str(column)`
        # below can also collapse two distinct labels (`0` and `"0"`) onto one key, losing a
        # column with no error. Both are refused rather than guessed at.
        if frame.columns.duplicated().any():
            duplicated = sorted(
                {str(c) for c in frame.columns[frame.columns.duplicated()]}
            )
            raise ValueError(
                f"NullSchema cannot pass through duplicate column labels {duplicated}: the "
                f"Norm stores one array per name and the duplicate would arrive 2-D. Rename "
                f"them, or write a schema that maps each explicitly."
            )
        labels = [str(column) for column in frame.columns]
        if len(set(labels)) != len(labels):
            raise ValueError(
                f"NullSchema cannot pass through column labels that collide as strings "
                f"({labels}): one would silently replace the other."
            )
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
