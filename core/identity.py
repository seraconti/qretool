"""Content identity for jobs — what a run *is*, independent of when it ran.

An `Identity` folds three contributions through one canonical encoder:

    code     — the job file's source hash
    data     — the content hashes of the datasets it loads (sorted by path)
    children — the identities of the sub-jobs it includes (composites)

so a composite *consumes* its sub-jobs' identities instead of re-deriving them.
The encoder (`fold`) takes a name→hex mapping and sorts keys, so a new
contribution is added by putting another key in the mapping — no call site
changes. Everything folded is a deterministic hex digest (never a Python object
repr, never a memory address), so the same code on the same data always yields
the same identity.

Git commit is deliberately NOT folded here: it is code *lineage* (when/where),
recorded separately in provenance, not part of *what* the computation is.

This module builds and encodes identities; wiring identity into the output-dir
naming and the reuse decision is a later step. Reuse of these identities as a
cache key belongs to the artifact/reuse layer, not here.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from provenance import hash_file


def fold(components: Mapping[str, str]) -> str:
    """Canonical encoder: order-stable, injective digest of a name→hex mapping.

    Keys are sorted so insertion order never affects the result; adding a new
    contribution key extends the fold without touching existing call sites. JSON
    encoding (not "k=v" joining) keeps it injective even if a key or value ever
    contains a separator character — this is the load-bearing encoder a later
    increment keys artifact reuse on.
    """
    canonical = json.dumps(components, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# Dataset files are read-only published inputs, so their content is stable for the
# life of a process: hash each once and reuse (identity + provenance share this).
_CONTENT_HASH: dict[str, str] = {}


def content_hash(path: Path) -> str:
    """sha256 hex of a file's bytes, memoized per process by absolute path."""
    key = str(path)
    cached = _CONTENT_HASH.get(key)
    if cached is None:
        cached = hash_file(path)
        _CONTENT_HASH[key] = cached
    return cached


@dataclass(frozen=True, slots=True)
class Identity:
    """The folded identity of one job.

    `code`/`data`/`children` are the raw contributions (kept for introspection
    and so a parent can fold a child's `digest`); `digest` is the single hex value
    that changes iff any contribution changes.
    """

    code: str
    data: tuple[tuple[str, str], ...]  # sorted (dataset-root-relative path, hash)
    children: tuple[str, ...]  # child identity digests, in include order

    @property
    def digest(self) -> str:
        return fold(
            {
                "code": self.code,
                "data": fold(dict(self.data)),
                "children": fold({str(i): d for i, d in enumerate(self.children)}),
            }
        )
