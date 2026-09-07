"""The runner's graph contract: ordering, reachability, and what the builder cannot express.

Oracle: the definition of a topological order, and `core/job.py`'s registration rule.

`quebraplan.md` 5.5 names six runner invariants. Four were already covered when SPEC 0006
was written - deterministic identity, no reuse under code or content mismatch, no reuse under
a dirty tree - by `tests/test_identity*.py` and `tests/test_reuse_*.py`, and this file does
not rewrite over them. What was uncovered is the ordering itself: `_toposort` had no direct
test, so nothing asserted that a node's inputs precede it, that the order is deterministic,
or that a node reaching no sink is never executed.

The sixth invariant, "cycle detection reports the full chain", is covered where cycles are
actually reachable: `core/job.py:75-77` reports the whole include chain and
`tests/test_nesting.py` pins it. `runner.py`'s intra-job cycle message names one node, and
after the registration guard exercised below it cannot be reached from a job file at all, so
improving its wording would be polish on unreachable code.
"""

from __future__ import annotations

import pytest

from quebra.core.job import Job
from quebra.core.reference import LocalRef
from quebra.core.runner import _ancestors, _toposort

pytestmark = pytest.mark.integration


def _step(x=None, y=None):
    return x


def _diamond() -> tuple[Job, dict[str, LocalRef]]:
    """a -> b, a -> c, (b, c) -> d. The shape where a wrong order is visible."""
    job = Job("diamond")
    a = job.step(_step, name="a")
    b = job.step(_step, a, name="b")
    c = job.step(_step, a, name="c")
    d = job.step(_step, b, c, name="d")
    job.materialize(d, name="out")
    return job, {"a": a, "b": b, "c": c, "d": d}


def test_every_nodes_inputs_precede_it_in_the_order() -> None:
    """Oracle: the definition of a topological order, checked against the real edges."""
    job, refs = _diamond()
    order = _toposort(job, [refs["d"].node_id])
    position = {node_id: i for i, node_id in enumerate(order)}

    for node_id, node in job.dag.items():
        if node_id not in position:
            continue
        for ref in node.inputs:
            if isinstance(ref, LocalRef):
                assert position[ref.node_id] < position[node_id], (
                    f"{node_id} runs before its input {ref.node_id}"
                )


def test_a_planted_out_of_order_graph_is_caught() -> None:
    """Positive control: the assertion above must be able to fail.

    Reverses the check rather than the code - if `_toposort` returned its post-order
    backwards, every edge would be violated. Without this, a `_toposort` that returned the
    empty list would pass the test above vacuously.
    """
    job, refs = _diamond()
    reversed_order = list(reversed(_toposort(job, [refs["d"].node_id])))
    position = {node_id: i for i, node_id in enumerate(reversed_order)}

    violations = [
        (node_id, ref.node_id)
        for node_id, node in job.dag.items()
        if node_id in position
        for ref in node.inputs
        if isinstance(ref, LocalRef) and position[ref.node_id] >= position[node_id]
    ]
    assert violations, "a reversed order must violate at least one edge"


def test_the_order_is_deterministic_across_builds() -> None:
    """Two identical builds must order identically, or a cache key is not a function."""
    first, refs_first = _diamond()
    second, refs_second = _diamond()
    assert _toposort(first, [refs_first["d"].node_id]) == _toposort(
        second, [refs_second["d"].node_id]
    )


def test_a_node_reaching_no_sink_is_never_ordered_and_never_an_ancestor() -> None:
    """Oracle: `_toposort` is seeded from sink ids, so the DAG is lazy by construction.

    A registered node that no sink depends on is not merely skipped at execution: it never
    enters `ordered_ids`, and `_ancestors` does not see it either, which is what keeps it
    out of the provenance record's `pipeline_steps`. Neither property had a test.
    """
    job, refs = _diamond()
    orphan = job.step(_step, refs["a"], name="orphan")

    order = _toposort(job, [refs["d"].node_id])
    assert orphan.node_id in job.dag, "the orphan must really be registered"
    assert orphan.node_id not in order
    assert orphan.node_id not in _ancestors(job, refs["d"].node_id)

    # and the reachable ones all are, so this is not passing by ordering nothing
    for key in ("a", "b", "c", "d"):
        assert refs[key].node_id in order


def test_the_builder_refuses_a_reference_to_an_unregistered_node() -> None:
    """Oracle: `_register_node`'s membership check, which makes acyclicity a property.

    `LocalRef` is a public dataclass, so before this guard a caller could hand in a
    reference naming a node that did not exist yet. Two consequences, both reachable from
    an ordinary job file with no private access: a FORWARD reference made registration
    order stop being a topological order and built a real cycle, and a reference to an id
    never allocated at all surfaced as a bare `KeyError` from inside the traversal instead
    of an error where the mistake was written.

    With the guard, "registration order is a topological order" is true by construction
    rather than by convention, which is what lets the ordering tests above stand on
    something.
    """
    job = Job("guarded")
    a = job.step(_step, name="a")

    # the forward reference that used to build a cycle
    with pytest.raises(ValueError, match="has not registered"):
        job.step(
            _step, LocalRef(node_id="b", job_ref=job, fn_name="b", kwargs={}), name="b"
        )

    # the dangling reference that used to surface as a KeyError much later
    with pytest.raises(ValueError, match="has not registered"):
        job.step(
            _step,
            LocalRef(node_id="never_allocated", job_ref=job, fn_name="x", kwargs={}),
            name="c",
        )

    # a genuine reference is unaffected
    assert job.step(_step, a, name="d").node_id in job.dag


def test_a_sink_refuses_a_reference_to_an_unregistered_node() -> None:
    """Oracle: `_require_own_node`, at the two SINK sites rather than at `step`.

    This is the path the guard was actually added for, and the one nothing covered. A ghost
    reference handed to `figure()` or `materialize()` passed the ownership check, so the run
    reached `run_job`, created its timestamped output directory, and only then died as a
    `KeyError` from inside the traversal - after writing to disk, and naming the node id
    rather than the sink that referenced it.

    `test_the_builder_refuses_a_reference_to_an_unregistered_node` above covers `step`.
    Both call the same helper, but only by review: `_register_node` still carries its own
    inlined pair of raises, so the two paths can drift and each needs its own test.
    """
    job = Job("sinks")
    real = job.step(_step, name="a")
    ghost = LocalRef(node_id="ghost", job_ref=job, fn_name="g", kwargs={})

    with pytest.raises(ValueError, match="has not registered"):
        job.materialize(ghost, "out")
    with pytest.raises(ValueError, match="has not registered"):
        job.figure(object, ghost, ["static"])

    # a foreign but registered ref is still refused, by the ownership half
    other = Job("other")
    foreign = other.step(_step, name="a")
    with pytest.raises(ValueError, match="same-job node"):
        job.materialize(foreign, "out")

    # and a genuine reference still lands
    job.materialize(real, "out")
    assert any(getattr(s, "name", "") == "out" for s in job.sinks)
