"""Unpickle staleness guard for materialized panel-data artifacts.

A panel-data pickle written before the builder/renderer split lacks the derived
fields: unpickling restores ``__dict__`` directly, bypassing ``__init__`` defaults,
so a composite reusing such an artifact would crash mid-render (AttributeError on
a factory field) or silently draw a class-level default. Loading one must instead
fail loudly at the pickle boundary ("errors are raised, not swallowed"). Full
completeness validation at construction time is deferred to the artifact-contract
increment; this guard covers only the unpickle path.
"""

from __future__ import annotations

import dataclasses


class StaleArtifactGuard:
    """Mixin for non-slots panel-data dataclasses: validate state on unpickle.

    The required key set derives from ``dataclasses.fields()`` — never a
    hand-maintained list — so it tracks field additions automatically. A valid
    builder-produced pickle always carries every field in ``__dict__``
    (default_factory fields included); a pre-split pickle does not.
    """

    def __setstate__(self, state: dict[str, object]) -> None:
        cls = type(self)
        if not isinstance(state, dict):
            # e.g. the (dict, slots_dict) tuple a slots=True dataclass would emit —
            # fail with the guard's error, not an AttributeError on .keys().
            raise ValueError(
                f"stale {cls.__name__} artifact: unexpected pickle state of type "
                f"{type(state).__name__} — re-run the sub-job (run the composite "
                "without --reuse-deps)."
            )
        missing = {f.name for f in dataclasses.fields(cls)} - state.keys()
        if missing:
            raise ValueError(
                f"stale {cls.__name__} artifact: pickle lacks field(s) "
                f"{sorted(missing)} — it predates the builder/renderer split. "
                "Re-run the sub-job (run the composite without --reuse-deps)."
            )
        self.__dict__.update(state)
