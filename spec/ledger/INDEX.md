# Session index

One row per transcript in this directory. Fields that cannot be recovered from the
transcript are `unknown`. They are never filled with a plausible guess.

`Commit` is derived, not assumed: it is the commit that first added the files the session
created, read from `git log --diff-filter=A`. Where a session produced no new file, or its
work was folded into a commit alongside other work, the field is `unknown`.

| Session | Date (UTC) | Agent and model | Task | Spec or issue | Files changed | Commit |
|---|---|---|---|---|---|---|
| `7c6ea3af-5a33-4c59-b6d7-cc105163a4a2` | 2026-08-14, 14:33 to 15:30 | Claude Code, `claude-opus-5` | Build an example Kaplan-Meier job across the 6D2S records: survey all 34 for spread in mean T2\*, select a handful, then implement the estimator, a survival plot and a between-calibration histogram to draw them | none (`spec/` did not exist on this date) | `analyzers/kaplan_meier.py`, `plots/km_survival_plot.py`, `plots/mtbc_hist_plot.py`, `jobs/active/km_poster_6d2s.py`, `plots/theme.py`, `panels/_repairable_compute.py`, `plots/targets.py`, `analyzers/mtbf.py`, `jobs/active/mtbc_q6.py`, `tests/test_windows_not_interpolated.py` | `aff894e` |

## Not yet indexed

One further transcript exists in `~/.claude/projects/` and is not copied here. It is the
session that created this ledger, it is still open, and it is added when it closes. See
`README.md`.

## Sessions with no transcript

The git history contains agent-assisted commits from 2026-07-02 onward. Their transcripts
were swept before this ledger existed. Nothing about them is recoverable beyond the commits
themselves, so they are not listed as rows here. Listing them with every field `unknown`
would imply a record that does not exist.
