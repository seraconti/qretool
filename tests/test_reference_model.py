"""Reference-model contract (the composite → sub-job resolution path).

Pins the two behaviors a later locator swap (identity-keyed reuse) must preserve:
  - a single ArtifactRef fed to several steps locates its sub-job once and emits
    one `includes` entry;
  - two separate ref() calls to the same sub-job node are two references, located
    independently, emitting two `includes` entries in first-seen order.
Also pins the structural facts: ref() returns an ArtifactRef (not a DAG node),
no alias__ name mangling, and step inputs reject non-References.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quebra.core.job import Job
from quebra.core.reference import ArtifactRef
from quebra.core.runner import run_job

_SUB_SRC = (
    "from quebra.core.job import Job\n"
    "from quebra.core.dataset import Dataset\n"
    'job = Job(name="{name}")\n'
    'node = job.load_df(Dataset(path="data.csv", schema=None))\n'
    'job.materialize(node, name="panel_data")\n'
)


def _passthrough(*xs: object) -> object:
    return xs[0]


def _write_common(tmp_path: Path) -> None:
    (tmp_path / "data.csv").write_text("a,b\n1,2\n3,4\n")


def _composite(tmp_path: Path, name: str) -> tuple[Job, Path]:
    comp_py = tmp_path / f"{name}.py"
    comp_py.write_text("# synthetic composite job file\n")
    job = Job(name=name)
    job.job_file = comp_py.resolve()
    return job, comp_py


def _sub(tmp_path: Path, name: str) -> Path:
    p = tmp_path / f"{name}.py"
    p.write_text(_SUB_SRC.format(name=name))
    return p


def _includes(out: Path, job_name: str) -> list[dict]:
    run_dir = next(out.glob(f"{job_name}_*"))
    rec = json.loads((run_dir / "provenance" / "reused_out.prov.json").read_text())
    return rec["includes"]


def test_ref_returns_artifactref_not_a_node(tmp_path: Path) -> None:
    _write_common(tmp_path)
    job, _ = _composite(tmp_path, "c_refshape")
    inc = job.include(_sub(tmp_path, "s_shape"), alias="s")
    ref = inc.ref("panel_data")
    assert isinstance(ref, ArtifactRef)
    assert ref.node_name == "panel_data"
    # no composite node was registered for the reference
    assert job.dag == {}


def test_step_rejects_non_reference_input(tmp_path: Path) -> None:
    job, _ = _composite(tmp_path, "c_badinput")
    with pytest.raises(TypeError, match="must be References"):
        job.step(_passthrough, "not-a-ref", name="bad")


def test_step_rejects_reserved_load_node_fn_names() -> None:
    # The runner and build_identity classify nodes by fn.__name__, so a user
    # step named like an internal loader would be silently misclassified.
    def _load_dataset() -> None:
        pass

    job = Job(name="t_reserved")
    with pytest.raises(ValueError, match="reserved for internal"):
        job.step(_load_dataset, name="whatever")


def test_one_ref_two_steps_locates_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_common(tmp_path)
    job, _ = _composite(tmp_path, "c_oneref")
    inc = job.include(_sub(tmp_path, "s_one"), alias="s")
    ref = inc.ref("panel_data")  # ONE ArtifactRef object...
    a = job.step(_passthrough, ref, name="a")  # ...fed to two steps
    b = job.step(_passthrough, ref, name="b")
    reused = job.step(_passthrough, a, b, name="reused")
    job.materialize(reused, "reused_out")
    # real node ids exist now: none may carry alias__ mangling
    assert not any("__" in node_id for node_id in job.dag)

    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out"
    run_job(job, out, force=True, data_root=tmp_path)

    incs = _includes(out, "c_oneref")
    assert len(incs) == 1  # located once despite two consumers
    # the sub-job ran exactly once (one nested run dir)
    nested = list((out).glob("c_oneref_*/subjobs_output/s_one_*"))
    assert len(nested) == 1


def test_two_refs_two_includes_in_first_seen_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_common(tmp_path)
    job, _ = _composite(tmp_path, "c_tworef")
    inc = job.include(_sub(tmp_path, "s_two"), alias="s")
    r1 = inc.ref("panel_data")
    r2 = inc.ref("panel_data")  # distinct ArtifactRef => distinct locate
    reused = job.step(_passthrough, r1, r2, name="reused")
    job.materialize(reused, "reused_out")

    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out"
    run_job(job, out, force=True, data_root=tmp_path)

    incs = _includes(out, "c_tworef")
    assert len(incs) == 2  # two refs => two entries
    assert [i["node_name"] for i in incs] == ["panel_data", "panel_data"]
