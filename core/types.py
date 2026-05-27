from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from typing import Any


# Type aliases — semantic labels for array roles in the pipeline
TimeSeries = Any   # 1-D np.ndarray indexed by t_rel_s
Parameter = Any    # 1-D np.ndarray broadcast-constant (scalar value repeated to match t_rel_s)


class Norm(MutableMapping):
    """Normalized dataset mapping flowing between pipeline steps.

    Behaves exactly like a plain dict (MutableMapping). All canonical key names
    use unit suffixes (_hz, _rel_s, _unix_s). Use dict(norm) to get a plain dict.
    """

    __slots__ = ("_data",)

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = dict(data) if data is not None else {}

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"Norm({list(self._data.keys())})"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Norm:
        return cls(d)
