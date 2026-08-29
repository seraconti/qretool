"""The packaged fixtures must work for someone who has none of our data.

That is their whole reason to exist (SPEC 0003 R3.6), so these tests check the property a
reviewer depends on - the fixture is reachable from the installed package and runs the real
pipeline - rather than the numbers in it.
"""

from __future__ import annotations

import numpy as np
import pytest

import quebra.analyzers.t2star as t2star
from quebra._fixtures import FIXTURES, fixture_path
from quebra.core.dataset import Dataset
from quebra.core.job import _load_dataset


def test_every_declared_fixture_exists():
    for name in FIXTURES:
        assert fixture_path(name).is_file()


def test_an_unknown_fixture_is_refused_by_name():
    with pytest.raises(KeyError, match="unknown fixture"):
        fixture_path("no_such_file.csv")


def test_the_fixture_path_is_not_computed_from_the_source_tree():
    """It must come from the imported package, wherever that was installed."""
    import quebra._fixtures as module

    assert (
        fixture_path("ramsey_synthetic.csv").parent
        == module.fixture_path("ramsey_synthetic.csv").parent
    )


def test_the_ramsey_fixture_loads_through_the_default_normaliser():
    norm = _load_dataset(
        Dataset(
            path=fixture_path("ramsey_synthetic.csv"),
            qubit=1,
            device="synthetic",
            extra={"run_name": "ramsey_synthetic", "run_start_unix_s": 1.7e9},
        )
    )
    assert norm["t_rel_s"][0] == 0.0
    assert len(norm["t_rel_s"]) == 200
    assert "T2star_s" in norm and "T2star_error_s" in norm
    assert norm["meta"]["run_start_resolution"] == "explicit"


def test_the_ramsey_fixture_runs_the_real_t2star_analyzer():
    """The point of shipping it: a reviewer with no private data reaches a real result."""
    norm = _load_dataset(
        Dataset(
            path=fixture_path("ramsey_synthetic.csv"),
            qubit=1,
            extra={"run_start_unix_s": 1.7e9},
        )
    )
    result = t2star.run(t2star.make_inputs_from_norm(norm))
    assert len(result.frame) == 200
    assert np.all(result.frame["t2star_s"] > 0)


def test_the_fixture_carries_the_step_it_claims_to():
    """A fixture with no structure would let every downstream figure look correct while
    proving nothing, so the step is part of the contract, not an accident of the seed."""
    norm = _load_dataset(
        Dataset(
            path=fixture_path("ramsey_synthetic.csv"),
            qubit=1,
            extra={"run_start_unix_s": 1.7e9},
        )
    )
    t2 = np.asarray(norm["T2star_s"], dtype=float)
    before, after = t2[:130].mean(), t2[140:].mean()
    assert before - after > 8e-6, f"step not present: {before:.2e} -> {after:.2e}"
