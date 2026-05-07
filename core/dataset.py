from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Dataset:
    path: Path | str
    schema: Any = None
    qubit: int | None = None
    device: str | None = None
    duration_h: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        # keep path normalized; dataset no longer carries a 'companion' path
