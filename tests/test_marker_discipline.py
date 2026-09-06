"""The tier axis is total: every collected test answers exactly one kind of question.

Oracle: the marker list in `pyproject.toml`. This is a policy test, not a statistical one.

`spec/quebraplan.md` 5.1 proposed six tier DIRECTORIES. `spec/spectests06.md` declined them
and put the tier on a marker instead, because directories cross-cut the oracle-and-subject
index in `AGENTS.md` section 7 and several files here legitimately hold more than one tier.
A marker scheme decays silently unless something makes it total, which is what this file is.

The check is decidable, which is why it exists at all: "does this item carry one of these
seven names" is a property of the item. The neighbouring oracle rule ("does this docstring
name a source of truth") is a judgement, and `spec/spectests06.md` R6.1 declines to guard it
rather than enforce a regex that would check something else.
"""

from __future__ import annotations

import pytest

# The tier axis. Exactly one per test.
TIER_MARKERS = frozenset(
    {
        "unit",
        "properties",
        "statistical",
        "integration",
        "validation",
        "regression",
        "policy",
    }
)

# The cost axis. Orthogonal: zero or more per test, and never a substitute for a tier.
COST_MARKERS = frozenset({"slow", "heavy", "real", "r"})


def tier_markers_of(item) -> set[str]:
    """The tier markers on one collected item. The detector both tests below share."""
    return {mark.name for mark in item.iter_markers()} & TIER_MARKERS


def _violations(items) -> list[tuple[str, list[str]]]:
    """(nodeid, tiers) for every item not carrying exactly one tier marker."""
    out = []
    for item in items:
        tiers = sorted(tier_markers_of(item))
        if len(tiers) != 1:
            out.append((item.nodeid, tiers))
    return out


class _FakeMark:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeItem:
    """A planted item, for the positive control. Mirrors the `iter_markers` surface."""

    def __init__(self, nodeid: str, names: tuple[str, ...]) -> None:
        self.nodeid = nodeid
        self._names = names

    def iter_markers(self):
        return [_FakeMark(name) for name in self._names]


@pytest.mark.policy
def test_every_collected_test_carries_exactly_one_tier_marker(request) -> None:
    """Reads the real session, so it cannot pass by checking a copy of itself.

    Under a partial selection (`pytest tests/test_foo.py`) this sees only what was
    collected, which is still true but weaker. The full run is what makes it total.
    """
    bad = _violations(request.session.items)
    assert not bad, (
        f"{len(bad)} collected test(s) do not carry exactly one tier marker "
        f"({'/'.join(sorted(TIER_MARKERS))}):\n"
        + "\n".join(f"  {nodeid}  ->  {tiers or 'none'}" for nodeid, tiers in bad[:20])
    )


@pytest.mark.policy
def test_the_detector_catches_a_missing_and_a_doubled_tier() -> None:
    """Positive control. Without it the guard above passes whenever collection is empty."""
    planted = [
        _FakeItem("planted::no_tier", ()),
        _FakeItem("planted::cost_only", ("slow", "real")),
        _FakeItem("planted::two_tiers", ("unit", "statistical")),
        _FakeItem("planted::ok", ("unit",)),
        _FakeItem("planted::ok_with_cost", ("statistical", "slow")),
    ]
    bad = dict(_violations(planted))
    assert set(bad) == {
        "planted::no_tier",
        "planted::cost_only",
        "planted::two_tiers",
    }
    assert bad["planted::two_tiers"] == ["statistical", "unit"]


@pytest.mark.policy
def test_the_two_axes_are_exactly_what_pyproject_declares(request) -> None:
    """Oracle: `[tool.pytest.ini_options] markers`, read rather than re-typed.

    The sets above are literals, so without this they are a second copy of the
    declaration and could drift from it silently - deleting a marker from `pyproject.toml`
    would leave this file green while the declared and asserted axes disagreed. That is the
    defect class this whole checkpoint exists to remove, so the guard must not carry it.
    """
    import tomllib

    # `config.getini("markers")` also returns builtin and plugin markers (parametrize,
    # skipif, hypothesis, ...), so it cannot say what THIS project declares. Read the file.
    # `rootpath` is derived from the ini file's own location, not the cwd, so this keeps
    # working from an unrelated working directory.
    pyproject = request.config.rootpath / "pyproject.toml"
    entries = tomllib.loads(pyproject.read_text())["tool"]["pytest"]["ini_options"][
        "markers"
    ]
    declared = {entry.split(":", 1)[0].strip() for entry in entries}
    assert TIER_MARKERS | COST_MARKERS == declared, (
        "the two axes here and the markers declared in pyproject.toml have drifted:\n"
        f"  declared not classified: {sorted(declared - (TIER_MARKERS | COST_MARKERS))}\n"
        f"  classified not declared: {sorted((TIER_MARKERS | COST_MARKERS) - declared)}"
    )
    assert not (TIER_MARKERS & COST_MARKERS), (
        "a name on both axes would make 'exactly one tier' ambiguous"
    )
