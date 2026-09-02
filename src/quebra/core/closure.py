"""The set of `quebra` modules a job's steps can actually reach, and their content hashes.

SPEC 0005 R5.1. Identity used to be `hash(job file) + dataset hashes + child identities`, which
meant the analyzer that produced the numbers could change completely while the digest asserted
nothing had. Measured before the change: appending a line to `analyzers/t2star.py` left
`t2star_q1_070423`'s identity byte-identical.

This computes the other half. Hashing all of `src/quebra/` would fix the over-claim and
recreate the blast radius the plan warned about - editing a plot module would invalidate every
cached compute artifact. Hashing the STATIC IMPORT CLOSURE of the step functions a job calls
fixes it and keeps the radius narrow.

**What this buys is truth, not caching.** `runner._reuse_eligible_dir` keys on a repo-wide
`git_commit`, so any commit to any file already invalidates every cached artifact. This does
not change that. What it changes is that a run directory name, a provenance record and a
promoted `PROMOTED.toml` begin describing the computation that actually ran.

Four hazards this is built to avoid, each of which silently produces a wrong closure:

1. **`sys.modules` is not a valid source.** `quebra run --all` imports every job into one
   process in a loop, so a closure read from `sys.modules` would give job N the union of jobs
   1..N, and `run --all` would disagree with `run <one job>`. The traversal here is static.
2. **Function-local imports count.** `quebra.analyzers.permutation` is reachable ONLY through
   a function body, and it computes the xi permutation null that `xi_seed` feeds. `grimp`
   walks them; a module-body-only AST pass would drop it.
3. **`from <package> import <submodule>` must resolve to the submodule**, not the package.
4. **Never key on a file path or on `module.__name__` for job modules.** Job modules are named
   `subjob_<stem>_<sha256(abspath)[:8]>`, so the name embeds an absolute path and differs
   between machines. Keys here are dotted `quebra.*` names; values are hashes of file BYTES.
   That is what makes an identity equal under an editable install and under a wheel.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
from functools import lru_cache
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

PACKAGE = "quebra"


@lru_cache(maxsize=1)
def _graph() -> object:
    """The static import graph of `quebra`, built once per process.

    Built lazily: importing this module must not cost a graph build, because
    `quebra.core.job` imports it and every `import quebra` would then pay for it.
    """
    import grimp

    # `cache_dir=None`, NOT the default. grimp's cache is keyed on MTIME, so a content change
    # that preserves mtime - `cp -p`, `rsync --times`, `tar -x`, a container layer restore -
    # yields a STALE graph. Measured: adding an import to `analyzers/t2star.py` and restoring
    # its mtime left the cached graph reporting the new dependency as absent, while
    # `cache_dir=None` on the identical tree reported it present. An identity computed from
    # the stale graph silently stops covering that module, which is the exact failure this
    # module exists to prevent.
    #
    # It also removes a filesystem side effect: the default writes `.grimp_cache/` into the
    # process CWD, so computing an identity created a directory, and did so by failing with
    # PermissionError under a read-only CWD - normal in a CI container.
    #
    # The cost is affordable: the graph build is tens of milliseconds cold, and
    # `job_code_hash` is memoized per job, so a run pays it once.
    return grimp.build_graph(PACKAGE, cache_dir=None)


def _quebra_imports_of_file(path: Path) -> set[str]:
    """`quebra.*` modules imported by a file that is NOT part of the package.

    Job files live outside `quebra`, so grimp cannot see them, but they are where the steps
    that call the analyzers are defined - measured, the three steps of `t2star_q1_070423`
    that reach `t2star.run` belong to the job module, not a `quebra.*` one. Seeding only
    `quebra.*` step modules would therefore miss the analyzers entirely and make the whole
    scheme a no-op.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        # Raised, not swallowed. Returning an empty seed set here would make the closure
        # empty and silently restore the pre-SPEC-0005 behaviour - identity covering the job
        # file alone - which is the defect this module was written to remove. `_seed_modules`
        # already raises for the analogous unresolvable-module case.
        raise ValueError(
            f"cannot read imports from {path}: {exc}. Its steps' library code cannot enter "
            f"the identity, and an identity that quietly stops covering an input is the "
            f"failure this scheme exists to prevent."
        ) from exc

    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == PACKAGE or alias.name.startswith(f"{PACKAGE}."):
                    found.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module == PACKAGE or node.module.startswith(f"{PACKAGE}."):
                found.add(node.module)
                # `from quebra.analyzers import t2star` names submodules, not attributes.
                for alias in node.names:
                    found.add(f"{node.module}.{alias.name}")
    return found


