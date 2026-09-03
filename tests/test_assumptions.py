"""The assumption records say what the package actually does.

Oracle: the package's own constants. Every check a record names is compared against the real
`CHECK_NAME` in the module that defines it, so a renamed or deleted check breaks these tests
rather than leaving a record pointing at nothing.

These are contract tests, not statistical ones. The claim under test is that a record cannot
promise a diagnostic the package does not have, which is the failure mode that makes an
assumption record worse than no record at all.

The second thing under test is that ADDING a record is cheap. More are expected
(`spec/quebraplan.md` section 9), so the tests below drive the constructor directly rather
than only the shipped registry: a new record must be one literal plus one line in `_RECORDS`,
with no second registry to update.
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from quebra.analyzers.assumptions import (
    ASSUMPTIONS,
    DISPOSITION_RAISES,
    DISPOSITION_REPORTS,
    DISPOSITION_UNDETECTED,
    DISPOSITIONS,
    SHIPPED_CHECK_NAMES,
    Assumption,
)
from quebra.analyzers.checks import c1_lewis_robinson as c1
from quebra.analyzers.checks import c2_anderson_darling as c2
from quebra.analyzers.checks import c3_serial_copula as c3
from quebra.analyzers.checks import c5_rank_autocorr as c5
from quebra.analyzers.checks import c6_exchangeability as c6
from quebra.analyzers.checks import cvm_cramer_von_mises as cvm

EVERY_CHECK = (c1, c2, c3, c5, c6, cvm)
TESTS_DIR = Path(__file__).resolve().parent


def _record(**overrides) -> Assumption:
    """A minimal valid record, for driving one field at a time."""
    base = dict(
        id="a9_probe",
        statement="s",
        diagnostic="d",
        consequence="c",
        reference="r",
        disposition=DISPOSITION_REPORTS,
        diagnostic_checks=(c1.CHECK_NAME,),
    )
    return Assumption(**{**base, **overrides})


# ------------------------------------------------------------- the shipped registry


def test_the_shipped_check_names_are_the_six_modules_own_constants():
    """The oracle for everything below."""
    assert SHIPPED_CHECK_NAMES == frozenset(m.CHECK_NAME for m in EVERY_CHECK)
    assert len(SHIPPED_CHECK_NAMES) == 6


def test_a1_is_diagnosed_by_all_six_checks_and_the_count_is_six_not_five():
    """Pins the count against a doc claim that is currently stale.

    `docs/iid_checks/iid_checks_basics.md:20` and `analyzers/checks/__init__.py` both still
    say FIVE checks; CvM was promoted after they were written. This test is why a record
    cannot inherit that error - it counts the modules rather than trusting the prose.
    """
    names = ASSUMPTIONS["a1_renewal_durations"].diagnostic_checks
    assert len(names) == 6, f"expected all six shipped checks; got {sorted(names)}"
    assert set(names) == SHIPPED_CHECK_NAMES


def test_a1_reports_rather_than_raises():
    """A failed check suppresses nothing: SPEC 0008's governing constraint is that the band
    is always drawn and the check outcome is shown beside it."""
    assert ASSUMPTIONS["a1_renewal_durations"].disposition == DISPOSITION_REPORTS


def test_every_registry_key_is_its_records_own_id():
    """A mismatched key would make `ASSUMPTIONS[x].id != x`, so a figure looking a record up
    by id would label it with another assumption's name."""
    for key, record in ASSUMPTIONS.items():
        assert record.id == key


def test_every_shipped_record_is_internally_consistent():
    for record in ASSUMPTIONS.values():
        assert record.disposition in DISPOSITIONS
        assert set(record.diagnostic_checks) <= SHIPPED_CHECK_NAMES


# ------------------------------------------------------------- adding a record is cheap


def test_a_new_record_needs_no_second_registry():
    """Expandability, asserted rather than hoped for. `diagnostic_checks` lives ON the
    record, so constructing one is the whole job: there is no parallel mapping a new entry
    could be missing from."""
    fields = {f.name for f in dataclasses.fields(Assumption)}
    assert "diagnostic_checks" in fields
    made = _record(id="a4_probe_two", diagnostic_checks=(c5.CHECK_NAME,))
    assert made.diagnostic_checks == (c5.CHECK_NAME,)


