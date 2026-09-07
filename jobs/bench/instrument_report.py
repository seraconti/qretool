"""Write `jobs/bench/results/instrument_report.md` from the instrument validation artifact.

A writer, not a study. It lives in `bench/` for one reason: `jobs/bench/results/*.md` is this
repo's only tracked home for GENERATED markdown (the `!jobs/bench/results/*.md` rule in
.gitignore exists for `promotion_report.md`), and the tier table has to be generated rather
than hand-maintained or it goes stale exactly the way CLAUDE.md warns status tables do.

It is NOT a bench product and the file it writes says so in its own header. The bench scores
none of the tiers; it measures size and power, which the instrument report deliberately does
not claim.

Direction of the import is legal: `bench/` may import the pipeline, the pipeline may not
import `bench/` (tests/test_bench_isolation.py).

Run:  python jobs/bench/instrument_report.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


from quebra.analyzers.instrument_validation import (
    build_instrument_validation,
    render_tier_table_markdown,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "jobs" / "bench" / "results" / "instrument_report.md"


def render() -> str:
    """The markdown this writer would emit, from the tracked inputs it reads.

    Split out of `main` so a test can compare the committed file against what the code
    renders WITHOUT duplicating the input list here - a guard that assembled its own inputs
    would drift from the writer and then compare two different reports, which is exactly
    the mistake the first version of that guard made.
    """
    tie_path = ROOT / "jobs" / "bench" / "results" / "xi_tie_experiment.csv"
    if not tie_path.exists():
        raise FileNotFoundError(
            f"{tie_path} is missing. Run `python jobs/bench/xi_ties.py` first - the report "
            "quotes its divergence numbers and must not invent them."
        )
    data = build_instrument_validation(
        pd.read_csv(ROOT / "jobs" / "reference" / "load_haul_dump.csv"),
        pd.read_csv(ROOT / "jobs" / "reference" / "load_haul_dump_published.csv"),
        pd.read_csv(ROOT / "jobs" / "reference" / "r_reference_inputs.csv"),
        pd.read_csv(ROOT / "jobs" / "reference" / "r_reference_values.csv"),
        pd.read_csv(tie_path),
    )
    return render_tier_table_markdown(data)


def main() -> None:
    OUT.write_text(render())
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
