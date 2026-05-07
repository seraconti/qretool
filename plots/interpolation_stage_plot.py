from __future__ import annotations

from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objects as go

from plots.base import BasePlot
from plots.theme import mix_with_white, qubit_color


@dataclass(slots=True)
class InterpolationStageResult:
    filter_bundle: dict[str, object]
    interp_bundle: dict[str, object]
    meta: dict[str, object]


def _scale_to_khz(values_hz: np.ndarray) -> np.ndarray:
    return np.asarray(values_hz, dtype=float) / 1000.0


class InterpolationStagePlot(BasePlot):
    def build_matplotlib(self, result: InterpolationStageResult, style: str = "default") -> plt.Figure:
        if style not in {"default", "paper"}:
            raise ValueError(f"Unknown InterpolationStage style '{style}'")

        plt_style = "default" if style == "default" else "classic"
        with plt.style.context(plt_style):
            filter_bundle = result.filter_bundle
            interp_bundle = result.interp_bundle
            stage_order = list(filter_bundle.get("stage_order", []))
            by_stage = dict(interp_bundle.get("by_stage", {}))
            available_stages = [stage for stage in stage_order if stage in by_stage]
            if len(available_stages) == 0:
                raise ValueError("InterpolationStageResult contains no overlapping stages to plot")

            dataset_id = str(result.meta.get("dataset_id", filter_bundle.get("meta", {}).get("dataset_id", self.name)))
            base_color = qubit_color(dataset_id=dataset_id, meta=filter_bundle.get("meta", {}))
            interp_color = mix_with_white(base_color, amount=0.3)

            n_rows = len(available_stages)
            fig, axes = plt.subplots(
                n_rows,
                4,
                figsize=(16, 4.5 * n_rows),
                squeeze=False,
                gridspec_kw={"width_ratios": [4.0, 1.4, 4.0, 1.4], "wspace": 0.15},
                constrained_layout=True,
            )

            for row, stage in enumerate(available_stages):
                raw_stage = filter_bundle["stages"][stage]
                interp_stage = by_stage[stage]
                raw_meta = dict(raw_stage.get("meta", {}))
                interp_meta = dict(interp_stage.get("meta", {}))

                t_raw_h = np.asarray(raw_stage["t_s"], dtype=float) / 3600.0
                t_interp_h = np.asarray(interp_stage["t_s"], dtype=float) / 3600.0
                raw_khz = _scale_to_khz(raw_stage["delta_hz"])
                interp_khz = _scale_to_khz(interp_stage["delta_hz"])

                y_all = np.concatenate([raw_khz, interp_khz]) if len(raw_khz) and len(interp_khz) else (raw_khz if len(raw_khz) else interp_khz)
                if len(y_all) == 0:
                    y_all = np.array([0.0], dtype=float)
                y_min = float(np.min(y_all))
                y_max = float(np.max(y_all))
                if y_max > y_min:
                    pad = 0.06 * (y_max - y_min)
                    y_lims = (y_min - pad, y_max + pad)
                else:
                    y_lims = (y_min - 1.0, y_max + 1.0)

                bins = np.histogram_bin_edges(y_all, bins="auto")
                if len(bins) < 2:
                    bins = np.linspace(y_lims[0], y_lims[1], 10)

                ax_raw = axes[row][0]
                ax_raw_hist = axes[row][1]
                ax_interp = axes[row][2]
                ax_interp_hist = axes[row][3]

                ax_raw.plot(t_raw_h, raw_khz, ".", markersize=2.5, alpha=0.85, color=base_color)
                ax_raw.set_title(f"{stage}: input (n={len(raw_khz)})")
                ax_raw.set_ylabel("Delta frequency (kHz)" if row == 0 else "")
                ax_raw.set_xlabel("Elapsed time (h)")
                ax_raw.set_ylim(*y_lims)
                ax_raw.grid(True, alpha=0.25)

                ax_raw_hist.hist(raw_khz, bins=bins, orientation="horizontal", alpha=0.65, color=base_color, edgecolor="none")
                ax_raw_hist.set_title("Raw dist")
                ax_raw_hist.set_xlabel("Count")
                ax_raw_hist.set_ylim(*y_lims)
                ax_raw_hist.tick_params(axis="y", labelleft=False)
                ax_raw_hist.grid(True, axis="x", alpha=0.25)

                ax_interp.plot(t_interp_h, interp_khz, "-", linewidth=1.0, color=interp_color)
                ax_interp.set_title(f"{stage}: interpolated (n={len(interp_khz)})")
                ax_interp.set_xlabel("Elapsed time (h)")
                ax_interp.set_ylim(*y_lims)
                ax_interp.grid(True, alpha=0.25)
                pct_real = interp_meta.get("pct_real_points")
                pct_interp = interp_meta.get("pct_interpolated_points")
                if pct_real is not None and pct_interp is not None:
                    ax_interp.text(
                        0.02,
                        0.98,
                        f"real={float(pct_real):.1f}%  interp={float(pct_interp):.1f}%",
                        transform=ax_interp.transAxes,
                        va="top",
                        ha="left",
                        fontsize=8,
                        bbox={"facecolor": "white", "alpha": 0.7, "edgecolor": "none"},
                    )

                ax_interp_hist.hist(interp_khz, bins=bins, orientation="horizontal", alpha=0.65, color=interp_color, edgecolor="none")
                ax_interp_hist.set_title("Interp dist")
                ax_interp_hist.set_xlabel("Count")
                ax_interp_hist.set_ylim(*y_lims)
                ax_interp_hist.tick_params(axis="y", labelleft=False)
                ax_interp_hist.grid(True, axis="x", alpha=0.25)

            fig.suptitle(f"Interpolation by Filter Stage - {dataset_id}", fontsize=13, y=1.01)
            return fig

    def build_plotly(self, result: InterpolationStageResult) -> go.Figure:
        raise NotImplementedError(f"{self.__class__.__name__} has no plotly backend")