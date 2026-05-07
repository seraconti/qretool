from __future__ import annotations

import re

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


def extract_qubit_id(dataset_id: str | None = None, meta: dict[str, object] | None = None) -> int | None:
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


def qubit_color(dataset_id: str | None = None, meta: dict[str, object] | None = None) -> str:
    qubit = extract_qubit_id(dataset_id=dataset_id, meta=meta)
    if qubit in QUBIT_COLOR_MAP:
        return QUBIT_COLOR_MAP[qubit]
    return "tab:gray"


def mix_with_white(color: str, amount: float = 0.4) -> tuple[float, float, float]:
    base = np.asarray(mcolors.to_rgb(color), dtype=float)
    amount = float(np.clip(amount, 0.0, 1.0))
    mixed = (1.0 - amount) * base + amount * np.ones(3, dtype=float)
    return tuple(mixed.tolist())