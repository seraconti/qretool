from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

import matplotlib.pyplot as plt
import plotly.graph_objects as go


class _RenderablePlot(Protocol):
    name: str

    def build_matplotlib(self, result: object, style: str = "default") -> plt.Figure: ...

    def build_plotly(self, result: object) -> go.Figure: ...


RenderFn = Callable[[_RenderablePlot, object, Path], None]

RENDER_TARGETS: dict[str, RenderFn] = {}


def register_target(name: str) -> Callable[[RenderFn], RenderFn]:
    target_name = name.strip().lower()
    if not target_name:
        raise ValueError("Target name must be a non-empty string")

    def decorator(fn: RenderFn) -> RenderFn:
        existing = RENDER_TARGETS.get(target_name)
        if existing is not None and existing is not fn:
            raise ValueError(f"Target already registered: {target_name}")
        RENDER_TARGETS[target_name] = fn
        return fn

    return decorator


@register_target("static")
def render_static(plot: _RenderablePlot, result: object, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    figure = plot.build_matplotlib(result, style="default")
    figure.savefig(out_dir / f"{plot.name}.pdf", dpi=300, bbox_inches="tight")
    plt.close(figure)


@register_target("academic")
def render_academic(plot: _RenderablePlot, result: object, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    figure = plot.build_matplotlib(result, style="paper")
    figure.savefig(out_dir / f"{plot.name}.pdf", dpi=600, bbox_inches="tight")
    plt.close(figure)


@register_target("interactive")
def render_interactive(plot: _RenderablePlot, result: object, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    figure = plot.build_plotly(result)
    figure.write_html(out_dir / f"{plot.name}.html", include_plotlyjs="cdn")
