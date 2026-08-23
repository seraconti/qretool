"""Staleness guard for materialized panel-data artifacts (Increment 2.5a).

A pre-split pickle restores __dict__ without the derived fields; the guard must
fail loudly at the pickle boundary instead of crashing mid-render or silently
drawing class defaults. Synthetic tests drive __setstate__ exactly as pickle
protocol 2 does (``cls.__new__(cls)`` then ``__setstate__(state)``); the
real-artifact test exercises the actual pickle.load path end-to-end.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")

from analyzers import windows
from panels._within_calibration_compute import build_within_calibration_panel_data
from panels._across_calibration_compute import build_across_calibration_panel_data
from panels.within_calibration import WithinCalibrationPanelData
from panels.across_calibration import AcrossCalibrationPanelData

REPO_ROOT = Path(__file__).resolve().parents[1]


def _carved(t_h, series, thresholds):
    """Carve through the real analyzer, as a job does.

    The builder no longer carves: it consumes the window and read tables, so a test
    that constructs panel data has to produce them the same way production does.
    """
    result = windows.run(
        windows.WindowsInputs(
            t_rel_s=np.asarray(t_h, dtype=float) * 3600.0,
            values=np.asarray(series, dtype=float),
            thresholds=thresholds,
            dataset_id="unit",
        )
    )
    return result.windows, result.reads


_GUARD_THRESHOLDS = [("1e-4", 1e-4, False)]


def _valid_within_calibration() -> WithinCalibrationPanelData:
    rng = np.random.default_rng(7)
    t_h = np.linspace(0.0, 12.0, 200)
    series = 1e-5 + 1e-5 * rng.random(200)
    return build_within_calibration_panel_data(
        t_h=t_h,
        primary_series=series,
        primary_label="Infidelity",
        thresholds=_GUARD_THRESHOLDS,
        meta={"qubit": "1"},
        windows=_carved(t_h, series, _GUARD_THRESHOLDS)[0],
        reads=_carved(t_h, series, _GUARD_THRESHOLDS)[1],
    )


def _valid_across_calibration() -> AcrossCalibrationPanelData:
    rng = np.random.default_rng(8)
    ev = 1.6e9 + np.cumsum(rng.gamma(2.0, 3600.0, 60))
    iv = np.diff(ev)
    ev = ev[1:]
    return build_across_calibration_panel_data(
        intervals_s=iv,
        event_times_unix_s=ev,
        stats={
            "count": int(len(iv)),
            "mean_s": float(np.mean(iv)),
            "std_s": float(np.std(iv)),
            "min_s": float(np.min(iv)),
            "max_s": float(np.max(iv)),
        },
        meta={"qubit": "2", "device": "6D2S", "dataset_id": "unit"},
    )


@pytest.mark.parametrize(
    ("cls", "make", "derived_field"),
    [
        (WithinCalibrationPanelData, _valid_within_calibration, "distinguish"),
        (AcrossCalibrationPanelData, _valid_across_calibration, "elapsed_days"),
    ],
)
def test_stale_state_raises(cls, make, derived_field) -> None:
    state = dict(make().__dict__)
    del state[derived_field]
    obj = cls.__new__(cls)
    with pytest.raises(ValueError, match="stale .* artifact"):
        obj.__setstate__(state)


def test_missing_cv_alone_raises() -> None:
    # cv used to be a plain class default: a stale instance silently drew CV=nan.
    # With default_factory + the guard, its absence must raise like any field. It now
    # lives on the signal band, so this exercises the NESTED guard.
    band = _valid_within_calibration().signal
    state = dict(band.__dict__)
    del state["cv"]
    obj = type(band).__new__(type(band))
    with pytest.raises(ValueError, match="cv"):
        obj.__setstate__(state)


def test_nested_band_guard_fires_on_a_stale_band() -> None:
    """The whole point of making every band inherit the guard.

    StaleArtifactGuard derives its key set from dataclasses.fields(cls), so the OUTER
    class only ever validates {signal, distinguish, reliability, meta, ...}. A band
    missing half its fields would load clean unless the band guards itself.
    """
    obj = _valid_within_calibration()
    blob = pickle.dumps(obj)
    # rename `occupancy` inside the reliability band's pickled state
    tampered = blob.replace(b"\x8c\toccupancy", b"\x8c\toccupanZy")
    assert tampered != blob, "fixture did not contain the expected pickled key"
    with pytest.raises(ValueError, match="stale ReliabilityBand artifact"):
        pickle.loads(tampered)


def test_outer_guard_alone_would_not_catch_it() -> None:
    """Documents WHY the per-band guards exist: the outer key set is only four names."""
    import dataclasses

    outer_fields = {f.name for f in dataclasses.fields(WithinCalibrationPanelData)}
    assert "occupancy" not in outer_fields
    assert {"signal", "distinguish", "reliability"} <= outer_fields


@pytest.mark.parametrize("make", [_valid_within_calibration, _valid_across_calibration])
def test_builder_pickle_round_trip(make) -> None:
    obj = make()
    loaded = pickle.loads(pickle.dumps(obj))
    assert type(loaded) is type(obj)
    assert set(loaded.__dict__) == set(obj.__dict__)


def test_non_dict_state_raises() -> None:
    # a slots=True dataclass would pickle state as (dict, slots_dict); the guard
    # must answer with its own error, not AttributeError on .keys()
    obj = WithinCalibrationPanelData.__new__(WithinCalibrationPanelData)
    with pytest.raises(ValueError, match="unexpected pickle state"):
        obj.__setstate__(({}, {"x": 1}))


class _StalePickle:
    """Pickles into <cls> + a partial state dict - byte-wise what a pre-split
    artifact looks like on load (object.__new__ then __setstate__)."""

    def __init__(self, cls: type, state: dict) -> None:
        self.cls, self.state = cls, state

    def __reduce__(self):
        return (object.__new__, (self.cls,), self.state)


def _identity(x: object) -> object:
    return x


def _import_job_module(job_py: Path):
    # delegate to the real CLI loader so this test tracks its behavior
    from main import _module_from_path

    return _module_from_path(job_py).job


def test_composite_reuse_of_reuse_eligible_stale_artifact_aborts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defense-in-depth: even a cached sub-job artifact that PASSES the reuse gate
    (matching identity + commit, clean tree) must abort at load if its pickle is
    schema-stale - the guard, not a mid-render crash. Requires seeding the cache
    dir by the sub-job's IDENTITY and forcing a clean tree so the gate admits it."""
    from core.dataset import Dataset  # noqa: F401  (sub-job module imports it)
    from core.job import Job
    from core import runner
    from core.runner import run_job
    from provenance import get_git_commit

    sub_py = tmp_path / "tiny_sub.py"
    sub_py.write_text(
        "from core.job import Job\n"
        "from core.dataset import Dataset\n"
        'job = Job(name="tiny_sub")\n'
        'node = job.load_df(Dataset(path="data.csv", schema=None))\n'
        'job.materialize(node, name="panel_data")\n'
    )
    (tmp_path / "data.csv").write_text("a,b\n1,2\n")
    out = tmp_path / "out"

    # the sub-job's real identity names its cache dir; seed a prov record whose
    # identity + commit MATCH this run so the gate admits it, plus a stale pickle
    sub_identity = _import_job_module(sub_py).build_identity(tmp_path).digest
    cached = out / f"tiny_sub_{sub_identity[:6]}_20200101_000000"
    (cached / "provenance").mkdir(parents=True)
    with (cached / "panel_data.pkl").open("wb") as fh:
        pickle.dump(_StalePickle(WithinCalibrationPanelData, {"t_h": None}), fh)
    (cached / "provenance" / "panel_data.prov.json").write_text(
        json.dumps(
            {
                "identity": sub_identity,
                "git_commit": get_git_commit(),
                "tree_clean": True,
            }
        )
    )
    # force the clean-tree half of the gate (the real repo tree is dirty in dev)
    monkeypatch.setattr(runner, "is_tree_clean", lambda: True)

    comp_py = tmp_path / "tiny_comp.py"
    comp_py.write_text("# synthetic composite job file\n")
    comp = Job(name="tiny_comp")
    inc = comp.include(sub_py, alias="s1")
    node = comp.step(_identity, inc.ref("panel_data"), name="reused")
    comp.materialize(node, name="reused_out")
    comp.job_file = comp_py.resolve()

    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="stale WithinCalibrationPanelData"):
        run_job(comp, out, force=True, data_root=tmp_path, reuse_deps=True)


