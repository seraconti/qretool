"""The manifest must describe the records that are actually here.

The manifest is committed and the records are not, so it is the only
statement a reviewer can check. A manifest that has drifted from the files is worse than no
manifest: it asserts a provenance nobody verified.

**These tests skip rather than fail when `data/real_private/` is absent.** That is the whole
point of the split - someone who has none of the embargoed data must still get a green suite.
A failure here would punish a reviewer for the one thing they cannot fix.
"""

from __future__ import annotations

import hashlib
import sys
import tomllib
from pathlib import Path

import pytest

from quebra.core.paths import repo_root

pytestmark = pytest.mark.policy


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


@pytest.mark.real
def test_the_manifest_parses_and_is_not_empty():
    records = _records()
    assert records, "a manifest with no records is not a manifest"
    for record in records:
        assert record["path"] and record["sha256"] and record["embargo"]


@pytest.mark.real
def test_every_present_file_has_an_entry():
    """A record that arrived without being manifested is invisible to a reviewer."""
    present = {str(p.relative_to(PRIVATE_ROOT)) for p in _present_files()}
    listed = {r["path"] for r in _records()}
    missing = sorted(present - listed)
    assert not missing, f"present but unmanifested: {missing[:5]}"


@pytest.mark.real
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


@pytest.mark.real
def test_the_declared_count_matches_the_entries():
    manifest = (
        tomllib.loads(MANIFEST.read_text())
        if MANIFEST.is_file()
        else pytest.skip("manifest absent")
    )
    assert manifest["manifest"]["file_count"] == len(manifest.get("record", []))


def test_a_corrupted_record_would_be_caught(tmp_path, monkeypatch):
    """A positive control that exercises the CHECK, not hashlib.

    The previous version hashed a literal and asserted the digest changed when a byte was
    appended. That is a property of sha256; it touched no project code and would have passed
    with the manifest check deleted. This builds a synthetic private tree, runs the same
    comparison the real test runs, and asserts it catches a flipped byte.
    """
    import quebra.core.paths as paths_module

    private = tmp_path / "data" / "real_private"
    (private / "6D2S").mkdir(parents=True)
    record = private / "6D2S" / "rec.pickle"
    record.write_bytes(b"payload")
    digest = hashlib.sha256(record.read_bytes()).hexdigest()
    (private / "MANIFEST.toml").write_text(
        f"[manifest]\nfile_count = 1\n\n[[record]]\n"
        f'path = "6D2S/rec.pickle"\nsha256 = "{digest}"\nbytes = {len(b"payload")}\n'
        f'embargo = "embargoed"\n'
    )
    monkeypatch.setattr(paths_module, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(sys.modules[__name__], "PRIVATE_ROOT", private)
    monkeypatch.setattr(sys.modules[__name__], "MANIFEST", private / "MANIFEST.toml")

    # Intact: the check passes.
    test_every_manifest_entry_matches_the_file_on_disk()

    # One byte flipped: the check must fail.
    record.write_bytes(b"payloae")
    with pytest.raises(AssertionError, match="manifest says"):
        test_every_manifest_entry_matches_the_file_on_disk()


def test_the_completeness_check_catches_an_unmanifested_file(tmp_path, monkeypatch):
    """The other direction: a record that arrived without being listed."""
    import quebra.core.paths as paths_module

    private = tmp_path / "data" / "real_private"
    (private / "6D2S").mkdir(parents=True)
    (private / "6D2S" / "listed.pickle").write_bytes(b"a")
    (private / "MANIFEST.toml").write_text(
        "[manifest]\nfile_count = 1\n\n[[record]]\n"
        'path = "6D2S/listed.pickle"\nsha256 = "x"\nbytes = 1\nembargo = "embargoed"\n'
    )
    monkeypatch.setattr(paths_module, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(sys.modules[__name__], "PRIVATE_ROOT", private)
    monkeypatch.setattr(sys.modules[__name__], "MANIFEST", private / "MANIFEST.toml")

    test_every_present_file_has_an_entry()

    (private / "6D2S" / "smuggled.pickle").write_bytes(b"b")
    with pytest.raises(AssertionError, match="present but unmanifested"):
        test_every_present_file_has_an_entry()
