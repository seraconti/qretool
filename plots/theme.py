"""Single source of colour and typography for the render layer.

Every data-derived quantity lives in the typed artifact; this module owns only the
functions-of-axes/theme half of that split. Constants and small helpers - no config
layer, no second theme module.

All colour accessors return a hex `str`. `mix_with_white` is the one exception and
predates the rule: it returns an RGB float tuple, so helpers built on it convert back.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Iterator

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import colors as mcolors


QUBIT_COLOR_MAP = {
    1: "#438ECB",
    2: "#E91B63",
    3: "#FDC113",
    4: "#1D988A",
    5: "#CDDC39",
    6: "#8F3F97",
}

# Ladder colours are sampled from one perceptually ordered map rather than taken from
# a fixed list, so a threshold ladder of ANY length gets distinct colours. The previous
# 8-entry list wrapped modulo its length and drew the 1 us and 9 us thresholds in the
# same blue on a 10-entry ladder.
THRESHOLD_CMAP = "cividis"

# Sampling is clipped away from both ends of the map: cividis bottoms out near-black
# and tops out in a yellow that is hard to see on white.
_THRESHOLD_SPAN = (0.05, 0.90)

# Hue for a dataset whose qubit id could not be resolved.
_UNKNOWN_QUBIT_COLOR = "tab:gray"

# Spec-state semantics. Relative luminances (WCAG, computed - not asserted) are spaced
# so the three states stay separable in greyscale print:
#   in_spec 0.166 above unresolved, out_of_spec 0.164 below it.
#     in_spec      #66C2A5  L=0.441
#     unresolved   #9B8F63  L=0.275
#     out_of_spec  #B3261E  L=0.111
#     censored     #4D4D4D  L=0.074   (deliberately below the ladder; it marks
#                                      absence of an observation, not a state)
# `unresolved` is reserved for the next pass. It exists now so nothing invents a
# colour for it later.
STATE_COLORS = {
    "in_spec": "#66C2A5",
    "out_of_spec": "#B3261E",
    "unresolved": "#9B8F63",
    "censored": "#4D4D4D",
}

# Confidence/tolerance bands: the fill carries the extent, the edge carries the method.
BAND_STYLE = {
    "fill_alpha": 0.18,
    "edge_alpha": 0.55,
    "edge_linewidth": 0.8,
}

# Censoring marks on a survival/duration axis.
CENSOR_TICK = {
    "marker": "|",
    "markersize": 5.0,
    "linewidth": 0.9,
}

# The region where the risk set has fallen below the point of being informative.
EPSILON_SHADE = {
    "color": "#B0B0B0",
    "alpha": 0.20,
}

# rcParams by RENDER TARGET, not by matplotlib style name. `static` keeps the sans
# default; `academic` goes serif at a smaller base for print.
RCPARAMS: dict[str, dict[str, object]] = {
    "static": {
        "font.family": "sans-serif",
        "font.size": 9.0,
        "axes.titlesize": 10.0,
        "axes.labelsize": 9.0,
        "xtick.labelsize": 8.0,
        "ytick.labelsize": 8.0,
        "legend.fontsize": 8.0,
        "figure.titlesize": 12.0,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": "#CCCCCC",
        "grid.linewidth": 0.5,
        "grid.alpha": 0.4,
    },
    "academic": {
        "font.family": "serif",
        "font.serif": ["DejaVu Serif"],
        "mathtext.fontset": "dejavuserif",
        "font.size": 8.0,
        "axes.titlesize": 9.0,
        "axes.labelsize": 8.0,
        "xtick.labelsize": 7.0,
        "ytick.labelsize": 7.0,
        "legend.fontsize": 7.0,
        "figure.titlesize": 10.0,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": "#CCCCCC",
        "grid.linewidth": 0.4,
        "grid.alpha": 0.4,
    },
}

# Renderers are handed matplotlib style names by plots/targets.py; the theme is keyed
# by render target. One mapping, here, so no renderer has to know both vocabularies.
_TARGET_FOR_STYLE = {"default": "static", "paper": "academic"}


def extract_qubit_id(
    dataset_id: str | None = None, meta: dict[str, object] | None = None
) -> int | None:
    if isinstance(meta, dict) and meta.get("qubit") is not None:
        try:
            qubit = int(meta.get("qubit"))
            if qubit > 0:
                return qubit
        except (TypeError, ValueError):
            pass

    dataset = str(dataset_id) if dataset_id is not None else ""
    patterns = [r"(?:^|[_-])q(\d+)(?:[_-]|$)", r"qubit(\d+)"]
    for pattern in patterns:
        match = re.search(pattern, dataset, flags=re.IGNORECASE)
        if match:
            qubit = int(match.group(1))
            if qubit > 0:
                return qubit
    return None


def qubit_color(
    dataset_id: str | None = None, meta: dict[str, object] | None = None
) -> str:
    qubit = extract_qubit_id(dataset_id=dataset_id, meta=meta)
    if qubit in QUBIT_COLOR_MAP:
        return QUBIT_COLOR_MAP[qubit]
    return mcolors.to_hex(_UNKNOWN_QUBIT_COLOR)


def mix_with_white(color: str, amount: float = 0.4) -> tuple[float, float, float]:
    base = np.asarray(mcolors.to_rgb(color), dtype=float)
    amount = float(np.clip(amount, 0.0, 1.0))
    mixed = (1.0 - amount) * base + amount * np.ones(3, dtype=float)
    return tuple(mixed.tolist())


# Ramp stops short of white so the last dataset in a long series is still legible.
_RAMP_MAX_MIX = 0.55


def dataset_ramp(qubit: int | None, index: int, n: int) -> str:
    """Chronological lightness ramp within one qubit's hue.

    `index` is the dataset's position in time, `n` the number of datasets sharing the
    hue. Earliest is the saturated base colour, latest the most washed-out.
    """
    base = QUBIT_COLOR_MAP.get(qubit, _UNKNOWN_QUBIT_COLOR)
    if n <= 1:
        return mcolors.to_hex(base)
    position = float(np.clip(index / (n - 1), 0.0, 1.0))
    return mcolors.to_hex(mix_with_white(base, _RAMP_MAX_MIX * position))


def threshold_color(i: int, n: int) -> str:
    """Colour for threshold `i` of a ladder of `n`, sampled across `THRESHOLD_CMAP`."""
    lo, hi = _THRESHOLD_SPAN
    if n <= 1:
        position = lo
    else:
        position = lo + (hi - lo) * float(np.clip(i / (n - 1), 0.0, 1.0))
    return mcolors.to_hex(plt.get_cmap(THRESHOLD_CMAP)(position))


def apply_rcparams(target: str) -> None:
    """Apply this render target's rcParams to the live matplotlib state.

    Call inside a style context - see `style_context`. Called outside one it still
    mutates global rcParams, but the effect is DISCARDED the moment a renderer enters
    its stylesheet, because entering one resets rcParams wholesale. That is why this
    is not called from plots/targets.py's render functions directly.
    """
    if target not in RCPARAMS:
        raise ValueError(
            f"Unknown render target: {target!r}. Known: {sorted(RCPARAMS)}"
        )
    plt.rcParams.update(RCPARAMS[target])


@contextmanager
def style_context(style: str) -> Iterator[None]:
    """The one stylesheet every renderer draws inside.

    Opens matplotlib's `default` stylesheet, then layers this project's rcParams on
    top. Ordering is load-bearing: the stylesheet must be entered FIRST, because
    entering one resets rcParams to that sheet's values and would otherwise discard
    the theme. `plt.style.context` restores the previous state on exit, so rendering
    several targets in one run cannot leak settings between them.
    """
    target = _TARGET_FOR_STYLE.get(style)
    if target is None:
        raise ValueError(
            f"Unknown style: {style!r}. Known: {sorted(_TARGET_FOR_STYLE)}"
        )
    with plt.style.context("default"):
        apply_rcparams(target)
        yield
