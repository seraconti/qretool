from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from core.dataset import Dataset
from core.types import CalibrationEvent, Norm


class CalibrationLogSchema:
    """Schema for 6D2S calibration-log pickles (Supplementary/Sup fig 1/6D2S/).

    Each row is one calibration event. Converts the DataFrame to a Norm whose
    ``events["calibration"]`` list contains one CalibrationEvent per row.
    The ``date`` column (naive datetime64[ns]) is converted to Unix seconds
    via the naive-as-UTC convention (ts.value / 1e9), consistent with
    TIME_SEMANTICS.md for the calibration log dataset family.

    This schema provides ``to_norm`` rather than ``validate`` so that
    ``_load_dataset`` bypasses the standard timestamp/frequency normalization.
    """

    @classmethod
    def to_norm(cls, df: pd.DataFrame, dataset: Dataset) -> Norm:
        required = {"date"}
        missing = required - set(df.columns)
        if missing:
            raise KeyError(f"CalibrationLogSchema: missing columns {missing}")

        events: list[CalibrationEvent] = []
        other_cols = [c for c in df.columns if c != "date"]
        for ts, *rest in zip(df["date"], *[df[c] for c in other_cols]):
            t_unix_s = float(pd.Timestamp(ts).value / 1e9)
            payload = dict(zip(other_cols, rest))
            events.append(CalibrationEvent(t_event_unix_s=t_unix_s, payload=payload))

        meta: dict[str, object] = {
            "dataset_id": str(dataset.extra.get("run_name", Path(dataset.path).stem)),
            "n_events": len(events),
            "qubit": dataset.qubit,
            "device": dataset.device,
        }
        norm = Norm({"meta": meta})
        norm.events["calibration"] = events
        return norm
