from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go

from analyzers.fidelity import FidelityResult
from panels.non_repairable import NonRepairablePanel, NonRepairablePanelData
from plots.base import BasePlot
from plots.theme import qubit_color


# ---------------------------------------------------------------------------
# Threshold selection: nines thresholds that the infidelity data crosses
# ---------------------------------------------------------------------------

def _fidelity_panel_thresholds(infidelity: np.ndarray) -> list[tuple[str, float]]:
    """Return nines thresholds (in infidelity units) that the data crosses."""
    inf = np.asarray(infidelity, dtype=float)
    inf_finite = inf[np.isfinite(inf) & (inf > 0)]
    if len(inf_finite) == 0:
        return []
    inf_min, inf_max = float(np.min(inf_finite)), float(np.max(inf_finite))
    thresholds: list[tuple[str, float]] = []
    for n in range(0, 8):
        # n=0 → infidelity<0.01 = 99% fidelity; n=1 → infidelity<0.001 = 99.9%; ...
        inf_thr = 10.0 ** (-(n + 2))
        label = "99" + ("." + "9" * n if n > 0 else "") + "%"
        if inf_min < inf_thr < inf_max:
            thresholds.append((label, inf_thr))
    return thresholds


# ---------------------------------------------------------------------------
# Adapter: FidelityResult → NonRepairablePanelData
# ---------------------------------------------------------------------------

def make_fidelity_panel_data(result: FidelityResult, dataset_id: str = "") -> NonRepairablePanelData:
    """Convert FidelityResult to NonRepairablePanelData for NonRepairablePanel."""
    frame = result.frame
    t_h = frame["t_rel_s"].to_numpy(dtype=float) / 3600.0
    infidelity = np.clip(frame["infidelity"].to_numpy(dtype=float), 1e-16, None)

    thresholds = _fidelity_panel_thresholds(infidelity)

    traces: list[tuple[str, np.ndarray]] | None = None
    if "infidelity_f0" in frame.columns:
        traces = [
            ("f−fₘₑₐₙ", np.clip(frame["infidelity"].to_numpy(dtype=float), 1e-16, None)),
            ("f−f₀", np.clip(frame["infidelity_f0"].to_numpy(dtype=float), 1e-16, None)),
        ]

    meta: dict[str, object] = {"dataset": dataset_id}
    rabi_base_hz = result.meta.get("rabi_base_hz")
    if rabi_base_hz is not None:
        meta["rabi_base_hz"] = f"{rabi_base_hz:.4g} Hz"
    profile = result.meta.get("profile")
    if profile:
        meta["profile"] = str(profile)

    return NonRepairablePanelData(
        t_h=t_h,
        primary_series=infidelity,
        primary_label="Infidelity",
        thresholds=thresholds,
        meta=meta,
        traces=traces,
        use_log_scale=True,
        higher_is_better=False,
        color=qubit_color(dataset_id=dataset_id),
        # above infidelity threshold = out of spec (high infidelity is bad)
        direction="above",
    )


# ---------------------------------------------------------------------------
# Plot class
# ---------------------------------------------------------------------------

class FidelityPlot(BasePlot):
    def build_matplotlib(self, result: FidelityResult, style: str = "default") -> plt.Figure:
        if not isinstance(result, FidelityResult):
            raise TypeError("FidelityPlot expects a FidelityResult")
        panel_data = make_fidelity_panel_data(
            result, dataset_id=str(result.meta.get("dataset_id", self.name))
        )
        return NonRepairablePanel(self.name).build_matplotlib(panel_data, style=style)

    def build_plotly(self, result: FidelityResult) -> go.Figure:
        raise NotImplementedError(f"{self.__class__.__name__} has no plotly backend")
