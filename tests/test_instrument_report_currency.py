"""The committed instrument report is what the current code renders.

Oracle: `jobs/bench/instrument_report.render()`, run against the tracked file it writes.
A policy test over a generated artifact, not a statistical one.

Its own file rather than an entry in `tests/test_instrument_validation.py`, per `AGENTS.md`
section 7's index: that file's subject is the artifact `build_instrument_validation` produces
and its oracles are published values and re-measurement, while this one's subject is the
COMMITTED markdown and its oracle is the writer. Same precedent as
`tests/test_job_manifest.py`, which guards `docs/JOBS.md` the same way and for the same
reason.
"""

from __future__ import annotations

import pathlib

import pytest

pytestmark = pytest.mark.policy


def test_the_committed_tier_table_is_what_this_code_renders() -> None:
    """Oracle: the renderer, run against the tracked file it wrote.

    `render_tier_table_markdown`'s own docstring justifies generating this file rather than
    hand-maintaining it because "a stale table is a visible diff on the next run". Nothing
    made that true: the file could drift from the code indefinitely and the suite stayed
    green, which is how it came to be missing a Kaplan-Meier row after the rows were added.

    Compared as RENDERED TEXT rather than by pinning `0.9462` in a test. Be clear about what
    that does and does not buy: the rendered text CONTAINS that number, so a change to the
    draw stream - a numpy version bump, which CI takes on every run because every bound is a
    `>=` - turns this red too, with probability near one. What the design buys is a better
    failure: the diff names the row and the message says to re-run the writer, instead of an
    assertion comparing two bare floats. It does not buy immunity, and an earlier version of
    this docstring implied it did.

    Imports from `jobs.bench`, which `tests/` is permitted to do and
    `tests/test_bench_uses_real_carve.py` already does; the direction the isolation contract
    forbids is the pipeline importing the bench, not the suite.
    """
    from jobs.bench.instrument_report import render

    committed = (
        pathlib.Path(__file__).resolve().parents[1]
        / "jobs"
        / "bench"
        / "results"
        / "instrument_report.md"
    )
    assert committed.is_file(), (
        f"{committed} is missing; run jobs/bench/instrument_report.py"
    )

    # `render()` is the writer's own function, so this cannot compare two different
    # reports the way a guard assembling its own inputs would.
    assert render() == committed.read_text(), (
        "the committed tier table is not what this code renders. Re-run "
        "`python jobs/bench/instrument_report.py` and commit the result."
    )
