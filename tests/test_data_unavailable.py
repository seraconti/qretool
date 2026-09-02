"""A missing dataset must say which kind of missing it is.

Without the distinction both raise the same `FileNotFoundError`: a reviewer who lacks an
embargoed record and a user who mistyped a path get identical output, and only the first of
them can do anything about it.

These tests need none of the private data - they drive `_is_manifested` and `DataUnavailable`
against a manifest written under `tmp_path`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quebra.core import paths as paths_module
from quebra.core.paths import DataUnavailable, resolve_dataset_path


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """A checkout with a manifest listing one record that is not present."""
    private = tmp_path / "data" / "real_private"
    private.mkdir(parents=True)
    (private / "MANIFEST.toml").write_text(
        "[manifest]\nfile_count = 1\n\n"
        '[[record]]\npath = "6D2S/embargoed.pickle"\n'
        'sha256 = "0" \nbytes = 1\nembargo = "embargoed"\n'
    )
    monkeypatch.setattr(paths_module, "repo_root", lambda: tmp_path)
    return tmp_path


def test_a_manifested_but_absent_record_is_reported_as_embargoed(fake_repo):
    with pytest.raises(DataUnavailable) as excinfo:
        resolve_dataset_path("data/real_private/6D2S/embargoed.pickle", fake_repo)
    error = excinfo.value
    assert error.manifested is True
    assert "EMBARGOED" in str(error)
    # The message must end in an action, not an apology.
    assert "fixture" in str(error)


def test_a_wrong_path_is_not_reported_as_embargoed(fake_repo):
    """The failure this separates out. Claiming embargo here would send someone asking for
    data that would not help them."""
    with pytest.raises(DataUnavailable) as excinfo:
        resolve_dataset_path("data/real_private/6D2S/typo.pickle", fake_repo)
    error = excinfo.value
    assert error.manifested is False
    assert "EMBARGOED" not in str(error)
    assert "does not exist" in str(error)


def test_it_is_still_a_FileNotFoundError(fake_repo):
    """Subclassing keeps every existing `except FileNotFoundError` working."""
    with pytest.raises(FileNotFoundError):
        resolve_dataset_path("data/real_private/6D2S/typo.pickle", fake_repo)


def test_an_absent_manifest_degrades_to_not_manifested(tmp_path, monkeypatch):
    """The error path must not acquire a second failure mode of its own."""
    monkeypatch.setattr(paths_module, "repo_root", lambda: tmp_path)
    assert paths_module._is_manifested(Path("anything.pickle")) is False
    with pytest.raises(DataUnavailable) as excinfo:
        resolve_dataset_path("anything.pickle", tmp_path)
    assert excinfo.value.manifested is False


def test_an_unparseable_manifest_degrades_rather_than_replacing_the_error(
    tmp_path, monkeypatch
):
    """A broken manifest must not turn 'your dataset is missing' into a TOML error."""
    private = tmp_path / "data" / "real_private"
    private.mkdir(parents=True)
    (private / "MANIFEST.toml").write_text("this is not [valid toml")
    monkeypatch.setattr(paths_module, "repo_root", lambda: tmp_path)
    assert paths_module._is_manifested(Path("x.pickle")) is False
    with pytest.raises(DataUnavailable):
        resolve_dataset_path("x.pickle", tmp_path)


def test_the_error_names_every_location_it_tried(fake_repo):
    with pytest.raises(DataUnavailable) as excinfo:
        resolve_dataset_path("data/real_private/6D2S/typo.pickle", fake_repo)
    assert len(excinfo.value.candidates) >= 1
    for candidate in excinfo.value.candidates:
        assert str(candidate) in str(excinfo.value)
