"""Promoting a run must commit the trail and never the artifacts.

SPEC 0003 R3.5. `output/` is gitignored because it is hundreds of megabytes; the provenance
is kilobytes and is what makes a published figure auditable. The failure this guards is a
promotion command that quietly copies a 4 MB pickle into the tree, which would make the
gitignore rule protecting `output/` pointless.

Driven entirely against synthetic run directories under `tmp_path` - no private data, no
real run required.
"""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from promote_run import promote  # noqa: E402


def _make_run(tmp_path: Path, *, tree_clean: bool = True, nodes: int = 2) -> Path:
    run = tmp_path / "output" / "demo_job_abc123_20260101_000000"
    (run / "provenance").mkdir(parents=True)
    for index in range(nodes):
        record = {
            "node_name": f"node_{index}",
            "identity": "abc123def456",
            "job_file": "jobs/active/demo_job.py",
            "git_commit": "deadbee",
            "tree_clean": tree_clean,
            "dataset_path": f"data/real_private/6D2S/rec_{index}.pickle",
            "dataset_hash": f"sha256:{index:064d}",
        }
        (run / "provenance" / f"node_{index}.prov.json").write_text(json.dumps(record))
        (run / "provenance" / f"node_{index}.prov.md").write_text(f"# node_{index}\n")
    # The artifacts that must NOT travel.
    (run / "big_artifact.pkl").write_bytes(b"\0" * 4096)
    (run / "figure_static.pdf").write_bytes(b"%PDF-1.4\n")
    return run


def test_it_copies_the_provenance(tmp_path):
    run = _make_run(tmp_path)
    destination = promote(run, note="thesis fig 1", allow_dirty=False, root=tmp_path)
    copied = sorted(p.name for p in (destination / "provenance").iterdir())
    assert copied == [
        "node_0.prov.json",
        "node_0.prov.md",
        "node_1.prov.json",
        "node_1.prov.md",
    ]


def test_it_never_copies_an_artifact(tmp_path):
    """The load-bearing assertion. A promotion that carried artifacts would defeat the
    gitignore rule that keeps 361 MB of evidence out of the repository."""
    run = _make_run(tmp_path)
    destination = promote(run, note="thesis fig 1", allow_dirty=False, root=tmp_path)
    carried = [p.name for p in destination.rglob("*") if p.is_file()]
    assert not any(name.endswith((".pkl", ".pdf", ".png")) for name in carried), carried


def test_a_dirty_run_is_refused_by_default(tmp_path):
    """A run made against an uncommitted tree is reproducible from no commit at all, so
    promoting it silently would commit a claim nobody can check."""
    run = _make_run(tmp_path, tree_clean=False)
    with pytest.raises(SystemExit, match="DIRTY working tree"):
        promote(run, note="thesis fig 1", allow_dirty=False, root=tmp_path)


def test_a_dirty_run_can_be_promoted_deliberately_and_says_so(tmp_path):
    run = _make_run(tmp_path, tree_clean=False)
    destination = promote(run, note="thesis fig 1", allow_dirty=True, root=tmp_path)
    manifest = tomllib.loads((destination / "PROMOTED.toml").read_text())
    assert manifest["promotion"]["tree_clean"] is False


def test_the_record_carries_what_makes_the_figure_auditable(tmp_path):
    run = _make_run(tmp_path)
    destination = promote(
        run, note="thesis ch4 fig 3", allow_dirty=False, root=tmp_path
    )
    manifest = tomllib.loads((destination / "PROMOTED.toml").read_text())
    promotion = manifest["promotion"]
    assert promotion["note"] == "thesis ch4 fig 3"
    assert promotion["identity"] == "abc123def456"
    assert promotion["git_commit"] == "deadbee"
    assert promotion["record_count"] == 2
    # The dataset digests are the link to data/real_private/MANIFEST.toml.
    assert {node["dataset_hash"] for node in manifest["node"]} == {
        "sha256:" + "0" * 64,
        "sha256:" + "0" * 63 + "1",
    }


def test_a_run_without_provenance_is_refused(tmp_path):
    run = tmp_path / "output" / "empty_run"
    run.mkdir(parents=True)
    with pytest.raises(SystemExit, match="no provenance"):
        promote(run, note="x", allow_dirty=False, root=tmp_path)


def test_a_provenance_directory_with_no_records_is_refused(tmp_path):
    run = tmp_path / "output" / "hollow_run"
    (run / "provenance").mkdir(parents=True)
    with pytest.raises(SystemExit, match="no .prov.json"):
        promote(run, note="x", allow_dirty=False, root=tmp_path)


def test_unreadable_json_is_reported_as_such(tmp_path):
    run = _make_run(tmp_path)
    (run / "provenance" / "node_0.prov.json").write_text("{not json")
    with pytest.raises(SystemExit, match="not readable JSON"):
        promote(run, note="x", allow_dirty=False, root=tmp_path)
