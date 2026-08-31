"""The survey must describe the SAME windows the panels describe.

`jobs/composite/independence_survey.py` cannot `include` thirty-four per-dataset jobs
because thirty-two of them do not exist, so it re-wires the carve. Its docstring says the
parameters "must stay equal to those jobs' or the survey and the panels describe different
windows". This file is what makes that true rather than a comment - a carve parameter drifting
in one file and not the other is silent, produces plausible figures, and is exactly the class
of defect this repo's provenance rules exist to catch.
"""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from quebra.analyzers.check_ledger import (
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_UNDERPOWERED,
)
from quebra.analyzers.checks.battery import ROW_KEYS
from quebra.analyzers.independence_survey import (
    CHECK_LABELS,
    CHECK_NULL,
    InstrumentGrid,
    build_independence_survey,
    survey_summary,
)
from quebra.plots.independence_survey_plot import SURVEY_PLOTS

REPO = Path(__file__).resolve().parents[1]


def _module_constants(relative: str) -> dict[str, object]:
    """Read a job's module-level literal assignments WITHOUT importing it.

    Importing a job builds its DAG and, for the survey, declares thirty-four datasets - so
    a test that imported them would be slow and would fail on a machine with no data root.
    The AST route reads only what is written in the file.
    """
    tree = ast.parse((REPO / relative).read_text())
    out: dict[str, object] = {}
    for node in tree.body:
        # AnnAssign as well as Assign: `DATASET_FILES: tuple[str, ...] = (...)` is an
        # annotated assignment, and reading only `Assign` silently skipped it - the test
        # that was meant to guard the dataset list passed by not finding it.
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name, value = node.target.id, node.value
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            name, value = node.targets[0].id, node.value
        else:
            continue
        if value is None:
            continue
        try:
            out[name] = ast.literal_eval(value)
        except (ValueError, SyntaxError, TypeError):
            pass
    return out


SURVEY = _module_constants("jobs/composite/independence_survey.py")
LEDGER_JOB = _module_constants("jobs/composite/check_ledger_q1.py")


# ------------------------------------------------------------------ the carve matches


