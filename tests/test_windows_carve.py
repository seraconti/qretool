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

import re

import numpy as np
import pytest

from quebra.analyzers import windows
from quebra.core.paths import repo_root


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


@pytest.mark.unit
def test_spacing() -> None:
    median_s, gap_threshold_s, n_gaps, n_nonpositive = windows.spacing(T, gap_mult=10.0)
    assert median_s == 1.0
    assert gap_threshold_s == 10.0
    assert n_gaps == 1
    assert n_nonpositive == 0


@pytest.mark.statistical
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


@pytest.mark.statistical
def test_complete_excludes_every_unobserved_endpoint() -> None:
    wins = _carve(T, Y, u=1.0)
    complete = _complete(wins)
    assert _bounds(complete) == [(4, 7)]
    assert all(w["birth_type"] != windows.BIRTH_SCAN_START for w in complete)
    assert all(w["birth_type"] != windows.BIRTH_GAP_RESUME for w in complete)
    assert all(w["death_type"] != windows.DEATH_GAP_START for w in complete)
    assert all(w["death_type"] != windows.DEATH_SCAN_END for w in complete)


@pytest.mark.unit
def test_gap_mult_sensitivity() -> None:
    _, gap_threshold_s, n_gaps, _ = windows.spacing(T, gap_mult=200.0)
    assert (gap_threshold_s, n_gaps) == (200.0, 0)
    # Without a gap, idx 8..12 merge into a single window.
    wins = _carve(T, Y, u=1.0, gap_mult=200.0)
    assert _bounds(wins) == [(0, 2), (4, 7), (8, 13), (14, 20)]


@pytest.mark.unit
def test_duplicate_timestamps_do_not_collapse_the_threshold() -> None:
    t_dup = np.repeat(np.arange(10) * 2.0, 2)
    median_s, gap_threshold_s, _, n_nonpositive = windows.spacing(t_dup, gap_mult=10.0)
    assert median_s == 2.0  # median over POSITIVE steps only
    assert n_nonpositive == 10
    assert gap_threshold_s == 20.0


@pytest.mark.unit
def test_gap_beats_a_simultaneous_down_crossing() -> None:
    # The read after the gap is out-of-spec: the open window must die gap_start, not
    # down_crossing. Gap wins ties because the gap check runs first.
    t = np.r_[np.arange(4) * 1.0, np.array([100.0])]
    y = np.array([2, 2, 2, 2, 0], dtype=float)
    wins = _carve(t, y, u=1.0)
    assert len(wins) == 1
    assert wins[0]["death_type"] == windows.DEATH_GAP_START


@pytest.mark.unit
def test_a_reading_exactly_at_the_threshold_is_in_spec_and_the_asymmetry_is_deliberate() -> (
    None
):
    """Oracle: `AGENTS.md` section 5 ("in-spec means at or above the threshold") and the
    KNOWN DIVERGENCE recorded in `windows.in_spec_mask`'s own docstring.

    Section 5 says none of the domain invariants fails a test, and measured, that was true
    here: mutating `in_spec_mask`'s `>=` to `>` (and its `<` to `<=`) left the entire suite
    green, because every carve fixture uses values well clear of its threshold.

    Both directions are pinned, including the asymmetry the docstring calls inherited
    rather than a typo: with `big_values_good=True` a reading AT the threshold is in spec,
    and with `big_values_good=False` the same reading is OUT of spec. That second half is
    the documented divergence from `within_calibration_compute._out_of_spec_mask`, which
    calls it in spec. Reconciling them changes published numbers, so this test pins the
    divergence as it stands rather than asserting the pair agree.
    """
    at = np.array([5.0])
    assert windows.in_spec_mask(at, 5.0, big_values_good=True).tolist() == [True]
    assert windows.in_spec_mask(at, 5.0, big_values_good=False).tolist() == [False]
    # and the neighbours, so the test fails on a shifted comparison rather than only a
    # flipped one
    assert windows.in_spec_mask(np.array([4.99, 5.01]), 5.0, True).tolist() == [
        False,
        True,
    ]
    assert windows.in_spec_mask(np.array([4.99, 5.01]), 5.0, False).tolist() == [
        True,
        False,
    ]


@pytest.mark.unit
def test_equality_is_not_a_gap() -> None:
    # spacing exactly == gap_threshold must not count; the test is strict `>`.
    t = np.array([0.0, 1.0, 2.0, 12.0])  # median 1.0 -> threshold 10.0, last step 10.0
    _, gap_threshold_s, n_gaps, _ = windows.spacing(t, gap_mult=10.0)
    assert gap_threshold_s == 10.0
    assert n_gaps == 0


# -------------------- what does and does not move a boundary (8.4a)


PRIVATE_ROOT = repo_root() / "data" / "real_private"


# READ from the jobs, not transcribed. A hardcoded copy is not a guard: it agreed with
# itself while either job drifted, which is the dead-control defect AGENTS.md section 4
# records. `GAP_MULT` is the parameter that actually moves a boundary.
def _job_gap_mult(stem: str) -> float:
    path = repo_root() / "jobs" / "active" / f"{stem}.py"
    if not path.is_file():
        pytest.skip(f"{path} absent")
    text = path.read_text(encoding="utf-8")
    found = re.search(r"gap_mult=([0-9.]+)", text) or re.search(
        r"^GAP_MULT\s*=\s*([0-9.]+)", text, re.M
    )
    assert found, f"no gap_mult literal found in {stem}.py"
    return float(found.group(1))


