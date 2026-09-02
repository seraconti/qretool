# Development ledger

Raw Claude Code session transcripts, one `.jsonl` per session. Each line is a single
record: a user turn, an assistant turn, or a tool call with its result. They are the
verbatim working record of how this codebase was built, including the reasoning that was
wrong and later corrected.

## Why these are kept

Claude Code writes transcripts to `~/.claude/projects/<project-slug>/` and sweeps them on a
retention schedule. Once swept they cannot be recovered. Copying them into the repository
is the only way to keep them.

They are intended as the evidence base for two things: the AI usage disclosure section of a
JOSS submission, and the methods chapter of the thesis.

## What survived, and what did not

**Two sessions existed when this ledger was created on 2026-08-23. One is copied here.**

That is not the full development history. The git log carries agent-assisted commits from
2026-07-02 onward, so most sessions were swept before this ledger existed. The retention
loss R0.3.1 warns about had already happened by the time the requirement was written.

`INDEX.md` describes what is here. It does not describe the sessions that are gone, because
nothing about them is recoverable beyond the commits they produced.

The second surviving transcript is the session that created this ledger. It is still being
written and is not copied yet. Copying a live file would capture a mid-sentence snapshot
that its own index row then describes. It is added when the session closes.

## Redaction

These files are redacted. Sera authorised the substitutions below on 2026-08-23; nothing
else was changed, and no record was removed.

| Original | Replacement | Count |
|---|---|---|
| the absolute repository path | `<repo>` | 671 |
| the workspace directory above it | `<workspace>` | 7 |
| the user home directory | `<home>` | 20 |
| private dataset filenames | `<dataset>.pickle` | 70 |
| private dataset identifiers without an extension | `<dataset>` | 560 |
| companion calibration record names | `<dataset>_freq_log` | 16 |
| the scratchpad path, dash-mangled spelling | `<scratchpad>` | 10 |
| the Unix owner and group from `ls -la` output | `<user>` | 34 |

Two things that look like dataset names are deliberately left in place. One is a regular
expression literal, `r"(\d{6})_6D2S_qubit(\d)"`, and one is a format string,
`6D2S_qubit{q}_freq_log.pickle`. Both are patterns. Neither names a record, and blanking
them would corrupt the code being discussed.

The directory names `tool/datasets/` and `FOR ZENODO/` are left as they are. `CLAUDE.md`
already documents both publicly, so removing them here would hide nothing.

Every line still parses as JSON after redaction. That was checked, not assumed.

The last two rows were a SECOND pass. The first pass matched only the slash-separated
spelling of the repository path, so the scratchpad directory survived in its dash-mangled
form and still carried the username and the full directory chain, and `ls -la` output still
printed the Unix owner. A review caught both. They are recorded here rather than quietly
corrected, because the point of this file is that the redaction is inspectable.

Two strings that look like identifiers are left alone: `qre_tool` and `912days` are the
repository and workspace directory names, and both already appear in tracked source
(`core/paths.py`, `docs/TIME_SEMANTICS.md`). Removing them here would hide nothing.

**Audited before copying, and clean:** no API keys, no bearer tokens, no private key
blocks, no GitHub tokens, no email addresses. No raw measurement content: no float arrays,
no pickle binary markers, no data column dumps. The datasets themselves never entered the
transcripts, only their paths.

## Reading a transcript

Records are newline-delimited JSON. The fields that matter most are `type` (`user` or
`assistant`), `timestamp`, and `message.content`, which is either a string or a list of
blocks. A block of `"type": "tool_use"` carries the tool name and its input; the matching
result arrives in the following user record.
