"""`job.load` must be generic: a schema decides the shape, not the runtime.

Three defects prompted this file, all of them invisible in-repo because every caller that
used `Dataset.extra` also used a `.pickle` path, and `_load_pickle` discards the dict it is
handed. A user with a CSV hit all three on their first job.

1. `Dataset.extra` was forwarded to the loader AND read back as run metadata. On CSV that
   meant `pd.read_csv(path, **extra)`, so setting `extra['run_start_unix_s']` - the fix
   `_load_dataset`'s own error message recommends - raised `unexpected keyword argument`.
2. `int(dataset.qubit)` ran unconditionally, above the schema dispatch, so `qubit=None`
   died with `int() argument must be...` naming neither `qubit` nor `Dataset`, and a
   `to_norm` schema that never looks at a qubit still had to declare one.
3. The `timestamp`/`frequency` requirement and the run-start resolution were hardcoded into
   the generic path, so `job.load` was the Ramsey pipeline wearing a generic name.

The equivalence of the moved normaliser against the pre-refactor implementation was checked
separately on four real 6D2S records (three `Norm` shapes, 7 keys each, arrays compared
elementwise) and is not re-checked here - these tests are about the CONTRACT, and they run
without any private dataset.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quebra.core.dataset import Dataset
from quebra.core.job import _load_dataset
from quebra.core.types import Norm
from quebra.schemas.ramsey_series import RamseySeriesSchema


class _ShapelessSchema:
    """A `to_norm` schema for data with no timestamp, no frequency and no qubit.

    This is the case the old code could not express at all, which is the point of it.
    """

    @classmethod
    def to_norm(cls, frame: pd.DataFrame, dataset: Dataset) -> Norm:
        return Norm(
            {
                "day": frame["day"].to_numpy(dtype=float),
                "reading": frame["reading"].to_numpy(dtype=float),
                "meta": {"dataset_id": "shapeless", **dataset.extra},
            }
        )


@pytest.fixture
def semicolon_csv(tmp_path):
    """Semicolon-separated on purpose: it can only be read via `loader_kwargs`."""
    path = tmp_path / "readings.csv"
    path.write_text("day;reading\n1;3.1\n2;3.4\n3;2.9\n")
    return path


def test_a_job_with_no_qubit_and_no_ramsey_columns_can_use_load(semicolon_csv):
    """The headline claim. Every element here was previously fatal."""
    norm = _load_dataset(
        Dataset(
            path=semicolon_csv,
            schema=_ShapelessSchema,
            loader_kwargs={"sep": ";"},
            extra={"run_name": "demo"},
        )
    )
    assert np.array_equal(norm["day"], [1.0, 2.0, 3.0])
    assert norm["meta"]["run_name"] == "demo"


def test_extra_does_not_reach_the_file_reader(semicolon_csv):
    """Defect 1. `run_start_unix_s` is metadata; sending it to `read_csv` is a TypeError."""
    norm = _load_dataset(
        Dataset(
            path=semicolon_csv,
            schema=_ShapelessSchema,
            loader_kwargs={"sep": ";"},
            extra={"run_start_unix_s": 1.7e9},
        )
    )
    assert norm["meta"]["run_start_unix_s"] == 1.7e9


def test_loader_kwargs_do_reach_the_file_reader(semicolon_csv):
    """The other half: the split is only correct if `loader_kwargs` still works.

    Without `sep=';'` pandas reads one column named `day;reading` and the schema raises
    KeyError, so this genuinely exercises the forwarding rather than asserting a default.
    """
    with pytest.raises(KeyError):
        _load_dataset(Dataset(path=semicolon_csv, schema=_ShapelessSchema))


def test_qubit_is_optional_and_is_not_injected_when_absent(semicolon_csv):
    """Defect 2, checked at the column level rather than by absence of an exception."""
    seen: dict[str, list[str]] = {}

    class _Capture:
        @classmethod
        def to_norm(cls, frame, dataset):
            seen["columns"] = list(frame.columns)
            return Norm({"meta": {}})

    _load_dataset(
        Dataset(path=semicolon_csv, schema=_Capture, loader_kwargs={"sep": ";"})
    )
    assert "qubit_id" not in seen["columns"]
    assert "device" not in seen["columns"]

    _load_dataset(
        Dataset(
            path=semicolon_csv,
            schema=_Capture,
            loader_kwargs={"sep": ";"},
            qubit=4,
            device="6D2S",
        )
    )
    assert seen["columns"][-2:] == ["qubit_id", "device"]


def test_the_default_normaliser_still_applies_when_no_schema_is_given(tmp_path):
    """`schema=None` means the DEFAULT normaliser, not "no normalisation".

    Pinning this matters both ways: it is the behaviour ten in-repo call sites rely on,
    and it is the behaviour the docs must not describe as "no validation".
    """
    path = tmp_path / "070423_run.csv"
    path.write_text("timestamp,frequency\n0,5.1\n1,5.3\n2,5.2\n")
    norm = _load_dataset(Dataset(path=path, qubit=1))
    assert np.array_equal(norm["t_rel_s"], [0.0, 1.0, 2.0])
    assert norm["meta"]["run_start_resolution"] == "date_only_midnight"


def test_the_default_normaliser_names_itself_and_the_way_out(semicolon_csv):
    """A wrong-shape error must point somewhere. The old one said only that the dataset
    "must contain 'timestamp' and 'frequency' columns", which reads as a hard requirement
    of the tool rather than of one replaceable schema."""
    with pytest.raises(KeyError) as excinfo:
        _load_dataset(Dataset(path=semicolon_csv, loader_kwargs={"sep": ";"}, qubit=1))
    message = str(excinfo.value)
    assert "RamseySeriesSchema" in message
    assert "to_norm" in message and "load_df" in message


def test_an_object_that_is_not_a_schema_is_rejected_by_name(semicolon_csv):
    """Previously an object with neither method fell through to the Ramsey path and failed
    with a column error, blaming the data for a mistake in the schema argument."""
    with pytest.raises(TypeError, match="not a usable schema"):
        _load_dataset(
            Dataset(path=semicolon_csv, schema=object(), loader_kwargs={"sep": ";"})
        )


def test_the_ramsey_normaliser_is_importable_and_is_what_load_defaults_to(tmp_path):
    """The default must be a named, replaceable object rather than inlined runtime code -
    that is the whole difference between this and the previous design."""
    path = tmp_path / "070423_run.csv"
    path.write_text("timestamp,frequency\n0,5.1\n1,5.3\n2,5.2\n")
    dataset = Dataset(path=path, qubit=1)
    direct = RamseySeriesSchema.to_norm(pd.read_csv(path), dataset)
    viaload = _load_dataset(dataset)
    assert np.array_equal(direct["t_rel_s"], viaload["t_rel_s"])
    assert np.array_equal(direct["delta_hz"], viaload["delta_hz"])


def test_null_schema_passes_every_column_through(semicolon_csv):
    """The four-line-job case: no requirements on the data at all."""
    from quebra.schemas.null import NullSchema

    norm = _load_dataset(
        Dataset(path=semicolon_csv, schema=NullSchema, loader_kwargs={"sep": ";"})
    )
    assert np.array_equal(norm["reading"], [3.1, 3.4, 2.9])
    assert list(norm["day"]) == [1, 2, 3]
    assert norm["meta"]["dataset_id"] == "readings"


def test_null_schema_keeps_non_numeric_columns_as_they_are(tmp_path):
    """Guessing which columns are meant to be numeric would be the wrong kind of helpful."""
    from quebra.schemas.null import NullSchema

    path = tmp_path / "labelled.csv"
    path.write_text("label,value\na,3.1\nb,3.4\n")
    norm = _load_dataset(Dataset(path=path, schema=NullSchema))
    assert list(norm["label"]) == ["a", "b"]
    assert np.array_equal(norm["value"], [3.1, 3.4])


def test_null_schema_refuses_a_column_that_would_shadow_meta(tmp_path):
    """`meta` is the one reserved key; silently overwriting it would lose provenance."""
    from quebra.schemas.null import NullSchema

    path = tmp_path / "clash.csv"
    path.write_text("meta,value\nx,3.1\n")
    with pytest.raises(ValueError, match="column named 'meta'"):
        _load_dataset(Dataset(path=path, schema=NullSchema))