def _poster_carve() -> dict:
    return {
        "gap_mult": _job_gap_mult("km_poster_6d2s"),
        "k": 1.0,
        "use_uncertainty": False,
    }


def _survey_carve() -> dict:
    return {
        "gap_mult": _job_gap_mult("km_with_checks_6d2s"),
        "k": 1.0,
        "use_uncertainty": True,
    }


THRESHOLD_LABEL = "3.0 µs"
THRESHOLD = [(THRESHOLD_LABEL, 3.0e-6, True)]


def _synthetic_reads(n: int = 400):
    """Reads that cross the rung many times, with a sigma large enough to make most of them
    'uncertain' if uncertainty were allowed to move anything."""
    rng = np.random.default_rng(11)
    t = np.arange(n, dtype=float) * 30.0
    values = 3.0e-6 + 1.2e-6 * np.sin(np.arange(n) / 7.0) + rng.normal(0, 3e-7, n)
    sigma = np.full(n, 8e-7)
    return t, values, sigma


def _carve_annotated(*, use_uncertainty: bool):
    t, values, sigma = _synthetic_reads()
    return windows.run(
        windows.WindowsInputs(
            t_rel_s=t,
            values=values,
            thresholds=THRESHOLD,
            sigma=sigma if use_uncertainty else None,
            k=1.0,
            gap_mult=10.0,
            use_uncertainty=use_uncertainty,
        )
    )


@pytest.mark.unit
def test_uncertainty_annotates_reads_and_never_moves_a_window_boundary():
    """The contract, on synthetic reads, in CI. Both halves are asserted: the window table
    must be identical AND the read states must actually differ, or the test would pass
    vacuously on a sigma too small to annotate anything."""
    plain = _carve_annotated(use_uncertainty=False)
    annotated = _carve_annotated(use_uncertainty=True)

    wp = plain.windows.reset_index(drop=True)
    wa = annotated.windows.reset_index(drop=True)
    assert len(wp) > 5, "the fixture must produce several windows to be worth comparing"
    assert wp.equals(wa), (
        "use_uncertainty moved a window boundary; it must only annotate"
    )

    states_plain = set(plain.reads["state"])
    states_annotated = set(annotated.reads["state"])
    assert states_plain != states_annotated, (
        "the fixture's sigma is too small to annotate anything, so the test above proved "
        f"nothing: {states_plain} vs {states_annotated}"
    )
    assert any("uncertain" in s for s in states_annotated)


@pytest.mark.integration
@pytest.mark.real
@pytest.mark.parametrize(
    "stem,qubit",
    [
        ("280623_6D2S_qubit2", 2),
        ("040423_6D2S_qubit1", 1),
        ("220423_6D2S_qubit1", 1),
        ("090623_6D2S_qubit6", 6),
        ("070723_6D2S_qubit4", 4),
    ],
)
def test_the_two_job_configurations_agree_on_the_real_records(stem, qubit, in_repo):
    """The differential CHECKPOINT 8.4a owes: real records, the real parameter sets.

    Skips without the private tree, following `tests/test_data_manifest.py`. If this ever
    fails, the two jobs have diverged on something that DOES move boundaries and the new job's
    check outcome would describe a different carve from the band beside it.
    """
    path = PRIVATE_ROOT / "6D2S" / f"{stem}.pickle"
    if not path.is_file():
        pytest.skip(f"{path} absent (expected without the private data)")

    from quebra.analyzers import t2star
    from quebra.core.dataset import Dataset
    from quebra.core.job import _load_dataset
    from quebra.recipes import RAMSEY_CONFIG, _filter_step, _final_stage
    from quebra.schemas.track912 import track912Schema

    dataset = Dataset(
        path=f"data/real_private/6D2S/{stem}.pickle",
        schema=track912Schema,
        qubit=qubit,
        device="6D2S",
        extra={"run_name": stem},
    )
    norm = _final_stage(_filter_step(RAMSEY_CONFIG)(_load_dataset(dataset)))
    frame = t2star.run(t2star.make_inputs_from_norm(norm)).frame

    def carve(config):
        return windows.run(
            windows.make_inputs_from_frame(
                frame,
                time_col="t_rel_s",
                value_col="t2star_s",
                thresholds=THRESHOLD,
                dataset_id=stem,
                sigma_col="t2star_error_s" if config["use_uncertainty"] else None,
                **config,
            )
        ).windows

    poster = carve(_poster_carve()).reset_index(drop=True)
    survey = carve(_survey_carve()).reset_index(drop=True)

    assert len(poster), f"{stem} produced no windows at {THRESHOLD_LABEL}"
    assert poster.equals(survey), (
        f"{stem}: the poster and survey carve configurations disagree on the window table. "
        f"That is a divergence in something that moves boundaries, not an annotation."
    )
