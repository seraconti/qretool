# Panel Contract

Defines the interface between metric modules and `NonRepairablePanel`.
Last updated: R1 (2026-05-26).

---

## Architecture

`NonRepairablePanel` is a **generic** rendering component. It knows nothing
about fidelity, Allan deviation, or any other specific metric. All
domain-specific knowledge lives in adapter functions (e.g.
`plots/fidelity_plot.py::make_fidelity_panel_data`) that convert a typed
result into `NonRepairablePanelData`.

The panel does **not** import from `analyzers.*`. Adapters do.

---

## NonRepairablePanelData — full field reference

```python
@dataclass
class NonRepairablePanelData:
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

    # big_values_good is per-threshold (third element of each threshold tuple):
    #   False: above threshold = out-of-spec (lower is better, e.g. infidelity)
    #   True:  below threshold = out-of-spec (higher is better, e.g. T2*)
```

---

## Panel-internal computations

The following are computed entirely inside `NonRepairablePanel` from
`(t_h, primary_series, thresholds, direction, damage_fn)`. They are NOT
separate metric modules. No analyzer module should reimplement them.

| Computation | Method | Integration rule | Notes |
|---|---|---|---|
| Threshold compliance timeline | `_draw_threshold_timeline` | — | Gantt-style bar chart |
| Window survival | `_draw_survival` | — | Empirical survival function |
| CV, initial value, range | `_draw_summary` | — | Summary text |
| Per-threshold window stats | `_draw_summary` | — | Above/below counts, mean, p90 |
| **Cumulative time out of spec** | `_cumulative_time_out_of_spec` | Left-Riemann | Step-function indicator; result in hours |
| **Cumulative damage** | `_cumulative_damage` | Trapezoidal | Continuous damage_rate; result in primary_unit · h |
| **MTTR (first crossing time)** | `_mttr` | — | Scalar per threshold; shown in summary text |

### Why left-Riemann for time out of spec, trapezoidal for damage

The out-of-spec indicator is a step function: `{0, 1}`. Trapezoidal
integration would interpolate between 0 and 1 at transitions, which is
physically wrong — a moment is either in-spec or out-of-spec. Left-Riemann
correctly assigns the state at the left edge of each interval.

The damage rate (excess after applying `damage_fn`) is continuous assuming
`damage_fn` is continuous (the linear default is). Trapezoidal integration
is second-order accurate and appropriate for continuous integrands.

### Polarity convention (big_values_good per threshold)

Each threshold tuple carries a `big_values_good: bool` as its third element.
Polarity is per-threshold — different thresholds in the same panel can have
different polarities.

For `big_values_good=False` (e.g. infidelity — lower is better):
  - `out_of_spec[i] = primary_series[i] > threshold_value`
  - `excess[i] = max(primary_series[i] - threshold_value, 0)`
  - MTTF: first `i` where `primary_series[i] > threshold_value`

For `big_values_good=True` (e.g. T2* — higher is better):
  - `out_of_spec[i] = primary_series[i] < threshold_value`
  - `excess[i] = max(threshold_value - primary_series[i], 0)`
  - MTTF: first `i` where `primary_series[i] < threshold_value`

### Default damage_fn

`None` → identity on excess (`lambda x: x`). Produces linear damage in the
excess above/below the threshold. The y-axis label is
`"Cumulative damage ({primary_label} · h)"`. Callers using nonlinear
`damage_fn` should note that the label is not automatically updated — they
may supply a descriptive `primary_label` that includes units if needed.

### Empty thresholds

If `thresholds == []`, the new subplots render with "No thresholds defined"
and axis turned off. The panel never crashes on empty thresholds.

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
8 — the shipped T2* ladder has 10.

---

## Layout

Two axes variants depending on flags:

**8-axis layout** (default — both cumulative flags True):
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

To add a new metric that uses `NonRepairablePanel`:

1. Write a compute function or analyzer that returns a typed result.
2. Write an adapter function `make_<metric>_panel_data(result) -> NonRepairablePanelData`.
   Set `t_h`, `primary_series`, `thresholds`, `direction`, and other fields.
3. Write a plot class that calls the adapter and delegates to `NonRepairablePanel`.

**No metric needs to modify the panel.** The panel's internal computations
(including cumulative time, cumulative damage, and MTTR) cover the standard
non-repairable degradation analysis surface. Only add panel-internal
computation if a new view is fundamentally about `(t, primary_series,
thresholds)` and cannot be expressed as a step result or adapter field.

### What is panel-internal forever (R1 decision)

Cumulative time out of spec, cumulative damage, and MTTR are **not**
candidates for separate analyzer modules. They are panel-internal views
derived from `(t, primary_series, thresholds, direction, damage_fn)`. Any
metric that supplies these inputs automatically gets all three views.

---

## Fidelity adapter

`plots/fidelity_plot.py::make_fidelity_panel_data(result: FidelityResult, dataset_id: str) -> NonRepairablePanelData`

Decisions made by the adapter:
- `primary_series` = infidelity (clipped to ≥ 1e-16 for log scale)
- `primary_label` = "Infidelity"
- `thresholds` = "nines" thresholds in infidelity units (e.g. 0.01 = 99%
  fidelity, 0.001 = 99.9%) — only thresholds that the data actually
  crosses (`inf_min < thr < inf_max`) are included
- `use_log_scale` = True
- `big_values_good` = False per threshold (above infidelity threshold = out of spec)
- For longrun profile: `traces` includes f−fₘₑₐₙ and f−f₀ infidelity traces

---

## File size note

`panels/non_repairable.py` is ~650 lines, exceeding the project's 200-line
guideline. The natural split is to extract the compute helpers into
`panels/_non_repairable_compute.py`. This has been deferred; R1 requires
these views to be panel-internal and the file boundary is the most auditable
location. A split does not change any public API and can be done at any time.
