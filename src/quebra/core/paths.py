"""CWD-independent path anchors and resolvers.

Two distinct roots exist and must never be conflated:
  - repo root (qre_tool/): code, jobs, output/ - anchored off this file's location,
    the same pattern as provenance.get_git_commit.
  - dataset root (912days/ by default, --data-root overrides): the published
    read-only datasets live OUTSIDE the git repo, one level above it.

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


PROJECT_MARKERS = ("quebra.toml", "pyproject.toml", ".git")


def repo_root() -> Path:
    """The PROJECT root: the nearest directory at or above the cwd carrying a marker.

    Discovered by walking up from the working directory, NOT computed from `__file__`.
    That distinction is the whole of SPEC 0002 R1.3.1, and it was found the hard way: with
    `parents[3]` arithmetic an installed wheel reported its repo root as
    `<venv>/lib/python3.13`, and the four jobs that declare `jobs/bench/results/*.csv` as a
    Dataset raised FileNotFoundError under `scripts/acceptance.sh`. The editable install
    never showed it, because there `src/` really does sit inside the repository.

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
    a `quebra.toml`, then a user data directory - and never `__file__`. It used to return
    `repo_root().parent`, which was correct only from a git checkout.

    From THIS checkout the answer is unchanged, because `quebra.toml` at the repository root
    declares `data_root = ".."`. The behaviour is the same; the route to it is declared
    rather than inferred.
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
    try:
        records = tomllib.loads(manifest.read_text()).get("record", [])
    except (OSError, tomllib.TOMLDecodeError):
        return False
    # Match on the tail, because a job writes `data/real_private/6D2S/x.pickle` while the
    # manifest keys on `6D2S/x.pickle` - relative to the private root.
    text = raw.as_posix()
    return any(text.endswith(str(record.get("path", "\0"))) for record in records)


def resolve_dataset_path(path: str | Path, dataset_root: Path) -> Path:
    """Resolve a Dataset.path against dataset_root, then the repo root; must exist.

    Absolute paths pass through (but are existence-checked too - a typo must fail
    up front, before any output dir is created, not later at hash time).

    The repo-root fallback exists for tracked in-repo tables that are genuine data inputs
    rather than code - `jobs/bench/results/size_table.csv` is the case that forced it. Anchoring
    those on the dataset root would look for them one directory ABOVE the repo, and writing
    'qre_tool/jobs/bench/results/…' instead would break the moment --data-root moved. The dataset
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
# Data root resolution (SPEC 0002 R1.3)
# --------------------------------------------------------------------------------------

QUEBRA_DATA_ROOT_ENV = "QUEBRA_DATA_ROOT"
QUEBRA_TOML = "quebra.toml"


class DataUnavailable(FileNotFoundError):
    """A dataset path did not resolve, with the reason a reader actually needs.

    Subclasses `FileNotFoundError` so existing handlers keep working; what it adds is the
    distinction between the two situations that used to look identical:

    - the file is one of ours and is embargoed, so the reader is not missing a step - they
      are missing data we cannot redistribute, and the simulated path is the way forward;
    - the path is simply wrong, and no amount of asking us will produce the file.

    SPEC 0003 R3.4. `data/real_private/MANIFEST.toml` is what separates the two: it is
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
    """No data root could be resolved, with every location that was tried.

    Raised rather than guessed. A relative fallback here would silently point an installed
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
    """Where datasets live. First hit wins, in the order SPEC 0002 R1.3.3 fixes.

    1. an explicit argument (the `--data-root` flag arrives here)
    2. the `QUEBRA_DATA_ROOT` environment variable
    3. `[tool.quebra] data_root` in a `quebra.toml`, at the working directory or above
    4. a `platformdirs` user data directory

    None of these consults `__file__`. That is the point: the old `repo_root().parent` was
    correct only inside a git checkout, and an installed package has no repository to be
    the parent of.
    """
    tried: list[str] = []

    if explicit is not None:
        root = Path(explicit).expanduser().resolve()
        tried.append(f"explicit argument: {root}")
        if root.is_dir():
            return root
    else:
        # Listed even when absent. R1.3.4 asks for every location tried, and "you did not
        # pass one" is information: it tells a reader the --data-root flag exists.
        tried.append("explicit argument: none passed (--data-root)")

    env = os.environ.get(QUEBRA_DATA_ROOT_ENV)
    if env:
        root = Path(env).expanduser().resolve()
        tried.append(f"{QUEBRA_DATA_ROOT_ENV}: {root}")
        if root.is_dir():
            return root
    else:
        tried.append(f"{QUEBRA_DATA_ROOT_ENV}: not set")

    from_toml, toml_tried = _data_root_from_toml(Path.cwd())
    tried.append(
        f"{QUEBRA_TOML} searched upward from {Path.cwd()}: " + ", ".join(toml_tried)
    )
    if from_toml is not None and from_toml.is_dir():
        return from_toml

    try:
        import platformdirs

        user_root = Path(platformdirs.user_data_dir("quebra"))
        tried.append(f"platformdirs user data dir: {user_root}")
        if user_root.is_dir():
            return user_root
    except ImportError:
        tried.append("platformdirs user data dir: platformdirs is not installed")

    raise DataRootNotFound(
        "could not resolve a data root. Tried, in order:\n  "
        + "\n  ".join(tried)
        + f"\n\nSet {QUEBRA_DATA_ROOT_ENV}, or write a {QUEBRA_TOML} with "
        "[tool.quebra] data_root, or pass --data-root."
    )
