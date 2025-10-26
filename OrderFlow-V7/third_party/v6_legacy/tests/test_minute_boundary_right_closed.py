from __future__ import annotations

import pandas as pd

from data.alignment import merge_to_features


def test_right_closed_minute_assignment() -> None:
    raw = pd.DataFrame(
        {
            "timestamp": [
                "2024-01-01T00:00:00",
                "2024-01-01T00:00:59",
                "2024-01-01T00:01:00",
                "2024-01-01T00:01:01",
            ]
        }
    )

    normalised = merge_to_features.normalise_atas_frame(raw, "UTC")
    buckets = normalised["timestamp"].dt.strftime("%H:%M:%S").tolist()
    assert buckets == ["00:00:00", "00:00:00", "00:01:00", "00:01:00"]
