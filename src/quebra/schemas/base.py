from __future__ import annotations

import pandera.pandas as pa
from pandera.typing import Series


class BaseQubitSchema(pa.DataFrameModel):
    # timestamp_s: seconds from the start of the run.
    timestamp: Series[float] = pa.Field(alias="timestamp")
    # qubit_id: integer qubit label.
    qubit_id: Series[int] = pa.Field(alias="qubit_id")
