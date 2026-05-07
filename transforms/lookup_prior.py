from __future__ import annotations

from typing import Mapping

import pandas as pd
import numpy as np


def lookup_prior(main: Mapping[str, object] | pd.DataFrame,
                 source: pd.DataFrame,
                 fields: list[str],
                 aliases: Mapping[str, str] | None = None,
                 time_col: str = "date",
                 reference_time: pd.Timestamp | None = None) -> Mapping[str, object]:
    """Broadcast last-known values from `source` (before reference_time) onto `main`.

    main may be either a normalized mapping (as produced by _load_dataset) or a
    pandas.DataFrame. When main is a mapping, the fields will be added as arrays
    of the same length as `main['t_s']` filled with the constant value. When
    main is a DataFrame, the fields are added as columns.
    """
    # validate source time column
    if time_col not in source.columns:
        raise ValueError(f"Source DataFrame missing time column '{time_col}'")
    src = source.copy()
    if not pd.api.types.is_datetime64_any_dtype(src[time_col]):
        src[time_col] = pd.to_datetime(src[time_col], errors="coerce")
    if not pd.api.types.is_datetime64_any_dtype(src[time_col]):
        raise ValueError(f"Source column '{time_col}' is not datetime dtype after parsing")

    if reference_time is None:
        # determine reference_time from main
        if isinstance(main, Mapping):
            meta = main.get("meta", {}) if isinstance(main.get("meta", {}), Mapping) else {}
            run_unix = meta.get("run_start_unix_s")
            if run_unix is None:
                raise ValueError("reference_time not provided and main mapping has no 'run_start_unix_s' in meta")
            reference_time = pd.to_datetime(float(run_unix), unit="s")
        elif isinstance(main, pd.DataFrame):
            if time_col not in main.columns:
                raise ValueError(f"Main DataFrame missing time column '{time_col}' to infer reference_time")
            mdf = main.copy()
            if not pd.api.types.is_datetime64_any_dtype(mdf[time_col]):
                mdf[time_col] = pd.to_datetime(mdf[time_col], errors="coerce")
            reference_time = mdf[time_col].min()
        else:
            raise TypeError("main must be a mapping or pandas.DataFrame")

    # filter source rows before reference_time
    before = src[src[time_col] < reference_time]
    if len(before) == 0:
        earliest = src[time_col].min()
        raise ValueError(f"No source rows found before {reference_time}. Earliest source timestamp: {earliest}")

    last_row = before.iloc[before[time_col].argmax()]

    # ensure requested fields exist
    missing = [f for f in fields if f not in src.columns]
    if missing:
        raise ValueError(f"Requested fields missing from source: {missing}")

    alias_map = dict(aliases) if aliases is not None else {}

    # extract values with optional output-name aliasing
    values = {alias_map.get(f, f): last_row[f] for f in fields}

    # produce output without mutating inputs
    if isinstance(main, Mapping):
        out = dict(main)
        t_s = np.asarray(out.get("t_s", []), dtype=float)
        n = len(t_s)
        for f, v in values.items():
            arr = np.full(n, v)
            out[f] = arr
        return out
    else:
        outdf = main.copy()
        for f, v in values.items():
            outdf[f] = v
        return outdf
