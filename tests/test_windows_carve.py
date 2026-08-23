"""Carving semantics, ported from monoliths/v13fig/test_carve.py.

The monolith file could not be used as-is: it has no test_ functions, its `check()`
helper prints instead of raising, and a module-scope `raise SystemExit` makes pytest
abort the whole session with an INTERNALERROR. Its 19 checks are reproduced here as
asserts against analyzers/windows.py.

ONE CHECK DID NOT PORT: the monolith's `min_reads=3` filter test. `min_reads` is
deliberately not implemented (see the analyzers/windows.py docstring) - this repo's carve
has never had that filter, so omitting it is what preserves parity. The check is gone
rather than faked.

The reference fixture: reads at t = 0..9, then a 100-unit gap, then 10 more reads.
  idx 0,1      in   -> window opens at index 0        -> birth scan_start
  idx 2,3      out
  idx 4,5,6    in   -> real up-crossing and down      -> COMPLETE
  idx 7        out
  idx 8,9      in   -> open when the gap hits         -> death gap_start
  idx 10,11,12 in   -> first reads after the gap      -> birth gap_resume
  idx 13       out
  idx 14..19   in   -> runs to the end                -> death scan_end
"""

from __future__ import annotations

import numpy as np

from analyzers import windows

T = np.r_[np.arange(10) * 1.0, np.arange(10) * 1.0 + 110.0]
Y = np.array(
    [2, 2, 0, 0, 2, 2, 2, 0, 2, 2, 2, 2, 2, 0, 2, 2, 2, 2, 2, 2],
    dtype=float,
)


def _carve(t: np.ndarray, y: np.ndarray, u: float, gap_mult: float = 10.0):
    _, gap_threshold_s, _, _ = windows.spacing(t, gap_mult)
    return windows.carve(
        t,
        windows.in_spec_mask(y, u, True),
        windows.gap_flags(t, gap_threshold_s),
    )


def _bounds(wins: list[dict[str, object]]) -> list[tuple[int, int]]:
    return [(int(w["s"]), int(w["e"])) for w in wins]


def _complete(wins: list[dict[str, object]]) -> list[dict[str, object]]:
    """Windows with an observed birth AND an observed death."""
    return [
        w
        for w in wins
        if w["birth_type"] == windows.BIRTH_UP_CROSSING
        and w["death_type"] == windows.DEATH_DOWN_CROSSING
    ]


def test_spacing() -> None:
    median_s, gap_threshold_s, n_gaps, n_nonpositive = windows.spacing(T, gap_mult=10.0)
    assert median_s == 1.0
    assert gap_threshold_s == 10.0
    assert n_gaps == 1
    assert n_nonpositive == 0


def test_carving_bounds_births_and_deaths() -> None:
    wins = _carve(T, Y, u=1.0)
    assert len(wins) == 5
    assert _bounds(wins) == [(0, 2), (4, 7), (8, 10), (10, 13), (14, 20)]
    assert [w["birth_type"] for w in wins] == [
        windows.BIRTH_SCAN_START,
        windows.BIRTH_UP_CROSSING,
        windows.BIRTH_UP_CROSSING,
        windows.BIRTH_GAP_RESUME,
        windows.BIRTH_UP_CROSSING,
    ]
    assert [w["death_type"] for w in wins] == [
        windows.DEATH_DOWN_CROSSING,
        windows.DEATH_DOWN_CROSSING,
        windows.DEATH_GAP_START,
        windows.DEATH_DOWN_CROSSING,
        windows.DEATH_SCAN_END,
    ]


def test_complete_excludes_every_unobserved_endpoint() -> None:
    wins = _carve(T, Y, u=1.0)
    complete = _complete(wins)
    assert _bounds(complete) == [(4, 7)]
    assert all(w["birth_type"] != windows.BIRTH_SCAN_START for w in complete)
    assert all(w["birth_type"] != windows.BIRTH_GAP_RESUME for w in complete)
    assert all(w["death_type"] != windows.DEATH_GAP_START for w in complete)
    assert all(w["death_type"] != windows.DEATH_SCAN_END for w in complete)


def test_gap_mult_sensitivity() -> None:
    _, gap_threshold_s, n_gaps, _ = windows.spacing(T, gap_mult=200.0)
    assert (gap_threshold_s, n_gaps) == (200.0, 0)
    # Without a gap, idx 8..12 merge into a single window.
    wins = _carve(T, Y, u=1.0, gap_mult=200.0)
    assert _bounds(wins) == [(0, 2), (4, 7), (8, 13), (14, 20)]


def test_duplicate_timestamps_do_not_collapse_the_threshold() -> None:
    t_dup = np.repeat(np.arange(10) * 2.0, 2)
    median_s, gap_threshold_s, _, n_nonpositive = windows.spacing(t_dup, gap_mult=10.0)
    assert median_s == 2.0  # median over POSITIVE steps only
    assert n_nonpositive == 10
    assert gap_threshold_s == 20.0


def test_gap_beats_a_simultaneous_down_crossing() -> None:
    # The read after the gap is out-of-spec: the open window must die gap_start, not
    # down_crossing. Gap wins ties because the gap check runs first.
    t = np.r_[np.arange(4) * 1.0, np.array([100.0])]
    y = np.array([2, 2, 2, 2, 0], dtype=float)
    wins = _carve(t, y, u=1.0)
    assert len(wins) == 1
    assert wins[0]["death_type"] == windows.DEATH_GAP_START


def test_equality_is_not_a_gap() -> None:
    # spacing exactly == gap_threshold must not count; the test is strict `>`.
    t = np.array([0.0, 1.0, 2.0, 12.0])  # median 1.0 -> threshold 10.0, last step 10.0
    _, gap_threshold_s, n_gaps, _ = windows.spacing(t, gap_mult=10.0)
    assert gap_threshold_s == 10.0
    assert n_gaps == 0
