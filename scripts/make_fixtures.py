#!/usr/bin/env python3
"""Regenerate the packaged fixtures in `src/quebra/_fixtures/`.

The CSVs are committed rather than generated at import time, because a fixture that is
rebuilt on every run is not a fixture - a change in numpy's generator would silently move
every number a reviewer sees. This script exists so the committed files are reproducible
and their construction is inspectable, not so they are rebuilt routinely.

Rerun only when the fixture contract changes, and commit the result:

    python scripts/make_fixtures.py

SPEC 0003 R3.6. Synthetic throughout - no measured value from any device appears here, which
is what lets these ship inside the wheel.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "src" / "quebra" / "_fixtures"

# Fixed, written out rather than derived. A rerun must reproduce the committed bytes.
SEED = 20260829
N_POINTS = 200
CADENCE_S = 60.0
QUBIT_FREQUENCY_HZ = 5.0e9
T2STAR_MEAN_S = 40e-6


def ramsey_series() -> pd.DataFrame:
    """A qubit that drifts, wanders, and takes one step - enough to exercise the pipeline.

    The step at two thirds is deliberate: a record with no structure cannot demonstrate that
    the windowing or the change detection does anything, so a fixture without one would make
    every downstream figure look correct while proving nothing.
    """
    rng = np.random.default_rng(SEED)
    t_s = np.arange(N_POINTS) * CADENCE_S

    # Frequency: slow linear drift plus noise.
    drift_hz = np.linspace(0.0, 4.0e4, N_POINTS)
    frequency_hz = QUBIT_FREQUENCY_HZ + drift_hz + rng.normal(0.0, 5.0e3, N_POINTS)

    # T2*: a stable stretch, then a step down to a worse regime.
    t2star_s = rng.normal(T2STAR_MEAN_S, 4e-6, N_POINTS)
    step_at = (2 * N_POINTS) // 3
    t2star_s[step_at:] -= 12e-6
    t2star_s = np.clip(t2star_s, 5e-6, None)

    # Uncertainty grows as the coherence time falls, which is the usual direction.
    t2star_error_s = 1.5e-6 + 0.06 * (T2STAR_MEAN_S - t2star_s).clip(0.0)

    return pd.DataFrame(
        {
            "timestamp": t_s,
            "frequency": frequency_hz,
            "T2star": t2star_s,
            "T2star error": t2star_error_s,
        }
    )


def main() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    target = FIXTURE_DIR / "ramsey_synthetic.csv"
    # `%.9g` keeps the file small and the round-trip exact enough for a fixture, without
    # committing 17 digits of noise.
    ramsey_series().to_csv(target, index=False, float_format="%.9g")
    print(f"wrote {target} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
