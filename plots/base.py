from __future__ import annotations

import matplotlib.pyplot as plt
import plotly.graph_objects as go


class BasePlot:
    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    def build_matplotlib(self, result: object, style: str = "default") -> plt.Figure:
        raise NotImplementedError(f"{self.__class__.__name__} has no matplotlib backend")

    def build_plotly(self, result: object) -> go.Figure:
        raise NotImplementedError(f"{self.__class__.__name__} has no plotly backend")
