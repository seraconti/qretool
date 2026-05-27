from __future__ import annotations

import matplotlib.pyplot as plt
import plotly.graph_objects as go

from analyzers.t2star import T2StarResult, make_panel_data
from panels.non_repairable import NonRepairablePanel
from plots.base import BasePlot


class T2StarPlot(BasePlot):
    def build_matplotlib(self, result: T2StarResult, style: str = "default") -> plt.Figure:
        if not isinstance(result, T2StarResult):
            raise TypeError("T2StarPlot expects a T2StarResult")
        panel_data = make_panel_data(result)
        return NonRepairablePanel(self.name).build_matplotlib(panel_data, style=style)

    def build_plotly(self, result: T2StarResult) -> go.Figure:
        raise NotImplementedError(f"{self.__class__.__name__} has no plotly backend")
