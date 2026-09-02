# Panel Contract

Defines the interface between metric modules and `WithinCalibrationPanel`.

---

## Architecture

`WithinCalibrationPanel` is a **generic** rendering component. It knows nothing
about fidelity, Allan deviation, or any other specific metric. All
domain-specific knowledge lives in adapter functions beside their analyzer
(`analyzers/t2star.py::make_panel_data`, `analyzers/fidelity.py::make_panel_data`)
that convert a typed result into `WithinCalibrationPanelData`.

Those adapters are called by a job STEP, never at draw time. `FidelityPlot` and
`T2StarPlot` must not build panel data inside `build_matplotlib`, where no DAG node
could supply the window tables; both are gone and jobs use `WithinCalibrationPanel`
directly off a panel-data step.

The panel does **not** import from `analyzers.*` for domain logic. It does import
`analyzers.windows` constants for the birth/death vocabulary, which is shared, not
domain-specific.

---

## Three bands

`WithinCalibrationPanelData` is composed of one contract per band, each produced by its own
step, each complete on its own, each replaceable without touching the others:

| band | step | question it answers |
|---|---|---|
| `signal` | `analyzers/signal_band.py` | what was measured, before any threshold |
| `distinguish` | `analyzers/distinguish_band.py` | can a reader tell in from out at all |
| `reliability` | `analyzers/reliability_band.py` | what follows from the 2-state carve |

The outer class owns only what all three share - the ladder, `primary_label`, `traces`,
the render flags - plus `meta`.

**Two guard requirements, both silent if forgotten.** `StaleArtifactGuard` derives its
key set from `dataclasses.fields(cls)`, so the outer class alone would validate nothing
but the four band names: **every band inherits the guard**, and no band uses
`slots=True` (the guard's non-dict branch fires on the slots tuple even for a valid
load). And because the per-threshold maps moved off the class that owns `thresholds`,
each band exposes `check_thresholds(labels)` which the outer `__post_init__` calls -
without it the construction-time completeness contract silently drops to nothing.

**Both compliance timelines are drawn, never merged.** Band 2 renders the 4-state view
(uncertainty included), band 3 the 2-state view the carve actually used, on a shared
x-axis and vertically aligned. If they look the same, resolvability costs nothing. If
they differ, that difference is the finding.

**`estimator` is a field.** The reliability band declares which estimator produced its
survival curve and the axis label is derived from it, so the label cannot go stale.
`cumulative_hazard`, `band_lower` and `band_upper` are reserved and are `None` here. The
estimator exists - `analyzers/kaplan_meier.py` - but this panel does not consume it; wiring
it in changes only that band.

**Occupancy is fraction of OBSERVED time**, gap intervals excluded. There is one
definition: `reliability.occupancy` and the renderer's >=5% timeline cull read the same
number, and `_cumulative_time_out_of_spec` uses the same denominator. Counting gap time
credited unobserved hours to whichever state held at the left edge.

**Not drawn**: the detail/zoom view and the 30-minute median/IQR/p90 view, with
`binned_stats_per_trace` and `adaptive_ylim`. Extra `traces` are now overlaid on the
signal axis rather than in a subplot of their own.

**Shape statistics are reported only where they have support.** Complete windows only
(`up_crossing` birth, uncensored), then `shape_min_reads`; a threshold with fewer surviving
windows than `SHAPE_SUPPORT_FLOOR` is named as unsupported rather than drawn. On the
shipped T2* ladder that is one threshold. Every median ships with its defined-count, and
`rho2` is never rendered without Chatterjee's xi and the falling-limb rho beside it -
a symmetric excursion drives Spearman to zero by construction.

---

## WithinCalibrationPanelData - full field reference

```python
@dataclass
class WithinCalibrationPanelData:
    # Required
    t_h: np.ndarray            # time in hours (x-axis for all subplots)
    primary_series: np.ndarray # metric values (same units as thresholds)
    primary_label: str         # y-axis label, e.g. "Infidelity"
    thresholds: list[tuple[str, float, bool]]  # (label, value, big_values_good); empty = no threshold views
    meta: dict[str, object]    # key-value pairs shown in summary text (≤4 items displayed)

    # Optional
    traces: list[tuple[str, np.ndarray]] | None  # extra series for zoom/binned subplots
    use_log_scale: bool         # semilogy on primary panel (default False)
    higher_is_better: bool      # True → above threshold = green (default True)
    color: object               # matplotlib color for primary trace (default "C0")

    # R1 additions
    damage_fn: Callable[[np.ndarray], np.ndarray] | None
        # Applied to per-threshold excess before integration in cumulative-damage
        # computation. None = linear default (identity on excess).
        # Signature: (excess: np.ndarray) -> np.ndarray
        # The panel does NOT mutate PanelData; damage_fn is called read-only.

    include_cumulative_time: bool    # render cumulative time-out-of-spec subplot (default True)
    include_cumulative_damage: bool  # render cumulative damage subplot (default True)
    include_mttr: bool               # include first-crossing times in summary text (default True)

    # from the window/read tables
    primary_sigma: np.ndarray | None
        # per-read 1-sigma on primary_series, same units. Drawn as error bars under
        # the trace; snapshotted y-limits keep it from driving autoscale.
    gap_spans_h: list[tuple[float, float]]
        # (t_before, t_after) per read gap. The trace is BROKEN across these - a line
        # through unobserved time is an interpolation the data does not support.
    timeline_segments_per_threshold: dict[str, list[tuple[float, float, str]]]
        # (t_start_h, t_end_h, state) runs. Required per threshold by __post_init__.

    # big_values_good is per-threshold (third element of each threshold tuple):
    #   False: above threshold = out-of-spec (lower is better, e.g. infidelity)
    #   True:  below threshold = out-of-spec (higher is better, e.g. T2*)
```