def _seed_modules(functions: Sequence[object]) -> set[str]:
    """Seed the traversal from every step's defining module.

    A `quebra.*` module seeds itself. A job module seeds the `quebra.*` modules it imports,
    read statically from its source. An unresolvable callable RAISES: `build_identity`
    already sets that precedent, and its reason applies with full force here - an identity
    that quietly stops covering an input is the failure this whole scheme exists to prevent.
    """
    seeds: set[str] = set()
    for fn in functions:
        module: ModuleType | None = inspect.getmodule(fn)
        if module is None:
            raise TypeError(
                f"cannot resolve a defining module for step {getattr(fn, '__name__', fn)!r}. "
                f"Its source cannot enter the identity, so the identity would silently stop "
                f"covering it."
            )
        name = module.__name__
        if name == PACKAGE or name.startswith(f"{PACKAGE}."):
            seeds.add(name)
            continue
        source = getattr(module, "__file__", None)
        if source is None:
            raise TypeError(
                f"step {getattr(fn, '__name__', fn)!r} is defined in module {name!r}, which "
                f"has no source file, so its imports cannot be read."
            )
        seeds.update(_quebra_imports_of_file(Path(source)))
    return seeds


def _reachable(seeds: set[str]) -> set[str]:
    """Every `quebra` module reachable from the seeds, seeds included."""
    graph = _graph()
    known = set(graph.modules)  # type: ignore[attr-defined]
    seen: set[str] = set()
    stack = [s for s in seeds if s in known]
    while stack:
        module = stack.pop()
        if module in seen:
            continue
        seen.add(module)
        stack.extend(graph.find_modules_directly_imported_by(module))  # type: ignore[attr-defined]
    return seen


def _module_digest(name: str) -> str:
    """sha256 of a module's file bytes.

    Bytes, not text: a file is what it is regardless of how a platform decodes it, and the
    digest must be equal under an editable install and a wheel.

    The module itself is located, not imported. The closure is the STATIC import graph, so it
    holds modules this run never executes; importing one to reach `__file__` would run its
    module scope and pull in its dependencies - sklearn via the TLF analyzer, scipy's
    permutation machinery, a plotting stack - purely to compute a digest. Worse, a
    module-scope failure in a reachable-but-unused module would surface as a failure of
    IDENTITY COMPUTATION, before the output directory exists, naming a module the job does
    not run.

    What `find_spec` does still import is the target's PARENT PACKAGES, since it has to import
    a package to ask it where its submodule lives. So `quebra.analyzers.checks.<x>` imports
    `quebra`, `quebra.analyzers`, `quebra.analyzers.checks` and whatever their `__init__.py`
    files re-export - numpy arrives that way. The saving is real (scipy, sklearn and
    matplotlib stay out) but it holds only while those `__init__.py` files stay thin, and one
    already re-exports.

    `find_spec` reads the same path the import would bind, including a package's own
    `__init__.py`, and returns the already-loaded spec for anything imported earlier - so the
    digest is identical either way.
    """
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, AttributeError, ValueError) as exc:
        raise ValueError(f"module {name!r} could not be located to hash") from exc
    source = spec.origin if spec is not None else None
    if source is None:
        raise ValueError(f"module {name!r} has no source file to hash")
    return hashlib.sha256(Path(source).read_bytes()).hexdigest()


