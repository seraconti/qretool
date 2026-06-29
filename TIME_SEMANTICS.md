# Time Semantics (Project Convention)

This document exists to prevent ambiguous time handling across shared steps (e.g. `lookup_prior`, fidelity, Allan) and dataset types.

The goal is **documentation, not enforcement**: shared code should avoid guessing clocks/units. Jobs should be explicit when a dataset format provides a real experiment start time.

## Unit-Suffix Discipline

Every variable, dict key, column, or metadata field that carries a physical
unit must end with the corresponding suffix. This applies to all new code and
was extended in Fix 2 (2026-05-26) to cover frequency quantities.

### Time suffixes

- `*_rel_s`: relative seconds (dimension: s), typically starting at 0 for a run.
- `*_unix_s`: seconds since Unix epoch (float), i.e. “Unix seconds”.
- `*_local_dt`: naive `datetime` / `pd.Timestamp` representing a **local** wall-clock time (timezone known externally, but not encoded).
- `*_utc_dt`: timezone-aware or explicitly UTC-normalized datetime.

### Frequency suffixes

- `*_hz`: Hertz. All frequency quantities in the Norm (norm keys, DataFrame
  columns, Parameter values) use this suffix.

Canonical Norm frequency keys:
| Key | Meaning |
|---|---|
| `delta_hz` | Ramsey detuning (fitted frequency − mean) |
| `raw_frequency_hz` | Fitted qubit frequency (absolute) |
| `rabi_hz` | Rabi drive frequency from calibration |
| `qubit_frequency_hz` | Carrier/qubit frequency from calibration (was `qubit_frequency`) |


**Source column names** in the calibration pickles (`FOR ZENODO/Main/Fig 2/qubit*.pickle`)
are not renamed — they remain `frequency` and `Rabi_frequency` as verified in the
external data. The `aliases` argument to `lookup_prior` maps them to the
correct norm keys:
```python
fields=[“frequency”, “Rabi_frequency”],
aliases={“frequency”: “qubit_frequency_hz”, “Rabi_frequency”: “rabi_hz”},
```

## Run-Start Time Resolution Levels

`Job.load()` determines `run_start_unix_s` via three resolution levels (in priority order):

| Level | Source | `run_start_resolution` value | Notes |
|---|---|---|---|
| 1 — explicit | `Dataset.extra['run_start_unix_s']` | `"explicit"` | Validated via `check_unix_s`. Preferred. |
| 2 — date_only_midnight | DDMMYY_ filename prefix (e.g. `040423_...`) | `"date_only_midnight"` | Midnight local naive. Emits `UserWarning`. Intra-day precision lost. |
| 3 — missing | Neither source available | raises `ValueError` | Do NOT fall back to `t_raw[0]` (~1970 epoch). |

**Why not fall back to `t_raw[0]`?** In at least one inspected 912days Ramsey file, `timestamp` starts at 0 (relative seconds), so `t_raw[0] == 0` would yield 1970-01-01 and silently select an incorrect calibration prior.

## Normalized Mapping Time Keys

When `Job.load()` produces the normalized mapping:

- `t_rel_s`: relative time in seconds.

`t_s` is no longer emitted; downstream steps must use `t_rel_s`.

## Verified Dataset Types

### 1) Calibration log pickles (`FOR ZENODO/Main/Fig 2/qubit*.pickle`)

**Verified fields:**

- `date`: `datetime64[ns]` **naive** timestamps.
- `uuid`: `int64` nanoseconds since epoch (UTC).

**Semantics (VERIFIED):**

- `date` behaves like **lab-local wall clock** stored without timezone.
- `uuid` is a real epoch timestamp; when converted to Europe/Rome and then made naive, it matches `date` up to small rounding/serialization error.

### 2) core-tools HDF5 calibration sweeps (`FOR ZENODO/Main/Fig 1/frequency_cal_q1.hdf5`)

**Verified fields:**

- File attribute `measurement_time`: string like `"2023-11-30 10:02:45.303548"` (naive).
- File attribute `uuid`: `int64` nanoseconds since epoch (UTC).
- Dataset `freq`: 1D float array (frequency sweep), plus other acquisition arrays.

**Semantics (VERIFIED):**

- `measurement_time` is **lab-local wall clock** stored without timezone.
- `uuid` is a real epoch timestamp.

**Loader behavior:**

- When loaded via the built-in HDF5 loader, selected file attributes are preserved on the returned DataFrame as `df.attrs["hdf5"]` (including `measurement_time` and `uuid_ns`).

### 3) 912days Ramsey pickles (`tool/datasets/.../*_qubit*.pickle`)

**Observed fields:**

- `timestamp`: numeric.

**Semantics (UNVERIFIED beyond “relative seconds”):**

- In at least one inspected file, `timestamp` ranges from `0` to ~`4.7e4`, which is consistent with **relative seconds** over a multi-hour run.
- The absolute wall clock (“what real date/time does `timestamp==0` correspond to?”) is not encoded in the column itself.

## The “Local-Naive Treated As UTC” Trap

Mixing a timezone-aware epoch timestamp (true UTC) with a naive local timestamp will silently shift comparisons by the local offset.

This project currently has dataset types where the primary time column is **naive local** (`date`, `measurement_time`). If you convert one side to Unix seconds *correctly* (respecting timezone) but later compare it to naive-local timestamps, you will be off by typically 1–2 hours (DST dependent).

Pragmatic rule for calibration lookup:

- `lookup_prior` does **no timezone conversion**.
- Whatever you provide as `reference_time` (or derive from `run_start_unix_s`) must be in the **same naive clock** as `source[time_col]`.

If you need `run_start_unix_s` to round-trip back to the same naive clock via `pd.to_datetime(run_start_unix_s, unit="s")`, compute it from a naive timestamp using:

```python
run_start_unix_s = float(run_start_local_dt.value / 1e9)
```

This is intentionally the “naive-as-UTC” representation (document it when used).

## Job Guidance (recommended)

- If a dataset format provides an explicit experiment start (`measurement_time`, header timestamp, etc.), derive a **single** reference time and use it consistently.
- Prefer passing `run_start_unix_s` explicitly via `Dataset.extra` for formats where `Job.load()` cannot infer a correct start.
- Use `transforms.lookup_prior.check_unix_s(...)` in jobs when you derive unix seconds to catch obvious unit mistakes (ms vs s vs ns). (`_check_unix_s` is a deprecated alias and will be removed.)

## Verified Calibration Lookup Example

Using:

- main: `frequency_cal_q1.hdf5` (`measurement_time` = `2023-11-30 10:02:45.303548`)
- source: `qubit1.pickle` (`date` column)

The strict “latest calibration strictly before experiment start” selection returns:

- `date`: `2023-11-29 16:59:25.165609`
- `frequency`: ~`1.5988e10`
- `Rabi_frequency`: ~`7.297e6`
