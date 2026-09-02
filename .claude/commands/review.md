Review a bounded slice of the current diff: $ARGUMENTS

If $ARGUMENTS is empty, do NOT review everything. Instead run `git diff --stat`, print the
changed paths grouped into slices of at most ~400 changed lines each, and ask which slice
to review. A whole-repo review is what kills the reviewer mid-pass.

Otherwise pass $ARGUMENTS to the code-reviewer subagent as its scope. Remind it that
`.claude/review-findings.md` is its ledger and that it must resume from it if the scope
matches.

When the subagent returns, report CRITICAL and IMPORTANT first, then MINOR, then
SHIP / DO NOT SHIP. If the subagent died without finishing, say so plainly, read
`.claude/review-findings.md` yourself, report what was salvaged, and name the first
unreviewed file so I can respawn on exactly that scope.
