"""Time-based lookup of the last-known calibration prior to an experiment start.

Selection rule: returns the source row with the LATEST date STRICTLY BEFORE
reference_time. Strictly-before is intentional: a calibration logged at the exact
same instant as the reference was not 'known back then.'
"""

from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd


def check_unix_s(value: object, *, label: str = "unix_s") -> float:
    """Validate a unix-seconds scalar.

    Jobs call this when deriving run_start_unix_s from file metadata.
    """

    try:
        unix_s = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{label} must be a number of seconds, got {value!r}") from exc

    if not np.isfinite(unix_s):
        raise ValueError(f"{label} must be finite, got {unix_s!r}")

    lower = pd.Timestamp("2000-01-01").value / 1e9
    upper = pd.Timestamp("2100-01-01").value / 1e9
    if not (lower <= unix_s <= upper):
        raise ValueError(
            f"{label}={unix_s:.6g} looks implausible; expected seconds since epoch in range "
            f"[{lower:.6g}, {upper:.6g}]."
        )
    return unix_s


def lookup_prior(
    main: Mapping[str, object] | pd.DataFrame,
    source: pd.DataFrame,
    fields: list[str],
    aliases: Mapping[str, str] | None = None,
    time_col: str = "date",
    reference_time: pd.Timestamp | None = None,
) -> Mapping[str, object] | pd.DataFrame:
    """Broadcast last-known values from `source` onto `main`.

    Selection rule: returns the source row with the LATEST date STRICTLY BEFORE
    reference_time. Strictly-before is intentional: a calibration logged at the exact
    same instant as the reference was not 'known back then.'

    Time inputs:
    - reference_time: naive pd.Timestamp, in the SAME clock as source[time_col]. This
      function does NOT convert timezones; the caller is responsible for clock alignment.
    - If reference_time is None and main is a mapping, meta['run_start_unix_s'] must be
      a float in unix seconds. This function converts it using pd.to_datetime(x, unit='s'),
      which yields a UTC-naive timestamp. The caller must ensure this clock matches
      source[time_col].

    main may be either a normalized mapping (as produced by a Job loader) or a
    pandas.DataFrame. When main is a mapping, fields are added as arrays with the
    same length as the relative time vector (t_rel_s). When main is a DataFrame,
    fields are added as scalar columns.
    """
    if time_col not in source.columns:
        raise ValueError(f"Source DataFrame missing time column '{time_col}'")

    src = source.copy()
    if not pd.api.types.is_datetime64_any_dtype(src[time_col]):
        src[time_col] = pd.to_datetime(src[time_col], errors="coerce")
    if not pd.api.types.is_datetime64_any_dtype(src[time_col]):
        raise ValueError(f"Source column '{time_col}' is not datetime dtype after parsing")

    if reference_time is None:
        if isinstance(main, Mapping):
            meta = main.get("meta", {}) if isinstance(main.get("meta", {}), Mapping) else {}
            run_start_unix_s = meta.get("run_start_unix_s")
            if run_start_unix_s is None:
                raise ValueError("reference_time not provided and main mapping has no 'run_start_unix_s' in meta")
            reference_time = pd.to_datetime(float(run_start_unix_s), unit="s")
        elif isinstance(main, pd.DataFrame):
            if time_col not in main.columns:
                raise ValueError(f"Main DataFrame missing time column '{time_col}' to infer reference_time")
            mdf = main.copy()
            if not pd.api.types.is_datetime64_any_dtype(mdf[time_col]):
                mdf[time_col] = pd.to_datetime(mdf[time_col], errors="coerce")
            reference_time = mdf[time_col].min()
        else:
            raise TypeError("main must be a mapping or pandas.DataFrame")

    if not isinstance(reference_time, pd.Timestamp):
        reference_time = pd.to_datetime(reference_time)

    before = src[src[time_col] < reference_time]
    if len(before) == 0:
        earliest = src[time_col].min()
        raise ValueError(f"No source rows found before {reference_time}. Earliest source timestamp: {earliest}")

    last_row = before.loc[before[time_col].idxmax()]

    missing = [f for f in fields if f not in src.columns]
    if missing:
        raise ValueError(f"Requested fields missing from source: {missing}")

    alias_map = dict(aliases) if aliases is not None else {}
    values = {alias_map.get(f, f): last_row[f] for f in fields}

    if isinstance(main, Mapping):
        out = dict(main)
        if "t_rel_s" not in out:
            raise KeyError("lookup_prior requires main mapping to include 't_rel_s' (relative seconds)")
        t_rel_s = np.asarray(out["t_rel_s"], dtype=float)

        n = len(t_rel_s)
        for key, value in values.items():
            out[key] = np.full(n, value)

        meta = out.get("meta", {}) if isinstance(out.get("meta", {}), Mapping) else {}
        lp = meta.get("lookup_prior_sources", [])
        if not isinstance(lp, list):
            lp = []

        try:
            src_time = last_row[time_col]
            src_unix = float(pd.to_datetime(src_time).value / 1e9)
        except Exception:
            src_unix = None

        entry = {
            "fields": list(fields),
            "aliases": alias_map,
            "source_time_unix_s": src_unix,
            "source_value": {alias_map.get(f, f): last_row[f] for f in fields},
        }
        lp.append(entry)
        meta["lookup_prior_sources"] = lp
        out["meta"] = meta
        return out

    outdf = main.copy()
    for key, value in values.items():
        outdf[key] = value
    return outdf