def _effective_t2star_carve() -> dict[str, object]:
    """The carve the T2* job ACTUALLY uses: a job override if present, else the recipe default.

    SPEC 0005 R5.3 collapsed the two T2* jobs onto `recipes.configure_t2star_job`, so these
    three moved from inline step kwargs into the recipe's signature. Reading only the job file
    would now find nothing and this control would pass vacuously; reading only the recipe
    would miss a job that overrides it. The effective value is the one that decides the
    windows, so the effective value is what must match.
    """
    import inspect

    from quebra.recipes import configure_t2star_job

    effective = {
        name.upper(): param.default
        for name, param in inspect.signature(configure_t2star_job).parameters.items()
        if name in ("gap_mult", "k", "use_uncertainty")
    }
    # A job passing its own value wins over the default. An override we cannot READ must
    # FAIL, not fall back to the default: pre-seeding the defaults and then swallowing an
    # unreadable override made this control weaker than the form it replaced. Measured -
    # `gap_mult=MY_GAP` in the job left the scan reporting the default 10.0 and the test
    # passing while the job carved with 99.0, where the pre-collapse form raised on the
    # missing key. That is precisely the "survey and panel describe different windows"
    # defect this module exists to catch.
    tree = ast.parse((REPO / "jobs/active/t2star_q1_070423.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg in ("gap_mult", "k", "use_uncertainty"):
                    try:
                        effective[kw.arg.upper()] = ast.literal_eval(kw.value)
                    except (ValueError, SyntaxError):
                        pytest.fail(
                            f"the T2* job overrides {kw.arg} with a non-literal, so this "
                            f"control cannot tell what it carves with. Make it a literal, or "
                            f"teach this scan to evaluate it - do not let it read as the "
                            f"recipe default."
                        )
    return effective


@pytest.mark.parametrize("name", ["GAP_MULT", "K", "USE_UNCERTAINTY"])
def test_the_survey_carves_windows_the_same_way_the_t2star_job_does(name):
    """These three define the carve. A difference here means different windows."""
    found = _effective_t2star_carve()
    assert name in found, f"{name} is neither a recipe default nor a job override"
    assert SURVEY[name] == found[name], (
        f"survey {name}={SURVEY[name]} but the T2* job effectively uses {found[name]}; the "
        "survey would describe different windows from the panel"
    )


def _evaluated_constant(relative: str, name: str) -> object:
    """Evaluate a module-level constant that `literal_eval` cannot handle.

    `THRESHOLDS` is a list COMPREHENSION in both composites, and `ast.literal_eval` raises
    on a ListComp - so `_module_constants` silently omitted it and any test reading it from
    there got a KeyError or, worse, compared against a value retyped in the test. That is
    what happened here: this test used to build its own copy of the ladder and assert the
    T2* job matched IT, so mutating the SURVEY's ladder changed nothing and the test passed.
    Measured: `k / 1e6` -> `k * 1e-6` and `range(1, 11)` -> `range(1, 9)` both left 20/20
    green. A control that cannot fail when the thing it guards is broken is not a control.

    `eval` on repo source, not on input: the file is read from this repository and its AST
    is unparsed back, so nothing outside the tree is executed.
    """
    tree = ast.parse((REPO / relative).read_text())
    for node in tree.body:
        target = (
            node.target
            if isinstance(node, ast.AnnAssign)
            else node.targets[0]
            if isinstance(node, ast.Assign) and len(node.targets) == 1
            else None
        )
        if (
            isinstance(target, ast.Name)
            and target.id == name
            and node.value is not None
        ):
            # `range` is needed by the comprehension; the namespace stays otherwise empty.
            return eval(  # noqa: S307
                ast.unparse(node.value), {"__builtins__": {"range": range}}, {}
            )
    raise AssertionError(f"{name} not found in {relative}")


def test_the_survey_scores_the_same_threshold_ladder():
    """Compare the survey's OWN ladder to the panel's, both read from their source.

    The T2* job writes explicit tuples and the survey builds a comprehension, so the two
    never match textually. What must match is the ladder they produce - a survey scoring a
    different set of thresholds would put its columns out of correspondence with the
    panel's without anything looking wrong.
    """
    survey_ladder = [
        tuple(row)
        for row in _evaluated_constant(
            "jobs/composite/independence_survey.py", "THRESHOLDS"
        )
    ]
    # The ladder moved to `recipes.T2STAR_THRESHOLDS` when SPEC 0005 R5.3 collapsed the
    # family. Read it from there, which is where the T2* job now gets it.
    from quebra.recipes import T2STAR_THRESHOLDS

    panel_ladder = [tuple(row) for row in T2STAR_THRESHOLDS]
    assert len(survey_ladder) == 10
    # Exact equality, including the float. `k * 1e-6` fails this at k = 5 and k = 10,
    # which is how the discrepancy was found; `k / 1e6` reproduces the literals exactly.
    assert survey_ladder == panel_ladder, (
        f"survey ladder {survey_ladder[:2]}... != T2* job ladder {panel_ladder[:2]}..."
    )


@pytest.mark.parametrize(
    "name",
    ["ALPHA", "MIN_EVENTS_PASS", "TIE_CUTOFF_DISTINCT", "LAG_MAX", "N_PERMUTATIONS"],
)
def test_the_survey_turns_p_values_into_verdicts_the_same_way_the_q1_ledger_does(name):
    """Otherwise a cell could be `pass` in one figure and `underpowered` in the other.

    SEED is deliberately NOT in this list - see `test_the_two_ledgers_use_different_seeds`.
    """
    assert SURVEY[name] == LEDGER_JOB[name], (
        f"survey {name}={SURVEY[name]} but check_ledger_q1 uses {LEDGER_JOB[name]}"
    )


def test_the_two_ledgers_use_different_seeds():
    """The one parameter that must NOT match, and the reason it must not.

    Sharing a permutation seed across two jobs makes their Monte Carlo error identical
    rather than independent, so a rung sitting near alpha lands the same way in both and
    reads as corroboration when it is one draw counted twice. The five verdict parameters
    above must match; this one must differ.
    """
    assert SURVEY["SEED"] != LEDGER_JOB["SEED"]


def test_c3_is_on_and_its_simulation_count_is_declared():
    """C3 was OFF and this test pinned that; inverted, not deleted, when it was turned on.

    C3 is the one instrument in the survey with no bench cell, so it cannot be scored the
    way the other nine are. The count matters as much as the flag: the C3 p-value floor is
    `1/(N+1)`, so a survey run at N = 200 is reading a different object from the
    single-dataset ledger at N = 1000, and the number has to be declared rather than
    inherited from a module default.
    """
    assert SURVEY["INCLUDE_C3"] is True
    assert SURVEY["C3_N_NULL_SIM"] >= 200, (
        "below N = 200 the p-value floor rises above 0.005 and starts to crowd alpha"
    )


def test_c3_is_not_in_the_row_schema_so_it_cannot_be_bench_scored():
    """The consequence of C3 being on: it is in the figures but not in ROW_KEYS.

    Nothing may quietly start treating it as a scored check - `bench_acceptance_at_n` has
    no cell for it, so its verdicts carry no power evidence.
    """
    assert not any(key[0] == "c3_serial_copula" for key in ROW_KEYS)


def test_every_declared_dataset_is_unique_and_named_once():
    files = SURVEY["DATASET_FILES"]
    assert len(files) == len(set(files))
    assert all(f.endswith(".pickle") for f in files)


# -------------------------------------------------------------- one figure per check


def test_there_is_exactly_one_figure_per_surveyed_instrument():
    """Adding a check to the battery must add a figure, not silently drop one.

    The list is SURVEY_KEYS, not ROW_KEYS: C3 is surveyed but deliberately not bench-scored,
    and it was RUN but drawn nowhere until this was separated - the ledger computed C3 rows
    for every dataset and every grid was built from ROW_KEYS, so they went in the bin.
    """
    from quebra.analyzers.independence_survey import SURVEY_KEYS

    assert len(SURVEY_PLOTS) == len(SURVEY_KEYS)
    assert [p.KEY for p in SURVEY_PLOTS] == list(SURVEY_KEYS)


def test_the_survey_draws_c3_even_though_the_bench_cannot_score_it():
    from quebra.analyzers.independence_survey import C3_KEY, SURVEY_KEYS

    assert C3_KEY in SURVEY_KEYS
    assert C3_KEY not in ROW_KEYS
    assert any(p.KEY == C3_KEY for p in SURVEY_PLOTS)


def test_every_surveyed_key_has_a_label_and_a_stated_null():
    """A grid whose caption cannot say what a red cell MEANS is not publishable."""
    from quebra.analyzers.independence_survey import SURVEY_KEYS

    for key in SURVEY_KEYS:
        assert key in CHECK_LABELS and CHECK_LABELS[key].strip()
        assert key in CHECK_NULL and "reject" in CHECK_NULL[key]


# --------------------------------------------------------------------- the reshape


def _fake_ledger(dataset_id: str, verdicts: dict[str, str]) -> object:
    rows = []
    for threshold, verdict in verdicts.items():
        for check, calibration, variant in ROW_KEYS:
            rows.append(
                {
                    "dataset_id": dataset_id,
                    "threshold_label": threshold,
                    "clock": "in_spec",
                    "check_id": check,
                    "calibration": calibration,
                    "variant": variant,
                    "p_value": 0.01 if verdict == VERDICT_FAIL else 0.5,
                    "verdict": verdict,
                    "n_events": 100,
                }
            )

    class _L:
        pass

    ledger = _L()
    ledger.rows = pd.DataFrame(rows)
    ledger.dataset_id = dataset_id
    return ledger


def test_the_reshape_keeps_every_dataset_and_threshold():
    a = _fake_ledger("A", {"1 µs": VERDICT_PASS, "2 µs": VERDICT_FAIL})
    b = _fake_ledger("B", {"1 µs": VERDICT_FAIL, "2 µs": VERDICT_PASS})
    data = build_independence_survey(a, b, dataset_labels=("A", "B"))
    assert data.datasets == ["A", "B"]
    assert data.thresholds == ["1 µs", "2 µs"]
    assert len(data.grids) == len(ROW_KEYS)
    for grid in data.grids:
        assert grid.verdicts.shape == (2, 2)


def test_a_label_count_mismatch_raises_rather_than_guessing():
    a = _fake_ledger("A", {"1 µs": VERDICT_PASS})
    with pytest.raises(ValueError, match="will not guess"):
        build_independence_survey(a, dataset_labels=("A", "B"))


def test_a_non_ledger_input_raises():
    with pytest.raises(TypeError, match="not a CheckLedger"):
        build_independence_survey(object())


def test_threshold_order_follows_the_ladder_not_alphabetical_sort():
    """`10 µs` sorts before `2 µs` as a string; the ladder must not be drawn out of order."""
    a = _fake_ledger("A", {"2 µs": VERDICT_PASS, "10 µs": VERDICT_PASS})
    data = build_independence_survey(a, dataset_labels=("A",))
    assert data.thresholds == ["2 µs", "10 µs"]


def test_rejection_share_divides_by_DECIDED_cells_not_by_every_cell():
    """The claim CLAUDE.md's aggregation rule is about: state what the denominator is.

    A grid of 2 rejections and 38 powerless cells is "2 of 2 decided cells rejected", not
    "5% rejection". The second reads as reassurance and is not a rate of anything.
    """
    verdicts = pd.DataFrame(
        [[VERDICT_FAIL, VERDICT_UNDERPOWERED], [VERDICT_UNDERPOWERED, VERDICT_PASS]]
    )
    grid = InstrumentGrid(
        key=ROW_KEYS[0],
        label="x",
        null_statement="rejects when x",
        clock="in_spec",
        verdicts=verdicts,
        p_values=verdicts,
        n_events=verdicts,
    )
    assert grid.counts[VERDICT_UNDERPOWERED] == 2
    assert grid.rejection_share_of_decided == pytest.approx(0.5)


def test_a_grid_with_nothing_decided_reports_nan_not_zero():
    """Zero would read as 'nothing rejected', which is not what 'nothing was decided' means."""
    verdicts = pd.DataFrame([[VERDICT_UNDERPOWERED, VERDICT_UNDERPOWERED]])
    grid = InstrumentGrid(
        key=ROW_KEYS[0],
        label="x",
        null_statement="rejects when x",
        clock="in_spec",
        verdicts=verdicts,
        p_values=verdicts,
        n_events=verdicts,
    )
    assert np.isnan(grid.rejection_share_of_decided)


def test_the_summary_has_one_row_per_grid():
    a = _fake_ledger("A", {"1 µs": VERDICT_PASS})
    data = build_independence_survey(a, dataset_labels=("A",))
    assert len(survey_summary(data)) == len(data.grids)
