"""Path anchors and resolvers: one root discovered from the cwd, one declared.

Two distinct roots exist and must never be conflated:
  - project root: code, jobs, output/ - the nearest directory at or above the WORKING
    DIRECTORY carrying a project marker. Found by walking up from the cwd, never computed
    from this file's location. `provenance.get_git_commit` anchors on the cwd for the same
    reason, so a run's project root and its recorded commit describe one tree.
  - dataset root: where relative `Dataset.path` values resolve. Declared rather than
    inferred - by `--data-root`, `QUEBRA_DATA_ROOT`, or `[tool.quebra] data_root` in a
    `quebra.toml`. It may be inside the project or outside it.

Every dataset path is resolved exactly once per run (core/runner.run_job) through
resolve_dataset_path, and that single resolved path feeds BOTH the loader and the
provenance hash - so the recorded hash always describes the file actually loaded.
Resolution failures raise immediately (errors are raised, not swallowed); nothing
downstream may ever record a placeholder hash.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

import platformdirs


PROJECT_MARKERS = ("quebra.toml", "pyproject.toml", ".git")


def repo_root() -> Path:
    """The PROJECT root: the nearest directory at or above the cwd carrying a marker.

    Discovered by walking up from the working directory, NOT computed from `__file__`. That
    distinction is load-bearing: under `parents[3]` arithmetic an installed wheel reports its
    project root as a directory inside the virtualenv, and every job declaring an in-repo
    table such as `jobs/bench/results/*.csv` as a Dataset then raises FileNotFoundError. An
    editable install hides it, because there `src/` really does sit inside the repository.

    Anchoring on the caller's project is also what the rest of the tool already does: the
    CLI writes `output/` relative to the cwd, and `quebra.toml` is discovered by walking up
    from it. A project is where you are working, not where the library happens to be
    installed.

    Falls back to the cwd when no marker is found, which keeps this total. It backs the
    in-repo fallback in `resolve_dataset_path`; a caller with no project simply gets no
    second candidate.
    """
    start = Path.cwd().resolve()
    for directory in [start, *start.parents]:
        if any((directory / marker).exists() for marker in PROJECT_MARKERS):
            return directory
    return start


def default_dataset_root() -> Path:
    """Where relative dataset paths anchor.

    Delegates to `resolve_data_root`, which consults the explicit argument, the environment,
    a `quebra.toml`, then a user data directory - and never `__file__`. `repo_root().parent`
    would be correct only from a git checkout.

    From THIS checkout the answer is the repository itself, because `quebra.toml` at its root
    declares `data_root = "."`. The route to it is declared rather than inferred.
    """
    return resolve_data_root()


_MANIFEST_RELATIVE = Path("data") / "real_private" / "MANIFEST.toml"


def _is_manifested(raw: Path) -> bool:
    """Is this path one of the records the private manifest lists?

    Read lazily and failure-tolerantly on purpose: this runs only on the error path, and an
    unreadable or absent manifest must degrade to "not manifested" rather than replace a
    missing-dataset message with a manifest-parsing one.
    """
    manifest = repo_root() / _MANIFEST_RELATIVE
    if not manifest.is_file():
        return False
    # `Exception`, not a named tuple: this runs only while another error is being raised, and
    # a diagnostic helper that can itself raise replaces "your dataset is missing" with a
    # traceback from the code trying to explain it. Measured shapes that reached here -
    # `[record]` written for `[[record]]`, `record = "hello"`, `record = [1, 2]` - all raised
    # AttributeError past an `(OSError, TOMLDecodeError)` guard, and a non-UTF-8 locale raised
    # UnicodeDecodeError.
    try:
        parsed = tomllib.loads(manifest.read_text(encoding="utf-8"))
        records = parsed.get("record", [])
        listed = {
            record["path"]
            for record in records
            if isinstance(record, dict) and isinstance(record.get("path"), str)
        }
    except Exception:
        return False
    # Match on whole path COMPONENTS. A bare `endswith` crossed component boundaries, so
    # `/elsewhere/mine2x2/030723_2x2_qubit1.pickle` matched the record `2x2/030723_2x2_qubit1.pickle`
    # and a plainly wrong path was reported as an embargoed one - the exact inversion this
    # function exists to prevent.
    text = raw.as_posix()
    return any(text == entry or text.endswith("/" + entry) for entry in listed)


def resolve_dataset_path(path: str | Path, dataset_root: Path) -> Path:
    """Resolve a Dataset.path against dataset_root, then the repo root; must exist.

    Absolute paths pass through (but are existence-checked too - a typo must fail
    up front, before any output dir is created, not later at hash time).

    The repo-root fallback exists for tracked in-repo tables that are genuine data inputs
    rather than code - `jobs/bench/results/size_table.csv` is the case that forced it. Anchoring
    those on the dataset root would look for them one directory ABOVE the repo, and writing
    a project-name-prefixed path instead would break the moment --data-root moved. The dataset
    root is still tried first, so an external dataset can never be shadowed by a same-named
    file inside the repo.
    """
    raw = Path(path)
    if raw.is_absolute():
        candidates = [raw.resolve()]
    else:
        candidates = [(dataset_root / raw).resolve(), (repo_root() / raw).resolve()]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise DataUnavailable(raw, candidates, dataset_root, _is_manifested(raw))


def resolve_repo_path(path: str | Path) -> Path:
    """Resolve a repo-root-relative path (e.g. an include's 'jobs/active/…')."""
    raw = Path(path)
    return (raw if raw.is_absolute() else repo_root() / raw).resolve()


# --------------------------------------------------------------------------------------
# Data root resolution
# --------------------------------------------------------------------------------------

QUEBRA_DATA_ROOT_ENV = "QUEBRA_DATA_ROOT"
QUEBRA_TOML = "quebra.toml"


class DataUnavailable(FileNotFoundError):
    """A dataset path did not resolve, with the reason a reader actually needs.

    Subclasses `FileNotFoundError` so existing handlers keep working; what it adds is the
    distinction between two situations that otherwise look identical:

    - the file is one of ours and is embargoed, so the reader is not missing a step - they
      are missing data we cannot redistribute, and the simulated path is the way forward;
    - the path is simply wrong, and no amount of asking us will produce the file.

    `data/real_private/MANIFEST.toml` is what separates the two: it is
    committed precisely so this message can be specific without shipping any record.
    """

    def __init__(
        self,
        raw: Path,
        candidates: list[Path],
        dataset_root: Path,
        manifested: bool,
    ) -> None:
        self.raw = raw
        self.candidates = candidates
        self.dataset_root = dataset_root
        self.manifested = manifested
        tried = " or ".join(f"'{c}'" for c in candidates)
        if manifested:
            reason = (
                f"'{raw}' is listed in data/real_private/MANIFEST.toml, so this is an "
                f"EMBARGOED record rather than a wrong path. It is not distributed with the "
                f"repository. Run against the packaged fixtures instead - see "
                f"`quebra._fixtures.fixture_path` and docs/WRITING_A_JOB.md - or set "
                f"--data-root to a tree that has it."
            )
        else:
            reason = (
                f"'{raw}' is not in data/real_private/MANIFEST.toml, so this is a PATH that "
                f"does not exist rather than data being withheld. Check the spelling, and "
                f"note that relative dataset paths anchor on the dataset root, falling back "
                f"to the repo root for tracked in-repo tables - pass --data-root to "
                f"override the former."
            )
        super().__init__(
            f"dataset not found: {reason} Tried {tried} "
            f"(dataset root: '{dataset_root}', repo root: '{repo_root()}')."
        )


class DataRootNotFound(RuntimeError):
    """No usable data root. Raised in two distinct situations, with different messages.

    - A root was NAMED - by `--data-root` or `QUEBRA_DATA_ROOT` - and is not a directory.
      The message names that one root only, because the others are irrelevant: the caller
      said which tree to use, and the answer is that it is not there. Listing alternatives
      would suggest one of them might be substituted, which is exactly what must not happen.
    - NOBODY named one and no candidate exists. That message lists every location tried, so
      a reader can see the whole chain and pick where to intervene.

    Raised rather than guessed in both cases. A silent fallback would point an installed
    package at whatever directory it happened to be launched from, and the first symptom
    would be a dataset hash that does not match the one in a published provenance record.
    """


def _data_root_from_toml(start: Path) -> tuple[Path | None, list[str]]:
    """Walk up from `start` looking for `quebra.toml` with `[tool.quebra] data_root`."""
    tried: list[str] = []
    for directory in [start, *start.parents]:
        candidate = directory / QUEBRA_TOML
        tried.append(str(candidate))
        if not candidate.is_file():
            continue
        with candidate.open("rb") as handle:
            data = tomllib.load(handle)
        configured = data.get("tool", {}).get("quebra", {}).get("data_root")
        if configured is None:
            continue
        # Relative to the file that declares it, not to the process cwd. A config that
        # means something different depending on where you stand is not a config.
        return (candidate.parent / str(configured)).resolve(), tried
    return None, tried


def resolve_data_root(explicit: str | Path | None = None) -> Path:
    """Where datasets live. Two demands, then two candidates.

    A DEMAND is a root somebody named for this run. If it does not exist, that is an error
    and this raises:

    1. an explicit argument (the `--data-root` flag arrives here)
    2. the `QUEBRA_DATA_ROOT` environment variable

    A CANDIDATE is a place to look when nobody named one. First existing hit wins:

    3. `[tool.quebra] data_root` in a `quebra.toml`, at the working directory or above
    4. a `platformdirs` user data directory

    The demand/candidate split is the whole of the contract. Treating a named root as a
    candidate means a typo in `--data-root` silently resolves to whatever comes next - and
    since `quebra.toml` here declares `data_root = "."`, that next thing is the repository
    itself. The run then loads different files from the ones requested and records THEIR
    hashes, which is the failure `DataRootNotFound` exists to make impossible.

    None of these consults `__file__`. That is the point: `repo_root().parent` would be
    correct only inside a git checkout, and an installed package has no repository to be the
    parent of.
    """
    tried: list[str] = []

    if explicit is not None:
        root = Path(explicit).expanduser().resolve()
        if root.is_dir():
            return root
        raise DataRootNotFound(
            f"the data root was given as '{explicit}' (resolved to '{root}') but that is "
            f"not a directory. This is what `--data-root` sets. A root you name for a run is "
            f"a demand, not a candidate: falling back to another mechanism here would "
            f"analyse a different tree than the one you asked for, and record its dataset "
            f"hashes as if they were yours."
        )
    # Listed even when absent, because "you did not pass one" is information: it tells a
    # reader the --data-root flag exists.
    tried.append("explicit argument: none passed (--data-root)")

    env = os.environ.get(QUEBRA_DATA_ROOT_ENV)
    if env:
        root = Path(env).expanduser().resolve()
        if root.is_dir():
            return root
        raise DataRootNotFound(
            f"{QUEBRA_DATA_ROOT_ENV} is set to '{env}' (resolved to '{root}') but that is "
            f"not a directory. Set it to a real tree or unset it; an environment variable "
            f"naming a root is a demand, and silently ignoring it would analyse a different "
            f"tree than the one it names."
        )
    tried.append(f"{QUEBRA_DATA_ROOT_ENV}: not set")

    from_toml, toml_tried = _data_root_from_toml(Path.cwd())
    tried.append(
        f"{QUEBRA_TOML} searched upward from {Path.cwd()}: " + ", ".join(toml_tried)
    )
    if from_toml is not None and from_toml.is_dir():
        return from_toml

    # `platformdirs` is a hard dependency, so this is a lookup and not a fallback.
    user_root = Path(platformdirs.user_data_dir("quebra"))
    tried.append(f"platformdirs user data dir: {user_root}")
    if user_root.is_dir():
        return user_root

    raise DataRootNotFound(
        "could not resolve a data root. Tried, in order:\n  "
        + "\n  ".join(tried)
        + f"\n\nSet {QUEBRA_DATA_ROOT_ENV}, or write a {QUEBRA_TOML} with "
        "[tool.quebra] data_root, or pass --data-root."
    )
