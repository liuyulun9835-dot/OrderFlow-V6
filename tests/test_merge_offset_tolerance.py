from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from preprocessing import merge_to_features as merge


def _make_frame(start: datetime, periods: int) -> pd.DataFrame:
    timestamps = [start + timedelta(minutes=i) for i in range(periods)]
    return pd.DataFrame({"timestamp": pd.to_datetime(timestamps, utc=True), "close": range(periods)})


def test_offset_grid_scans_negative_shift() -> None:
    kline = _make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc), 5)
    atas = _make_frame(datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc), 5)

    offset, applied, diagnostics = merge.estimate_offset_minutes(atas, kline)
    assert offset == -1
    assert applied
    assert len(diagnostics) == 5


def test_merge_respects_backward_tolerance() -> None:
    base_time = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    kline = _make_frame(base_time, 3)
    atas = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [base_time + timedelta(minutes=1), base_time + timedelta(minutes=2)], utc=True
            ),
            "absorption_detected": [True, False],
        }
    )

    merged = merge.merge_streams(kline, atas, tolerance_seconds=2)
    assert merged["absorption_detected"].notna().sum() == 2
