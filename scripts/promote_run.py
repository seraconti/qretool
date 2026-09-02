#!/usr/bin/env python3
"""Promote one run's provenance into the committed tree.

SPEC 0003 R3.5. `output/` is gitignored because the artifacts are hundreds of megabytes, but
a figure that appears in a paper needs an auditable trail. The provenance records are
kilobytes and carry the identity, the dataset digests, the pipeline steps, the git commit and
the software version - enough to say exactly what produced a figure without shipping any of
it. So those get committed, and nothing else does.

    python scripts/promote_run.py output/<run-dir> --note "thesis ch4 fig 3"
    make promote RUN=output/<run-dir> NOTE="thesis ch4 fig 3"

Copies ONLY `provenance/`. Artifacts and figures are never copied: if this script could put a
4 MB pickle into the tree, the gitignore rule protecting `output/` would be pointless.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

PUBLISHED = Path("published")


# TOML basic-string escapes. Escaping only `\\` and `"` was not enough: a note containing a
# newline wrote a raw control character inside a quoted string, which `tomllib` rejects with
# `Illegal character`. The failure was silent - the script exited 0 having written an audit
# record that cannot be read back.
_TOML_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
}


def _quote(value: str) -> str:
    out = []
    for char in value:
        if char in _TOML_ESCAPES:
            out.append(_TOML_ESCAPES[char])
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            out.append(f"\\u{ord(char):04X}")
        else:
            out.append(char)
    return '"' + "".join(out) + '"'


def _load_records(run_dir: Path) -> list[tuple[Path, dict]]:
    provenance = run_dir / "provenance"
    if not provenance.is_dir():
        raise SystemExit(
            f"{run_dir} has no provenance/ directory. Only a completed run can be promoted."
        )
    records = []
    for path in sorted(provenance.glob("*.prov.json")):
        try:
            records.append((path, json.loads(path.read_text())))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path} is not readable JSON: {exc}") from exc
    if not records:
        raise SystemExit(f"{provenance} contains no .prov.json records.")
    return records


def promote(
    run_dir: Path, note: str, allow_dirty: bool, root: Path = Path(".")
) -> Path:
    records = _load_records(run_dir)

    # A record whose tree was dirty cannot be reproduced from any commit: the working tree it
    # ran against does not exist anywhere. Promoting one silently would put an unreproducible
    # claim in the committed history, which is the opposite of what this directory is for.
    dirty = [r for _, r in records if not r.get("tree_clean", False)]
    if dirty and not allow_dirty:
        raise SystemExit(
            f"{run_dir} ran against a DIRTY working tree (tree_clean=false in "
            f"{len(dirty)} of {len(records)} records), so no commit reproduces it. "
            f"Commit first and re-run, or pass --allow-dirty to promote it anyway with "
            f"that fact recorded."
        )

    # Every sink of one run is emitted with the same identity, commit and tree state, so
    # disagreement here means this directory does not hold exactly one run: records from two
    # runs have been merged, or a run was overwritten part-way. The identity and job name
    # below are read from the FIRST record, which would silently describe the whole promotion
    # by whichever record sorted first.
    #
    # This cannot verify that every sink RAN - the expected sink set lives in the job file,
    # which is not available here - so it checks the stronger thing it can see: that the
    # records present are mutually consistent.
    for field in ("identity", "git_commit"):
        values = {r.get(field) for _, r in records}
        if len(values) > 1:
            listed = ", ".join(sorted(str(v) for v in values))
            raise SystemExit(
                f"{run_dir} holds records that disagree on '{field}' ({listed}), so it is "
                f"not one run. Promote a directory written by a single run."
            )

    # `or ""` not `get(..., "")`: `build_prov_record`'s `identity` parameter defaults to
    # None, so a record can carry an explicit null, which the default form would subscript.
    full_identity = records[0][1].get("identity") or ""
    identity = full_identity[:6] or "unknown"
    job = Path(records[0][1].get("job_file", run_dir.name)).stem
    destination = root / PUBLISHED / f"{job}_{identity}"

    # Two runs can share a six-character identity prefix. Without this guard the second
    # promotion writes into the first's directory: same-named records are overwritten,
    # differently-named ones accumulate, and PROMOTED.toml is rewritten to describe only the
    # second run - so the directory silently misdescribes what it holds. Measured: two runs
    # produced one directory whose manifest said `record_count = 1` beside two records.
    existing = destination / "PROMOTED.toml"
    if existing.is_file():
        previous = existing.read_text()
        marker = f'identity = "{full_identity}"'
        if full_identity and marker not in previous:
            raise SystemExit(
                f"{destination} already holds a promotion with a different identity. Two runs "
                f"share the six-character prefix '{identity}'. Remove the existing directory "
                f"if it is stale, or promote under a longer prefix."
            )

    (destination / "provenance").mkdir(parents=True, exist_ok=True)

    for path, _ in records:
        shutil.copy2(path, destination / "provenance" / path.name)
        markdown = path.with_suffix("").with_suffix(".prov.md")
        if markdown.is_file():
            shutil.copy2(markdown, destination / "provenance" / markdown.name)

    lines = [
        "# GENERATED by scripts/promote_run.py. Do not hand-edit.",
        "#",
        "# The provenance of a figure that appears in a publication. The artifacts it",
        "# describes are NOT here - output/ is gitignored - but everything needed to say",
        "# what produced them is.",
        "",
        "[promotion]",
        f"note = {_quote(note)}",
        f"promoted = {_quote(date.today().isoformat())}",
        f"run_directory = {_quote(run_dir.name)}",
        f"job_file = {_quote(str(records[0][1].get('job_file', '')))}",
        f"identity = {_quote(str(records[0][1].get('identity', '')))}",
        f"git_commit = {_quote(str(records[0][1].get('git_commit', '')))}",
        f"tree_clean = {'true' if not dirty else 'false'}",
        f"record_count = {len(records)}",
        "",
    ]
    for _, record in records:
        lines.append("[[node]]")
        lines.append(f"name = {_quote(str(record.get('node_name', '')))}")
        for key in ("dataset_path", "dataset_hash"):
            if record.get(key):
                lines.append(f"{key} = {_quote(str(record[key]))}")
        lines.append("")

    (destination / "PROMOTED.toml").write_text("\n".join(lines))
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir", type=Path, help="a run directory under output/")
    parser.add_argument(
        "--note",
        required=True,
        help="where this figure appears, e.g. 'thesis ch4 fig 3'",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="promote a run made against an uncommitted tree, recording that it was",
    )
    args = parser.parse_args(argv)

    if not args.run_dir.is_dir():
        raise SystemExit(f"no such run directory: {args.run_dir}")

    destination = promote(args.run_dir, args.note, args.allow_dirty)
    copied = sorted(p.name for p in (destination / "provenance").iterdir())
    print(f"promoted {args.run_dir} -> {destination}")
    for name in copied:
        print(f"  {name}")
    print("  PROMOTED.toml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