---

## Panel-internal computations

The following are computed by `build_within_calibration_panel_data` from
`(t_h, primary_series, thresholds, direction, damage_fn)` plus the window and read
tables. They are NOT separate metric modules. No analyzer module should reimplement
them.

**Window carving is not one of them.** It lives in `analyzers/windows.py` and reaches
the builder as two required DataFrames, so the gap policy, censoring and per-read state
are the same facts in the artifact, the figure and any downstream analysis. The builder
raises rather than carving a second time.

| Computation | Method | Integration rule | Notes |
|---|---|---|---|
| Threshold compliance timeline | `_timeline_segments` | - | Gantt bars over per-read `state`; 2 or 4 states depending on `use_uncertainty` |
| Window survival | `_window_survival` | - | Empirical survival, **censored windows dropped** |
| CV, initial value, range | `_draw_summary` | - | Summary text |
| Per-threshold window stats | `_analyze_threshold_windows` + `_carve_counts` | - | Above/below counts, mean, p90, plus `n_windows`, `n_censored`, `n_endurance_bags`, `n_gaps` |
| **Cumulative time out of spec** | `_cumulative_time_out_of_spec` | Left-Riemann | Step-function indicator; result in hours |
| **Cumulative damage** | `_cumulative_damage` | Trapezoidal | Continuous damage_rate; result in primary_unit · h |
| **MTTR (first crossing time)** | `_mttr` | - | Scalar per threshold; shown in summary text |

### Why left-Riemann for time out of spec, trapezoidal for damage

The out-of-spec indicator is a step function: `{0, 1}`. Trapezoidal
integration would interpolate between 0 and 1 at transitions, which is
physically wrong - a moment is either in-spec or out-of-spec. Left-Riemann
correctly assigns the state at the left edge of each interval.

The damage rate (excess after applying `damage_fn`) is continuous assuming
`damage_fn` is continuous (the linear default is). Trapezoidal integration
is second-order accurate and appropriate for continuous integrands.

### Polarity convention (big_values_good per threshold)

Each threshold tuple carries a `big_values_good: bool` as its third element.
Polarity is per-threshold - different thresholds in the same panel can have
different polarities.

For `big_values_good=False` (e.g. infidelity - lower is better):
  - `out_of_spec[i] = primary_series[i] > threshold_value`
  - `excess[i] = max(primary_series[i] - threshold_value, 0)`
  - TTF: first `i` where `primary_series[i] > threshold_value`

For `big_values_good=True` (e.g. T2* - higher is better):
  - `out_of_spec[i] = primary_series[i] < threshold_value`
  - `excess[i] = max(threshold_value - primary_series[i], 0)`
  - TTF: first `i` where `primary_series[i] < threshold_value`

### Default damage_fn

`None` → identity on excess (`lambda x: x`). Produces linear damage in the
excess above/below the threshold. The y-axis label is
`"Cumulative damage ({primary_label} · h)"`. Callers using nonlinear
`damage_fn` should note that the label is not automatically updated - they
may supply a descriptive `primary_label` that includes units if needed.

### Empty thresholds

If `thresholds == []`, the new subplots render with "No thresholds defined"
and axis turned off. The panel never crashes on empty thresholds.

---

## Window statistics: two definitions on one panel

The summary block's above/below stats (`_analyze_threshold_windows`) and the survival
curve (the window table) answer different questions and do not have to agree:

- **above/below** is direction-agnostic run-length bookkeeping on the raw series. It has
  no gap policy and no censoring; a run spanning a read gap is one run.
- **the window table** applies the gap policy, labels births and deaths, and marks
  censored windows. The survival curve uses only uncensored windows.

Both are correct for what they measure. Do not read the summary `count` as the number of
windows in the window table.

