"""The typed artifact NonRepairablePanel renders.

Separated from the renderer so the contract can be imported without importing
matplotlib, and so the trio reads as one thing: `_non_repairable_data` (this file,
the contract), `_non_repairable_compute` (the builder that fills it), and
`non_repairable` (the renderer that draws it).

Re-exported from panels.non_repairable, which stays the public import surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from panels._artifact_guard import StaleArtifactGuard


@dataclass
class NonRepairablePanelData(StaleArtifactGuard):
    """Complete typed contract for NonRepairablePanel.

    Built by build_non_repairable_panel_data (panels/_non_repairable_compute.py),
    the sole constructor path. `__post_init__` enforces completeness: constructing
    with thresholds present but the per-threshold derived maps unpopulated raises
    ValueError, so an incomplete artifact never materializes — go through the
    builder. Unpickling a stale pre-split artifact (one missing any field) raises
    ValueError via StaleArtifactGuard (that path bypasses __post_init__).

    Raw input fields
    ----------------
    t_h              : time array in hours (x-axis for all subplots)
    primary_series   : metric values (same units as threshold values)
    primary_label    : y-axis label, e.g. "Infidelity" or "T2* (µs)"
    thresholds       : list of (label, value, big_values_good) triples.
                       big_values_good=False: above threshold = out-of-spec
                         (lower is better, e.g. infidelity)
                       big_values_good=True: below threshold = out-of-spec
                         (higher is better, e.g. T2*)
    meta             : arbitrary dict shown in summary text (≤4 items displayed)
    traces           : optional extra labeled series for zoom/binned subplots;
                       None → panel uses primary_series as the sole trace
    use_log_scale    : semilogy on the primary panel (default False)
    color            : matplotlib color for primary trace; "C0" if None
    include_cumulative_time   : render cumulative time-out-of-spec subplot
    include_cumulative_damage : render cumulative damage subplot
    include_mttf     : include first-crossing times in summary/timeline text

    Note: damage is no longer a field here. The damage function is a builder
    parameter only (# EXTENSION: future DamageModel) — a callable cannot be hashed
    deterministically for identity nor labeled stably, so it never enters the
    materialized artifact; only the resulting damage curve does.

    Derived fields (populated by the builder)
    -----------------------------------------
    Keyed by threshold label unless noted. See _non_repairable_compute for the math.
    """

    # raw inputs
    t_h: np.ndarray
    primary_series: np.ndarray
    primary_label: str
    thresholds: list[tuple[str, float, bool]]
    meta: dict[str, object]
    traces: list[tuple[str, np.ndarray]] | None = None
    use_log_scale: bool = False
    color: object = None
    include_cumulative_time: bool = True
    include_cumulative_damage: bool = True
    include_mttf: bool = True
    # per-read 1-sigma on primary_series, same units; None when the dataset has none
    primary_sigma: np.ndarray | None = None
    # (t_before_h, t_after_h) for each read gap. The trace is broken across these: a
    # line drawn through unobserved time is an interpolation the data does not support.
    gap_spans_h: list[tuple[float, float]] = field(default_factory=list)
    # Distribution of primary_series, drawn rotated beside the trace. Empty when the
    # series is constant or has nothing finite.
    primary_hist_counts: np.ndarray = field(default_factory=lambda: np.array([]))
    primary_hist_edges: np.ndarray = field(default_factory=lambda: np.array([]))
    # Distribution of the per-read fit error, so its own spread is visible rather than
    # only its effect on the trace. Empty when there is no sigma.
    sigma_hist_counts: np.ndarray = field(default_factory=lambda: np.array([]))
    sigma_hist_edges: np.ndarray = field(default_factory=lambda: np.array([]))
    # x-limit holding 99% of the fit-error mass, and how many reads fall beyond it.
    # Rendered as text, so it is a fact the artifact owns, not a draw-time view choice.
    sigma_hist_view_x_max: float = field(default_factory=lambda: float("nan"))
    sigma_hist_n_above_view: int = 0
    sigma_mean: float = field(default_factory=lambda: float("nan"))
    sigma_median: float = field(default_factory=lambda: float("nan"))

    # derived (populated by build_non_repairable_panel_data)
    cumulative_time_per_threshold: dict[str, np.ndarray] = field(default_factory=dict)
    cumulative_damage_per_threshold: dict[str, np.ndarray] = field(default_factory=dict)
    mttf_per_threshold: dict[str, float | None] = field(default_factory=dict)
    threshold_window_stats: dict[str, dict[str, object]] = field(default_factory=dict)
    window_survival_per_threshold: dict[str, list[tuple[float, float]]] = field(
        default_factory=dict
    )
    # (t_start_h, t_end_h, state) runs per threshold, from the read table. The renderer
    # used to recompute these by walking primary_series at draw time; state is data.
    timeline_segments_per_threshold: dict[str, list[tuple[float, float, str]]] = field(
        default_factory=dict
    )
    binned_stats_per_trace: dict[str, tuple[np.ndarray, ...]] = field(
        default_factory=dict
    )
    # default_factory (not a plain class default) so the value lives in instance
    # __dict__ like every other derived field: absence is then detectable rather
    # than silently falling back to a class attribute.
    cv: float = field(default_factory=lambda: float("nan"))
    threshold_in_spec_frac: dict[str, float] = field(default_factory=dict)
    threshold_summary: dict[str, dict[str, float] | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Completeness contract: the builder populates one entry per threshold in
        # every per-threshold derived map; direct construction (empty defaults)
        # with thresholds present is incomplete and must not materialize.
        # (__setstate__ handles the unpickle path and bypasses __init__/__post_init__.)
        labels = [label for label, _, _ in self.thresholds]
        per_threshold = {
            "cumulative_time_per_threshold": self.cumulative_time_per_threshold,
            "cumulative_damage_per_threshold": self.cumulative_damage_per_threshold,
            "mttf_per_threshold": self.mttf_per_threshold,
            "threshold_window_stats": self.threshold_window_stats,
            "window_survival_per_threshold": self.window_survival_per_threshold,
            "timeline_segments_per_threshold": self.timeline_segments_per_threshold,
            "threshold_in_spec_frac": self.threshold_in_spec_frac,
            "threshold_summary": self.threshold_summary,
        }
        for field_name, mapping in per_threshold.items():
            missing = [label for label in labels if label not in mapping]
            if missing:
                raise ValueError(
                    f"incomplete NonRepairablePanelData: {field_name} is missing "
                    f"threshold(s) {missing} — construct via "
                    f"build_non_repairable_panel_data()"
                )


# ---------------------------------------------------------------------------
# Panel class (pure renderer)
# ---------------------------------------------------------------------------