def test_real_pre_split_artifact_raises() -> None:
    """The actual pre-split artifacts on disk must fail to load, one way or the other.

    TWO failure modes now, and the second one is a deliberate, accepted loss.

    `ValueError` is the guard working as designed: the artifact loaded, its field names
    did not match the current contract, and `StaleArtifactGuard` said so.

    `ModuleNotFoundError` is the vocabulary rename of 2026-08-23. Artifacts written before
    it name `panels.non_repairable.NonRepairablePanelData` in their pickle stream, and that
    module no longer exists. 77 pickles under `output/` and `output_backup*/` are affected,
    plus 5 naming `panels.repairable`. A compatibility shim would not have helped: the
    MODULE is gone, not just the symbol, so `pickle.load` fails before any re-export could
    be consulted. Recovering them means re-running the jobs that wrote them.

    This is recorded rather than hidden because `output/` is append-only and those
    artifacts are evidence. They are not recoverable by editing code; they are recovered by
    re-running the jobs that produced them, which is the accepted plan.

    Post-rename artifacts in the same locations must still load cleanly. Skips if no
    pre-split artifact exists (a fresh checkout has none).
    """
    candidates = [
        p
        for root in ("output", "output_backup2")
        for p in (REPO_ROOT / root).glob("*/subjobs_output/*/t2star_panel_data.pkl")
    ]
    stale_errors: list[str] = []
    for pkl in candidates:
        try:
            with pkl.open("rb") as fh:
                obj = pickle.load(fh)
        except ValueError as exc:
            assert "stale" in str(exc) and "--reuse-deps" in str(exc)
            stale_errors.append(str(exc))
        except (ModuleNotFoundError, AttributeError) as exc:
            # The rename. Assert it is THAT module and not some unrelated import error,
            # or this clause would swallow a genuine packaging break.
            assert "non_repairable" in str(exc) or "repairable" in str(exc), exc
            stale_errors.append(str(exc))
        else:
            assert isinstance(obj, WithinCalibrationPanelData)
    if not stale_errors:
        pytest.skip("no pre-split artifact present on this machine")
