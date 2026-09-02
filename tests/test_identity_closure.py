"""Identity must cover the code that produced the numbers.

`job_code_hash` over the job file alone would leave `t2star_q1_070423`'s identity
byte-identical after appending a line to `analyzers/t2star.py` — the analyzer could change
completely while the digest asserted nothing had. These tests pin both directions, because the
claim must not rest on a probe someone ran once by hand.

The negative direction is as load-bearing as the positive one. Hashing all of `src/quebra/`
would also make the probe move, and would carry an unacceptable blast radius: editing a plot
module would invalidate every cached compute artifact. So a test that only checked "editing
something moves the identity" would pass for the wrong implementation.
"""

from __future__ import annotations

import pathlib

import pytest

import quebra.analyzers.t2star as t2star
import quebra.plots.km_survival_plot as km_plot
from quebra.core.closure import code_closure

REPO = pathlib.Path(__file__).resolve().parent.parent


def _t2star_closure() -> dict[str, str]:
    return code_closure([t2star.run])


def test_the_closure_contains_the_analyzer_the_step_calls():
    assert "quebra.analyzers.t2star" in _t2star_closure()


def test_the_closure_reaches_transitively_not_just_directly():
    """`t2star.run` calls into the within-calibration compute; that must be covered too."""
    closure = _t2star_closure()
    assert "quebra.analyzers.within_calibration_compute" in closure
    assert "quebra.analyzers.within_calibration_data" in closure


def test_the_closure_contains_no_render_module():
    """The blast-radius guard, and the reason SPEC 0005 R5.0.4 came before this requirement.

    Until the within-calibration compute was moved out of `panels/`, `analyzers.t2star`
    reached `plots.base`, `plots.theme`, `plots.fidelity_helpers` and
    `panels._within_calibration_render` — so editing a module that draws and computes no
    number would have invalidated every cached compute artifact.
    """
    offenders = sorted(
        name
        for name in _t2star_closure()
        if ".plots." in name or "_render" in name or ".panels." in name
    )
    assert not offenders, f"render modules leaked into a compute closure: {offenders}"


def test_an_unreached_module_is_absent():
    """The negative direction. `km_survival_plot` is real code in the package and is simply
    not reachable from this analyzer; a whole-package hash would include it."""
    assert km_plot.__name__ not in _t2star_closure()


def test_the_closure_is_deterministic_and_sorted():
    first, second = _t2star_closure(), _t2star_closure()
    assert first == second
    assert list(first) == sorted(first), "fold order must be a property of the graph"


def test_every_entry_is_a_quebra_module_with_a_real_digest():
    for name, digest in _t2star_closure().items():
        assert name == "quebra" or name.startswith("quebra.")
        assert len(digest) == 64 and int(digest, 16) >= 0


def test_a_step_defined_in_a_job_file_still_seeds_the_analyzers():
    """The case that would have made the whole requirement a no-op.

    A step defined in the JOB module is not a `quebra.*` module, so filtering the SEED set to
    `quebra.*` would drop it — and with it every analyzer it reaches. The filter applies to
    what is hashed, not to where the walk starts.

    Uses `mtbf_q1`, not a T2* job. The T2* jobs were the original measurement for this, but
    SPEC 0005 R5.3 collapsed them onto `recipes.configure_t2star_job`, so all their steps now
    live in a `quebra.*` module and they no longer exercise this path. That is the test
    telling us its premise moved, which is why the premise is asserted rather than assumed.
    """
    from quebra.core.job import _import_job

    job = _import_job(REPO / "jobs" / "active" / "mtbf_q1.py")
    modules = {getattr(node.fn, "__module__", "") for node in job.dag.values()}
    assert any(not m.startswith("quebra") for m in modules), (
        "expected at least one step defined in the job file; the test's premise is stale"
    )
    closure = code_closure([node.fn for node in job.dag.values()])
    assert "quebra.analyzers.mtbf" in closure


def test_an_unresolvable_step_raises_rather_than_being_skipped():
    """An identity that quietly stops covering an input is the failure this scheme exists to
    prevent, so an unresolvable callable must be loud. `build_identity` sets the precedent."""

    class _Opaque:
        __module__ = None  # type: ignore[assignment]

        def __call__(self) -> None: ...

    with pytest.raises(TypeError, match="cannot resolve a defining module"):
        code_closure([_Opaque()])


def test_a_job_module_with_no_source_file_raises():
    exec_globals: dict[str, object] = {}
    exec("def synthetic_step():\n    return None\n", exec_globals)
    fn = exec_globals["synthetic_step"]
    with pytest.raises(
        TypeError, match="cannot resolve a defining module|has no source file"
    ):
        code_closure([fn])