def code_closure(step_functions: Sequence[object]) -> dict[str, str]:
    """`{dotted module name: sha256}` for every `quebra` module the steps can reach.

    Sorted by the caller (a dict preserves insertion order and this inserts in sorted order),
    so two builds of the same graph fold in the same sequence regardless of DAG iteration.
    """
    reachable = _reachable(_seed_modules(step_functions))
    return {name: _module_digest(name) for name in sorted(reachable)}


def _render(value: object) -> str:
    """A cross-process-stable rendering of a step argument, or a TypeError.

    An ALLOWLIST, because the first version of this was a denylist - it rejected reprs
    containing " at 0x" and accepted everything else - and three realistic kwarg types walked
    straight through it:

    - **`set` / `frozenset`**: iteration order follows per-process randomised string hashing,
      so the same job produced three different rows in three processes. Rendered sorted here.
    - **`pathlib.Path`**: renders as `PosixPath('/abs/path')`, putting an absolute path into
      the identity and breaking install-independence - the very thing hazard 4 above forbids.
      Rejected; pass a repo-relative string.
    - **`numpy.ndarray`**: reprs longer than the print threshold elide the middle
      (`array([0, 1, 2, ..., 1998, 1999])`), so two different arrays render identically and
      COLLIDE - the failure `parameter_row` exists to close, reopened.

    A denylist of repr shapes can only ever chase the forms someone has already met.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return repr(value)
    if isinstance(value, (list, tuple)):
        inner = ", ".join(_render(v) for v in value)
        return f"[{inner}]" if isinstance(value, list) else f"({inner})"
    if isinstance(value, (set, frozenset)):
        # Sorted by RENDERING, not by value: a set may mix types that do not order.
        return "{" + ", ".join(sorted(_render(v) for v in value)) + "}"
    if isinstance(value, dict):
        items = sorted((_render(k), _render(v)) for k, v in value.items())
        return "{" + ", ".join(f"{k}: {v}" for k, v in items) + "}"
    raise TypeError(
        f"step argument of type {type(value).__name__} cannot enter an identity: only "
        f"scalars and containers of scalars have a rendering that is stable across "
        f"processes and installs. Pass a value, not an object "
        f"(a repo-relative string rather than a Path; an explicit list rather than an array)."
    )


def parameter_row(nodes: Sequence[object]) -> list[str]:
    """The resolved parameter row: what each step was CALLED WITH, deterministically.

    `quebraplan.md` 3.1 asks for "per-step sources rather than the module file, resolved
    parameter row rather than the table", and the row is the half that is easy to forget.

    It matters twice. Today every job parameter sits in the job file's text, so hashing that
    file covers them for free; the moment a job family moves its rows into a manifest,
    identity stops covering them. And `Identity` is `code + data + children` with no
    `job.name`, so two family members sharing a definition file and differing only by a
    parameter would collide on one digest. Measured before this existed: two jobs differing
    only by `x=1` versus `x=999` both produced `93f7286634eef03b`.

    `Dataset` values are skipped: their content hash is already the `data` contribution, and
    their repr carries a schema class whose module name embeds an absolute path for a schema
    defined inside a job file - machine-dependent, and exactly what R5.1.3 forbids keying on.
    """
    from quebra.core.dataset import Dataset

    rows: list[str] = []
    for node in nodes:
        kwargs = getattr(node, "kwargs", {})
        parts = []
        for key in sorted(kwargs):
            value = kwargs[key]
            if isinstance(value, Dataset):
                continue
            try:
                parts.append(f"{key}={_render(value)}")
            except TypeError as exc:
                raise TypeError(
                    f"step {getattr(node, 'node_id', '?')!r} kwarg {key!r}: {exc}"
                ) from exc
        rows.append(f"{getattr(node, 'node_id', '?')}({','.join(parts)})")
    return sorted(rows)
