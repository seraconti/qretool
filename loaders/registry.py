from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pandas as pd
import yaml

LoaderFn = Callable[[Path, dict[str, Any]], pd.DataFrame]

_LOADER_REGISTRY: dict[str, LoaderFn] = {}


def _normalize_extension(extension: str) -> str:
    normalized = extension.strip().lower()
    if not normalized:
        raise ValueError("Loader extensions must be non-empty strings")
    if not normalized.startswith("."):
        normalized = f".{normalized}"
    return normalized


def _resolve_input_path(path: Path) -> Path:
    if path.is_absolute():
        return path

    cwd = Path.cwd()
    candidates = [cwd / path, cwd.parent / path]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    return (cwd.parent / path).resolve()


def register_loader(*extensions: str) -> Callable[[LoaderFn], LoaderFn]:
    if not extensions:
        raise ValueError("register_loader() requires at least one file extension")

    normalized_extensions = tuple(_normalize_extension(extension) for extension in extensions)

    def decorator(fn: LoaderFn) -> LoaderFn:
        for extension in normalized_extensions:
            existing = _LOADER_REGISTRY.get(extension)
            if existing is not None and existing is not fn:
                raise ValueError(f"Loader already registered for extension '{extension}'")
            _LOADER_REGISTRY[extension] = fn
        return fn

    return decorator


def _ensure_dataframe(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value
    if isinstance(value, pd.Series):
        return value.to_frame().T
    if value is None:
        return pd.DataFrame()
    if isinstance(value, list):
        return pd.DataFrame(value)
    if isinstance(value, dict):
        return pd.DataFrame([value])
    return pd.DataFrame([{"value": value}])


def _load_yaml(path: Path, meta: dict[str, Any]) -> pd.DataFrame:
    del meta
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return _ensure_dataframe(data)


def _load_hdf(path: Path, meta: dict[str, Any]) -> pd.DataFrame:
    key = meta.get("key")
    if key is not None:
        return _ensure_dataframe(pd.read_hdf(path, key=key))

    with pd.HDFStore(path, mode="r") as store:
        keys = list(store.keys())

    if not keys:
        raise ValueError(f"HDF5 file {path} does not contain any tables")
    if len(keys) > 1:
        available = ", ".join(keys)
        raise ValueError(
            f"HDF5 file {path} contains multiple tables ({available}); pass meta={'key': '<table-key>'}"
        )
    return _ensure_dataframe(pd.read_hdf(path, key=keys[0]))


@register_loader(".csv")
def _load_csv(path: Path, meta: dict[str, Any]) -> pd.DataFrame:
    return pd.read_csv(path, **meta)


@register_loader(".yaml", ".yml")
def _load_yaml_registered(path: Path, meta: dict[str, Any]) -> pd.DataFrame:
    return _load_yaml(path, meta)


@register_loader(".h5", ".hdf5")
def _load_hdf_registered(path: Path, meta: dict[str, Any]) -> pd.DataFrame:
    return _load_hdf(path, meta)


@register_loader(".pkl", ".pickle")
def _load_pickle(path: Path, meta: dict[str, Any]) -> pd.DataFrame:
    del meta
    return _ensure_dataframe(pd.read_pickle(path))


def load(path: str | Path, meta: dict[str, Any] | None = None) -> pd.DataFrame:
    file_path = _resolve_input_path(Path(path))
    extension = file_path.suffix.lower()
    loader = _LOADER_REGISTRY.get(extension)
    if loader is None:
        known_extensions = ", ".join(sorted(_LOADER_REGISTRY)) or "<none>"
        raise ValueError(
            f"No loader registered for extension '{extension or '<none>'}' for path {file_path}. "
            f"Known extensions: {known_extensions}"
        )
    return loader(file_path, {} if meta is None else dict(meta))
