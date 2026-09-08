"""Test-module citations under `src/`, `jobs/`, `docs/`, `scripts/` and the two root docs
name files that exist.

Oracle: the filesystem. A citation either resolves or it does not, so within the scope it
walks this guard is decidable. `AGENTS.md` section 10 forbids inventing a locator; nothing
before this noticed when a correct one went stale.

A docstring citing a renamed or deleted test is a claim about evidence that is no longer
there, and it is worse than no citation: a reader who follows it and finds nothing learns
only that something moved, while a reader who does not follow it carries away a belief in a
control that may never have existed.

Measured in the state this ships: 38 citation sites naming 18 distinct test modules, all of
which resolve. Three were stale when this landed and all three are corrected in the same
change: `jobs/bench/arms.py:48` named `tests/test_checks_c2.py`, and
`src/quebra/analyzers/checks/c1_lewis_robinson.py` and `c2_anderson_darling.py` named
`test_checks_c1.py` and `test_checks_c2.py` in the bare form. None of those three modules
has ever existed; each now names the test in `tests/test_checks_statistics.py` that actually
asserts the property being claimed.

**What is NOT walked, stated because the omissions are load-bearing.** `tests/` itself,
`pyproject.toml`, `spec/` and `.claude/` are all out of scope, and between them they hold
more citation sites than the scope does. `tests/` is excluded because a test may legitimately
write a placeholder path in a docstring, which
`tests/test_marker_discipline.py` does; the cost is that a stale citation inside `tests/`
goes unseen, and one did - this file's own opening paragraph named a module that never
existed until a review caught it. `spec/` is excluded because a phase spec is a dated record
of what was true when written, and because this repository's specs quote stale paths AS their
examples, so a guard over them would flag a spec for describing a defect correctly.
`.claude/` holds review ledgers rewritten on every review; one tracked ledger carries such a
citation today.

The sharpest cost of the `spec/` exclusion: `spec/specvalidity08.md:117` and `:158` both cite
`tests/test_calendar_tau_truncation.py` as pinning the calendar-clock tau truncation, and
`git log --all` shows that module never existed under any commit. The property is in fact
covered by `tests/test_checks_statistics.py`. This guard does not catch it and is not
intended to.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.policy

REPO_ROOT = Path(__file__).resolve().parents[1]

# Resolved against this file, never the working directory: an earlier guard in this phase
# used `repo_root()` and grew `scripts/acceptance.sh`'s failure set by one.
SCOPE = ("src/", "jobs/", "docs/", "scripts/", "AGENTS.md", "CONTRIBUTING.md")

# The `tests/` prefix is OPTIONAL, and that is the whole difference between this guard
# working and not. A first version required it and therefore missed the bare form, which
# this repository also writes: two stale citations were live in
# `src/quebra/analyzers/checks/`, naming the same absent module the guard was built to catch
# in `jobs/bench/arms.py`. A guard that misses a form the tree uses is not total.
#
# The lookbehind is load-bearing in the other direction. Without it the optional prefix
# matches INSIDE ordinary words and other directories: `latest_run.py` yields `test_run.py`,
# `contest_data.py` yields `test_data.py`, and `src/test_helper.py` yields `test_helper.py`,
# which canonicalises to a `tests/` path nobody cited. Each is a phantom the author then has
# to disprove. `test_citation_pattern_accepts_and_rejects_the_forms_it_claims` pins both
# directions, including the forms this pattern deliberately does NOT match.
CITATION = re.compile(r"(?<![\w/])(?:tests/)?test_[a-z_0-9]+\.py")

# Per-prefix floors, and they are what guards the WALK. A single total cannot: the prefixes
# contribute unequally (measured: src/ 13, jobs/ 14, docs/ 7, scripts/ 1, AGENTS.md 2,
# CONTRIBUTING.md 1, summing to 38), so at any total low enough to survive an ordinary
# docstring edit, dropping `docs/` or `scripts/` still passes. An earlier version of this
# file asserted only that each SCOPE entry was READ, which cannot catch a DELETED entry at
# all, because it iterated over SCOPE itself - dropping `src/`, where both real stale
# citations lived, left the suite green. Measured.
#
# The keys ARE the expected scope, so removing an entry from SCOPE fails the comparison
# below rather than silently shrinking what is checked. Floors sit well under the
# measurement so an edit that moves a citation does not fail here.
MIN_PER_PREFIX = {
    "src/": 8,
    "jobs/": 8,
    "docs/": 4,
    "scripts/": 1,
    "AGENTS.md": 1,
    "CONTRIBUTING.md": 1,
}


def _canonical(cited: str) -> str:
    """A citation resolved to a repository path, whichever form it was written in.

    `test_foo.py` and `tests/test_foo.py` name the same module, so both must resolve against
    `tests/` and both must count as one entry when the distinct total is reported. `tests/`
    is flat and stays flat, so there is no other directory a bare name could mean.
    """
    return cited if cited.startswith("tests/") else f"tests/{cited}"


def _stale(documents: list[tuple[str, str]]) -> list[tuple[str, int, str]]:
    """Citations naming no existing file, as (file, line, cited path).

    Takes documents rather than reading them so the positive control below can drive this
    same function with a planted citation. A control that re-implemented the check would
    pass while this one was broken.
    """
    found: list[tuple[str, int, str]] = []
    for name, text in documents:
        for lineno, line in enumerate(text.splitlines(), 1):
            for match in CITATION.finditer(line):
                if not (REPO_ROOT / _canonical(match.group(0))).is_file():
                    found.append((name, lineno, match.group(0)))
    return found


def _tracked_documents() -> list[tuple[str, str]]:
    """Every tracked file in scope, as (path, text). `cwd` is pinned to the repository."""
    listing = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()

    documents: list[tuple[str, str]] = []
    for relative in listing:
        if not relative.startswith(SCOPE):
            continue
        path = REPO_ROOT / relative
        try:
            documents.append((relative, path.read_text(encoding="utf-8")))
        except (UnicodeDecodeError, OSError):
            continue  # a binary or absent tracked file cites nothing
    return documents


def test_every_cited_test_module_exists() -> None:
    """Oracle: the filesystem. A cited path resolves or the citation is stale."""
    documents = _tracked_documents()

    # The walk itself, checked per prefix rather than inferred from a total. The key
    # comparison is what catches a SCOPE entry being deleted; the counts catch one being
    # mistyped, or a tree that stops being read for any other reason.
    assert set(MIN_PER_PREFIX) == set(SCOPE), (
        f"SCOPE is {sorted(SCOPE)} but the per-prefix floors cover "
        f"{sorted(MIN_PER_PREFIX)}; a prefix was added or removed without a floor, and the "
        "walk would then go unchecked for it"
    )
    counted = dict.fromkeys(SCOPE, 0)
    for name, text in documents:
        for prefix in SCOPE:
            if name.startswith(prefix):
                counted[prefix] += len(CITATION.findall(text))
                break
    thin = {p: counted[p] for p in SCOPE if counted[p] < MIN_PER_PREFIX[p]}
    assert not thin, (
        f"these prefixes yielded fewer citations than their floor: {thin} against "
        f"{ {p: MIN_PER_PREFIX[p] for p in thin} }. Either the walk is not reaching them or "
        "the pattern stopped matching; both make this guard pass while checking less than it "
        "claims"
    )

    stale = _stale(documents)
    assert not stale, "citations naming no existing file:\n" + "\n".join(
        f"  {name}:{lineno} -> {cited}" for name, lineno, cited in stale
    )


def test_the_guard_fires_on_a_planted_citation() -> None:
    """Positive control, against the real `_stale`, not a copy of it.

    Both citation forms are planted, because the prefixed and the bare branch of the pattern
    are separately breakable. A resolving path is included so the control also shows the
    guard is not simply flagging everything, which an inverted existence test would do while
    still catching both plants.
    """
    planted = "tests/test_a_module_that_does_not_exist.py"
    bare = "test_another_module_that_does_not_exist.py"
    assert not (REPO_ROOT / planted).is_file(), "the plant must name a real absence"
    assert not (REPO_ROOT / _canonical(bare)).is_file(), "so must the bare plant"

    document = [
        (
            "planted.py",
            f"see {planted}\nand {bare}\nand tests/test_stale_references.py\n",
        )
    ]
    stale = _stale(document)

    assert stale == [("planted.py", 1, planted), ("planted.py", 2, bare)], (
        f"the guard did not isolate both planted citations: {stale}"
    )


def test_citation_pattern_accepts_and_rejects_the_forms_it_claims() -> None:
    """Oracle: the pattern's own stated contract, as a table.

    Without this the lookbehind and the optional prefix each had no test: deleting the
    lookbehind left the suite green, because no phantom-producing word happens to sit in
    scope today. A comment calling a construct load-bearing is not evidence that it bears
    load.

    The rejected column is the point. Two of those rejections are deliberate blind spots
    rather than wins: a relative or nested path (`./tests/test_x.py`) is not matched, and
    neither is a hyphenated near-miss (`my-test_run.py`), which the lookbehind lets through
    as `test_run.py` because `-` is not a word character. Both are recorded here rather than
    left for a reader to discover.
    """
    accepted = {
        "tests/test_x.py": "tests/test_x.py",
        "see `test_checks_c1.py` asserts": "test_checks_c1.py",
        "(tests/test_z.py)": "tests/test_z.py",
        "tests/test_a.py::test_b": "tests/test_a.py",
    }
    for text, expected in accepted.items():
        assert CITATION.findall(text) == [expected], f"must accept: {text!r}"

    for text in (
        "latest_run.py",
        "contest_data.py",
        "fastest_path.py",
        "mytest_foo.py",
    ):
        assert CITATION.findall(text) == [], (
            f"must reject {text!r}: the optional prefix would otherwise match inside an "
            "ordinary word and invent a citation nobody wrote"
        )

    for text in ("src/test_helper.py", "jobs/bench/test_arm.py", "./tests/test_x.py"):
        assert CITATION.findall(text) == [], (
            f"must reject {text!r}: a path in another directory is not a `tests/` citation, "
            "and canonicalising it would name a file nobody cited"
        )

    # The known leak, asserted so it is a recorded decision and not a surprise.
    assert CITATION.findall("my-test_run.py") == ["test_run.py"], (
        "a hyphen is not a word character, so this form still leaks; if that ever produces "
        "a phantom in scope, extend the lookbehind to reject `-` as well"
    )
