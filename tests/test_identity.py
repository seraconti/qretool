"""Content identity (Increment 4).

Pins the fold's determinism and the composite→child folding that a later
identity-keyed reuse step will depend on: a composite's identity must change iff
one of its included sub-jobs' identities changes, and identity must be stable
across repeated builds (memoized) and independent of dict/insertion order.
"""

from __future__ import annotations

from pathlib import Path


from core.dataset import Dataset
from core.identity import Identity, fold
from core.job import Job

# --- fold encoder -----------------------------------------------------------


def test_fold_is_order_independent() -> None:
    assert fold({"a": "1", "b": "2"}) == fold({"b": "2", "a": "1"})


def test_fold_is_injective_under_adversarial_separators() -> None:
    # a value/key containing the old "k=v\n" separators must not collide with a
    # genuinely different mapping (this encoder becomes the reuse key later)
    assert fold({"a": "x", "b": "y"}) != fold({"a": "x\nb=y"})
    assert fold({"a": "b=c"}) != fold({"a": "b", "c": ""})


def test_fold_changes_with_any_value() -> None:
    base = fold({"code": "x", "data": "y"})
    assert base != fold({"code": "x", "data": "z"})
    # extending with a new key changes the digest (the extensibility seam)
    assert base != fold({"code": "x", "data": "y", "extra": "w"})


def test_identity_digest_reflects_each_contribution() -> None:
    base = Identity(code="c", data=(("d.csv", "h"),), children=("k",))
    assert (
        Identity(code="c2", data=(("d.csv", "h"),), children=("k",)).digest
        != base.digest
    )
    assert (
        Identity(code="c", data=(("d.csv", "h2"),), children=("k",)).digest
        != base.digest
    )
    assert (
        Identity(code="c", data=(("d.csv", "h"),), children=("k2",)).digest
        != base.digest
    )
    # same contributions => same digest (deterministic)
    assert (
        Identity(code="c", data=(("d.csv", "h"),), children=("k",)).digest
        == base.digest
    )


# --- Job.build_identity -----------------------------------------------------


def _standalone(tmp_path: Path, name: str, csv: str = "a,b\n1,2\n") -> Job:
    (tmp_path / f"{name}.csv").write_text(csv)
    job_py = tmp_path / f"{name}.py"
    job_py.write_text("# synthetic job\n")
    job = Job(name=name)
    node = job.load_df(Dataset(path=f"{name}.csv", schema=None))
    job.materialize(node, name="out")
    job.job_file = job_py.resolve()
    return job


def test_build_identity_is_memoized(tmp_path: Path) -> None:
    job = _standalone(tmp_path, "s")
    first = job.build_identity(tmp_path)
    assert job.build_identity(tmp_path) is first  # same cached object


def test_identity_stable_and_data_sensitive(tmp_path: Path) -> None:
    root_a = tmp_path / "a"
    root_a.mkdir()
    root_b = tmp_path / "b"
    root_b.mkdir()
    root_c = tmp_path / "c"
    root_c.mkdir()

    # identical source + identical dataset content in separate roots => same digest
    j_a = _standalone(root_a, "s")
    j_b = _standalone(root_b, "s")
    assert j_a.build_identity(root_a).digest == j_b.build_identity(root_b).digest

    # different dataset content => different digest (content-based, not path-based)
    j_c = _standalone(root_c, "s", csv="a,b\n9,9\n")
    assert j_c.build_identity(root_c).digest != j_a.build_identity(root_a).digest


def _composite_over(tmp_path: Path, sub_csv: str) -> Job:
    """A composite including one sub-job that loads sub.csv."""
    (tmp_path / "sub.csv").write_text(sub_csv)
    sub_py = tmp_path / "sub.py"
    sub_py.write_text(
        "from core.job import Job\n"
        "from core.dataset import Dataset\n"
        'job = Job(name="sub")\n'
        'node = job.load_df(Dataset(path="sub.csv", schema=None))\n'
        'job.materialize(node, name="panel")\n'
    )
    comp_py = tmp_path / "comp.py"
    comp_py.write_text("# composite\n")
    comp = Job(name="comp")
    inc = comp.include(sub_py, alias="s")
    comp.step(lambda x: x, inc.ref("panel"), name="use")
    comp.job_file = comp_py.resolve()
    return comp


def test_composite_identity_changes_iff_child_changes(tmp_path: Path) -> None:
    root1 = tmp_path / "r1"
    root1.mkdir()
    root2 = tmp_path / "r2"
    root2.mkdir()
    root3 = tmp_path / "r3"
    root3.mkdir()

    same_a = _composite_over(root1, "a,b\n1,2\n")
    same_b = _composite_over(root2, "a,b\n1,2\n")  # identical child data
    changed = _composite_over(root3, "a,b\n7,7\n")  # child dataset differs

    d_a = same_a.build_identity(root1).digest
    d_b = same_b.build_identity(root2).digest
    d_changed = changed.build_identity(root3).digest

    assert d_a == d_b  # identical children => identical composite identity
    assert d_a != d_changed  # a child's data change flips the composite identity
    # and the change propagates through the child's identity specifically
    assert same_a.includes[0].job.build_identity(root1).digest != (
        changed.includes[0].job.build_identity(root3).digest
    )
