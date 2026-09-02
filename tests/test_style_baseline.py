"""Ratchet on hardcoded style literals in the render layer.

Colour and typography belong in plots/theme.py. Sweeping every existing call site in
one pass is not worth the churn, so this pins the current count instead: the number
may go DOWN, never up. A new panel that hardcodes its own hex or font sizes fails here.

Scope is deliberately narrow - hex literals and `fontsize=`. It does not catch 3- or
8-digit hex, named colours ("lightgray"), plt.cm.*, or size=/labelsize=/fontdict=.
Widening it means re-pinning the baseline, which is a separate decision.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# plots/theme.py is the one place these literals are supposed to live.
THEME_FILE = REPO_ROOT / "src" / "quebra" / "plots" / "theme.py"

PATTERNS = {
    "hex": re.compile(r"#[0-9A-Fa-f]{6}\b"),
    "fontsize": re.compile(r"fontsize="),
}

# An earlier baseline was 18 (`fontsize=` only; the 8 hex were the tab10 clone in
# panels/within_calibration.py, deleted in favour of plots.theme.threshold_color).
# It ratchets DOWN only. 17 is the current floor: the distribution histograms were written with explicit sizes,
# this test rejected them, and the primary legend went to rcParams in the same edit.
BASELINE = 17


def _counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for directory in ("src/quebra/panels", "src/quebra/plots"):
        for path in sorted((REPO_ROOT / directory).glob("*.py")):
            if path == THEME_FILE:
                continue
            source = path.read_text(encoding="utf-8")
            n = sum(len(pattern.findall(source)) for pattern in PATTERNS.values())
            if n:
                counts[str(path.relative_to(REPO_ROOT))] = n
    return counts


def test_hardcoded_style_literals_do_not_grow() -> None:
    counts = _counts()
    total = sum(counts.values())
    breakdown = "\n".join(f"  {name}: {n}" for name, n in sorted(counts.items()))
    assert total <= BASELINE, (
        f"Hardcoded style literals rose to {total}, above the pinned baseline "
        f"{BASELINE}. This number ratchets DOWN, never up - move the new colour or "
        f"font size into plots/theme.py rather than raising the baseline.\n{breakdown}"
    )


def test_baseline_is_tight() -> None:
    # If the count has dropped, re-pin it. A baseline left slack above the real count
    # silently re-opens the room it was meant to close.
    total = sum(_counts().values())
    assert total == BASELINE, (
        f"Hardcoded style literals are down to {total}; re-pin BASELINE to {total} "
        f"in this file to keep the ratchet tight."
    )