def test_the_fold_moves_when_a_reached_module_changes(monkeypatch, tmp_path):
    """The fold itself, isolated from the graph walk.

    Mutating a real source file inside the suite would leave the tree dirty if the test
    failed part-way, so the walk is tested by its CONTENTS above and the fold is tested here
    by substituting a digest. Together they cover 'editing a reached module moves identity'
    without a test that writes to `src/`.
    """
    from quebra.core import job as job_module

    job_file = tmp_path / "070423_probe.py"
    job_file.write_text("from quebra.core.job import Job\njob = Job('probe')\n")

    calls = {"n": 0}

    def fake_closure(_functions: list[object]) -> dict[str, str]:
        calls["n"] += 1
        return {"quebra.analyzers.t2star": f"{calls['n']:064d}"}

    monkeypatch.setattr(job_module, "code_closure", fake_closure)

    first = job_module.Job("probe")
    first.job_file = job_file
    second = job_module.Job("probe")
    second.job_file = job_file

    assert first.job_code_hash() != second.job_code_hash(), (
        "a changed module digest must change the code contribution"
    )


def test_two_jobs_differing_only_by_a_step_kwarg_do_not_collide(tmp_path):
    """R5.1.7. `Identity` is code + data + children with no `job.name`, so before the
    parameter row was folded these produced ONE digest — measured, both `93f7286634eef03b`.

    Masked today because every parameter lives in the job file's text, which `code` hashes.
    It goes live the moment a job family moves its rows into a manifest, which is exactly
    what R5.3 does, which is why this is pinned before that lands.
    """
    from quebra.core.job import Job

    job_file = tmp_path / "070423_fam.py"
    job_file.write_text("from quebra.core.job import Job\njob = Job('fam')\n")

    def stepfn(x: int = 0) -> int:
        return x

    # An explicit root, not `default_dataset_root()`: these jobs load no dataset, and
    # resolving one would make the test require a configured data root, which it does not
    # have when the suite runs from an unrelated cwd under a wheel install.
    root = tmp_path
    first = Job("fam")
    first.job_file = job_file
    first.step(stepfn, name="s", x=1)
    second = Job("fam")
    second.job_file = job_file
    second.step(stepfn, name="s", x=999)

    assert first.build_identity(root).digest != second.build_identity(root).digest


def test_an_opaque_object_kwarg_is_refused(tmp_path):
    """Was `test_a_kwarg_whose_repr_carries_an_address_is_refused`, asserting the old
    denylist's wording. The guard is an ALLOWLIST now, so the message changed while the
    property strengthened: an address-bearing repr is still refused, and so is every other
    type without a cross-process-stable rendering."""
    from quebra.core.closure import parameter_row

    class _Node:
        node_id = "n"
        kwargs = {"handler": object()}

    with pytest.raises(TypeError, match="cannot enter an identity"):
        parameter_row([_Node()])


def test_a_dataset_kwarg_is_left_to_the_data_contribution(tmp_path):
    """Datasets are hashed by content into `data`; their repr names a schema class whose
    module embeds an absolute path when the schema is defined in a job file."""
    from quebra.core.closure import parameter_row
    from quebra.core.dataset import Dataset

    class _Node:
        node_id = "load"
        kwargs = {"dataset": Dataset(path="x.csv")}

    assert parameter_row([_Node()]) == ["load()"]


# ---------------------------------------------------------------- argument rendering (R5.1.7)


def test_a_set_kwarg_renders_the_same_in_every_process():
    """Set iteration follows per-process randomised string hashing.

    Measured before the allowlist: the same job produced three different rows in three
    processes, so the digest was not reproducible at all — the one property this scheme
    sells. Rendering sorted makes it order-free.
    """
    from quebra.core.closure import _render

    assert (
        _render({"zz", "x", "ab"}) == _render({"ab", "zz", "x"}) == "{'ab', 'x', 'zz'}"
    )


def test_a_dict_kwarg_renders_key_sorted():
    from quebra.core.closure import _render

    assert _render({"b": 2, "a": 1}) == _render({"a": 1, "b": 2})


def test_a_path_kwarg_is_refused():
    """A Path renders as an ABSOLUTE path, which would put the machine into the identity and
    break the install-independence `closure.py`'s own hazard 4 forbids."""
    import pathlib

    from quebra.core.closure import _render

    with pytest.raises(TypeError, match="cannot enter an identity"):
        _render(pathlib.Path("/abs/x.csv"))


def test_a_numpy_array_kwarg_is_refused():
    """A long array's repr ELIDES its middle, so two different arrays render identically and
    collide — reopening the exact hole `parameter_row` was added to close."""
    import numpy as np

    from quebra.core.closure import _render

    long_a, long_b = np.arange(2000), np.arange(2000)
    long_b[1000] = -1
    assert repr(long_a) == repr(long_b), "premise: the reprs collide"
    with pytest.raises(TypeError, match="cannot enter an identity"):
        _render(long_a)


def test_nested_containers_of_scalars_are_accepted():
    from quebra.core.closure import _render

    assert _render([1, ("a", 2.5), {"k": True}]) == "[1, ('a', 2.5), {'k': True}]"


def test_the_rejection_names_the_node_and_the_kwarg():
    from quebra.core.closure import parameter_row

    class _Node:
        node_id = "the_step"
        kwargs = {"where": __import__("pathlib").Path("/x")}

    with pytest.raises(TypeError, match="the_step.*where"):
        parameter_row([_Node()])
