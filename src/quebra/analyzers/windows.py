"""In-spec window carving: gap policy, censoring, window identity, per-read table.

Ported from `monoliths/v13fig/v13_shape.py::spacing/carve`, with two deliberate
differences from that reference:

- **Death timestamp.** This module keeps the repo's convention - a window dies at the
  FIRST OUT-OF-SPEC read, so the interval spanning the crossing is inside the lifetime.
  `v13_shape` measured to the last in-spec read instead. Censored windows have no
  out-of-spec read to point at, so they die at their last in-spec read.
- **`min_reads` is not ported HERE.** `v13_shape` drops windows with fewer than 5 reads
  before any statistic; carving without that filter is what preserves parity with the
  pre-existing carve. The filter does exist downstream: `analyzers/distinguish_band.py`
  applies `shape_min_reads` (default 5) to decide which windows enter the excursion
  shape statistics, and nothing else. It never touches a boundary, duration or count.

Everything else - the gap threshold, the strict `>` test, the positive-only median, the
birth/death taxonomy, gap-wins-ties - is the monolith's, verbatim.

Uncertainty is an ANNOTATION and never moves a window boundary. The carve is crisp
(`value >= threshold`), so `k` and `use_uncertainty` change the per-read `state` column
and nothing else. Deciding whether an uncertain read should break a window is a question
`scripts/probe_unresolved.py` exists to answer; it must not be answered by assumption here.

All times are SI seconds (`_s` suffixes). Values and thresholds share whatever unit the
caller supplies; only their comparison matters.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

DEFAULT_GAP_MULT = 10.0

# Birth types. A window is an "endurance bag" when its birth was not observed, i.e.
# birth_type != BIRTH_UP_CROSSING. Tagged here; never dropped here.
BIRTH_UP_CROSSING = "up_crossing"
BIRTH_SCAN_START = "scan_start"
BIRTH_GAP_RESUME = "gap_resume"

# Death types. censored == (death_type != DEATH_DOWN_CROSSING).
DEATH_DOWN_CROSSING = "down_crossing"
DEATH_GAP_START = "gap_start"
DEATH_SCAN_END = "scan_end"

# Per-read states. The two _uncertain states appear only when use_uncertainty is on.
STATE_IN_SPEC = "in_spec"
STATE_OUT_OF_SPEC = "out_of_spec"
STATE_IN_SPEC_UNCERTAIN = "in_spec_uncertain"
STATE_OUT_OF_SPEC_UNCERTAIN = "out_of_spec_uncertain"
# Not a state of the system - a state of the RECORD. A timeline that simply breaks at a
# gap is ambiguous (missing? in spec? a layout artefact?); an explicit grey band says
# "the instrument was not reporting here" and keeps the axis continuous so two timelines
# stay comparable read for read.
STATE_UNOBSERVED = "unobserved"

WINDOW_COLUMNS = [
    "dataset_id",
    "threshold_label",
    "threshold_value",
    "big_values_good",
    "window_index",
    "t_birth_s",
    "t_death_s",
    "duration_s",
    "birth_type",
    "death_type",
    "censored",
    "n_reads",
]

READ_COLUMNS = [
    "dataset_id",
    "threshold_label",
    "window_index",
    "t_read_s",
    "value",
    "margin",
    "window_age_s",
    "forward_time_s",
    "sigma_v",
    "sigma_known",
    "in_spec",
    "state",
]


@dataclass(slots=True)
class WindowsInputs:
    t_rel_s: np.ndarray
    values: np.ndarray
    thresholds: list[tuple[str, float, bool]]  # (label, value, big_values_good)
    sigma: np.ndarray | None = None  # per-read 1-sigma, same unit as values
    dataset_id: str = ""
    gap_mult: float = DEFAULT_GAP_MULT
    k: float = 1.0
    use_uncertainty: bool = False


@dataclass(slots=True)
class WindowsResult:
    windows: pd.DataFrame
    reads: pd.DataFrame
    meta: dict[str, object]
    diagnostics: dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Gap policy
# ---------------------------------------------------------------------------


def spacing(t_rel_s: np.ndarray, gap_mult: float = DEFAULT_GAP_MULT):
    """Median read spacing and the derived gap threshold.

    The median is over POSITIVE differences only. Duplicated timestamps are common in
    scan-structured records and would otherwise drive the median to zero, making every
    positive step a gap and destroying every window.

    Returns (median_spacing_s, gap_threshold_s, n_gaps, n_nonpositive_steps).
    """
    dt = np.diff(np.asarray(t_rel_s, dtype=float))
    if len(dt) == 0:
        return 1.0, float("inf"), 0, 0
    n_nonpositive = int((dt <= 0).sum())
    positive = dt[dt > 0]
    if not len(positive):
        # Every step is a duplicate or a step backwards, so there is no observed
        # spacing to scale the gap threshold by. Inventing one (the reference
        # monolith falls back to 1.0) would silently put a fabricated physical
        # scale into every window boundary downstream.
        raise ValueError(
            f"cannot derive a read spacing: all {len(dt)} inter-read steps are "
            f"non-positive. A gap threshold needs at least one positive spacing."
        )
    median_s = float(np.median(positive))
    gap_threshold_s = gap_mult * median_s
    # Strict: a spacing exactly equal to the threshold is NOT a gap.
    n_gaps = int((dt > gap_threshold_s).sum())
    return median_s, gap_threshold_s, n_gaps, n_nonpositive


def gap_flags(t_rel_s: np.ndarray, gap_threshold_s: float) -> np.ndarray:
    """Read i opens a new segment. Index 0 is never a gap, so the first read of a
    record is always a scan_start and never a gap_resume."""
    dt = np.diff(np.asarray(t_rel_s, dtype=float))
    return np.r_[False, dt > gap_threshold_s]


def carve(
    t_rel_s: np.ndarray,
    in_spec: np.ndarray,
    is_gap: np.ndarray,
) -> list[dict[str, object]]:
    """Segment a boolean in-spec mask into windows with birth and death types.

    Returns dicts of {s, e, birth_type, death_type} where `s` is the index of the first
    in-spec read and `e` is one past the last in-spec read - so for a down_crossing `e`
    indexes the first out-of-spec read, which is the death timestamp.

    The gap check runs BEFORE the in-spec check, so a read that is both post-gap and
    out-of-spec produces gap_start, not down_crossing. Gap wins ties.
    """
    n = len(in_spec)
    windows: list[dict[str, object]] = []
    i = 0
    while i < n:
        if not in_spec[i]:
            i += 1
            continue
        s = i
        if s == 0:
            birth = BIRTH_SCAN_START
        elif is_gap[s]:
            birth = BIRTH_GAP_RESUME
        else:
            birth = BIRTH_UP_CROSSING
        j = s
        death: str | None = None
        while j + 1 < n:
            if is_gap[j + 1]:
                death = DEATH_GAP_START
                break
            if not in_spec[j + 1]:
                death = DEATH_DOWN_CROSSING
                break
            j += 1
        if death is None:
            death = DEATH_SCAN_END
        windows.append({"s": s, "e": j + 1, "birth_type": birth, "death_type": death})
        i = j + 1
    return windows


def mark_gaps_in_segments(
    segments: list[tuple[float, float, str]],
    gap_spans_h: list[tuple[float, float]],
) -> list[tuple[float, float, str]]:
    """Replace the part of any timeline segment inside a read gap with STATE_UNOBSERVED.

    A compliance bar drawn across a gap asserts a state through hours the instrument
    was not reporting - the same claim the carve refuses to make when it terminates a
    window with `gap_start`. But a bar that simply STOPS is just as bad: a blank reads
    as "in spec" or as a rendering artefact. The gap gets its own colour instead, so the
    timeline stays continuous and unobserved time is stated rather than implied.

    Preconditions, held by the only producer (`run` emits one span per consecutive read
    pair): `gap_spans_h` are disjoint, and `segments` tile one contiguous stretch.
    Overlapping spans would double-count the overlap.
    """
    if not gap_spans_h:
        return sorted(segments)
    out: list[tuple[float, float, str]] = []
    for start, end, state in segments:
        pieces = [(start, end)]
        for lo, hi in gap_spans_h:
            nxt: list[tuple[float, float]] = []
            for a, b in pieces:
                if b <= lo or a >= hi:
                    nxt.append((a, b))
                    continue
                if a < lo:
                    nxt.append((a, lo))
                if b > hi:
                    nxt.append((hi, b))
            pieces = nxt
        out.extend((a, b, state) for a, b in pieces if b > a)
    # the gap itself, once per span, clipped to the timeline's own extent
    if segments:
        lo_edge = min(a for a, _, _ in segments)
        hi_edge = max(b for _, b, _ in segments)
        for lo, hi in gap_spans_h:
            a, b = max(lo, lo_edge), min(hi, hi_edge)
            if b > a:
                out.append((a, b, STATE_UNOBSERVED))
    return sorted(out)


def in_spec_mask(
    values: np.ndarray, threshold_value: float, big_values_good: bool
) -> np.ndarray:
    """In-spec test, matching the pre-existing panel carve exactly.

    Note the asymmetry - `>=` above, `<` below - it is inherited, not a typo.

    KNOWN DIVERGENCE, preserved deliberately: at exact equality with
    `big_values_good=False`, this calls `value == threshold` OUT of spec, while
    `panels/_within_calibration_compute._out_of_spec_mask` (`value > threshold`) calls it
    IN spec. Both predate this module and both are load-bearing - one drives the
    windows, the other drives cumulative time, TTF and in-spec fraction. Reconciling
    them changes published numbers, so it is a decision to take deliberately rather
    than a typo to fix in passing. Measure-zero in float; fidelity (`big_values_good=False`)
    is the direction where it is reachable at all.
    """
    if big_values_good:
        return values >= threshold_value
    return values < threshold_value


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


def make_inputs_from_frame(
    frame: pd.DataFrame,
    *,
    time_col: str,
    value_col: str,
    thresholds: list[tuple[str, float, bool]],
    dataset_id: str = "",
    sigma_col: str | None = None,
    gap_mult: float = DEFAULT_GAP_MULT,
    k: float = 1.0,
    use_uncertainty: bool = False,
) -> WindowsInputs:
    for col in (time_col, value_col):
        if col not in frame.columns:
            raise KeyError(f"windows requires column {col!r} in the frame")
    sigma = None
    if sigma_col is not None:
        if sigma_col not in frame.columns:
            raise KeyError(
                f"windows was asked for sigma column {sigma_col!r}, which the frame "
                f"does not have. Columns: {list(frame.columns)}"
            )
        sigma = frame[sigma_col].to_numpy(dtype=float)
    return WindowsInputs(
        t_rel_s=frame[time_col].to_numpy(dtype=float),
        values=frame[value_col].to_numpy(dtype=float),
        thresholds=list(thresholds),
        sigma=sigma,
        dataset_id=dataset_id,
        gap_mult=gap_mult,
        k=k,
        use_uncertainty=use_uncertainty,
    )


def make_inputs_from_norm(
    norm: Mapping[str, object],
    *,
    value_key: str,
    thresholds: list[tuple[str, float, bool]],
    sigma_key: str | None = None,
    gap_mult: float = DEFAULT_GAP_MULT,
    k: float = 1.0,
    use_uncertainty: bool = False,
) -> WindowsInputs:
    if "t_rel_s" not in norm:
        raise KeyError("windows requires 't_rel_s' in the normalized mapping.")
    if value_key not in norm:
        raise KeyError(f"windows requires {value_key!r} in the normalized mapping.")
    meta = norm.get("meta", {}) if isinstance(norm.get("meta", {}), Mapping) else {}
    sigma = None
    if sigma_key is not None:
        if sigma_key not in norm:
            raise KeyError(
                f"windows was asked for sigma key {sigma_key!r}, which the norm does "
                f"not have."
            )
        sigma = np.asarray(norm[sigma_key], dtype=float)
    return WindowsInputs(
        t_rel_s=np.asarray(norm["t_rel_s"], dtype=float),
        values=np.asarray(norm[value_key], dtype=float),
        thresholds=list(thresholds),
        sigma=sigma,
        dataset_id=str(meta.get("dataset_id", "")),
        gap_mult=gap_mult,
        k=k,
        use_uncertainty=use_uncertainty,
    )


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def run(inputs: WindowsInputs) -> WindowsResult:
    """Carve every threshold on the ladder and emit the window and read tables."""
    t_all = np.asarray(inputs.t_rel_s, dtype=float)
    v_all = np.asarray(inputs.values, dtype=float)
    if len(t_all) != len(v_all):
        raise ValueError(
            f"t_rel_s and values must be the same length; got {len(t_all)} and "
            f"{len(v_all)}"
        )
    sigma_all = inputs.sigma
    if sigma_all is not None:
        sigma_all = np.asarray(sigma_all, dtype=float)
        if len(sigma_all) != len(t_all):
            raise ValueError(
                f"sigma must be the same length as t_rel_s; got {len(sigma_all)} and "
                f"{len(t_all)}"
            )
    if inputs.use_uncertainty and sigma_all is None:
        raise ValueError(
            "use_uncertainty=True requires a sigma array. A dataset with no error "
            "column is legal, but then use_uncertainty must be False - the uncertain "
            "states cannot be silently inferred."
        )

    # ORDER IS LOAD-BEARING: drop non-finite (t, value) pairs BEFORE measuring spacing,
    # so a run of failed fits widens the interval into a real gap. Doing it the other
    # way round either measures spacing on the wrong array or lets NaN >= threshold
    # evaluate False and fabricate a down-crossing at every failed fit.
    finite = np.isfinite(t_all) & np.isfinite(v_all)
    t = t_all[finite]
    v = v_all[finite]
    sigma = sigma_all[finite] if sigma_all is not None else None

    # Durations are t_death - t_birth, so time running backwards yields NEGATIVE
    # lifetimes that flow straight onto the survival curve - finite, plausible and
    # wrong. Loaders sort by timestamp; a caller that did not has a bug upstream.
    if len(t) > 1 and bool(np.any(np.diff(t) < 0)):
        raise ValueError(
            "t_rel_s must be non-decreasing; got a time array that steps backwards. "
            "Sort the reads by timestamp before carving."
        )

    median_s, gap_threshold_s, n_gaps, n_nonpositive = spacing(t, inputs.gap_mult)
    is_gap = gap_flags(t, gap_threshold_s) if len(t) else np.zeros(0, dtype=bool)

    sigma_known = (
        np.isfinite(sigma) if sigma is not None else np.zeros(len(t), dtype=bool)
    )

    window_rows: list[dict[str, object]] = []
    read_rows: list[dict[str, object]] = []
    per_threshold: dict[str, dict[str, object]] = {}

    for label, thr_value, big_values_good in inputs.thresholds:
        if len(t) < 2:
            per_threshold[label] = {
                "n_windows": 0,
                "n_censored": 0,
                "n_endurance_bags": 0,
            }
            continue

        ins = in_spec_mask(v, thr_value, big_values_good)
        windows = carve(t, ins, is_gap)

        window_of_read = np.full(len(t), -1, dtype=int)
        birth_of_read = np.full(len(t), np.nan, dtype=float)
        death_of_read = np.full(len(t), np.nan, dtype=float)

        for index, w in enumerate(windows):
            s = int(w["s"])
            e = int(w["e"])
            death_type = str(w["death_type"])
            t_birth_s = float(t[s])
            # A down_crossing dies at the first OUT-OF-SPEC read (index e). A censored
            # window has no such read, so it dies at its last in-spec read (index e-1).
            if death_type == DEATH_DOWN_CROSSING:
                t_death_s = float(t[e])
            else:
                t_death_s = float(t[e - 1])
            window_rows.append(
                {
                    "dataset_id": inputs.dataset_id,
                    "threshold_label": label,
                    "threshold_value": float(thr_value),
                    "big_values_good": bool(big_values_good),
                    "window_index": index,
                    "t_birth_s": t_birth_s,
                    "t_death_s": t_death_s,
                    "duration_s": t_death_s - t_birth_s,
                    "birth_type": str(w["birth_type"]),
                    "death_type": death_type,
                    "censored": death_type != DEATH_DOWN_CROSSING,
                    "n_reads": e - s,
                }
            )
            window_of_read[s:e] = index
            birth_of_read[s:e] = t_birth_s
            death_of_read[s:e] = t_death_s

        margin = (v - thr_value) if big_values_good else (thr_value - v)
        state = np.where(ins, STATE_IN_SPEC, STATE_OUT_OF_SPEC).astype(object)
        if inputs.use_uncertainty:
            uncertain = np.zeros(len(t), dtype=bool)
            uncertain[sigma_known] = (
                np.abs(v[sigma_known] - thr_value) < inputs.k * sigma[sigma_known]
            )
            state[uncertain & ins] = STATE_IN_SPEC_UNCERTAIN
            state[uncertain & ~ins] = STATE_OUT_OF_SPEC_UNCERTAIN

        for i in range(len(t)):
            has_window = window_of_read[i] >= 0
            read_rows.append(
                {
                    "dataset_id": inputs.dataset_id,
                    "threshold_label": label,
                    "window_index": int(window_of_read[i]) if has_window else None,
                    "t_read_s": float(t[i]),
                    "value": float(v[i]),
                    "margin": float(margin[i]),
                    "window_age_s": float(t[i] - birth_of_read[i])
                    if has_window
                    else None,
                    "forward_time_s": float(death_of_read[i] - t[i])
                    if has_window
                    else None,
                    "sigma_v": float(sigma[i]) if sigma is not None else None,
                    "sigma_known": bool(sigma_known[i]),
                    "in_spec": bool(ins[i]),
                    "state": str(state[i]),
                }
            )

        n_censored = sum(1 for w in windows if w["death_type"] != DEATH_DOWN_CROSSING)
        n_endurance = sum(1 for w in windows if w["birth_type"] != BIRTH_UP_CROSSING)
        per_threshold[label] = {
            # n_censored and n_endurance_bags OVERLAP (a scan_start + scan_end window is
            # both). Never sum them.
            "n_windows": len(windows),
            "n_censored": n_censored,
            "n_endurance_bags": n_endurance,
        }

    windows_df = pd.DataFrame(window_rows, columns=WINDOW_COLUMNS)
    reads_df = pd.DataFrame(read_rows, columns=READ_COLUMNS)
    if len(windows_df):
        windows_df = windows_df.astype({"window_index": "int64", "n_reads": "int64"})
    if len(reads_df):
        reads_df["window_index"] = reads_df["window_index"].astype("Int64")

    # (t_before, t_after) for every gap, so consumers can break a line across one
    # instead of drawing a segment through unobserved time.
    gap_spans_s: list[tuple[float, float]] = []
    if len(t) > 1:
        for idx in np.flatnonzero(is_gap[1:]) + 1:
            gap_spans_s.append((float(t[idx - 1]), float(t[idx])))

    n_sigma_unknown = int((~sigma_known).sum()) if sigma is not None else len(t)
    diagnostics: dict[str, object] = {
        "n_reads_raw": int(len(t_all)),
        "n_reads_finite": int(len(t)),
        "n_reads_dropped_nonfinite": int(len(t_all) - len(t)),
        "n_reads_sigma_unknown": n_sigma_unknown,
        "median_spacing_s": median_s,
        "gap_threshold_s": gap_threshold_s,
        "n_gaps": n_gaps,
        "gap_spans_s": gap_spans_s,
        "n_nonpositive_steps": n_nonpositive,
        "per_threshold": per_threshold,
    }
    print(
        f"[windows] reads={len(t)}/{len(t_all)} thresholds={len(inputs.thresholds)} "
        f"windows={len(windows_df)} gaps={n_gaps} "
        f"gap_thr={gap_threshold_s:.1f}s median_dt={median_s:.1f}s",
        flush=True,
    )
    return WindowsResult(
        windows=windows_df,
        reads=reads_df,
        meta={
            "dataset_id": inputs.dataset_id,
            "gap_mult": inputs.gap_mult,
            "k": inputs.k,
            "use_uncertainty": inputs.use_uncertainty,
        },
        diagnostics=diagnostics,
    )