def test_a_record_with_no_diagnosing_check_is_allowed_when_it_says_undetected():
    """The shape the next record is likely to need: an assumption the package cannot see
    fail. It must be constructible without widening the vocabulary."""
    made = _record(diagnostic_checks=(), disposition=DISPOSITION_UNDETECTED)
    assert made.diagnostic_checks == ()
    assert made.disposition == DISPOSITION_UNDETECTED


@pytest.mark.parametrize("claimed", [DISPOSITION_REPORTS, DISPOSITION_RAISES])
def test_a_record_with_no_check_cannot_claim_to_report_or_raise(claimed):
    """The guard that stops a record promising a behaviour the package does not have. With
    nothing to run there is nothing to report, so the honest value is the only one allowed."""
    with pytest.raises(ValueError, match="names no diagnosing check"):
        _record(diagnostic_checks=(), disposition=claimed)


# ------------------------------------------------------------- construction guards


def test_naming_a_check_that_does_not_ship_is_refused():
    with pytest.raises(ValueError, match="do not ship"):
        _record(diagnostic_checks=("c9_imaginary",))


@pytest.mark.parametrize(
    "field_name", ["id", "statement", "diagnostic", "consequence", "reference"]
)
def test_an_empty_field_is_refused_at_construction(field_name):
    """An empty diagnostic reads as 'not checked' and an empty reference as 'no source'.
    Neither should be inferrable from a blank."""
    _record()  # the control: the base record must construct
    with pytest.raises(ValueError, match=field_name):
        _record(**{field_name: "   "})


@pytest.mark.parametrize(
    "bad_id", ["A5_Foo", "a_renewal", "renewal_durations", "a5-foo"]
)
def test_an_id_outside_the_grep_shape_is_refused(bad_id):
    """The traceability scheme is a grep over `a<number>_<snake_case>`, so an id outside that
    shape is invisible to it and must not be constructible."""
    with pytest.raises(ValueError, match="snake_case"):
        _record(id=bad_id)


def test_an_unknown_disposition_is_refused():
    with pytest.raises(ValueError, match="disposition"):
        _record(disposition="silently_ignores")


def test_a_record_cannot_be_edited_after_construction():
    """Frozen on purpose: a caller that could edit a record could make a figure claim a
    diagnostic that never ran."""
    record = ASSUMPTIONS["a1_renewal_durations"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.diagnostic = "nothing tests this"  # type: ignore[misc]


# ------------------------------------------------- the trace query (R8.6)


def _citations() -> dict[str, list[str]]:
    """Assumption id -> the test names that cite it, by name or first docstring line."""
    found: dict[str, list[str]] = {key: [] for key in ASSUMPTIONS}
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            doc = ast.get_docstring(node) or ""
            first_line = doc.splitlines()[0] if doc else ""
            haystack = f"{node.name} {first_line}"
            for key in found:
                if key in haystack:
                    found[key].append(f"{path.name}::{node.name}")
    return found


def test_every_registered_assumption_is_cited_by_a_test():
    # Deliberately no citing test in THIS file. A guard whose only satisfier is a test
    # written to satisfy it proves nothing; the citation lives on a check test that has a
    # real oracle, so the trace query lands on evidence.
    """The guard R8.6 owes. Modelled on
    `test_independence_survey.py::test_every_surveyed_key_has_a_label_and_a_stated_null`."""
    citations = _citations()
    uncited = sorted(key for key, tests in citations.items() if not tests)
    assert not uncited, (
        f"assumption(s) {uncited} are registered but no test cites them by full id in its "
        f"name or first docstring line. Either write the evidence, or say in the record "
        f"that there is none - a registry that looks traced and is not is worse than one "
        f"that admits the gap."
    )


def test_the_matcher_is_not_dead():
    """The liveness half, and the reason this file is not circular.

    `test_every_registered_assumption_is_cited_by_a_test` passes trivially on an empty
    registry, and would also pass if `_citations` silently stopped parsing anything. So:
    assert the registry is non-empty AND that the scan really reached the test suite.
    """
    assert ASSUMPTIONS, "the registry is empty, so the guard above asserts nothing"
    citations = _citations()
    assert sum(len(v) for v in citations.values()) > 0
    assert len(list(TESTS_DIR.glob("test_*.py"))) > 10, (
        "the scan found almost no test files; the glob or the directory moved"
    )