`window_survival_per_threshold` is an empirical survival function over **uncensored**
window lengths only: `S(x) = #{w >= x} / n`. `analyzers/kaplan_meier.py` uses the censored
windows rather than discarding them; this field does not, and the two are not interchangeable.

---

## Color scheme (D4)

Threshold colors come from `plots/theme.py::threshold_color`, which samples
`THRESHOLD_CMAP` across the ladder. They are used in four places:
- On the primary axis: one dashed horizontal line per threshold
- On the survival subplot: one curve per threshold
- On cumulative time and cumulative damage subplots: one curve per threshold

Threshold index `i` maps to `threshold_color(i, len(pd_.thresholds))` in all
four locations, so colors correspond visually.

Sampling across `len(thresholds)` replaced a fixed 8-entry list indexed
`i % 8`, which gave two thresholds the same color on any ladder longer than
8 - the shipped T2* ladder has 10.

Timeline bars are colored by per-read spec state through `plots/theme.py::state_color`,
not by the threshold color: `in_spec`, `out_of_spec`, and - when the carve ran with
`use_uncertainty=True` - `in_spec_uncertain` / `out_of_spec_uncertain`, which are the
crisp colors washed toward white. A read is uncertain when
`abs(value - threshold) < k * sigma`. Uncertainty is an annotation only: it never moves
a window boundary.

---

## Layout

Two axes variants depending on flags:

**8-axis layout** (default - both cumulative flags True):
```
Row 0: primary (spans 2 cols)                  height ratio 1.8
Row 1: threshold timeline (spans 2 cols)        height ratio 0.9
Row 2: detail view (col 0) | 30-min stats (col 1)  height ratio 3.2
Row 3: survival (spans 2 cols)                  height ratio 2.0
Row 4: cum. time (col 0) | cum. damage (col 1)  height ratio 2.0  [R1]
Row 5: summary text (spans 2 cols)              height ratio 1.2
Figure: 14 × 18.5 inches
```

**6-axis layout** (both cumulative flags False):
```
Row 0: primary (spans 2 cols)
Row 1: threshold timeline (spans 2 cols)
Row 2: detail view | 30-min stats
Row 3: survival (spans 2 cols)
Row 4: summary text (spans 2 cols)
Figure: 14 × 16 inches
```

Mixed (only one flag True): the single new subplot spans both columns in row 4.

MTTR first-crossing times are always in the **summary text** (row 5/4), not
in a separate subplot. This keeps scalar-per-threshold outputs out of the
2D plot space.

---

## Adding a new metric

To add a new metric that uses `WithinCalibrationPanel`:

1. Write a compute function or analyzer that returns a typed result.
2. Write an adapter function `make_<metric>_panel_data(result) -> WithinCalibrationPanelData`.
   Set `t_h`, `primary_series`, `thresholds`, `direction`, and other fields.
3. Write a plot class that calls the adapter and delegates to `WithinCalibrationPanel`.

**No metric needs to modify the panel.** The panel's internal computations
(including cumulative time, cumulative damage, and MTTR) cover the standard
within-calibration degradation analysis surface. Only add panel-internal
computation if a new view is fundamentally about `(t, primary_series,
thresholds)` and cannot be expressed as a step result or adapter field.

### What is panel-internal forever (R1 decision)

Cumulative time out of spec, cumulative damage, and MTTR are **not**
candidates for separate analyzer modules. They are panel-internal views
derived from `(t, primary_series, thresholds, direction, damage_fn)`. Any
metric that supplies these inputs automatically gets all three views.

---

## Fidelity adapter

`analyzers/fidelity.py::make_panel_data(result: FidelityResult, ...) -> WithinCalibrationPanelData`

Decisions made by the adapter:
- `primary_series` = infidelity (clipped to ≥ 1e-16 for log scale)
- `primary_label` = "Infidelity"
- `thresholds` = "nines" thresholds in infidelity units (e.g. 0.01 = 99%
  fidelity, 0.001 = 99.9%) - only thresholds that the data actually
  crosses (`inf_min < thr < inf_max`) are included
- `use_log_scale` = True
- `big_values_good` = False per threshold (above infidelity threshold = out of spec)
- For longrun profile: `traces` includes f−fₘₑₐₙ and f−f₀ infidelity traces

---

## File size note

`panels/within_calibration.py` is five times the project's 200-line guideline. A line count
written here goes stale silently, so it is not repeated; `wc -l` is the source.

The split is partly done: `analyzers/within_calibration_compute.py`
builds the artifact, `analyzers/within_calibration_data.py` is the typed contract, and
`panels/_within_calibration_render.py` holds the functions-of-axes half. What remains in the
main file is the
drawing sequence, which is still the largest module in the tree. A further split does not
change any public API and can be done at any time.
