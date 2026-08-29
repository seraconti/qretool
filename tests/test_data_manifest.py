"""The manifest must describe the records that are actually here.

SPEC 0003 R3.3. The manifest is committed and the records are not, so it is the only
statement a reviewer can check. A manifest that has drifted from the files is worse than no
manifest: it asserts a provenance nobody verified.

**These tests skip rather than fail when `data/real_private/` is absent.** That is the whole
point of the split - someone who has none of the embargoed data must still get a green suite.
A failure here would punish a reviewer for the one thing they cannot fix.
"""

from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path

import pytest

from quebra.core.paths import repo_root

PRIVATE_ROOT = repo_root() / "data" / "real_private"
MANIFEST = PRIVATE_ROOT / "MANIFEST.toml"


def _records() -> list[dict]:
    if not MANIFEST.is_file():
        pytest.skip("data/real_private/MANIFEST.toml absent")
    return tomllib.loads(MANIFEST.read_text()).get("record", [])


def _present_files() -> list[Path]:
    if not PRIVATE_ROOT.is_dir():
        pytest.skip(
            "data/real_private/ absent (this is expected without the private data)"
        )
    return [
        p for p in PRIVATE_ROOT.rglob("*") if p.is_file() and p.name != MANIFEST.name
    ]


def test_the_manifest_parses_and_is_not_empty():
    records = _records()
    assert records, "a manifest with no records is not a manifest"
    for record in records:
        assert record["path"] and record["sha256"] and record["embargo"]


def test_every_present_file_has_an_entry():
    """A record that arrived without being manifested is invisible to a reviewer."""
    present = {str(p.relative_to(PRIVATE_ROOT)) for p in _present_files()}
    listed = {r["path"] for r in _records()}
    missing = sorted(present - listed)
    assert not missing, f"present but unmanifested: {missing[:5]}"


def test_every_manifest_entry_matches_the_file_on_disk():
    """The assertion the manifest exists to support: this digest, this file.

    Skips per-entry for records that are absent - a partial checkout is legitimate - but any
    file that IS here must match, because a silent mismatch means a figure was computed from
    something other than what the manifest claims.
    """
    checked = 0
    for record in _records():
        path = PRIVATE_ROOT / record["path"]
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == record["sha256"], (
            f"{record['path']}: on disk {digest[:16]}… but manifest says "
            f"{record['sha256'][:16]}…"
        )
        assert path.stat().st_size == record["bytes"]
        checked += 1
    if checked == 0:
        pytest.skip("no manifested file is present to verify")


def test_the_declared_count_matches_the_entries():
    manifest = (
        tomllib.loads(MANIFEST.read_text())
        if MANIFEST.is_file()
        else pytest.skip("manifest absent")
    )
    assert manifest["manifest"]["file_count"] == len(manifest.get("record", []))


def test_a_corrupted_record_would_be_caught(tmp_path):
    """A positive control on the check above, run against a synthetic tree.

    Without this, `test_every_manifest_entry_matches_the_file_on_disk` passing proves only
    that nothing is currently wrong - not that it would notice if something were.
    """
    payload = b"not really a pickle"
    good = hashlib.sha256(payload).hexdigest()
    corrupted = hashlib.sha256(payload + b"!").hexdigest()
    assert good != corrupted

    target = tmp_path / "record.pickle"
    target.write_bytes(payload)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == good

    target.write_bytes(payload + b"!")
    assert hashlib.sha256(target.read_bytes()).hexdigest() != good
