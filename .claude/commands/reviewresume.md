Resume an interrupted review.

Read `.claude/review-findings.md`. Report its SCOPE, how many files are done, and which
remain. Then respawn the code-reviewer subagent with the SAME scope so it picks up from
the ledger, or with just the remaining files if the scope line is stale.

Do not start a fresh review and do not clear the ledger.
